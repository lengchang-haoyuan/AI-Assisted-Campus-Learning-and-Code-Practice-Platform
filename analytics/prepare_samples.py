"""冻结 S01 小样本，并生成独立合成规模输入；不写数据库。"""

import argparse
import copy
import json
import random
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from analytics.fixture_answers import assert_subset, calculate, deduplicate, validate_relations
from analytics.snapshot_files import begin_snapshot, publish_snapshot, write_json

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "开发相关文档/阶段报告/AI大数据改造/V2/S01-分析固定样例与独立答案.json"


def materialize_cases(fixture, root):
    results = []
    for case in fixture["cases"]:
        tables, manifest = copy.deepcopy(fixture["base_input"]), copy.deepcopy(fixture["manifest"])
        for change in case["input_changes"]:
            op, table = change["op"], change.get("table")
            if op == "manifest":
                manifest.update(change["values"])
            elif op == "clear_all":
                tables = {t: [] for t in tables}
            elif op == "clear":
                tables[table] = []
            elif op == "replace":
                tables[table] = copy.deepcopy(change["rows"])
            elif op == "append":
                tables[table].append(copy.deepcopy(change["row"]))
            else:
                matches = lambda row: all(row[k] == v for k, v in change["match"].items())
                if op == "delete":
                    tables[table] = [r for r in tables[table] if not matches(r)]
                elif op == "set":
                    for row in tables[table]:
                        if matches(row):
                            row.update(copy.deepcopy(change["values"]))
                else:
                    raise ValueError("unknown_patch")
        folder = root / "small" / case["case_id"]
        folder.mkdir(parents=True, exist_ok=False)
        # 故意脏输入是测试向量，不走 complete ODS 的入口。
        write_json(folder / "input.json", {"manifest": manifest, "tables": tables,
                   "artifact_kind": "fictional_test_vector_not_database_snapshot"})
        write_json(folder / "expected.json", case)
        if case["kind"] != "data":
            results.append({"case_id": case["case_id"], "status": "deferred_S05_policy_test"})
            continue
        try:
            answer = calculate(tables, manifest)
        except ValueError as error:
            if case["expected_status"] != "failed" or str(error) != case["expected_assertions"]["fatal_error"]:
                raise
            results.append({"case_id": case["case_id"], "status": "expected_rejection", "error": str(error)})
        else:
            if case["expected_status"] != "validated":
                raise AssertionError("expected_failure_not_detected")
            assert_subset(answer, case["expected_assertions"])
            write_json(folder / "independent-python-answer.json", answer)
            results.append({"case_id": case["case_id"], "status": "reference_matches_frozen_answer"})
    write_json(root / "small" / "verification.json", results)
    return results


def multi_subject(fixture, root):
    tables, _ = deduplicate(copy.deepcopy(fixture["base_input"]))
    # 第二主体是首次通过、低覆盖且仅取消任务；第三主体完全无样本。
    extra = {table: [] for table in tables}
    for table, ids in {"projects": [501], "daily_tasks": [13], "learning_records": [4, 5],
                       "teaching_classes": [301], "teaching_assignments": [603],
                       "campus_memberships": [201, 202], "class_memberships": [401, 402],
                       "submissions": [703], "submission_versions": [714], "feedback": [803]}.items():
        extra[table] = [copy.deepcopy(r) for r in tables[table] if r["id"] in ids]
        for row in extra[table]:
            for key, value in row.items():
                if value is None:
                    continue
                if key in ("user_id", "owner_id"):
                    row[key] = 1002 if value == 1001 else 2002
                elif key == "id" or key.endswith("_id"):
                    row[key] += 10000
    extra["learning_records"][1]["duration_minutes"] = 10
    extra["learning_records"][1]["occurred_at"] = "2026-10-01T02:00:00Z"
    extra["learning_records"][1]["created_at"] = "2026-10-01T02:00:00Z"
    for table in tables:
        tables[table] += extra[table]
    expected = {
        "1001": {"records.known_minutes": 75, "records.active_days": 3, "tasks.total": 4,
                 "topic.revised_count": 1, "topic.confirmed_count": 2},
        "1002": {"records.valid_unique_rows": 2, "records.known_minutes": 10, "records.active_days": 2,
                 "records.missing_duration_count": 1, "tasks.total": 1, "tasks.cancelled": 1,
                 "tasks.completion_rate.percent": "0.000000", "topic.cohort_count": 1,
                 "topic.revised_count": 0, "topic.confirmed_count": 1, "topic.first_pass_confirmed_count": 1,
                 "topic.first_review_wait_mean_minutes": "30.000000"},
        "1003": {"records.valid_unique_rows": 0, "tasks.total": 0, "tasks.completion_rate.percent": None,
                 "topic.cohort_count": 0, "topic.confirmation_rate.percent": None},
    }
    answers = {}
    for owner, assertions in expected.items():
        answers[owner] = calculate(tables, dict(fixture["manifest"], owner_user_id=int(owner)))
        assert_subset(answers[owner], assertions)
    folder = root / "small" / "M01"
    folder.mkdir()
    write_json(folder / "input.json", {"manifest": fixture["manifest"], "tables": tables,
                                     "scope": "offline_multi_subject", "subjects": [1001, 1002, 1003]})
    write_json(folder / "expected.json", {
        "assertions": expected,
        "should_describe": ["1001存在修订后确认且仍有待评", "1002首次通过，无需人为制造二次提交",
                            "1002只有取消任务，取消仍占分母", "1003无样本"],
        "must_not_infer": ["分钟少等于能力低", "修订导致学习提升", "无任务等于完成率100%", "教师确认等于执行代码"],
        "scoring": {"dimensions": ["事实准确", "模式与反例", "覆盖与限制", "可回溯证据"],
                    "points_each": [0, 1, 2], "threshold": 6,
                    "full_score_example": "1001有1个修订后通过，但另有首次通过和待评；1002首次通过说明修订不是必经步骤。记录分钟与任务状态仅描述覆盖和进展，不证明能力或因果。1003无样本。"},
        "ai_judge_status": "not_run_S06",
    })
    write_json(folder / "independent-python-answer.json", answers)


def generate_scale(fixture, root, count=10000, seed=20261020):
    if count not in (10000, 100000, 1000000):
        raise ValueError("unsupported_scale")
    tick = time.perf_counter()
    rng, subjects = random.Random(seed), count // 100
    tables = {t: [] for t in fixture["schema"]}
    tables["source_claim_projection"] = []
    base = datetime(2026, 10, 1, tzinfo=UTC)
    stamp = lambda d: d.isoformat(timespec="microseconds").replace("+00:00", "Z")
    initial = "2026-09-30T00:00:00.000000Z"
    teacher_id = 900000000
    tables["teaching_classes"] = [{"id": 1, "status": "active"}]
    tables["campus_memberships"] = [{"id": teacher_id, "user_id": teacher_id, "role": "teacher", "status": "active"}]
    tables["class_memberships"] = [{"id": teacher_id, "class_id": 1, "campus_membership_id": teacher_id,
                                   "member_role": "teacher", "status": "active", "joined_at": initial, "left_at": None}]
    modes = ["first_accept"] * (subjects*3//10) + ["revised_accept"] * (subjects*3//10) + ["returned"] * (subjects//5) + ["pending"] * (subjects//5)
    rng.shuffle(modes)
    accepted_record_ids = set()
    for i, mode in enumerate(modes):
        sid, uid = i+1, 1000000+i
        tables["projects"].append({"id": sid, "owner_id": uid, "status": "in_progress",
                                   "completed_at": None, "created_at": initial, "updated_at": initial})
        tables["campus_memberships"].append({"id": sid, "user_id": uid, "role": "student", "status": "active"})
        tables["class_memberships"].append({"id": sid, "class_id": 1, "campus_membership_id": sid,
                                           "member_role": "student", "status": "active", "joined_at": initial, "left_at": None})
        first = base + timedelta(days=i % 25, hours=1)
        last = first
        second = mode == "revised_accept"
        tables["teaching_assignments"].append({
            "id": sid, "class_id": 1, "due_at": stamp(first+timedelta(days=3)), "status": "published",
            "published_at": initial, "closed_at": None, "archived_at": None, "created_at": initial, "updated_at": initial})
        for version in range(1, 3 if second else 2):
            submitted = first if version == 1 else first+timedelta(days=2)
            decision = ("accept" if mode == "first_accept" or version == 2 else
                        "return" if mode in ("returned", "revised_accept") else None)
            reviewed = submitted + timedelta(minutes=(10, 180, 1500)[i % 3]) if decision else None
            last = reviewed or submitted
            tables["submission_versions"].append({
                "id": sid*2+version, "submission_id": sid, "version_number": version,
                "source_project_id": sid, "status": "accepted" if decision == "accept" else "returned" if decision else "submitted",
                "submitted_at": stamp(submitted), "reviewed_at": stamp(reviewed) if reviewed else None,
                "revision": 2 if decision else 1})
            if decision:
                lrid = i*100+1 if decision == "accept" else None
                if lrid:
                    accepted_record_ids.add(lrid)
                tables["feedback"].append({
                    "id": sid*2+version, "submission_id": sid, "version_number": version,
                    "class_id": 1, "teacher_membership_id": teacher_id, "decision": decision,
                    "created_at": stamp(reviewed), "learning_record_id": lrid})
        tables["submissions"].append({
            "id": sid, "class_id": 1, "assignment_id": sid, "student_membership_id": sid,
            "assignment_due_at": stamp(first+timedelta(days=3)), "latest_version_number": 2 if second else 1,
            "revision": 4 if second else 2 if mode != "pending" else 1,
            "created_at": stamp(first), "updated_at": stamp(last)})
    rest = [i for i in range(1, count+1) if i not in accepted_record_ids]
    rng.shuffle(rest)
    missing = accepted_record_ids | set(rest[:count//5-len(accepted_record_ids)])
    remaining = [i for i in rest if i not in missing]
    zero = set(remaining[:count//10])
    accepted_times = {f["learning_record_id"]: f["created_at"] for f in tables["feedback"] if f["decision"] == "accept"}
    for rid in range(1, count+1):
        i = (rid-1)//100
        # 每主体100记录；前1/3主体集中前5日，其余覆盖30日，避免只改变分钟。
        day = rng.randrange(5 if i % 3 == 0 else 30)
        occurred = accepted_times.get(rid, stamp(base+timedelta(days=day, hours=rng.randrange(0, 15))))
        tables["learning_records"].append({
            "id": rid, "user_id": 1000000+i, "project_id": None if rid in accepted_record_ids else i+1,
            "course_id": None, "task_id": None, "record_type": "task" if rid in accepted_record_ids else "study",
            "duration_minutes": None if rid in missing else 0 if rid in zero else rng.randint(1, 120),
            "occurred_at": occurred, "created_at": occurred})
    n_tasks = count//4
    states = ["completed"]*(n_tasks//2) + ["pending"]*(n_tasks//4) + ["in_progress"]*(n_tasks*15//100) + ["cancelled"]*(n_tasks//10)
    rng.shuffle(states)
    for i, status in enumerate(states):
        owner_index = i % subjects
        scheduled = base+timedelta(days=rng.randrange(30), hours=2)
        tables["daily_tasks"].append({
            "id": i+1, "user_id": 1000000+owner_index, "project_id": owner_index+1, "plan_id": None,
            "status": status, "scheduled_date": scheduled.date().isoformat(),
            "completed_at": stamp(scheduled) if status == "completed" else None,
            "created_at": initial, "updated_at": stamp(scheduled)})
    validate_relations(tables)
    unique_records = tables["learning_records"]
    independent = {"records": count, "known_minutes": sum(r["duration_minutes"] or 0 for r in unique_records),
                   "known_duration_count": count*4//5, "missing_duration_count": count//5, "known_zero_count": count//10,
                   "exact_duplicates": count//50, "tasks": n_tasks, "task_statuses": dict(Counter(states)),
                   "cohort_count": subjects, "confirmed_count": subjects*6//10, "revised_count": subjects*3//10,
                   "first_pass_confirmed_count": subjects*3//10, "revised_confirmed_count": subjects*3//10,
                   "returned_latest_count": subjects//5, "pending_latest_count": subjects//5,
                   "missing_teaching_record_links": 0, "trusted_teaching_count": len(accepted_record_ids)}
    actual_null = sum(r["duration_minutes"] is None for r in unique_records)
    assert actual_null == independent["missing_duration_count"]
    tables["learning_records"] += [copy.deepcopy(r) for r in rng.sample(unique_records, count//50)]
    sid = f"synthetic-{count}-seed-{seed}-v1"
    pending, final = begin_snapshot(root, sid)
    manifest = dict(fixture["manifest"], dataset_id=f"synthetic-{count}-v1", snapshot_id=sid,
                    batch_id=str(uuid4()), owner_user_id=None, dataset_kind="synthetic", scope="offline_multi_subject",
                    source_provenance="independent_generated_files_not_business_users", period_end="2026-10-30",
                    source_cutoff="2026-10-30T16:00:00Z", snapshot_started_at=None, snapshot_finished_at=None,
                    subject_coverage={"namespace": "synthetic_subject", "count": subjects, "min": 1000000, "max": 1000000+subjects-1},
                    generator_version="s03-synthetic-1.0", seed=seed,
                    generation={"unique_learning_records": count, "duplicate_rate": ".02", "missing_rate": ".20",
                                "known_zero_rate": ".10", "subjects_equal_record_count": 100,
                                "temporal_skew": "subject index mod3=0 concentrates ordinary records in first5days",
                                "largest_remainder": "all fixed quotas integral for supported scales",
                                "spark_partitions": "not_run; S06 proposed 8", "online_import_allowed": False},
                    generated_at=datetime.now(UTC).isoformat())
    result = publish_snapshot(pending, final, tables, manifest)
    write_json(root / f"{sid}-expected.json", independent)
    write_json(root / f"{sid}-generation.json", {"elapsed_seconds": time.perf_counter()-tick,
               "row_counts": result["row_counts"], "input_bytes": result["total_input_bytes"],
               "spark_runs": 0, "seed": seed})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    results = materialize_cases(fixture, args.output)
    multi_subject(fixture, args.output)
    scale = generate_scale(fixture, args.output)
    write_json(args.output / "data-dictionary.json", {
        "schema_version": "scholarhub-source-1.0", "tables": fixture["schema"],
        "source_claim_projection": fixture["source_claim_projection"]})
    print(json.dumps({"cases": results, "scale_rows": scale["row_counts"],
                      "scale_bytes": scale["total_input_bytes"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

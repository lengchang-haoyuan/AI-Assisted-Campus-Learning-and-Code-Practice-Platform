"""S06 只读重核旧固定向量和不可变 S04 产物；不导入 Spark 或应用数据库。"""

import copy
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path

os.environ["PYTHONTZPATH"] = r"\\wsl.localhost\Ubuntu-24.04\usr\share\zoneinfo"

from analytics.fixture_answers import calculate

V2 = Path(__file__).resolve().parent.parent
ARTIFACTS = V2 / "S04-产物"
CASE_ROOT = V2 / "S03-样本/small"
UNITS = []


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def compare(actual, expected, path=""):
    if isinstance(expected, dict):
        assert set(actual) == set(expected), (path, "field sets")
        return sum(compare(actual[k], v, path+"."+k) for k, v in expected.items())
    if isinstance(expected, list):
        assert len(actual) == len(expected), (path, "length")
        return sum(compare(a, e, f"{path}[{i}]") for i, (a, e) in enumerate(zip(actual, expected)))
    valid = (math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10)
             if isinstance(expected, float) else actual == expected)
    assert valid, (path, actual, expected)
    return 1


def dimensions(case_id, path):
    groups = []
    if "topic." in path or "daily[" in path and any(path.endswith("."+key) for key in ("cohort", "revised", "confirmed")):
        groups.append("cohort_and_version")
    if (case_id in ("D04", "D08", "D12", "D16", "M01") or
            any(k in path for k in ("trusted_teaching", "unverified_claim", "ordinary_count", "owner_user_id"))):
        groups.append("source_relations")
    if (any(k in path for k in ("records.", "tasks.", ".percent", "eligible_to_complete_plan")) or
            "daily[" in path and not path.endswith(".date")):
        groups.append("numbers_null")
    if (case_id in ("D01", "D02", "D03", "D05", "D06", "D15") or
            any(k in path for k in (".date", "active_days", "quality.", "new_batch_required"))):
        groups.append("time_quality")
    return groups


def frozen_units(case_id, actual, expected, prefix=""):
    if isinstance(expected, dict):
        for key, value in expected.items():
            child = actual
            for part in key.split("."):
                child = child[part]
            frozen_units(case_id, child, value, (prefix+"."+key).lstrip("."))
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for i, (a, e) in enumerate(zip(actual, expected)):
            frozen_units(case_id, a, e, f"{prefix}[{i}]")
    else:
        passed = actual == expected
        assert passed, (case_id, prefix, actual, expected)
        UNITS.append({"case_id": case_id, "field_path": prefix, "expected": expected,
                      "actual": actual, "passed": passed, "coverage_dimensions": dimensions(case_id, prefix)})


def reapply(s01, case):
    tables, manifest = copy.deepcopy(s01["base_input"]), copy.deepcopy(s01["manifest"])
    for change in case["input_changes"]:
        op, table = change["op"], change.get("table")
        if op == "manifest":
            manifest.update(change["values"])
        elif op == "clear_all":
            tables = {key: [] for key in tables}
        elif op == "clear":
            tables[table] = []
        elif op == "replace":
            tables[table] = copy.deepcopy(change["rows"])
        elif op == "append":
            tables[table].append(copy.deepcopy(change["row"]))
        else:
            matches = lambda row: all(row[key] == value for key, value in change["match"].items())
            if op == "delete":
                tables[table] = [row for row in tables[table] if not matches(row)]
            elif op == "set":
                for row in tables[table]:
                    if matches(row):
                        row.update(copy.deepcopy(change["values"]))
            else:
                raise ValueError(op)
    return manifest, tables


def quality_checks(quality):
    assert quality["reconciled"]
    for table in quality["tables"]:
        assert table["raw_rows"] == table["unique_rows"]+table["exact_duplicates"]+table["invalid_rows"]


def rule_checks(case_id, answers, actual):
    expected = []
    for owner, answer in answers.items():
        topic, records, tasks = answer["topic"], answer["records"], answer["tasks"]
        rules = [
            ("revision_observed", "revised_count>0", topic["revised_count"], topic["cohort_count"], "dwd/cohort_facts"),
            ("first_pass_counterexample", "first_pass_confirmed_count>0", topic["first_pass_confirmed_count"], topic["cohort_count"], "dwd/cohort_facts"),
            ("pending_review", "pending_latest_count>0", topic["pending_latest_count"], topic["cohort_count"], "dwd/cohort_facts"),
            ("unknown_duration", "missing_duration_count>0", records["missing_duration_count"], records["valid_unique_rows"], "dwd/record_facts"),
            ("no_tasks", "task_total=0", int(tasks["total"] == 0), tasks["total"], "dwd/task_facts"),
        ]
        for rule_id, condition, numerator, denominator, ref in rules:
            row = next(r for r in actual if r["owner_user_id"] == int(owner) and r["rule_id"] == rule_id)
            facts = {"owner_user_id": int(owner), "snapshot_id": f"fixture-{case_id}", "rule_id": rule_id,
                     "condition": condition, "triggered": numerator > 0, "numerator": numerator,
                     "denominator": denominator, "dates": [r["date"] for r in answer["daily"]], "evidence_ref": ref}
            checks = {key: row[key] == value for key, value in facts.items()}
            assert all(checks.values()), (case_id, owner, rule_id, checks)
            expected.append({"case_id": case_id, "owner_user_id": int(owner), "rule_id": rule_id,
                             "expected_triggered": numerator > 0, "actual_triggered": row["triggered"],
                             "numerator": numerator, "denominator": denominator, "dates": facts["dates"],
                             "checked_fields": checks, "interpretation_material": row["interpretation"],
                             "J1_semantic_score": None, "passed": True})
    assert len(actual) == len(expected)
    return expected


def main():
    s01 = read(V2/"S01-分析固定样例与独立答案.json")
    assert s01["contract_id"] == "V2-S01-r2"
    rubric = (V2/"S01-评价评分表.md").read_text(encoding="utf-8")
    for phrase in ("群组与版本关联 | 30", "来源与关系 | 20", "数字与空值 | 20", "时间与质量 | 20", "发布与权限 | 10"):
        assert phrase in rubric
    cases, rules = [], []
    full_fields = 0
    for case in s01["cases"]:
        if case["kind"] != "data":
            continue
        case_id = case["case_id"]
        data, expected = read(CASE_ROOT/case_id/"input.json"), read(CASE_ROOT/case_id/"expected.json")
        assert expected == case
        manifest, tables = reapply(s01, case)
        assert data["manifest"] == manifest and data["tables"] == tables
        start = len(UNITS)
        job_id = "v1-"+case_id
        final = ARTIFACTS/"jobs"/job_id
        if case["expected_status"] == "failed":
            failure_dirs = [p for p in (ARTIFACTS/".incomplete").glob(job_id+"-*") if (p/"failure.json").is_file()]
            assert len(failure_dirs) == 1 and not final.exists()
            failure = read(failure_dirs[0]/"failure.json")
            quality = read(failure_dirs[0]/"quality.json")
            quality_checks(quality)
            assert quality["fatal_errors"] > 0
            try:
                calculate(tables, manifest)
            except ValueError as error:
                assert str(error) == case["expected_assertions"]["fatal_error"] == failure["reason"]
            else:
                raise AssertionError("independent Python accepted rejected vector")
            frozen_units(case_id, {"fatal_error": failure["reason"], "publish": failure["published"]}, case["expected_assertions"])
            provenance = str(failure_dirs[0].relative_to(V2))
            state = "expected_rejection_rechecked"
            count = 0
        else:
            metadata, quality, actual = read(final/"manifest.json"), read(final/"quality.json"), read(final/"ads/answers.json")
            assert metadata["state"] == "computed" and metadata["rule_version"] == "quality-1.0"
            quality_checks(quality)
            assert quality["fatal_errors"] == 0
            answer = calculate(tables, manifest)
            count = compare(actual, {str(manifest["owner_user_id"]): answer})
            full_fields += count
            frozen_units(case_id, answer, case["expected_assertions"])
            rules.extend(rule_checks(case_id, actual, read(final/"ads/conclusions.json")))
            provenance, state = str(final.relative_to(V2)), "immutable_S04_ADS_matches_current_Python"
        cases.append({"case_id": case_id, "name": case["name"], "status": "passed", "kind": state,
                      "source": provenance, "S01_S03_input_and_expected_equal": True,
                      "frozen_leaf_assertions": len(UNITS)-start, "full_answer_leaf_checks": count})

    data = read(CASE_ROOT/"M01/input.json")
    expected = read(CASE_ROOT/"M01/expected.json")
    final = ARTIFACTS/"jobs/v1-M01"
    actual = read(final/"ads/answers.json")
    independent = {}
    start = len(UNITS)
    for owner in data["subjects"]:
        answer = calculate(data["tables"], dict(data["manifest"], owner_user_id=owner))
        answer["records"].pop("raw_rows")
        answer["records"].pop("exact_duplicates")
        independent[str(owner)] = answer
        frozen_units("M01", answer, expected["assertions"][str(owner)], str(owner))
    quality = read(final/"quality.json")
    metadata = read(final/"manifest.json")
    assert metadata["state"] == "computed" and metadata["rule_version"] == "quality-1.0"
    quality_checks(quality)
    assert quality["fatal_errors"] == 0
    count = compare(actual, independent)
    full_fields += count
    rules.extend(rule_checks("M01", actual, read(final/"ads/conclusions.json")))
    cases.append({"case_id": "M01", "name": "多主体、低覆盖、首次通过与无样本反例", "status": "passed",
                  "kind": "immutable_S04_ADS_matches_current_Python", "source": "S04-产物/jobs/v1-M01",
                  "subjects": data["subjects"], "frozen_leaf_assertions": len(UNITS)-start,
                  "full_answer_leaf_checks": count, "should_describe_material": expected["should_describe"],
                  "must_not_infer_material": expected["must_not_infer"], "J1_score": None})
    weights = {"cohort_and_version": 30, "source_relations": 20, "numbers_null": 20, "time_quality": 20}
    assert all(unit["coverage_dimensions"] for unit in UNITS)
    dimension_scores = {}
    for dimension, maximum in weights.items():
        selected = [unit for unit in UNITS if dimension in unit["coverage_dimensions"]]
        assert selected
        passed = sum(unit["passed"] for unit in selected)
        dimension_scores[dimension] = {"weight_from_S01": maximum, "passed": passed, "covered_assertions": len(selected),
                                       "score": round(maximum*passed/len(selected), 1)}
    confusion = {}
    for rule_id in sorted({row["rule_id"] for row in rules}):
        selected = [row for row in rules if row["rule_id"] == rule_id]
        confusion[rule_id] = {"TP": sum(r["expected_triggered"] and r["actual_triggered"] for r in selected),
                              "TN": sum(not r["expected_triggered"] and not r["actual_triggered"] for r in selected),
                              "FP": sum(not r["expected_triggered"] and r["actual_triggered"] for r in selected),
                              "FN": sum(r["expected_triggered"] and not r["actual_triggered"] for r in selected)}
    result = {"contract_id": "V2-S01-r2", "rechecked_at": datetime.now(UTC).isoformat(), "status": "passed",
              "method": "Current independent standard-library Python recalculates same frozen S03 vectors; rereads immutable S04 ADS/quality/conclusions. No new Spark run, no database or model connection.",
              "data_vectors": 15, "M01_subjects": 3, "frozen_leaf_assertions": len(UNITS),
              "full_Python_ADS_leaf_checks": full_fields, "cases": cases, "assertions": UNITS,
              "coverage_mapping_note": "Weights and equal-assertion scoring are frozen S01 rules. Field/case tags here are a transparent coverage index created this round, not a pre-existing frozen per-leaf dimension ID; one assertion may support multiple dimensions. No weights, thresholds or expected values changed.",
              "data_dimension_scores": dimension_scores, "data_score": {"earned": sum(d["score"] for d in dimension_scores.values()), "available": 90},
              "deterministic_rule_units": len(rules), "rule_checks": rules, "rule_confusion": confusion,
              "rule_metric_scope": "(case_id, owner_user_id, rule_id) against independently recalculated frozen facts, not AI semantic quality or generalization",
              "external_publication_permission": {"case_ids": ["D13", "D14"], "available": 10,
                    "current_score_in_this_readonly_recheck": None,
                    "S05_historical_evidence": "S05-验证证据/checks.json",
                    "S06_current_evidence": "S06-验证证据/publication-verification.json and browser/real-API evidence maintained by root",
                    "scope": "Not re-executed here; final S06 score must combine root current publication/authentication/GET verification, not copy historical test counts"},
              "combined_numeric_score": None, "J1_explanation_score": None, "J1_status": "pending_by_user_choice_zero_models",
              "models_called": 0, "Spark_jobs_started": 0, "database_connections": 0,
              "not_claimed": ["15 new Spark runs", "J1 passing score", "S06 overall acceptance", "teaching causality", "student code execution"]}
    target = Path(__file__).parent/"frozen-cases-recheck.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("status", "data_vectors", "M01_subjects", "frozen_leaf_assertions", "full_Python_ADS_leaf_checks", "data_score", "deterministic_rule_units", "rule_confusion")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""独立标准库小样本核算，不导入 Spark 或未来清洗作业。"""

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
BUCKETS = ("[0,60)", "[60,240)", "[240,1440)", "[1440,+inf)")


def instant(value):
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("timezone_missing")
    return value


def ratio(numerator, denominator):
    percent = None if not denominator else (Decimal(numerator) * 100 / denominator).quantize(
        Decimal(".000001"), rounding=ROUND_HALF_UP)
    return {"numerator": numerator, "denominator": denominator,
            "percent": None if percent is None else str(percent),
            "display": "无样本" if percent is None else f"{percent.quantize(Decimal('.1'), rounding=ROUND_HALF_UP)}%"}


def deduplicate(tables):
    result, duplicates = {}, {}
    for table, values in tables.items():
        if table == "source_claim_projection":
            result[table] = list(values)
            continue
        unique, duplicates[table] = {}, 0
        for row in values:
            key = row.get("id")
            if key is None:
                raise ValueError("required_key_missing")
            if key in unique:
                if row != unique[key]:
                    raise ValueError("duplicate_key_conflict")
                duplicates[table] += 1
            unique[key] = row
        result[table] = list(unique.values())
    return result, duplicates


def validate_relations(tables):
    indexed = {t: {r["id"]: r for r in rows} for t, rows in tables.items()
               if t != "source_claim_projection"}

    def ref(table, key):
        if key not in indexed[table]:
            raise ValueError("dangling_relation")
        return indexed[table][key]

    def same(actual, expected):
        if actual != expected:
            raise ValueError("relation_mismatch")

    for table in ("learning_records", "daily_tasks"):
        for row in tables[table]:
            if row["project_id"] is not None:
                same(ref("projects", row["project_id"])["owner_id"], row["user_id"])
            if table == "learning_records":
                if row["task_id"] is not None:
                    same(ref("daily_tasks", row["task_id"])["user_id"], row["user_id"])
                if row["duration_minutes"] is not None and row["duration_minutes"] < 0:
                    raise ValueError("negative_duration")
    for row in tables["class_memberships"]:
        ref("teaching_classes", row["class_id"])
        ref("campus_memberships", row["campus_membership_id"])
    versions, feedbacks = {}, {}
    for v in tables["submission_versions"]:
        ref("submissions", v["submission_id"])
        key = (v["submission_id"], v["version_number"])
        if key in versions:
            raise ValueError("duplicate_version_key")
        versions[key] = v
    for f in tables["feedback"]:
        key = (f["submission_id"], f["version_number"])
        if key not in versions:
            raise ValueError("dangling_relation")
        if key in feedbacks:
            raise ValueError("duplicate_feedback_key")
        feedbacks[key] = f
        v, head = versions[key], ref("submissions", f["submission_id"])
        teacher = ref("class_memberships", f["teacher_membership_id"])
        same(teacher["member_role"], "teacher")
        same(teacher["class_id"], head["class_id"])
        same(f["class_id"], head["class_id"])
        same(v["status"], "accepted" if f["decision"] == "accept" else "returned")
        if instant(f["created_at"]) < instant(v["submitted_at"]):
            raise ValueError("negative_feedback_wait")
        if v["reviewed_at"] is None or instant(v["reviewed_at"]) != instant(f["created_at"]):
            raise ValueError("review_timestamp_mismatch")
        if f["learning_record_id"] is not None:
            same(f["decision"], "accept")
            lr = ref("learning_records", f["learning_record_id"])
            student = ref("class_memberships", head["student_membership_id"])
            same(lr["user_id"], ref("campus_memberships", student["campus_membership_id"])["user_id"])
    for head in tables["submissions"]:
        student = ref("class_memberships", head["student_membership_id"])
        same(student["class_id"], head["class_id"])
        same(student["member_role"], "student")
        same(ref("teaching_assignments", head["assignment_id"])["class_id"], head["class_id"])
        ref("teaching_classes", head["class_id"])
        owner = ref("campus_memberships", student["campus_membership_id"])["user_id"]
        chain = sorted((v for v in tables["submission_versions"] if v["submission_id"] == head["id"]),
                       key=lambda v: v["version_number"])
        if [v["version_number"] for v in chain] != list(range(1, len(chain) + 1)):
            raise ValueError("version_gap")
        if not chain or head["latest_version_number"] != len(chain):
            raise ValueError("latest_version_mismatch")
        for i, v in enumerate(chain):
            if v["source_project_id"] is not None:
                same(ref("projects", v["source_project_id"])["owner_id"], owner)
            f = feedbacks.get((head["id"], v["version_number"]))
            if (v["status"] in ("accepted", "returned")) != (f is not None):
                raise ValueError("feedback_status_mismatch")
            if i and (chain[i-1]["status"] != "returned" or instant(v["submitted_at"]) < instant(chain[i-1]["reviewed_at"])):
                raise ValueError("revision_order_mismatch")


def calculate(tables, manifest):
    raw = tables
    tables, duplicates = deduplicate(tables)
    validate_relations(tables)
    owner = manifest["owner_user_id"]
    first, last = manifest["period_start"], manifest["period_end"]
    cutoff = instant(manifest["source_cutoff"])

    def day(value):
        return instant(value).astimezone(TZ).date().isoformat()

    def in_window(value):
        return first <= day(value) <= last and instant(value) < cutoff

    records = [r for r in tables["learning_records"] if r["user_id"] == owner and in_window(r["occurred_at"])]
    tasks = [t for t in tables["daily_tasks"] if t["user_id"] == owner and first <= t["scheduled_date"] <= last]
    cms = {r["id"]: r for r in tables["class_memberships"]}
    cps = {r["id"]: r for r in tables["campus_memberships"]}
    versions = {}
    for v in tables["submission_versions"]:
        versions.setdefault(v["submission_id"], []).append(v)
    feedback = {}
    for f in tables["feedback"]:
        if instant(f["created_at"]) < cutoff:
            feedback.setdefault(f["submission_id"], []).append(f)
    trusted = {f["learning_record_id"] for values in feedback.values() for f in values if f["decision"] == "accept"}
    claimed = {r["learning_record_id"] for r in tables.get("source_claim_projection", [])
               if any(v is not None for k, v in r.items() if k != "learning_record_id")}
    cohort = []
    for head in tables["submissions"]:
        chain = sorted(versions[head["id"]], key=lambda v: v["version_number"])
        if cps[cms[head["student_membership_id"]]["campus_membership_id"]]["user_id"] != owner or not in_window(chain[0]["submitted_at"]):
            continue
        chain = [v for v in chain if instant(v["submitted_at"]) < cutoff]
        fs = feedback.get(head["id"], [])
        accepted = any(f["version_number"] == chain[-1]["version_number"] and f["decision"] == "accept" for f in fs)
        wait = None
        if fs:
            earliest = min(fs, key=lambda f: f["created_at"])
            version = next(v for v in chain if v["version_number"] == earliest["version_number"])
            delta = instant(earliest["created_at"]) - instant(version["submitted_at"])
            wait = Decimal(delta.days * 86400000000 + delta.seconds * 1000000 + delta.microseconds) / Decimal(60000000)
        cohort.append({"day": day(chain[0]["submitted_at"]), "revised": len(chain) > 1,
                       "confirmed": accepted, "returned": any(f["decision"] == "return" for f in fs),
                       "pending": chain[-1]["status"] == "submitted", "attempts": len(chain)-1,
                       "missing_link": sum(f["decision"] == "accept" and f["learning_record_id"] is None for f in fs),
                       "wait": wait})
    known = [r["duration_minutes"] for r in records if r["duration_minutes"] is not None]
    overdue = lambda t: t["status"] in ("pending", "in_progress") and t["scheduled_date"] < cutoff.astimezone(TZ).date().isoformat()
    revised = sum(c["revised"] for c in cohort)
    confirmed = sum(c["confirmed"] for c in cohort)
    revised_confirmed = sum(c["revised"] and c["confirmed"] for c in cohort)
    waits = [c["wait"] for c in cohort if c["wait"] is not None]
    histogram = dict.fromkeys(BUCKETS, 0)
    for w in waits:
        histogram[BUCKETS[0 if w < 60 else 1 if w < 240 else 2 if w < 1440 else 3]] += 1
    daily = []
    days = sorted({day(r["occurred_at"]) for r in records} | {t["scheduled_date"] for t in tasks} | {c["day"] for c in cohort})
    for d in days:
        rs, ts, cs = ([r for r in records if day(r["occurred_at"]) == d],
                      [t for t in tasks if t["scheduled_date"] == d], [c for c in cohort if c["day"] == d])
        daily.append({"date": d, "records": len(rs), "known_minutes": sum(r["duration_minutes"] or 0 for r in rs),
                      "known_duration_count": sum(r["duration_minutes"] is not None for r in rs),
                      "missing_duration_count": sum(r["duration_minutes"] is None for r in rs),
                      "tasks": len(ts), "completed": sum(t["status"] == "completed" for t in ts),
                      "cancelled": sum(t["status"] == "cancelled" for t in ts), "overdue_unfinished": sum(map(overdue, ts)),
                      "cohort": len(cs), "revised": sum(c["revised"] for c in cs), "confirmed": sum(c["confirmed"] for c in cs)})
    return {
        "owner_user_id": owner, "new_batch_required": True,
        "eligible_to_complete_plan": bool(tasks) and all(t["status"] == "completed" for t in tasks),
        "records": {"raw_rows": len(raw["learning_records"]), "valid_unique_rows": len(records),
                    "exact_duplicates": duplicates["learning_records"], "known_minutes": sum(known),
                    "known_duration_count": len(known), "missing_duration_count": len(records)-len(known),
                    "known_zero_count": known.count(0), "active_days": len({day(r["occurred_at"]) for r in records}),
                    "trusted_teaching_count": sum(r["id"] in trusted for r in records),
                    "unverified_claim_count": sum(r["id"] in claimed and r["id"] not in trusted for r in records),
                    "ordinary_count": sum(r["id"] not in trusted and r["id"] not in claimed for r in records)},
        "tasks": {"total": len(tasks), "completed": sum(t["status"] == "completed" for t in tasks),
                  "cancelled": sum(t["status"] == "cancelled" for t in tasks), "overdue_unfinished": sum(map(overdue, tasks)),
                  "completion_rate": ratio(sum(t["status"] == "completed" for t in tasks), len(tasks))},
        "topic": {"cohort_count": len(cohort), "revised_count": revised, "confirmed_count": confirmed,
                  "returned_ever_count": sum(c["returned"] for c in cohort),
                  "first_pass_confirmed_count": confirmed-revised_confirmed, "revised_confirmed_count": revised_confirmed,
                  "pending_latest_count": sum(c["pending"] for c in cohort), "revision_attempts": sum(c["attempts"] for c in cohort),
                  "revised_rate": ratio(revised, len(cohort)), "confirmation_rate": ratio(confirmed, len(cohort)),
                  "revised_confirmation_rate": ratio(revised_confirmed, revised), "first_review_covered": len(waits),
                  "first_review_wait_sum_minutes": float(sum(waits)),
                  "first_review_wait_mean_minutes": str((sum(waits)/len(waits)).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP)) if waits else None,
                  "first_review_histogram": histogram, "missing_teaching_record_links": sum(c["missing_link"] for c in cohort)},
        "daily": daily,
        "quality": {"outside_observation_time": sum(r["user_id"] == owner and instant(r["occurred_at"]) >= cutoff for r in tables["learning_records"])},
    }


def assert_subset(actual, expected):
    for key, value in expected.items():
        target = actual
        for part in key.split("."):
            target = target[part]
        if isinstance(value, dict):
            assert_subset(target, value)
        elif target != value:
            raise AssertionError(f"{key}: expected={value!r}, observed={target!r}")

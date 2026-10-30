"""S10独立标准库答案；不导入Spark SQL、聚合器或后端推荐实现。"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("practice_timezone_missing")
    return parsed.astimezone(UTC)


def calculate_practice(tables, manifest):
    owner = manifest["owner_user_id"]
    tz = ZoneInfo("Asia/Shanghai")
    first = datetime.fromisoformat(manifest["period_start"]).replace(tzinfo=tz).astimezone(UTC)
    last = (datetime.fromisoformat(manifest["period_end"]) + timedelta(days=1)).replace(tzinfo=tz).astimezone(UTC)
    cutoff = instant(manifest["source_cutoff"])
    sessions = sorted((s for s in tables["practice_sessions"] if s["owner_user_id"] == owner
        and first <= instant(s["created_at"]) < min(last, cutoff)), key=lambda s: s["id"])
    facts, all_counts = [], Counter()
    for session in sessions:
        attempts = sorted((a for a in tables["practice_attempts"] if a["session_id"] == session["id"]
            and instant(a["created_at"]) < cutoff), key=lambda a: (a["attempt_no"], a["id"]))
        events = [e for e in tables["practice_events"] if e["session_id"] == session["id"] and instant(e["occurred_at"]) < cutoff]
        counts = Counter(e["event_type"] for e in events if first <= instant(e["occurred_at"]) < last)
        all_counts.update(counts)
        advice = []
        for attempt in attempts:
            reviews = [e for e in events if e["event_type"] == "review_finished" and e["attempt_id"] == attempt["id"]
                and first <= instant(e["occurred_at"]) < last
                and e["operation_id"] == attempt["bound_operation_id"] and e["ai_request_id"] == attempt["bound_ai_request_id"]]
            if not reviews:
                continue
            review = max(reviews, key=lambda e: (e["revision"], instant(e["occurred_at"]), e["id"]))
            for issue in events:
                if issue["event_type"] != "criterion_issue" or issue["attempt_id"] != attempt["id"] or issue["operation_id"] != review["operation_id"] or issue["ai_request_id"] != review["ai_request_id"]:
                    continue
                if not first <= instant(issue["occurred_at"]) < last:
                    continue
                advice.append({"attempt_id": attempt["id"], "attempt_no": attempt["attempt_no"],
                    "operation_id": issue["operation_id"], "ai_request_id": issue["ai_request_id"],
                    "review_event_id": review["id"], "issue_event_id": issue["id"],
                    "criterion_id": issue["criterion_id"], "issue_type": issue["issue_type"],
                    "prompt_version": issue["prompt_version"], "source": "ai_report"})
        advice.sort(key=lambda a: (a["attempt_no"], a["criterion_id"], a["issue_event_id"]))
        latest = attempts[-1] if attempts else None
        facts.append({"session_id": session["id"], **{k: session[k] for k in
            ("project_id", "template_id", "template_version", "context_version", "revision", "current_step_key", "status")},
            "created_at": instant(session["created_at"]).isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "attempt_count": len(attempts), "event_counts": dict(sorted(counts.items())),
            "latest_attempt_id": latest["id"] if latest else None,
            "latest_attempt_no": latest["attempt_no"] if latest else None,
            "latest_operation_id": latest["bound_operation_id"] if latest else None,
            "latest_ai_request_id": latest["bound_ai_request_id"] if latest else None,
            "personal_reviewed": bool(latest["personal_reviewed"]) if latest else False,
            "self_statement": bool(latest["self_statement"]) if latest and latest["self_statement"] is not None else None,
            "output_comparison": latest["output_comparison"] if latest else "unknown",
            "teacher_confirmation": bool(latest["teacher_confirmation"]) if latest and latest["teacher_confirmation"] is not None else None,
            "advice": advice})
    known_teacher = [s["teacher_confirmation"] for s in facts if s["teacher_confirmation"] is not None]
    return {"semantics": "advisory_process",
        "cohort_rule": "sessions_created_in_window;state_at_snapshot;events_in_window_before_cutoff",
        "observed_event_coverage_start": manifest.get("observed_event_coverage_start"),
        "coverage_basis": "first_retained_owner_event", "session_count": len(facts),
        "attempt_count": sum(s["attempt_count"] for s in facts),
        "no_submission_count": sum(s["attempt_count"] == 0 for s in facts),
        "submission_event_count": all_counts["attempt_submitted"],
        "personal_end_count": all_counts["session_completed"],
        "request_count": sum(all_counts[k] for k in ("session_started", "guidance_requested", "review_started")),
        "cancel_count": all_counts["session_cancelled"], "resume_count": all_counts["session_resumed"],
        "teacher_confirmation_count": sum(known_teacher) if known_teacher else None, "sessions": facts}


def calculate_answers(tables, manifest):
    from analytics.fixture_answers import calculate

    result = calculate(tables, manifest)
    if manifest["schema_version"] == "scholarhub-source-2.0":
        result["topic"] = {"teaching": result["topic"], "practice": calculate_practice(tables, manifest)}
    return result

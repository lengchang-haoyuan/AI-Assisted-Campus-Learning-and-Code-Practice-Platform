"""S10离线固定过程案例；无代码正文，不写入数据库。"""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

from analytics.practice_contract import COHORT_RULE, METRIC_VERSION, QUALITY_VERSION, SOURCE_VERSION

FROZEN_TOTALS = {"session_count": 6, "attempt_count": 6, "no_submission_count": 2,
    "submission_event_count": 6, "personal_end_count": 2, "request_count": 4, "cancel_count": 1, "resume_count": 2,
    "teacher_confirmation_count": None}


def make_practice_fixture(core_fixture):
    data = {"manifest": deepcopy(core_fixture["manifest"]), "tables": deepcopy(core_fixture["base_input"])}
    tables, manifest = data["tables"], data["manifest"]
    owner = manifest["owner_user_id"]
    project = next(p["id"] for p in tables["projects"] if p["owner_id"] == owner)
    manifest.update(schema_version=SOURCE_VERSION, metric_version=METRIC_VERSION, rule_version=QUALITY_VERSION,
        dataset_kind="controlled", snapshot_id="s10-fixed-process", practice_cohort_rule=COHORT_RULE,
        observed_event_coverage_start="2026-10-02T00:00:00Z", coverage_basis="first_retained_owner_event")
    tables.update(practice_sessions=[], practice_attempts=[], practice_events=[])
    serial = 10000
    now = datetime(2026, 10, 2, tzinfo=UTC)

    def uid():
        nonlocal serial
        serial += 1
        return str(UUID(int=serial))

    def moment():
        nonlocal now
        now += timedelta(seconds=1)
        return now.isoformat().replace("+00:00", "Z")

    def session():
        created = moment()
        item = dict(id=uid(), owner_user_id=owner, project_id=project, template_id="python-learning-csv",
            template_version="1.0", context_version=1, current_step_key="implement", status="waiting_submission",
            revision=1, created_at=created, updated_at=created)
        tables["practice_sessions"].append(item)
        event(item, "session_created")
        return item

    def event(s, kind, attempt=None, operation=None, request=None, criterion=None, issue=None, same_revision=False):
        if kind != "session_created" and not same_revision:
            s["revision"] += 1
        occurred = moment()
        item = dict(id=uid(), session_id=s["id"], attempt_id=attempt["id"] if attempt else None,
            event_key=f"fixture-{serial}", event_type=kind, criterion_id=criterion, issue_type=issue,
            confirmation_kind="practice_owner" if kind == "step_confirmed" else None,
            occurred_at=occurred, template_id=s["template_id"], template_version=s["template_version"],
            step_key=s["current_step_key"], context_version=1, revision=s["revision"],
            operation_id=operation, ai_request_id=request, ai_request_owner_id=owner if request else None,
            prompt_version="practice-advisory-r1" if request else None, status=s["status"])
        tables["practice_events"].append(item)
        s["updated_at"] = occurred
        return item

    def submit(s):
        created = moment()
        item = dict(id=uid(), session_id=s["id"], step_key="implement",
            attempt_no=1+sum(a["session_id"] == s["id"] for a in tables["practice_attempts"]),
            status="submitted", operation_id=None, ai_request_id=None, bound_operation_id=None,
            bound_ai_request_id=None, self_statement=None, output_comparison="unknown", personal_reviewed=0,
            teacher_confirmation=None, created_at=created, updated_at=created, reviewed_at=None)
        tables["practice_attempts"].append(item)
        s["status"] = "waiting_confirmation"
        event(s, "attempt_submitted", item)
        return item

    def review(s, a, failed=False):
        operation, request = uid(), serial
        a.update(operation_id=operation, ai_request_id=request)
        s["status"] = "running"
        event(s, "review_started", a, operation, request)
        s["status"] = "failed" if failed else "waiting_confirmation"
        finished = event(s, "review_failed" if failed else "review_finished", a, operation, request)
        a.update(status="review_failed" if failed else "reviewed", updated_at=finished["occurred_at"])
        if not failed:
            a.update(bound_operation_id=operation, bound_ai_request_id=request, reviewed_at=finished["occurred_at"])
            event(s, "criterion_issue", a, operation, request, "C03", "zero_as_missing", same_revision=True)

    def end(s, a):
        s["status"] = "completed"
        a.update(status="confirmed", personal_reviewed=1)
        result = event(s, "step_confirmed", a)
        a["updated_at"] = result["occurred_at"]
        event(s, "session_completed", a, same_revision=True)

    s = session(); end(s, submit(s))
    s = session(); review(s, submit(s)); review(s, submit(s))
    s = session()
    s = session(); s.update(current_step_key="understand", status="cancelled")
    event(s, "session_cancelled"); s["status"] = "ready"; event(s, "session_resumed")
    s = session(); a = submit(s); review(s, a, failed=True)
    s["status"] = "waiting_confirmation"; event(s, "session_resumed", a); end(s, a)
    s = session(); review(s, submit(s)); submit(s)
    return data


def make_window_boundary_fixture(core_fixture):
    """第二次提交、建议及本人结束在窗口后，但仍早于同一快照cutoff。"""
    data = make_practice_fixture(core_fixture)
    data["manifest"]["period_end"] = "2026-10-02"
    tables = data["tables"]
    session = tables["practice_sessions"][1]
    tables["practice_sessions"] = [session]
    tables["practice_attempts"] = [a for a in tables["practice_attempts"] if a["session_id"] == session["id"]]
    tables["practice_events"] = [e for e in tables["practice_events"] if e["session_id"] == session["id"]]
    latest = max(tables["practice_attempts"], key=lambda a: a["attempt_no"])
    outside = datetime(2026, 10, 2, 16, 0, 1, tzinfo=UTC)
    moved = sorted((e for e in tables["practice_events"] if e["attempt_id"] == latest["id"]),
        key=lambda e: e["occurred_at"])
    latest["created_at"] = outside.isoformat().replace("+00:00", "Z")
    for index, event in enumerate(moved, 1):
        event["occurred_at"] = (outside+timedelta(seconds=index)).isoformat().replace("+00:00", "Z")
        if event["event_type"] == "review_finished":
            latest["reviewed_at"] = event["occurred_at"]
    session["revision"] += 1
    session["status"] = "completed"
    for index, kind in enumerate(("step_confirmed", "session_completed"), 1):
        event = deepcopy(moved[-1])
        event.update(id=str(UUID(int=99000+index)), event_key=f"window-end-{index}", event_type=kind,
            criterion_id=None, issue_type=None, confirmation_kind="practice_owner" if kind == "step_confirmed" else None,
            revision=session["revision"], status="completed",
            occurred_at=(outside+timedelta(seconds=len(moved)+index)).isoformat().replace("+00:00", "Z"))
        tables["practice_events"].append(event)
    session["updated_at"] = tables["practice_events"][-1]["occurred_at"]
    latest.update(personal_reviewed=1, status="confirmed", updated_at=session["updated_at"])
    return data

"""S10 source-2.0的有限投影；不读取代码、Prompt或反馈正文。"""

SOURCE_VERSION = "scholarhub-source-2.0"
METRIC_VERSION = "learning-process-2.0"
QUALITY_VERSION = "quality-2.0"
COHORT_RULE = "sessions_created_in_window;state_at_snapshot;events_in_window_before_cutoff"
STATUSES = ["ready", "running", "waiting_submission", "waiting_revision", "waiting_confirmation", "failed", "cancelled", "completed"]
EVENT_TYPES = ["session_created", "session_started", "guidance_requested", "attempt_submitted", "review_started", "review_finished", "review_failed", "criterion_issue", "revision_requested", "step_confirmed", "session_cancelled", "session_resumed", "session_completed"]
ISSUE_TYPES = ["missing_header_validation", "row_validation", "csv_quoting", "counting", "zero_as_missing", "unknown_as_known", "sum_error", "empty_result_contract", "external_io"]
CRITERION_ISSUES = {
    "C01": ["missing_header_validation"], "C02": ["row_validation", "csv_quoting"],
    "C03": ["counting", "zero_as_missing", "unknown_as_known"], "C04": ["sum_error"],
    "C05": ["empty_result_contract"], "C06": ["external_io"],
}


def field(name, kind, nullable=False, values=None):
    result = {"field": name, "sql_type": kind, "nullable": nullable}
    if values is not None:
        result["enum_values"] = values
    return result


PRACTICE_DEFINITIONS = {
    "practice_sessions": [
        field("id", "CHAR(36)"), field("owner_user_id", "BIGINT"), field("project_id", "BIGINT"),
        field("template_id", "VARCHAR(64)", values=["python-learning-csv"]),
        field("template_version", "VARCHAR(32)", values=["1.0"]), field("context_version", "INTEGER"),
        field("current_step_key", "VARCHAR(32)", values=["understand", "implement"]),
        field("status", "VARCHAR(32)", values=STATUSES), field("revision", "INTEGER"),
        field("created_at", "DATETIME"), field("updated_at", "DATETIME"),
    ],
    "practice_attempts": [
        field("id", "CHAR(36)"), field("session_id", "CHAR(36)"),
        field("step_key", "VARCHAR(32)", values=["implement"]), field("attempt_no", "INTEGER"),
        field("status", "VARCHAR(32)", values=["submitted", "reviewing", "reviewed", "review_failed", "confirmed"]),
        field("operation_id", "CHAR(36)", True), field("ai_request_id", "BIGINT", True),
        field("bound_operation_id", "CHAR(36)", True), field("bound_ai_request_id", "BIGINT", True),
        field("self_statement", "INTEGER", True, [0, 1]),
        field("output_comparison", "VARCHAR(16)", values=["matched", "mismatched", "unknown"]),
        field("personal_reviewed", "INTEGER", values=[0, 1]),
        field("teacher_confirmation", "INTEGER", True, [0, 1]),
        field("created_at", "DATETIME"), field("updated_at", "DATETIME"), field("reviewed_at", "DATETIME", True),
    ],
    "practice_events": [
        field("id", "CHAR(36)"), field("session_id", "CHAR(36)"), field("attempt_id", "CHAR(36)", True),
        field("event_key", "VARCHAR(160)"), field("event_type", "VARCHAR(48)", values=EVENT_TYPES),
        field("criterion_id", "VARCHAR(8)", True, ["C01", "C02", "C03", "C04", "C05", "C06"]),
        field("issue_type", "VARCHAR(64)", True, ISSUE_TYPES),
        field("confirmation_kind", "VARCHAR(32)", True, ["understanding", "practice_owner"]),
        field("occurred_at", "DATETIME"), field("template_id", "VARCHAR(64)", values=["python-learning-csv"]),
        field("template_version", "VARCHAR(32)", values=["1.0"]),
        field("step_key", "VARCHAR(32)", values=["understand", "implement"]),
        field("context_version", "INTEGER"), field("revision", "INTEGER"),
        field("operation_id", "CHAR(36)", True), field("ai_request_id", "BIGINT", True),
        field("ai_request_owner_id", "BIGINT", True), field("prompt_version", "VARCHAR(100)", True),
        field("status", "VARCHAR(32)", values=STATUSES),
    ],
}


def validate_practice_sources(tables, owner, cutoff):
    """抽取前拒绝未知字段/冲突；Spark另行独立检查关系和顺序。"""
    from datetime import datetime
    from uuid import UUID

    sessions = {}
    for table, definitions in PRACTICE_DEFINITIONS.items():
        seen = set()
        for row in tables[table]:
            if set(row) != {f["field"] for f in definitions}:
                raise ValueError("practice_schema_fields_mismatch")
            if row["id"] in seen:
                raise ValueError("practice_duplicate_primary_key")
            seen.add(row["id"])
            for definition in definitions:
                name, value, kind = definition["field"], row[definition["field"]], definition["sql_type"]
                if value is None:
                    if not definition["nullable"]:
                        raise ValueError("practice_required_key_missing")
                    continue
                if "INT" in kind:
                    if type(value) is not int or value < (0 if name in ("self_statement", "personal_reviewed", "teacher_confirmation") else 1) or value > 2**63-1:
                        raise ValueError("practice_invalid_integer")
                elif not isinstance(value, str):
                    raise ValueError("practice_invalid_string")
                elif kind == "CHAR(36)":
                    if str(UUID(value)) != value:
                        raise ValueError("practice_invalid_uuid")
                elif kind.startswith("VARCHAR(") and len(value) > int(kind[8:-1]):
                    raise ValueError("practice_string_too_long")
                elif kind == "DATETIME":
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0 or parsed.replace(tzinfo=None) >= cutoff:
                        raise ValueError("practice_invalid_time")
                if definition.get("enum_values") and value not in definition["enum_values"]:
                    raise ValueError("practice_unknown_enum")
            if table == "practice_sessions":
                if row["owner_user_id"] != owner:
                    raise ValueError("practice_owner_mismatch")
                sessions[row["id"]] = row
            else:
                if row["session_id"] not in sessions:
                    raise ValueError("practice_missing_session")
                if table == "practice_events" and row["event_type"] == "criterion_issue" and row["issue_type"] not in CRITERION_ISSUES.get(row["criterion_id"], []):
                    raise ValueError("practice_criterion_issue_mismatch")
    if len(sessions) > 500:
        raise ValueError("practice_summary_session_bound_exceeded")

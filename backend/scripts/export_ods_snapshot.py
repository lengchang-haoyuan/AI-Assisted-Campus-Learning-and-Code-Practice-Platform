"""只读、单连接完整窗口导出。配置凭证只在内存中使用，不写 manifest。"""

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from analytics.snapshot_files import begin_snapshot, publish_snapshot, write_json
from analytics.practice_contract import (
    COHORT_RULE, METRIC_VERSION, PRACTICE_DEFINITIONS, QUALITY_VERSION,
    SOURCE_VERSION, validate_practice_sources,
)

FIXTURE = ROOT / "开发相关文档/阶段报告/AI大数据改造/V2/S01-分析固定样例与独立答案.json"
SCHEMA = json.loads(FIXTURE.read_text(encoding="utf-8"))["schema"]
AI_FIELDS = ("id", "user_id", "project_id", "status", "requested_at", "finished_at",
             "prompt_tokens", "completion_tokens", "latency_ms")


def iso(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return value


def utc_window(start, end):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if end < start or (end - start).days >= 90:
        raise ValueError("window_must_be_1_to_90_days")
    tz = ZoneInfo("Asia/Shanghai")
    return (datetime.combine(start, datetime.min.time(), tz).astimezone(UTC).replace(tzinfo=None),
            datetime.combine(end + timedelta(days=1), datetime.min.time(), tz).astimezone(UTC).replace(tzinfo=None))


class SnapshotReader:
    def __init__(self, connection):
        self.connection = connection
        self.reads = []

    def query(self, sql, params=None):
        return [dict(row) for row in self.connection.execute(text(sql), params or {}).mappings()]

    def table(self, name, condition="1=0", params=None):
        fields = [field["field"] for field in SCHEMA[name]] if name in SCHEMA else AI_FIELDS
        rows = self.query(f"SELECT {','.join(fields)} FROM {name} WHERE {condition} ORDER BY id", params)
        self.reads.append(name)
        return [{key: iso(value) for key, value in row.items()} for row in rows]

    def ids(self, name, ids):
        ids = sorted(set(ids) - {None})
        if not ids:
            return []
        placeholders = ",".join(f":v{i}" for i in range(len(ids)))
        return self.table(name, f"id IN ({placeholders})", {f"v{i}": v for i, v in enumerate(ids)})


def select_practice_sources(reader, owner, start, end, cutoff):
    """同事务投影群组及其父链；JSON只在SQL内按已定路径读取。"""
    params = {"owner": owner, "start": start, "end": end, "cutoff": cutoff}
    session_fields = ",".join(f["field"] for f in PRACTICE_DEFINITIONS["practice_sessions"])
    sessions = reader.query(f"SELECT {session_fields} FROM practice_sessions WHERE owner_user_id=:owner "
        "AND created_at>=:start AND created_at<:end AND created_at<:cutoff ORDER BY id LIMIT 501", params)
    if len(sessions) > 500:
        raise ValueError("practice_summary_session_bound_exceeded")
    coverage = reader.query("SELECT MIN(e.occurred_at) AS first_at FROM practice_events e "
        "JOIN practice_sessions s ON s.id=e.session_id WHERE s.owner_user_id=:owner AND e.occurred_at<:cutoff", params)[0]["first_at"]
    rows = {name: [] for name in PRACTICE_DEFINITIONS}
    rows["practice_sessions"] = sessions
    if sessions:
        params.update({f"p{i}": s["id"] for i, s in enumerate(sessions)})
        marks = ",".join(f":p{i}" for i in range(len(sessions)))
        rows["practice_attempts"] = reader.query(f"""
            SELECT a.id,a.session_id,a.step_key,a.attempt_no,a.status,a.operation_id,a.ai_request_id,
              NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.feedback,'$.ai_static_review.operation_id')),'null') AS bound_operation_id,
              CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.feedback,'$.ai_static_review.ai_request_id')),'null') AS UNSIGNED) AS bound_ai_request_id,
              CAST(a.self_statement AS UNSIGNED) AS self_statement,
              CASE JSON_UNQUOTE(JSON_EXTRACT(a.feedback,'$.submitted_output_match.matched'))
                WHEN 'true' THEN 'matched' WHEN 'false' THEN 'mismatched' ELSE 'unknown' END AS output_comparison,
              CASE WHEN JSON_UNQUOTE(JSON_EXTRACT(a.feedback,'$.personal_confirmation.source'))='authenticated_practice_owner'
                THEN 1 ELSE 0 END AS personal_reviewed,
              CASE JSON_UNQUOTE(JSON_EXTRACT(a.feedback,'$.teacher_confirmation.value'))
                WHEN 'true' THEN 1 WHEN 'false' THEN 0 ELSE NULL END AS teacher_confirmation,
              a.created_at,a.updated_at,a.reviewed_at
            FROM practice_attempts a WHERE a.session_id IN ({marks}) AND a.created_at<:cutoff ORDER BY a.id
        """, params)
        rows["practice_events"] = reader.query(f"""
            SELECT e.id,e.session_id,e.attempt_id,e.event_key,e.event_type,e.criterion_id,e.issue_type,
              e.confirmation_kind,e.occurred_at,
              JSON_UNQUOTE(JSON_EXTRACT(e.action_payload,'$.template_id')) AS template_id,
              JSON_UNQUOTE(JSON_EXTRACT(e.action_payload,'$.template_version')) AS template_version,
              JSON_UNQUOTE(JSON_EXTRACT(e.action_payload,'$.step_key')) AS step_key,
              CAST(JSON_UNQUOTE(JSON_EXTRACT(e.action_payload,'$.context_version')) AS UNSIGNED) AS context_version,
              CAST(JSON_UNQUOTE(JSON_EXTRACT(e.action_payload,'$.revision')) AS UNSIGNED) AS revision,
              NULLIF(JSON_UNQUOTE(JSON_EXTRACT(e.action_payload,'$.operation_id')),'null') AS operation_id,
              CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(e.action_payload,'$.ai_request_id')),'null') AS UNSIGNED) AS ai_request_id,
              ar.user_id AS ai_request_owner_id,
              NULLIF(JSON_UNQUOTE(JSON_EXTRACT(ar.request_metadata,'$.prompt_version')),'null') AS prompt_version,
              JSON_UNQUOTE(JSON_EXTRACT(e.action_payload,'$.status')) AS status
            FROM practice_events e LEFT JOIN ai_requests ar
              ON ar.id=CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(e.action_payload,'$.ai_request_id')),'null') AS UNSIGNED)
            WHERE e.session_id IN ({marks}) AND e.occurred_at<:cutoff ORDER BY e.id
        """, params)
    reader.reads.extend(PRACTICE_DEFINITIONS)
    return {table: [{key: iso(value) for key, value in row.items()} for row in values]
            for table, values in rows.items()}, iso(coverage)


def select_sources(reader, owner, start, end, cutoff, include_ai=False):
    p = {"owner": owner, "start": start, "end": end, "cutoff": cutoff}
    if reader.query("SELECT id FROM users WHERE id=:owner AND is_active=1", p) != [{"id": owner}]:
        raise ValueError("owner_not_active")
    rows = {table: [] for table in SCHEMA}
    rows["learning_records"] = reader.table(
        "learning_records", "user_id=:owner AND occurred_at>=:start AND occurred_at<:end AND occurred_at<:cutoff", p)
    rows["daily_tasks"] = reader.table(
        "daily_tasks", "user_id=:owner AND scheduled_date>=:first AND scheduled_date<=:last",
        {"owner": owner, "first": start.replace(tzinfo=UTC).astimezone(ZoneInfo("Asia/Shanghai")).date(),
         "last": (end.replace(tzinfo=UTC).astimezone(ZoneInfo("Asia/Shanghai")) - timedelta(days=1)).date()})
    # 群组与记录来源是两个入口；窗口外的来源父链也必须闭合。
    heads = reader.query("""
        SELECT DISTINCT s.id FROM submissions s
        JOIN class_memberships cm ON cm.id=s.student_membership_id
        JOIN campus_memberships cp ON cp.id=cm.campus_membership_id
        JOIN submission_versions v ON v.submission_id=s.id AND v.version_number=1
        WHERE cp.user_id=:owner AND v.submitted_at>=:start AND v.submitted_at<:end
          AND v.submitted_at<:cutoff
        UNION
        SELECT f.submission_id AS id FROM feedback f
        JOIN learning_records lr ON lr.id=f.learning_record_id
        WHERE lr.user_id=:owner AND lr.occurred_at>=:start AND lr.occurred_at<:end
          AND lr.occurred_at<:cutoff
    """, p)
    rows["submissions"] = reader.ids("submissions", [r["id"] for r in heads])
    head_ids = [row["id"] for row in rows["submissions"]]
    if head_ids:
        params = {f"s{i}": v for i, v in enumerate(head_ids)}
        marks = ",".join(f":s{i}" for i in range(len(head_ids)))
        # 保留所有已存版本；未来事件或不一致状态由验证拒绝，不能截断后假装无修订。
        rows["submission_versions"] = reader.table("submission_versions", f"submission_id IN ({marks})", params)
        rows["feedback"] = reader.table("feedback", f"submission_id IN ({marks})", params)
    record_ids = {r["id"] for r in rows["learning_records"]}
    extra = {f["learning_record_id"] for f in rows["feedback"]} - record_ids - {None}
    rows["learning_records"] += reader.ids("learning_records", extra)
    task_ids = {t["id"] for t in rows["daily_tasks"]}
    extra = {r["task_id"] for r in rows["learning_records"]} - task_ids - {None}
    rows["daily_tasks"] += reader.ids("daily_tasks", extra)
    members = {r["student_membership_id"] for r in rows["submissions"]}
    members |= {r["teacher_membership_id"] for r in rows["feedback"]}
    rows["class_memberships"] = reader.ids("class_memberships", members)
    rows["campus_memberships"] = reader.ids("campus_memberships",
        [r["campus_membership_id"] for r in rows["class_memberships"]])
    rows["teaching_classes"] = reader.ids("teaching_classes", [r["class_id"] for r in rows["submissions"]])
    rows["teaching_assignments"] = reader.ids("teaching_assignments", [r["assignment_id"] for r in rows["submissions"]])
    if include_ai:
        rows["ai_requests_aux"] = reader.table("ai_requests",
            "user_id=:owner AND requested_at>=:start AND requested_at<:end AND requested_at<:cutoff", p)
    project_ids = {r["project_id"] for t in ("learning_records", "daily_tasks") for r in rows[t]}
    project_ids |= {r["source_project_id"] for r in rows["submission_versions"]}
    project_ids |= {r["project_id"] for r in rows.get("ai_requests_aux", [])}
    rows["projects"] = reader.ids("projects", project_ids)
    # SQL 只投影保留键，原始 record_metadata 从不出库。
    rows["source_claim_projection"] = []
    if rows["learning_records"]:
        params = {f"r{i}": r["id"] for i, r in enumerate(rows["learning_records"])}
        marks = ",".join(f":r{i}" for i in range(len(params)))
        claims = reader.query(f"""
            SELECT id AS learning_record_id,
              JSON_EXTRACT(record_metadata,'$.source') AS source_claim,
              JSON_EXTRACT(record_metadata,'$.submission_id') AS submission_id_claim,
              JSON_EXTRACT(record_metadata,'$.version_number') AS version_number_claim
            FROM learning_records WHERE id IN ({marks}) ORDER BY id
        """, params)
        for claim in claims:
            for key in ("source_claim", "submission_id_claim", "version_number_claim"):
                value = json.loads(claim[key]) if claim[key] is not None else None
                valid = (isinstance(value, str) and len(value) <= 32) if key == "source_claim" else (
                    type(value) is int and 0 < value <= (2**31-1 if key == "version_number_claim" else 2**63-1))
                claim[key] = value if value is None or valid else ("[invalid]" if key == "source_claim" else None)
            if any(claim[k] is not None for k in claim if k != "learning_record_id"):
                rows["source_claim_projection"].append(claim)
    auxiliary = {"owner_exists": True, "checked_plan_refs": 0, "checked_course_refs": 0, "checked_user_refs": 0}
    for table, field, owner_field, sources in (
        ("learning_plans", "plan_id", "user_id", rows["daily_tasks"]),
        ("courses", "course_id", "owner_id", rows["learning_records"]),
    ):
        for ref in sorted({row[field] for row in sources} - {None}):
            if reader.query(f"SELECT id FROM {table} WHERE id=:id AND {owner_field}=:owner",
                            {"id": ref, "owner": owner}) != [{"id": ref}]:
                raise ValueError("auxiliary_owner_mismatch")
            auxiliary["checked_plan_refs" if table == "learning_plans" else "checked_course_refs"] += 1
    for uid in sorted({r["user_id"] for r in rows["campus_memberships"]}):
        if reader.query("SELECT id FROM users WHERE id=:id", {"id": uid}) != [{"id": uid}]:
            raise ValueError("auxiliary_user_missing")
        auxiliary["checked_user_refs"] += 1
    for values in rows.values():
        values.sort(key=lambda r: r.get("id", r.get("learning_record_id")))
    return rows, auxiliary


def validate_sources(rows, owner, cutoff):
    """抽取阶段验证完整性及归属；不产生 Spark/DWD 指标。"""
    from analytics.fixture_answers import validate_relations
    for table, fields in SCHEMA.items():
        ids = set()
        for row in rows[table]:
            if set(row) != {f["field"] for f in fields}:
                raise ValueError("schema_fields_mismatch")
            if row["id"] in ids:
                raise ValueError("duplicate_primary_key")
            ids.add(row["id"])
            for field in fields:
                value = row[field["field"]]
                if value is None:
                    if not field["nullable"]:
                        raise ValueError("required_key_missing")
                    continue
                kind = field["sql_type"]
                if "INT" in kind:
                    if type(value) is not int or not 0 <= value <= 2**63-1:
                        raise ValueError("integer_out_of_range")
                    if (field["field"] == "id" or field["field"].endswith("_id") or field["field"] in ("revision", "version_number", "latest_version_number")) and value < 1:
                        raise ValueError("positive_key_required")
                elif kind == "DATETIME":
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if parsed.utcoffset() != timedelta(0):
                        raise ValueError("not_utc")
                elif kind == "DATE":
                    date.fromisoformat(value)
                if field.get("enum_values") and value not in field["enum_values"]:
                    raise ValueError("unknown_enum")
    for table in ("learning_records", "daily_tasks"):
        if any(row["user_id"] != owner for row in rows[table]):
            raise ValueError("owner_mismatch")
    if any(row["owner_id"] != owner for row in rows["projects"]):
        raise ValueError("project_owner_mismatch")
    validate_relations(rows)
    for table, field in (("submission_versions", "submitted_at"), ("feedback", "created_at")):
        if any(datetime.fromisoformat(r[field].replace("Z", "+00:00")).replace(tzinfo=None) >= cutoff for r in rows[table]):
            raise ValueError("future_teaching_event")


def export_snapshot(engine, root, snapshot_id, owner, period_start, period_end,
                    include_ai=False, after_snapshot_started=None, after_read=None, include_practice=False):
    start, end = utc_window(period_start, period_end)
    pending, final = begin_snapshot(root, snapshot_id)
    started = datetime.now(UTC).isoformat()
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            connection.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
            connection.commit()
            connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            reader = SnapshotReader(connection)
            info = reader.query("SELECT UTC_TIMESTAMP(6) AS cutoff, CONNECTION_ID() AS connection_id, "
                                "@@transaction_isolation AS isolation_level, @@transaction_read_only AS read_only, DATABASE() AS db")[0]
            cutoff = info.pop("cutoff")
            engines = reader.query("SELECT TABLE_NAME AS name, ENGINE AS engine FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE()")
            required = set(SCHEMA) | {"users", "courses", "learning_plans"}
            if include_ai:
                required.add("ai_requests")
            if include_practice:
                required.update(PRACTICE_DEFINITIONS)
                required.add("ai_requests")
            if any(dict((r["name"], r["engine"]) for r in engines).get(t) != "InnoDB" for t in required):
                raise ValueError("non_transactional_or_missing_source")
            if after_snapshot_started:
                after_snapshot_started()
            rows, auxiliary = select_sources(reader, owner, start, end, cutoff, include_ai)
            if include_practice:
                practice_rows, coverage = select_practice_sources(reader, owner, start, end, cutoff)
                rows.update(practice_rows)
                project_ids = {r["id"] for r in rows["projects"]}
                rows["projects"] += reader.ids("projects", {s["project_id"] for s in practice_rows["practice_sessions"]} - project_ids)
            if after_read:
                after_read()
            validate_sources(rows, owner, cutoff)
            if include_practice:
                validate_practice_sources(rows, owner, cutoff)
            connection.commit()
        finished = datetime.now(UTC).isoformat()
        manifest = {
            "dataset_id": f"s02-controlled-owner-{owner}", "snapshot_id": snapshot_id,
            "batch_id": str(uuid4()), "owner_user_id": owner, "subject_coverage": [owner],
            "scope": "single_owner_with_relation_closure", "dataset_kind": "controlled",
            "source_provenance": "existing_api_created_isolated_fictional_data",
            "schema_version": "scholarhub-source-1.0", "metric_version": "learning-process-1.0",
            "rule_version": "quality-1.0", "contract_id": "V2-S01-r2",
            "period_start": period_start, "period_end": period_end, "business_timezone": "Asia/Shanghai",
            "window_start_utc": iso(start), "window_end_exclusive_utc": iso(end),
            "source_cutoff": iso(cutoff), "snapshot_started_at": started, "snapshot_finished_at": finished,
            "file_generated_at": datetime.now(UTC).isoformat(), "transaction": info,
            "transaction_method": "one connection; START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY; commit before file I/O",
            "filters": {"records": "owner and UTC window and occurred_at<cutoff plus feedback-linked closure",
                        "tasks": "owner and unshifted DATE window plus record-linked closure",
                        "submissions": "owner V1 in UTC window plus record-provenance closure; all versions",
                        "incremental_watermark": None},
            "auxiliary_checks": auxiliary, "source_tables_read": reader.reads,
            "auxiliary_schema_version": "ai-request-aux-1.0" if include_ai else None,
        }
        if include_practice:
            manifest.update(schema_version=SOURCE_VERSION, metric_version=METRIC_VERSION, rule_version=QUALITY_VERSION,
                practice_cohort_rule=COHORT_RULE, observed_event_coverage_start=coverage,
                coverage_basis="first_retained_owner_event")
            manifest["filters"]["practice"] = COHORT_RULE
        return final, publish_snapshot(pending, final, rows, manifest)
    except Exception as error:
        write_json(pending / "failure.json", {"extraction_status": "failed", "snapshot_id": snapshot_id,
                                             "error_type": type(error).__name__, "published": False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--owner", type=int, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot-id", default=f"ods-{uuid4().hex}")
    parser.add_argument("--include-ai-aux", action="store_true")
    parser.add_argument("--include-practice", action="store_true", help="显式使用source-2.0实践白名单；默认保留1.0")
    args = parser.parse_args()
    # 本轮入口限定已核实目标；扩展到业务源时必须明确数据授权及 kind。
    if args.database != "scholarhub_l4_s02_20261020" or args.owner not in (3, 4):
        parser.error("本轮只支持已授权隔离源与虚构主体3/4")
    url = make_url(Settings().database_url)
    if url.host not in ("localhost", "127.0.0.1") or (url.port or 3306) != 3306:
        parser.error("连接目标与授权不一致")
    engine = create_engine(url.set(database=args.database), echo=False)
    try:
        path, manifest = export_snapshot(engine, args.output, args.snapshot_id, args.owner,
                                         args.start, args.end, args.include_ai_aux, include_practice=args.include_practice)
        print(json.dumps({"path": str(path), "counts": manifest["row_counts"]}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

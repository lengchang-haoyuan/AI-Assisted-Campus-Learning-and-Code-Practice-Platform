"""显式 Schema、Spark DataFrame 规范化与可定位质量分流。"""

import json
from functools import reduce

from pyspark.sql import functions as F, types as T


def source_definitions(core):
    definitions = dict(core)
    definitions["source_claim_projection"] = [
        {"field": "learning_record_id", "sql_type": "BIGINT", "nullable": False},
        {"field": "source_claim", "sql_type": "VARCHAR(32)", "nullable": True},
        {"field": "submission_id_claim", "sql_type": "BIGINT", "nullable": True},
        {"field": "version_number_claim", "sql_type": "INTEGER", "nullable": True},
    ]
    definitions["ai_requests_aux"] = [
        {"field": name, "sql_type": kind, "nullable": nullable}
        for name, kind, nullable in [
            ("id", "BIGINT", False), ("user_id", "BIGINT", False), ("project_id", "BIGINT", True),
            ("status", "VARCHAR(16)", False), ("requested_at", "DATETIME", False),
            ("finished_at", "DATETIME", True), ("prompt_tokens", "INTEGER", True),
            ("completion_tokens", "INTEGER", True), ("latency_ms", "INTEGER", True),
        ]
    ]
    definitions["ai_requests_aux"][3]["enum_values"] = ["pending", "running", "completed", "failed"]
    return definitions


def normalize(spark, tables, definitions):
    frames, exceptions, stats_queries = {}, [], []
    for table, fields in definitions.items():
        names = [f["field"] for f in fields]
        key = "learning_record_id" if table == "source_claim_projection" else "id"
        raw_schema = T.StructType([T.StructField(n, T.StringType(), True) for n in names] +
                                  [T.StructField("_row", T.LongType(), False), T.StructField("_lexical", T.StringType(), True)])
        raw_rows = []
        for number, row in enumerate(tables.get(table, []), 1):
            lexical = "unexpected_field" if set(row) - set(names) else None
            for f in fields:
                value = row.get(f["field"])
                if value is not None and (("INT" in f["sql_type"] and type(value) is not int) or
                                          ("INT" not in f["sql_type"] and not isinstance(value, str))):
                    lexical = "invalid_json_type"
            raw_rows.append(tuple(None if row.get(n) is None else str(row[n]) for n in names) + (number, lexical))
        raw = spark.createDataFrame(raw_rows, raw_schema)
        expressions, errors = [], [F.col("_lexical")]
        for field in fields:
            name, kind = field["field"], field["sql_type"]
            original = F.col(name)
            if "INT" in kind:
                value = F.expr(f"try_cast(`{name}` AS BIGINT)")
                minimum = 1 if name in ("id", "learning_record_id", "revision", "version_number", "latest_version_number") or name.endswith("_id") else 0
                errors.append(F.when(original.isNotNull() & (value.isNull() | (value < minimum)), F.lit("integer_out_of_range")))
            elif kind in ("DATE", "DATETIME"):
                value = F.expr(f"try_cast(`{name}` AS {'DATE' if kind == 'DATE' else 'TIMESTAMP'})")
                pattern = r"^\d{4}-\d{2}-\d{2}$" if kind == "DATE" else r"(Z|[+-]\d{2}:\d{2})$"
                errors.append(F.when(original.isNotNull() & (value.isNull() | ~original.rlike(pattern)), F.lit("invalid_time")))
            else:
                value = original
                if field.get("enum_values"):
                    errors.append(F.when(original.isNotNull() & ~original.isin(field["enum_values"]), F.lit("unknown_enum")))
            if not field["nullable"]:
                errors.append(F.when(original.isNull(), F.lit("required_key_missing")))
            expressions.append(value.alias(name))
        normalized = raw.select(*expressions, "_row", F.coalesce(*errors).alias("_error"))
        normalized.createOrReplaceTempView(f"raw_{table}")
        fields_sql = ",".join(f"`{n}`" for n in names)
        stats_queries.append(f"SELECT '{table}' table_name, count(*) raw_rows, "
                             f"sum(CASE WHEN _error IS NOT NULL THEN 1 ELSE 0 END) invalid_rows, "
                             f"count(DISTINCT CASE WHEN _error IS NULL THEN struct({fields_sql}) END) unique_rows "
                             f"FROM raw_{table}")
        errors_df = normalized.filter("_error IS NOT NULL").select(
            F.lit(table).alias("table_name"), F.col(key).cast("string").alias("source_key"),
            F.col("_row").alias("source_row"), F.col("_error").alias("reason"))
        valid = normalized.filter("_error IS NULL").select(*names).dropDuplicates(names)
        valid.createOrReplaceTempView(f"v_{table}")
        conflict = valid.groupBy(key).count().filter("count>1").select(
            F.lit(table).alias("table_name"), F.col(key).cast("string").alias("source_key"),
            F.lit(None).cast("long").alias("source_row"), F.lit("duplicate_key_conflict").alias("reason"))
        exceptions.extend([errors_df, conflict])
        frames[table] = valid
    stats = [r.asDict() for r in spark.sql(" UNION ALL ".join(stats_queries)).collect()]
    for row in stats:
        row["invalid_rows"] = row["invalid_rows"] or 0
        row["exact_duplicates"] = row["raw_rows"] - row["invalid_rows"] - row["unique_rows"]
    failures = [r.asDict() for r in reduce(lambda a, b: a.unionByName(b), exceptions).collect()]
    return frames, stats, failures


def relationship_errors(spark, owner):
    checks = []

    def add(table, query, reason):
        checks.append(f"SELECT '{table}' table_name, cast(id as string) source_key, '{reason}' reason FROM ({query}) q")

    for child, field, parent, pkey in [
        ("learning_records", "project_id", "projects", "id"), ("learning_records", "task_id", "daily_tasks", "id"),
        ("daily_tasks", "project_id", "projects", "id"), ("class_memberships", "class_id", "teaching_classes", "id"),
        ("class_memberships", "campus_membership_id", "campus_memberships", "id"),
        ("submissions", "student_membership_id", "class_memberships", "id"),
        ("submissions", "assignment_id", "teaching_assignments", "id"),
        ("submission_versions", "submission_id", "submissions", "id"),
        ("submission_versions", "source_project_id", "projects", "id"),
        ("feedback", "submission_id", "submissions", "id"), ("feedback", "teacher_membership_id", "class_memberships", "id"),
        ("feedback", "learning_record_id", "learning_records", "id"),
    ]:
        add(child, f"SELECT c.id FROM v_{child} c LEFT JOIN v_{parent} p ON c.{field}=p.{pkey} WHERE c.{field} IS NOT NULL AND p.{pkey} IS NULL", "dangling_relation")
    if owner is not None:
        for table in ("learning_records", "daily_tasks", "ai_requests_aux"):
            add(table, f"SELECT id FROM v_{table} WHERE user_id<>{int(owner)}", "owner_mismatch")
        add("projects", f"SELECT id FROM v_projects WHERE owner_id<>{int(owner)}", "owner_mismatch")
    add("learning_records", "SELECT r.id FROM v_learning_records r JOIN v_projects p ON r.project_id=p.id WHERE r.user_id<>p.owner_id", "owner_mismatch")
    add("daily_tasks", "SELECT t.id FROM v_daily_tasks t JOIN v_projects p ON t.project_id=p.id WHERE t.user_id<>p.owner_id", "owner_mismatch")
    add("learning_records", "SELECT r.id FROM v_learning_records r JOIN v_daily_tasks t ON r.task_id=t.id WHERE r.user_id<>t.user_id", "owner_mismatch")
    add("submissions", """SELECT s.id FROM v_submissions s JOIN v_class_memberships m ON s.student_membership_id=m.id
        JOIN v_teaching_assignments a ON a.id=s.assignment_id WHERE m.class_id<>s.class_id OR a.class_id<>s.class_id OR m.member_role<>'student'""", "class_mismatch")
    add("submission_versions", """SELECT v.id FROM v_submission_versions v JOIN v_submissions s ON v.submission_id=s.id
        JOIN v_class_memberships cm ON cm.id=s.student_membership_id JOIN v_campus_memberships cp ON cp.id=cm.campus_membership_id
        JOIN v_projects p ON p.id=v.source_project_id WHERE cp.user_id<>p.owner_id""", "owner_mismatch")
    add("submissions", """SELECT s.id FROM v_submissions s LEFT JOIN
        (SELECT submission_id, count(*) n, min(version_number) lo, max(version_number) hi FROM v_submission_versions GROUP BY submission_id) v
        ON s.id=v.submission_id WHERE v.n IS NULL OR v.lo<>1 OR v.n<>v.hi OR s.latest_version_number<>v.hi""", "version_gap")
    add("submission_versions", "SELECT min(id) id FROM v_submission_versions GROUP BY submission_id,version_number HAVING count(*)>1", "duplicate_version_key")
    add("feedback", "SELECT min(id) id FROM v_feedback GROUP BY submission_id,version_number HAVING count(*)>1", "duplicate_feedback_key")
    add("feedback", "SELECT min(id) id FROM v_feedback WHERE learning_record_id IS NOT NULL GROUP BY learning_record_id HAVING count(*)>1", "duplicate_teaching_record_link")
    add("feedback", """SELECT f.id FROM v_feedback f LEFT JOIN v_submission_versions v ON f.submission_id=v.submission_id AND f.version_number=v.version_number
        JOIN v_submissions s ON s.id=f.submission_id JOIN v_class_memberships tm ON tm.id=f.teacher_membership_id
        JOIN v_class_memberships sm ON sm.id=s.student_membership_id JOIN v_campus_memberships cp ON cp.id=sm.campus_membership_id
        LEFT JOIN v_learning_records lr ON lr.id=f.learning_record_id
        WHERE v.id IS NULL OR tm.member_role<>'teacher' OR tm.class_id<>s.class_id OR f.class_id<>s.class_id
        OR (f.learning_record_id IS NOT NULL AND (f.decision<>'accept' OR lr.user_id<>cp.user_id))
        OR f.created_at<v.submitted_at OR v.reviewed_at IS NULL OR v.reviewed_at<>f.created_at
        OR (f.decision='accept' AND v.status<>'accepted') OR (f.decision='return' AND v.status<>'returned')""", "feedback_relation_mismatch")
    add("submission_versions", """SELECT v.id FROM v_submission_versions v LEFT JOIN v_feedback f
        ON f.submission_id=v.submission_id AND f.version_number=v.version_number
        WHERE (v.status IN ('accepted','returned') AND f.id IS NULL) OR (v.status='submitted' AND f.id IS NOT NULL)""", "feedback_status_mismatch")
    add("submission_versions", """SELECT v.id FROM v_submission_versions v JOIN v_submission_versions p
        ON v.submission_id=p.submission_id AND v.version_number=p.version_number+1
        WHERE p.status<>'returned' OR v.submitted_at<p.reviewed_at""", "revision_order_mismatch")
    return [r.asDict() for r in spark.sql(" UNION ALL ".join(checks)).collect()]

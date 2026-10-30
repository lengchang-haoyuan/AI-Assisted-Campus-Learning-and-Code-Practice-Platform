"""只组织已由Spark SQL聚合的实践结果，不在Python重新计算指标。"""

from analytics.practice_contract import COHORT_RULE


def utc_session_rows(spark):
    """在Spark的UTC会话内转字符串，避免collect的naive datetime受Python主机TZ影响。"""
    if spark.conf.get("spark.sql.session.timeZone") != "UTC":
        raise ValueError("practice_utc_spark_session_required")
    from pyspark.sql import functions as F
    return (spark.table("practice_session_facts")
        .withColumn("created_at", F.date_format("created_at", "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'"))
        .orderBy("session_id").collect())


def collect_practice(spark, manifest):
    event_counts = {}
    for row in spark.table("ads_practice_events").orderBy("session_id", "event_type").collect():
        event_counts.setdefault(row.session_id, {})[row.event_type] = row.event_count
    advice = {}
    for row in spark.table("practice_advice_facts").orderBy("session_id", "attempt_no", "criterion_id", "issue_event_id").collect():
        item = row.asDict()
        session_id = item.pop("session_id")
        advice.setdefault(session_id, []).append(item)
    facts = {}
    for row in utc_session_rows(spark):
        item = row.asDict()
        owner = item.pop("owner_user_id")
        item["personal_reviewed"] = bool(item["personal_reviewed"])
        for key in ("self_statement", "teacher_confirmation"):
            item[key] = bool(item[key]) if item[key] is not None else None
        item["event_counts"] = event_counts.get(item["session_id"], {})
        item["advice"] = advice.get(item["session_id"], [])
        if len(item["advice"]) > 600:
            raise ValueError("practice_advice_bound_exceeded")
        facts.setdefault(str(owner), []).append(item)
    result = {}
    for row in spark.table("ads_practice_summary").collect():
        item = row.asDict()
        owner = str(item.pop("owner_user_id"))
        item.update(semantics="advisory_process", cohort_rule=COHORT_RULE,
            observed_event_coverage_start=manifest.get("observed_event_coverage_start"),
            coverage_basis="first_retained_owner_event", sessions=facts.get(owner, []))
        result[owner] = item
    return result

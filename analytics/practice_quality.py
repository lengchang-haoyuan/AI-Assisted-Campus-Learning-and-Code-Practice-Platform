"""source-2.0实践关系、顺序和状态一致性；异常阻断发布。"""


def logical_event_order_queries():
    return [
        ("practice_events", """SELECT e.id FROM v_practice_events e LEFT JOIN v_practice_events c
            ON c.session_id=e.session_id AND c.event_type='session_created'
            WHERE e.event_type<>'session_created' AND
            (c.id IS NULL OR e.occurred_at<c.occurred_at OR e.revision<c.revision)""", "practice_event_before_creation_event"),
        ("practice_events", """SELECT e.id FROM v_practice_events e LEFT JOIN v_practice_events a
            ON a.session_id=e.session_id AND a.attempt_id=e.attempt_id AND a.event_type='attempt_submitted'
            WHERE e.attempt_id IS NOT NULL AND e.event_type<>'attempt_submitted' AND
            (a.id IS NULL OR e.occurred_at<a.occurred_at OR e.revision<a.revision)""", "practice_event_before_submission_event"),
    ]


def practice_relationship_errors(spark, manifest):
    checks = []

    def add(table, query, reason):
        checks.append(f"SELECT '{table}' table_name, cast(id as string) source_key, '{reason}' reason FROM ({query}) q")

    owner = int(manifest["owner_user_id"])
    cutoff = manifest["source_cutoff"]
    for table in ("practice_sessions", "practice_attempts", "practice_events"):
        add(table, f"SELECT id FROM v_{table} WHERE NOT id RLIKE '^[0-9a-f]{{8}}(-[0-9a-f]{{4}}){{3}}-[0-9a-f]{{12}}$'", "practice_invalid_uuid")
        time_fields = {"practice_sessions": ["created_at", "updated_at"], "practice_attempts": ["created_at", "updated_at", "reviewed_at"], "practice_events": ["occurred_at"]}[table]
        condition = " OR ".join(f"{field}>=TIMESTAMP '{cutoff}'" for field in time_fields)
        add(table, f"SELECT id FROM v_{table} WHERE {condition}", "practice_future_source")
    add("practice_sessions", f"SELECT s.id FROM v_practice_sessions s LEFT JOIN v_projects p ON s.project_id=p.id WHERE s.owner_user_id<>{owner} OR p.id IS NULL OR p.owner_id<>s.owner_user_id", "practice_owner_relation")
    add("practice_sessions", "SELECT id FROM v_practice_sessions WHERE updated_at<created_at OR context_version<1 OR revision<1", "practice_session_order")
    add("practice_attempts", "SELECT a.id FROM v_practice_attempts a LEFT JOIN v_practice_sessions s ON a.session_id=s.id WHERE s.id IS NULL OR a.created_at<s.created_at OR a.updated_at<a.created_at OR a.reviewed_at<a.created_at OR a.attempt_no<1", "practice_attempt_relation")
    add("practice_attempts", "SELECT min(id) id FROM v_practice_attempts GROUP BY session_id,step_key,attempt_no HAVING count(*)>1", "practice_duplicate_attempt_number")
    add("practice_attempts", "SELECT min(id) id FROM v_practice_attempts GROUP BY session_id HAVING min(attempt_no)<>1 OR max(attempt_no)<>count(*) OR count(*)>100", "practice_attempt_sequence_or_bound")
    add("practice_events", "SELECT min(id) id FROM v_practice_events GROUP BY session_id,event_key HAVING count(*)>1", "practice_duplicate_event_key")
    add("practice_events", f"""SELECT e.id FROM v_practice_events e LEFT JOIN v_practice_sessions s ON e.session_id=s.id
        LEFT JOIN v_practice_attempts a ON a.id=e.attempt_id
        WHERE s.id IS NULL OR (e.attempt_id IS NOT NULL AND (a.id IS NULL OR a.session_id<>s.id))
        OR e.template_id<>s.template_id OR e.template_version<>s.template_version
        OR e.context_version<>s.context_version OR e.revision>s.revision OR e.revision<1
        OR (e.ai_request_id IS NOT NULL AND (e.ai_request_owner_id IS NULL OR e.ai_request_owner_id<>{owner}))""", "practice_event_relation")
    # created_at由DB时钟产生，occurred_at由Python时钟产生；同事务微秒差不能证明倒序。
    # 顺序改用同一来源的事件时钟及revision，跨时钟差异另存观察报告。
    for table, query, reason in logical_event_order_queries():
        add(table, query, reason)
    add("practice_events", """SELECT id FROM v_practice_events WHERE
        (event_type IN ('review_started','review_finished','review_failed','criterion_issue') AND
            (attempt_id IS NULL OR operation_id IS NULL OR ai_request_id IS NULL))
        OR (event_type='criterion_issue' AND (criterion_id IS NULL OR issue_type IS NULL))
        OR (event_type<>'criterion_issue' AND (criterion_id IS NOT NULL OR issue_type IS NOT NULL))
        OR (event_type='step_confirmed' AND confirmation_kind IS NULL)
        OR (event_type<>'step_confirmed' AND confirmation_kind IS NOT NULL)
        OR (confirmation_kind='practice_owner' AND (attempt_id IS NULL OR step_key<>'implement'))
        OR (confirmation_kind='understanding' AND (attempt_id IS NOT NULL OR step_key<>'understand'))""", "practice_event_shape")
    from analytics.practice_contract import CRITERION_ISSUES
    pairs = " OR ".join("(criterion_id='" + criterion + "' AND issue_type IN (" + ",".join("'" + issue + "'" for issue in issues) + "))" for criterion, issues in CRITERION_ISSUES.items())
    add("practice_events", "SELECT id FROM v_practice_events WHERE event_type='criterion_issue' AND NOT (" + pairs + ")", "practice_criterion_issue_mismatch")
    add("practice_events", """SELECT e.id FROM v_practice_events e LEFT JOIN v_practice_events r
        ON r.session_id=e.session_id AND r.attempt_id=e.attempt_id AND r.operation_id=e.operation_id
        AND r.ai_request_id=e.ai_request_id AND r.event_type='review_finished'
        WHERE e.event_type='criterion_issue' AND (r.id IS NULL OR e.revision<>r.revision OR e.occurred_at<r.occurred_at)""", "practice_issue_review_binding")
    add("practice_events", """SELECT e.id FROM v_practice_events e LEFT JOIN v_practice_events r
        ON r.session_id=e.session_id AND r.attempt_id=e.attempt_id AND r.operation_id=e.operation_id
        AND r.ai_request_id=e.ai_request_id AND r.event_type='review_started'
        WHERE e.event_type IN ('review_finished','review_failed') AND (r.id IS NULL OR e.occurred_at<r.occurred_at OR e.revision<=r.revision)""", "practice_review_order")
    add("practice_events", "SELECT min(id) id FROM v_practice_events WHERE event_type='review_finished' GROUP BY session_id,attempt_id,operation_id HAVING count(*)>1", "practice_duplicate_review_finish")
    add("practice_events", "SELECT min(id) id FROM v_practice_events WHERE event_type='criterion_issue' GROUP BY session_id,attempt_id,operation_id,criterion_id HAVING count(*)>1", "practice_duplicate_review_criterion")
    add("practice_attempts", """SELECT a.id FROM v_practice_attempts a LEFT JOIN v_practice_events e
        ON e.session_id=a.session_id AND e.attempt_id=a.id AND e.event_type='attempt_submitted'
        WHERE e.id IS NULL""", "practice_missing_submission_event")
    add("practice_events", "SELECT min(id) id FROM v_practice_events WHERE event_type='attempt_submitted' GROUP BY session_id,attempt_id HAVING count(*)<>1", "practice_duplicate_submission_event")
    add("practice_attempts", """SELECT a.id FROM v_practice_attempts a LEFT JOIN v_practice_events e
        ON e.session_id=a.session_id AND e.attempt_id=a.id AND e.event_type='review_finished'
        AND e.operation_id=a.bound_operation_id AND e.ai_request_id=a.bound_ai_request_id
        WHERE (a.bound_operation_id IS NULL)<>(a.bound_ai_request_id IS NULL)
        OR (a.bound_operation_id IS NOT NULL AND e.id IS NULL)""", "practice_feedback_binding")
    add("practice_sessions", """SELECT s.id FROM v_practice_sessions s LEFT JOIN (
        SELECT session_id,sum(CASE WHEN event_type='session_created' THEN 1 ELSE 0 END) created,
        sum(CASE WHEN event_type='session_completed' THEN 1 ELSE 0 END) ended,
        sum(CASE WHEN event_type='step_confirmed' AND confirmation_kind='practice_owner' THEN 1 ELSE 0 END) confirmed,
        max(CASE WHEN event_type='session_cancelled' THEN revision ELSE 0 END) cancelled_at,
        max(CASE WHEN event_type='session_resumed' THEN revision ELSE 0 END) resumed_at
        FROM v_practice_events GROUP BY session_id) e ON e.session_id=s.id
        WHERE e.created IS NULL OR e.created<>1 OR e.ended>1 OR e.confirmed>1
        OR (s.status='completed' AND (e.ended<>1 OR e.confirmed<>1))
        OR (s.status<>'completed' AND e.ended<>0)
        OR (s.status='cancelled' AND e.cancelled_at<=e.resumed_at)
        OR (s.status NOT IN ('cancelled','completed') AND e.cancelled_at>e.resumed_at)""", "practice_state_event_conflict")
    add("practice_attempts", """SELECT a.id FROM v_practice_attempts a LEFT JOIN v_practice_events e
        ON e.attempt_id=a.id AND e.event_type='step_confirmed' AND e.confirmation_kind='practice_owner'
        WHERE (a.personal_reviewed=1 AND e.id IS NULL) OR (a.personal_reviewed=0 AND e.id IS NOT NULL)
        OR (a.status='confirmed' AND a.personal_reviewed<>1)""", "practice_personal_review_conflict")
    return [row.asDict() for row in spark.sql(" UNION ALL ".join(checks)).collect()]


def practice_clock_observations(spark):
    """保留跨时钟现象的精确引用，不修时间，也不将其当作同源事件倒序。"""
    return [row.asDict() for row in spark.sql("""
        SELECT 'practice_events' table_name,e.id source_key,'session_creation_cross_clock' reason,
            timestampdiff(MICROSECOND,e.occurred_at,s.created_at) database_ahead_microseconds
        FROM v_practice_events e JOIN v_practice_sessions s ON s.id=e.session_id
        WHERE e.event_type='session_created' AND e.occurred_at<s.created_at
        UNION ALL
        SELECT 'practice_events' table_name,e.id source_key,'attempt_creation_cross_clock' reason,
            timestampdiff(MICROSECOND,e.occurred_at,a.created_at) database_ahead_microseconds
        FROM v_practice_events e JOIN v_practice_attempts a ON a.id=e.attempt_id AND a.session_id=e.session_id
        WHERE e.event_type='attempt_submitted' AND e.occurred_at<a.created_at
    """).collect()]

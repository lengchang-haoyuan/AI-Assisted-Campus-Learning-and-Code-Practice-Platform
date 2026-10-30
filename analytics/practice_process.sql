-- @view practice_scope_sessions
SELECT * FROM v_practice_sessions
WHERE owner_user_id IN (SELECT owner_user_id FROM scope)
 AND created_at>=TIMESTAMP '{start_utc}' AND created_at<TIMESTAMP '{end_utc}'
 AND created_at<TIMESTAMP '{cutoff}'

-- @view practice_event_facts
SELECT e.*,s.owner_user_id,s.project_id
FROM v_practice_events e JOIN practice_scope_sessions s ON e.session_id=s.id
WHERE e.occurred_at>=TIMESTAMP '{start_utc}' AND e.occurred_at<TIMESTAMP '{end_utc}'
 AND e.occurred_at<TIMESTAMP '{cutoff}'

-- @view practice_latest_reviews
SELECT * FROM (
 SELECT e.*,row_number() OVER(PARTITION BY e.session_id,e.attempt_id ORDER BY e.revision DESC,e.occurred_at DESC,e.id DESC) rn
 FROM v_practice_events e JOIN v_practice_attempts a ON a.id=e.attempt_id AND a.session_id=e.session_id
 WHERE e.event_type='review_finished' AND e.occurred_at>=TIMESTAMP '{start_utc}'
 AND e.occurred_at<TIMESTAMP '{end_utc}' AND e.occurred_at<TIMESTAMP '{cutoff}'
 AND e.operation_id=a.bound_operation_id AND e.ai_request_id=a.bound_ai_request_id
) q WHERE rn=1

-- @view practice_advice_facts
SELECT e.session_id,e.attempt_id,a.attempt_no,e.operation_id,e.ai_request_id,r.id review_event_id,
 e.id issue_event_id,e.criterion_id,e.issue_type,e.prompt_version,'ai_report' source
FROM practice_latest_reviews r JOIN v_practice_events e
 ON e.session_id=r.session_id AND e.attempt_id=r.attempt_id AND e.operation_id=r.operation_id
 AND e.ai_request_id=r.ai_request_id AND e.event_type='criterion_issue'
JOIN v_practice_attempts a ON a.id=e.attempt_id
JOIN practice_scope_sessions s ON s.id=e.session_id
WHERE e.occurred_at>=TIMESTAMP '{start_utc}' AND e.occurred_at<TIMESTAMP '{end_utc}'
 AND e.occurred_at<TIMESTAMP '{cutoff}'

-- @view practice_session_facts
WITH attempts AS (
 SELECT *,row_number() OVER(PARTITION BY session_id ORDER BY attempt_no DESC,id DESC) rn
 FROM v_practice_attempts
), totals AS (
 SELECT session_id,count(*) attempt_count FROM v_practice_attempts GROUP BY session_id
)
SELECT s.id session_id,s.owner_user_id,s.project_id,s.template_id,s.template_version,s.context_version,
 s.revision,s.current_step_key,s.status,s.created_at,coalesce(t.attempt_count,0) attempt_count,
 a.id latest_attempt_id,a.attempt_no latest_attempt_no,a.bound_operation_id latest_operation_id,
 a.bound_ai_request_id latest_ai_request_id,coalesce(a.personal_reviewed,0) personal_reviewed,
 a.self_statement,coalesce(a.output_comparison,'unknown') output_comparison,a.teacher_confirmation
FROM practice_scope_sessions s LEFT JOIN totals t ON t.session_id=s.id
LEFT JOIN attempts a ON a.session_id=s.id AND a.rn=1

-- @view ads_practice_events
SELECT session_id,event_type,count(*) event_count
FROM practice_event_facts GROUP BY session_id,event_type

-- @view ads_practice_summary
WITH sessions AS (
 SELECT sc.owner_user_id,count(s.session_id) session_count,coalesce(sum(s.attempt_count),0) attempt_count,
 sum(CASE WHEN s.session_id IS NOT NULL AND s.attempt_count=0 THEN 1 ELSE 0 END) no_submission_count,
 CASE WHEN count(s.teacher_confirmation)=0 THEN NULL
      ELSE sum(CASE WHEN s.teacher_confirmation=1 THEN 1 ELSE 0 END) END teacher_confirmation_count
 FROM scope sc LEFT JOIN practice_session_facts s ON s.owner_user_id=sc.owner_user_id GROUP BY sc.owner_user_id
), events AS (
 SELECT sc.owner_user_id,
 sum(CASE WHEN e.event_type='attempt_submitted' THEN 1 ELSE 0 END) submission_event_count,
 sum(CASE WHEN e.event_type='session_completed' THEN 1 ELSE 0 END) personal_end_count,
 sum(CASE WHEN e.event_type IN ('session_started','guidance_requested','review_started') THEN 1 ELSE 0 END) request_count,
 sum(CASE WHEN e.event_type='session_cancelled' THEN 1 ELSE 0 END) cancel_count,
 sum(CASE WHEN e.event_type='session_resumed' THEN 1 ELSE 0 END) resume_count
 FROM scope sc LEFT JOIN practice_event_facts e ON e.owner_user_id=sc.owner_user_id GROUP BY sc.owner_user_id
)
SELECT s.*,e.submission_event_count,e.personal_end_count,e.request_count,e.cancel_count,e.resume_count
FROM sessions s JOIN events e ON s.owner_user_id=e.owner_user_id

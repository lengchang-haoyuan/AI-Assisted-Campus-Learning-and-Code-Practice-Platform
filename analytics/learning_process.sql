-- @view trusted_records
SELECT f.learning_record_id, f.id feedback_id, f.submission_id, f.version_number
FROM v_feedback f JOIN v_submission_versions v
 ON f.submission_id=v.submission_id AND f.version_number=v.version_number
JOIN v_submissions s ON s.id=f.submission_id AND s.class_id=f.class_id
JOIN v_class_memberships sm ON sm.id=s.student_membership_id AND sm.class_id=s.class_id
JOIN v_campus_memberships cp ON cp.id=sm.campus_membership_id
JOIN v_class_memberships tm ON tm.id=f.teacher_membership_id AND tm.class_id=s.class_id AND tm.member_role='teacher'
JOIN v_learning_records r ON r.id=f.learning_record_id AND r.user_id=cp.user_id
WHERE f.decision='accept' AND v.status='accepted' AND f.created_at<TIMESTAMP '{cutoff}'

-- @view record_facts
SELECT r.*, to_date(from_utc_timestamp(r.occurred_at,'Asia/Shanghai')) metric_date,
 CASE WHEN tr.learning_record_id IS NOT NULL THEN 'trusted_teaching'
      WHEN claim.learning_record_id IS NOT NULL THEN 'unverified_claim' ELSE 'ordinary' END source_kind,
 tr.feedback_id, tr.submission_id, tr.version_number
FROM v_learning_records r LEFT JOIN trusted_records tr ON r.id=tr.learning_record_id
LEFT JOIN (SELECT DISTINCT learning_record_id FROM v_source_claim_projection
 WHERE source_claim IS NOT NULL OR submission_id_claim IS NOT NULL OR version_number_claim IS NOT NULL) claim ON r.id=claim.learning_record_id
WHERE r.user_id IN (SELECT owner_user_id FROM scope)
 AND r.occurred_at>=TIMESTAMP '{start_utc}' AND r.occurred_at<TIMESTAMP '{end_utc}' AND r.occurred_at<TIMESTAMP '{cutoff}'

-- @view task_facts
SELECT t.*, scheduled_date metric_date, CASE WHEN scheduled_date<to_date(from_utc_timestamp(TIMESTAMP '{cutoff}','Asia/Shanghai'))
       AND status IN ('pending','in_progress') THEN 1 ELSE 0 END overdue_unfinished
FROM v_daily_tasks t WHERE user_id IN (SELECT owner_user_id FROM scope)
 AND scheduled_date BETWEEN DATE '{first}' AND DATE '{last}'

-- @view cohort_facts
WITH chain AS (
 SELECT submission_id, count(*) version_count, min(CASE WHEN version_number=1 THEN submitted_at END) first_at
 FROM v_submission_versions WHERE submitted_at<TIMESTAMP '{cutoff}' GROUP BY submission_id
), first_feedback AS (
 SELECT f.*, row_number() OVER(PARTITION BY submission_id ORDER BY created_at,id) rn
 FROM v_feedback f WHERE created_at<TIMESTAMP '{cutoff}'
), missing_links AS (
 SELECT submission_id, sum(CASE WHEN decision='accept' AND learning_record_id IS NULL THEN 1 ELSE 0 END) missing_links,
 max(CASE WHEN decision='return' THEN 1 ELSE 0 END) returned_ever
 FROM v_feedback WHERE created_at<TIMESTAMP '{cutoff}' GROUP BY submission_id
)
SELECT s.id submission_id, cp.user_id, to_date(from_utc_timestamp(c.first_at,'Asia/Shanghai')) metric_date,
 s.latest_version_number, lv.id latest_version_id, c.version_count-1 revision_attempts,
 CASE WHEN c.version_count>1 THEN 1 ELSE 0 END revised,
 CASE WHEN lf.decision='accept' AND lv.status='accepted' THEN 1 ELSE 0 END confirmed,
 CASE WHEN lv.status='submitted' THEN 1 ELSE 0 END pending_latest,
 coalesce(ml.returned_ever,0) returned_ever, coalesce(ml.missing_links,0) missing_teaching_record_links,
 ff.id first_feedback_id, ff.version_number first_feedback_version,
 cast(timestampdiff(MICROSECOND,fv.submitted_at,ff.created_at) AS DECIMAL(30,12))/60000000 first_wait_minutes
FROM v_submissions s JOIN chain c ON c.submission_id=s.id
JOIN v_class_memberships cm ON cm.id=s.student_membership_id
JOIN v_campus_memberships cp ON cp.id=cm.campus_membership_id
JOIN v_submission_versions lv ON lv.submission_id=s.id AND lv.version_number=s.latest_version_number
LEFT JOIN v_feedback lf ON lf.submission_id=s.id AND lf.version_number=s.latest_version_number AND lf.created_at<TIMESTAMP '{cutoff}'
LEFT JOIN first_feedback ff ON ff.submission_id=s.id AND ff.rn=1
LEFT JOIN v_submission_versions fv ON fv.submission_id=ff.submission_id AND fv.version_number=ff.version_number
LEFT JOIN missing_links ml ON ml.submission_id=s.id
WHERE cp.user_id IN (SELECT owner_user_id FROM scope)
 AND c.first_at>=TIMESTAMP '{start_utc}' AND c.first_at<TIMESTAMP '{end_utc}' AND c.first_at<TIMESTAMP '{cutoff}'

-- @view ads_records
SELECT sc.owner_user_id,
 count(r.id) valid_unique_rows, coalesce(sum(r.duration_minutes),0) known_minutes,
 count(r.duration_minutes) known_duration_count,
 sum(CASE WHEN r.id IS NOT NULL AND r.duration_minutes IS NULL THEN 1 ELSE 0 END) missing_duration_count,
 sum(CASE WHEN r.duration_minutes=0 THEN 1 ELSE 0 END) known_zero_count, count(DISTINCT metric_date) active_days,
 sum(CASE WHEN source_kind='trusted_teaching' THEN 1 ELSE 0 END) trusted_teaching_count,
 sum(CASE WHEN source_kind='unverified_claim' THEN 1 ELSE 0 END) unverified_claim_count,
 sum(CASE WHEN source_kind='ordinary' THEN 1 ELSE 0 END) ordinary_count
FROM scope sc LEFT JOIN record_facts r ON r.user_id=sc.owner_user_id GROUP BY sc.owner_user_id

-- @view ads_tasks
WITH a AS (
 SELECT sc.owner_user_id,count(t.id) total,
 sum(CASE WHEN status='completed' THEN 1 ELSE 0 END) completed,
 sum(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) cancelled,coalesce(sum(overdue_unfinished),0) overdue_unfinished
 FROM scope sc LEFT JOIN task_facts t ON t.user_id=sc.owner_user_id GROUP BY sc.owner_user_id
)
SELECT *, cast(cast(completed AS DECIMAL(30,10))*100/nullif(total,0) AS DECIMAL(30,6)) percent,
 CASE WHEN total>0 AND completed=total THEN true ELSE false END eligible_to_complete_plan FROM a

-- @view ads_topic
WITH a AS (
 SELECT sc.owner_user_id,count(c.submission_id) cohort_count,coalesce(sum(revised),0) revised_count,
 coalesce(sum(confirmed),0) confirmed_count,coalesce(sum(returned_ever),0) returned_ever_count,
 sum(CASE WHEN revised=0 AND confirmed=1 THEN 1 ELSE 0 END) first_pass_confirmed_count,
 sum(CASE WHEN revised=1 AND confirmed=1 THEN 1 ELSE 0 END) revised_confirmed_count,
 coalesce(sum(pending_latest),0) pending_latest_count, coalesce(sum(revision_attempts),0) revision_attempts,
 count(first_wait_minutes) first_review_covered, coalesce(sum(first_wait_minutes),0) first_review_wait_sum_minutes,
 cast(avg(first_wait_minutes) AS DECIMAL(30,6)) first_review_wait_mean_minutes,
 sum(CASE WHEN first_wait_minutes>=0 AND first_wait_minutes<60 THEN 1 ELSE 0 END) bucket_0,
 sum(CASE WHEN first_wait_minutes>=60 AND first_wait_minutes<240 THEN 1 ELSE 0 END) bucket_1,
 sum(CASE WHEN first_wait_minutes>=240 AND first_wait_minutes<1440 THEN 1 ELSE 0 END) bucket_2,
 sum(CASE WHEN first_wait_minutes>=1440 THEN 1 ELSE 0 END) bucket_3,
 coalesce(sum(missing_teaching_record_links),0) missing_teaching_record_links
 FROM scope sc LEFT JOIN cohort_facts c ON c.user_id=sc.owner_user_id GROUP BY sc.owner_user_id
)
SELECT *, cast(cast(revised_count AS DECIMAL(30,10))*100/nullif(cohort_count,0) AS DECIMAL(30,6)) revised_percent,
 cast(cast(confirmed_count AS DECIMAL(30,10))*100/nullif(cohort_count,0) AS DECIMAL(30,6)) confirmation_percent,
 cast(cast(revised_confirmed_count AS DECIMAL(30,10))*100/nullif(revised_count,0) AS DECIMAL(30,6)) revised_confirmation_percent FROM a

-- @view ads_daily
WITH pieces AS (
 SELECT user_id,metric_date,count(*) records,coalesce(sum(duration_minutes),0) known_minutes,
 count(duration_minutes) known_duration_count,sum(CASE WHEN duration_minutes IS NULL THEN 1 ELSE 0 END) missing_duration_count,
 0 tasks,0 completed,0 cancelled,0 overdue_unfinished,0 cohort,0 revised,0 confirmed
 FROM record_facts GROUP BY user_id,metric_date
 UNION ALL
 SELECT user_id,metric_date,0,0,0,0,count(*),sum(CASE WHEN status='completed' THEN 1 ELSE 0 END),
 sum(CASE WHEN status='cancelled' THEN 1 ELSE 0 END),sum(overdue_unfinished),0,0,0 FROM task_facts GROUP BY user_id,metric_date
 UNION ALL
 SELECT user_id,metric_date,0,0,0,0,0,0,0,0,count(*),sum(revised),sum(confirmed) FROM cohort_facts GROUP BY user_id,metric_date
)
SELECT user_id owner_user_id,cast(metric_date as string) date,sum(records) records,sum(known_minutes) known_minutes,
 sum(known_duration_count) known_duration_count,sum(missing_duration_count) missing_duration_count,
 sum(tasks) tasks,sum(completed) completed,sum(cancelled) cancelled,sum(overdue_unfinished) overdue_unfinished,
 sum(cohort) cohort,sum(revised) revised,sum(confirmed) confirmed FROM pieces GROUP BY user_id,metric_date

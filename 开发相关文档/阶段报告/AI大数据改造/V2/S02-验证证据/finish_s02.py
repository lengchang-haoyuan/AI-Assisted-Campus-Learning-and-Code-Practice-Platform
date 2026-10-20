"""仅补完首轮检查中断后的只读核对与预期拒绝请求；不重建或灌入。"""
import asyncio
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import os
from pathlib import Path
from secrets import token_urlsafe

import httpx
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from app.core.config import get_settings, get_security_settings
from app.core.database import get_engine, get_session_factory
from app.core.security import SecurityService
from app.main import create_app
from app.models.base import Base
from app.models.user import User
from app.models.ai import AIRequest
from app.models.learning import DailyTask, LearningRecord
from app.models.submission import Feedback, Submission, SubmissionVersion
from app.models.teaching import ClassMembership
from app.models.campus import CampusMembership

OUT = Path(r'C:\Users\Administrator\AppData\Local\Temp\ScholarHub-S02-20261020')
DATABASE = 'scholarhub_l4_s02_20261020'
objects = json.loads((OUT/'objects-partial.json').read_text(encoding='utf-8'))
checks = json.loads((OUT/'checks-partial.json').read_text(encoding='utf-8'))
events = json.loads((OUT/'api-evidence-partial.json').read_text(encoding='utf-8'))
original_url = make_url(get_settings().database_url)
assert original_url.host in {'127.0.0.1','localhost','::1'} and original_url.database != DATABASE
assert objects['database'] == DATABASE and len(objects['accounts']) == 4 and len(objects['task_ids']) == 204
os.environ['DATABASE_URL'] = original_url.set(database=DATABASE).render_as_string(hide_password=False)
os.environ['JWT_SECRET'] = token_urlsafe(48)
get_settings.cache_clear(); get_security_settings.cache_clear(); get_engine.cache_clear(); get_session_factory.cache_clear()

def save(name, data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=lambda x:x.isoformat() if hasattr(x,'isoformat') else str(x))+'\n',encoding='utf-8')

def check(name,value,expected=True):
    assert value==expected,f'{name}: expected {expected!r}, got {value!r}'
    checks.append({'check':name,'actual':value,'expected':expected,'status':'passed'})

uid=objects['accounts']['student']['id']; bid=objects['accounts']['boundary_student']['id']
tz=timezone(timedelta(hours=8)); today=datetime.now(tz).date(); yesterday=today-timedelta(days=1)
app=create_app()
with get_session_factory()() as session:
    check('resume_same_database',session.scalar(text('SELECT DATABASE()')),DATABASE)
    users=list(session.scalars(select(User)))
    check('resume_same_four_marked_accounts',len(users),4)
    assert all(u.username.startswith(objects['run_marker']+'_') for u in users)
    security=SecurityService(get_security_settings())
    headers={}
    for label,user_id in [('student',uid),('boundary',bid)]:
        user=session.get(User,user_id)
        headers[label]={'Authorization':'Bearer '+security.create_access_token(user.id,user.auth_version).value}
    # Tokens are only in memory and signed by this process's temporary secret.
    result_event=next(e for e in events if e['method']=='POST' and e['path']=='/agents/project-analysis')
    objects['ai_request_id']=result_event['response']['request_id']
    request=session.get(AIRequest,objects['ai_request_id'])
    check('fake_agent_response_completed',result_event['response']['status'],'completed')
    check('fake_provider_saved',request.provider,'fake')
    check('fake_agent_db_status_completed',str(request.status),'completed')
    check('exactly_one_auxiliary_AIRequest',session.scalar(select(func.count()).select_from(AIRequest)),1)
    records=list(session.scalars(select(LearningRecord).where(LearningRecord.user_id==uid).order_by(LearningRecord.id)))
    feedbacks=list(session.scalars(select(Feedback).where(Feedback.decision=='accept').order_by(Feedback.id)))
    trusted=[]
    for fb in feedbacks:
        lr=session.get(LearningRecord,fb.learning_record_id); sub=session.get(Submission,fb.submission_id)
        version=session.scalar(select(SubmissionVersion).where(SubmissionVersion.submission_id==sub.id,SubmissionVersion.version_number==fb.version_number))
        sm=session.get(ClassMembership,sub.student_membership_id); cm=session.get(CampusMembership,sm.campus_membership_id)
        tm=session.get(ClassMembership,fb.teacher_membership_id)
        check(f'feedback_{fb.id}_same_student',lr.user_id,cm.user_id)
        check(f'feedback_{fb.id}_same_class_and_teacher',[fb.class_id,tm.class_id,str(tm.member_role)],[sub.class_id,sub.class_id,'teacher'])
        check(f'feedback_{fb.id}_version_accepted',str(version.status),'accepted')
        check(f'feedback_{fb.id}_duration_NULL',lr.duration_minutes,None)
        check(f'feedback_{fb.id}_task_not_fabricated',lr.task_id,None)
        trusted.append({'feedback_id':fb.id,'submission_id':sub.id,'version_number':fb.version_number,'learning_record_id':lr.id,'user_id':lr.user_id,'teacher_membership_id':fb.teacher_membership_id,'class_id':sub.class_id})
    main_tasks=list(session.scalars(select(DailyTask).where(DailyTask.user_id==uid)))
    edge_tasks=list(session.scalars(select(DailyTask).where(DailyTask.plan_id==objects['boundary_plan_id'])))
    known=[r.duration_minutes for r in records if r.duration_minutes is not None]
    days=sorted({r.occurred_at.astimezone(tz).date().isoformat() for r in records})
    check('primary_records_minutes_known_missing',[len(records),sum(known),len(known),len(records)-len(known)],[4,75,2,2])
    check('primary_active_days',len(days),2)
    check('primary_tasks_completed_total_cancelled_overdue',[sum(str(t.status)=='completed' for t in main_tasks),len(main_tasks),sum(str(t.status)=='cancelled' for t in main_tasks),sum(t.scheduled_date<today and str(t.status) in ['pending','in_progress'] for t in main_tasks)],[2,4,1,1])
    check('boundary_199_of_200',[sum(str(t.status)=='completed' for t in edge_tasks),len(edge_tasks)],[199,200])
    check('boundary_exact_percent',str((Decimal(199)*100/Decimal(200)).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)),'99.500000')
    check('scheduled_DATE_unshifted',session.get(DailyTask,objects['task_ids'][3]).scheduled_date.isoformat(),yesterday.isoformat())
    check('record_timestamps_UTC',all(r.occurred_at.utcoffset()==timedelta(0) for r in records))
    count_models=[Submission,SubmissionVersion,Feedback,LearningRecord,DailyTask]
    counts={m.__tablename__:session.scalar(select(func.count()).select_from(m)) for m in count_models}
    check('cohort_version_feedback_record_task_counts',[counts[x] for x in ['submissions','submission_versions','feedback','learning_records','daily_tasks']],[3,4,3,4,204])
    check('rolled_back_record_ids_absent',all(session.get(LearningRecord,i) is None for i in objects['rolled_back_record_ids']))
    waits=[]
    for sid in objects['submissions']:
        fb=session.scalar(select(Feedback).where(Feedback.submission_id==sid).order_by(Feedback.created_at).limit(1))
        if fb:
            ver=session.scalar(select(SubmissionVersion).where(SubmissionVersion.submission_id==sid,SubmissionVersion.version_number==fb.version_number))
            seconds=Decimal(str((fb.created_at-ver.submitted_at).total_seconds()));assert seconds>=0
            waits.append({'submission_id':sid,'submitted_at':ver.submitted_at,'feedback_at':fb.created_at,'seconds':str(seconds),'minutes':str(seconds/60)})
    retained_counts={name:int(session.scalar(select(func.count()).select_from(table))) for name,table in Base.metadata.tables.items()}
    projected_records=[{'id':r.id,'user_id':r.user_id,'duration_minutes':r.duration_minutes,'occurred_at':r.occurred_at,'task_id':r.task_id,'project_id':r.project_id,'record_type':str(r.record_type)} for r in records]

async def rejected_checks():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url='http://s02-isolated') as client:
        for lr in trusted:
            path=f"/learning/records/{lr['learning_record_id']}"
            response=await client.put('/api/v1'+path,headers=headers['student'],json={'duration_minutes':60})
            events.append({'sequence':len(events)+1,'time':datetime.now(UTC).isoformat(),'method':'PUT','path':path,'request_body':{'duration_minutes':60},'status_code':response.status_code,'response':response.json(),'resume_auth':'existing SecurityService; process-only token'})
            check(f"teaching_record_{lr['learning_record_id']}_edit_denied",response.status_code,409)
        path=f"/agents/results/{objects['ai_request_id']}"
        response=await client.get('/api/v1'+path,headers=headers['boundary'])
        events.append({'sequence':len(events)+1,'time':datetime.now(UTC).isoformat(),'method':'GET','path':path,'status_code':response.status_code,'response':response.json(),'resume_auth':'existing SecurityService; process-only token'})
        check('auxiliary_AIResult_other_user_denied',response.status_code,404)
asyncio.run(rejected_checks())

engine=create_engine(original_url,hide_parameters=True)
try:
    with engine.connect() as connection:
        connection.exec_driver_sql('SET SESSION TRANSACTION READ ONLY');connection.commit()
        assert connection.scalar(text('SELECT @@session.transaction_read_only'))==1
        after={name:int(connection.scalar(select(func.count()).select_from(table))) for name,table in Base.metadata.tables.items()}
        connection.rollback()
finally:engine.dispose()
before=json.loads((OUT/'business-counts-before.json').read_text(encoding='utf-8'))
check('business_aggregate_counts_unchanged',after,before)
summary={'dataset_kind':'controlled','owner_user_id':uid,'source_cutoff':datetime.now(UTC).isoformat(),'period_start':yesterday.isoformat(),'period_end':today.isoformat(),'known_minutes':75,'record_count':4,'known_duration_count':2,'missing_duration_count':2,'known_zero_count':0,'active_days':days,'records':projected_records,'trusted_teaching_records':trusted,'primary_tasks':{'completed':2,'total':4,'cancelled':1,'overdue_unfinished':1,'percent':'50.000000'},'cohort':{'total':3,'revised':1,'confirmed':2,'first_pass':1,'revised_confirmed':1,'pending':1,'revised_percent':'33.333333','confirmation_percent':'66.666667','first_feedback_coverage':'2/3','first_feedback_waits':waits},'boundary_other_owner':{'user_id':bid,'completed':199,'total':200,'percent':'99.500000','display_progress':100,'completion_rejected':True,'terminal_plan_status':'cancelled'},'empty_tasks':{'sample_count':0,'percent':None,'plan_completion_rejected':True},'fake_ai_requests':1,'real_model_calls':0,'retained_for_S03':True,'interpretation':'真实API产生的受控样例，不是自然长期用户数据；不是代码快照、平台执行或自动判题。S02观测截止非S03一致性快照批次。'}
save('business-counts-after.json',after);save('independent-expected-and-observed.json',summary)
save('objects.json',objects);save('isolated-final-counts.json',retained_counts);save('checks.json',checks);save('api-evidence.json',events)
save('retention-and-cleanup.json',{'status':'retained_by_explicit_user_authorization','database':DATABASE,'run_marker':objects['run_marker'],'no_database_dropped':True,'no_existing_database_cleared':True,'failed_operations_left_no_rows':True,'rollback_probe_record_ids_absent':objects['rolled_back_record_ids'],'successful_sources_retained_for_S03':True,'resume_created_no_accounts_or_source_rows':True,'resume_auth':'existing SecurityService, temporary JWT secret in process, no stored credentials or account changes','environment_file_changed':False})
result={'status':'passed_after_harness_status_assertion_corrections','database':DATABASE,'run_marker':objects['run_marker'],'api_requests':len(events),'checks':len(checks),'fake_provider_calls':1,'real_model_calls':0,'source_code_changes':0,'retained_for_S03':True,'first_run_exit_code':1,'first_resume_exit_code':1,'final_resume_exit_code':0,'harness_corrections':['Agent response status completed, not succeeded','other-owner Agent result returns 404, not 403'],'resume_wrote_source_rows':False}
save('api-verification-result.json',result);print(json.dumps(result,ensure_ascii=False))

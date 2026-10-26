"""S06 explicitly approved isolated publication; max3 batches/8 daily, no models."""
import asyncio
import contextvars
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from secrets import token_urlsafe
from unittest.mock import patch
import httpx
from sqlalchemy import event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app.core.config import get_settings, get_security_settings
from app.core.database import get_engine, get_session_factory

root=Path.cwd().parent
v2=root/'开发相关文档/阶段报告/AI大数据改造/V2'
evidence=v2/'S06-验证证据'
url=make_url(get_settings().database_url)
assert url.host in ('localhost','127.0.0.1') and (url.port or 3306)==3306
os.environ['DATABASE_URL']=url.set(database='scholarhub_l4_s02_20261020').render_as_string(hide_password=False)
os.environ['JWT_SECRET']=token_urlsafe(48)
for factory in (get_settings,get_security_settings,get_engine,get_session_factory):factory.cache_clear()
from app.models import Base
from app.models.user import User
from app.models.analytics import AnalyticsBatch, AnalyticsDailyMetric
from app.core.security import SecurityService
from app.main import create_app
from app.repositories.analytics import AnalyticsRepository
from app.services.analytics import AnalyticsService
from app.services.analytics_artifacts import load_publication
from app.schemas.analytics import PublicationPayload
from app.core.exceptions import ConflictError
from app.ai.client import AIClient

def save(name,value):
    (evidence/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
engine=get_engine()
app=create_app()
method=contextvars.ContextVar('s06_method',default='')
observation={'GET_DML':[],'GET_publish_calls':0,'GET_process_calls':0,'model_calls':0}
@app.middleware('http')
async def monitor(request, call_next):
    token=method.set(request.method)
    try:return await call_next(request)
    finally:method.reset(token)
@event.listens_for(engine,'before_cursor_execute')
def track(conn,cursor,statement,parameters,context,many):
    verb=statement.strip().split()[0].upper()
    if method.get()=='GET' and verb in ('INSERT','UPDATE','DELETE','REPLACE','CREATE','ALTER','DROP'):
        observation['GET_DML'].append(verb)
def forbidden_model(*args,**kwargs):
    observation['model_calls']+=1
    raise AssertionError('S06 forbids models')
AIClient.complete=forbidden_model
headers={}
with Session(engine) as session:
    baseline={name:session.scalar(select(func.count()).select_from(table)) for name,table in Base.metadata.tables.items()}
    assert baseline['analytics_batches']==11 and baseline['analytics_daily_metrics']==15
    for uid in (3,4):
        user=session.get(User,uid)
        assert user.username.startswith('s02_3e08a80a_')
        headers[uid]={'Authorization':'Bearer '+SecurityService(get_security_settings()).create_access_token(uid,user.auth_version).value}
events=[]
async def get(path,owner=3,expected=200):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://s06-isolated') as client:
        started=time.perf_counter()
        response=await client.get('/api/v1/'+path,headers=headers.get(owner,{}))
        data=response.json()
        events.append({'method':'GET','path':path,'owner':owner,'status':response.status_code,'seconds':time.perf_counter()-started,'body':data})
        assert response.status_code==expected,(path,response.status_code,expected)
        return data

published={}
for key,job in [('primary','s06-e2e-main'),('boundary','s06-e2e-boundary')]:
    started=time.perf_counter()
    result=subprocess.run([sys.executable,'-B','-X','utf8','-m','scripts.publish_analytics','--database','scholarhub_l4_s02_20261020','--job-id',job],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
    save('publish-'+key+'-cli.json',{'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'seconds':time.perf_counter()-started})
    value=json.loads(result.stdout.strip().splitlines()[-1])
    published[key]=value
    p=load_publication(job)
    with Session(engine) as session:
        replay=AnalyticsService(AnalyticsRepository(session)).publish(p)
        assert replay==(value['batch_id'],True)
    value['replay_same_batch']=True
    value['details']=asyncio.run(get('offline-analytics/batches/'+value['batch_id'],p.owner_user_id))
    assert value['details']['records_summary']==p.records_summary.model_dump(mode='json')
    assert value['details']['tasks_summary']==p.tasks_summary.model_dump(mode='json')
    assert value['details']['topic_summary']==p.topic_summary.model_dump(mode='json')
    assert len(value['details']['daily'])==len(p.daily)
primary=published['primary']['batch_id']
boundary=published['boundary']['batch_id']
assert published['primary']['details']['records_summary']['known_minutes']==90
assert published['boundary']['details']['tasks_summary']['completion_rate']['percent']=='99.500000'

# One marked third batch, internal failure fixture only; never a formal Spark job.
fault=load_publication('s06-e2e-main').model_copy(deep=True)
fault.job_id='s06-transaction-recovery'
fault.quality={**fault.quality,'transaction_fixture':True}
fault_id=[]
def interrupt(identity):
    fault_id.append(identity)
    asyncio.run(get('offline-analytics/batches/'+identity,3,404))
    old=asyncio.run(get('offline-analytics/batches/'+primary))
    assert old['records_summary']['known_minutes']==90
    raise RuntimeError('S06 injected after first daily row before completed')
with Session(engine) as session:
    try:AnalyticsService(AnalyticsRepository(session)).publish(fault,before_complete=interrupt)
    except RuntimeError as error:assert str(error).startswith('S06 injected')
    else:raise AssertionError('failure was not injected')
with Session(engine) as session:
    row=session.get(AnalyticsBatch,fault_id[0])
    assert row.state=='failed'
    failed_rows=session.scalar(select(func.count()).select_from(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id==fault_id[0]))
    assert failed_rows==0
asyncio.run(get('offline-analytics/batches/'+fault_id[0],3,404))
with Session(engine) as session:
    identity,replayed=AnalyticsService(AnalyticsRepository(session)).publish(fault)
    assert identity==fault_id[0] and replayed is False
with Session(engine) as session:
    assert AnalyticsService(AnalyticsRepository(session)).publish(fault)==(identity,True)
changed=fault.model_copy(deep=True)
changed.records_summary.known_minutes+=1
with Session(engine) as session:
    try:AnalyticsService(AnalyticsRepository(session)).publish(changed)
    except ConflictError:pass
    else:raise AssertionError('completed changed content accepted')
with Session(engine) as session:
    row=session.get(AnalyticsBatch,identity)
    assert row.state=='completed' and row.input_counts['records_summary']['known_minutes']==90

unsupported=load_publication('s06-e2e-main').model_dump(mode='json')
unsupported['metric_version']='learning-process-9.0'
try:PublicationPayload.model_validate(unsupported)
except ValidationError:pass
else:raise AssertionError('unknown version accepted')

empty='45c55b05-ff63-4cc6-b6ca-734146054710'
asyncio.run(get('offline-analytics/batches/'+primary,4,404))
asyncio.run(get('offline-analytics/batches/'+boundary,3,404))
asyncio.run(get('offline-analytics/batches/'+empty,3))
asyncio.run(get('offline-analytics/batches/'+empty,4,404))
asyncio.run(get('offline-analytics/batches/'+empty,None,401))
for path in ['offline-analytics/batches?dataset_kind=controlled',
             'offline-analytics/batches?period_start=2025-01-01&period_end=2025-01-02',
             'offline-analytics/batches?page_size=51',
             'offline-analytics/batches?owner_user_id=4']:
    asyncio.run(get(path,3,422 if '51' in path or 'owner_' in path else 200))
with Session(engine) as session:
    final={name:session.scalar(select(func.count()).select_from(table)) for name,table in Base.metadata.tables.items()}
assert final['analytics_batches']-baseline['analytics_batches']==3
assert final['analytics_daily_metrics']-baseline['analytics_daily_metrics']==5
assert all(final[name]==count for name,count in baseline.items() if name not in ('analytics_batches','analytics_daily_metrics'))
assert observation['GET_DML']==[] and observation['model_calls']==0
save('publication-verification.json',{'status':'passed','primary':primary,'boundary':boundary,'fault_fixture':identity,
    'fault_before_complete_status':'prepared invisible','failed_daily_rows':failed_rows,
    'retry_same_batch':True,'completed_changed_content_rejected':True,'unknown_version_rejected':True,
    'all_unrelated_table_counts_unchanged':True,'before_counts':baseline,'after_counts':final,
    'observation':observation,'API_mode':'real ASGI application/authentication + isolated MySQL, no response mocks',
    'API_events':events})
(v2/'S06-发布结果.json').write_text(json.dumps(published,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
engine.dispose()
print(json.dumps({'status':'passed','new_batches':3,'new_daily_rows':5,'model_calls':0,'primary':primary,'boundary':boundary}))

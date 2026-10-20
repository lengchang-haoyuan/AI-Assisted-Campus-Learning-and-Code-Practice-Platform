import asyncio,copy,json,os,sys,subprocess
from pathlib import Path
from datetime import UTC,datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from unittest.mock import patch
from secrets import token_urlsafe
import httpx
from sqlalchemy import select,func,event,inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import get_settings,get_security_settings
from app.core.database import get_engine,get_session_factory,create_database_engine
from app.core.security import SecurityService
from app.core.exceptions import ConflictError,InputError
from app.models.analytics import AnalyticsBatch,AnalyticsDailyMetric
from app.models.user import User
from app.repositories.analytics import AnalyticsRepository
from app.services.analytics import AnalyticsService,batch_values
from app.services.analytics_artifacts import load_publication
from app.schemas.analytics import PublicationPayload
ROOT=Path.cwd().parent;V2=ROOT/'开发相关文档/阶段报告/AI大数据改造/V2';E=V2/'S05-验证证据';TMP=Path(os.environ['TEMP'])/'ScholarHub-S05-20261020'
DB='scholarhub_l4_s02_20261020';configured=make_url(get_settings().database_url)
assert configured.database!=DB and configured.host in ('127.0.0.1','localhost')
os.environ['DATABASE_URL']=configured.set(database=DB).render_as_string(hide_password=False)
os.environ['JWT_SECRET']=token_urlsafe(48)
get_settings.cache_clear();get_security_settings.cache_clear();get_engine.cache_clear();get_session_factory.cache_clear()
from app.main import create_app
app=create_app();engine=get_engine();checks=[];api_events=[];writes_during_get=[];monitor={'on':False}
def save(name,obj):(E/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.isoformat() if hasattr(x,'isoformat') else str(x))+'\n',encoding='utf8')
def check(name,actual,expected=True):
 checks.append({'check':name,'actual':actual,'expected':expected,'passed':actual==expected})
 if actual!=expected:raise AssertionError(name)
@event.listens_for(engine,'before_cursor_execute')
def track(conn,cursor,statement,parameters,context,executemany):
 verb=statement.strip().split()[0].upper()
 if monitor['on'] and verb not in ('SELECT','SHOW','DESCRIBE','EXPLAIN','SET'):
  writes_during_get.append(verb)
headers={}
with Session(engine) as s:
 for uid in (1,3,4):
  u=s.get(User,uid);assert u.username.startswith('s02_3e08a80a_')
  headers[uid]={'Authorization':'Bearer '+SecurityService(get_security_settings()).create_access_token(uid,u.auth_version).value}
 main=s.scalar(select(AnalyticsBatch).where(AnalyticsBatch.artifact_ref=='s03-owner3-restored/v2-controlled'))
 boundary=s.scalar(select(AnalyticsBatch).where(AnalyticsBatch.owner_user_id==4))
 MAIN=main.batch_id;BOUND=boundary.batch_id
 oldcounts={t:s.scalar(select(func.count()).select_from(table)) for t,table in __import__('app.models',fromlist=['Base']).Base.metadata.tables.items() if not t.startswith('analytics_')}
 check('migration_tables',len(inspect(engine).get_table_names()),36)
 check('batch_id_columns_CHAR',[str(next(c for c in inspect(engine).get_columns(t) if c['name']=='batch_id')['type']) for t in ('analytics_batches','analytics_daily_metrics')],['CHAR(36)','CHAR(36)'])
 save('source-counts-before.json',oldcounts)
async def get(path,user=3,expected=200):
 monitor['on']=True
 try:
  with patch('subprocess.Popen',side_effect=AssertionError('GET started process')) as spawn,patch('app.ai.client.AIClient.complete',side_effect=AssertionError('GET called model')) as model,patch.object(AnalyticsService,'publish',side_effect=AssertionError('GET published batch')) as publisher:
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url='http://s05-isolated') as c:
    response=await c.get('/api/v1'+path,headers=headers.get(user,{}))
   check('GET process/model/publish calls',[spawn.call_count,model.call_count,publisher.call_count],[0,0,0])
 finally:monitor['on']=False
 body=response.json()
 api_events.append({'method':'GET','path':path,'identity':user,'status':response.status_code,'response':body})
 if response.status_code!=expected:raise AssertionError((path,response.status_code,body))
 return body
p=load_publication('v2-controlled');b=load_publication('v1-boundary')
with Session(engine) as s:
 service=AnalyticsService(AnalyticsRepository(s))
 ident,replayed=service.publish(p);check('same_identity_replay',[ident,replayed],[MAIN,True])
 prior=s.get(AnalyticsBatch,MAIN);before_main={c.name:getattr(prior,c.name) for c in AnalyticsBatch.__table__.columns}
 changed=p.model_copy(deep=True);changed.records_summary.known_minutes+=1
 try:service.publish(changed)
 except ConflictError:check('completed_different_content_conflict',True)
 else:raise AssertionError('completed_overwrite')
 after=s.get(AnalyticsBatch,MAIN);check('completed_header_immutable',{c.name:getattr(after,c.name) for c in AnalyticsBatch.__table__.columns},before_main)
# Empty permission fixture is a direct isolated ORM fixture, never claimed as a Spark result.
empty=p.model_copy(deep=True);empty.job_id='s05-empty-permission-fixture';empty.dataset_id='s05-permission-fixture';empty.snapshot_id='s05-permission-empty';empty.quality['permission_fixture']=True
from app.services.analytics_artifacts import V2 as ARTIFACT_V2
zero=json.loads((ARTIFACT_V2/'S04-产物/jobs/v1-D07/ads/answers.json').read_text(encoding='utf8'))['1001']
empty.records_summary=type(p.records_summary).model_validate(zero['records']);empty.tasks_summary=type(p.tasks_summary).model_validate(zero['tasks']);empty.topic_summary=type(p.topic_summary).model_validate(zero['topic']);empty.daily=[]
with Session(engine) as s:
 EMPTY=str(uuid4());row=AnalyticsBatch(**batch_values(empty,EMPTY),state='completed',published_at=datetime.now(UTC));s.add(row);s.commit()
# Prepared row is hidden; no result rows are inserted.
prepared=p.model_copy(deep=True);prepared.job_id='s05-prepared-fixture';prepared.quality['permission_fixture']=True
with Session(engine) as s:
 PREPARED=AnalyticsRepository(s).reserve(batch_values(prepared,str(uuid4())))
async def permissions():
 first=await get('/offline-analytics/batches?dataset_kind=controlled')
 check('list_only_self',all(i['batch_id']!=BOUND for i in first['items']))
 check('prepared_hidden_in_list',all(i['batch_id']!=PREPARED for i in first['items']))
 await get('/offline-analytics/batches',user=None,expected=401)
 await get('/offline-analytics/batches/'+MAIN,user=None,expected=401)
 await get('/offline-analytics/batches/'+MAIN,user=4,expected=404)
 await get('/offline-analytics/batches/'+MAIN,user=1,expected=404)
 detail=await get('/offline-analytics/batches/'+MAIN)
 check('API_hand_ADS_values',[detail['records_summary']['known_minutes'],detail['records_summary']['missing_duration_count'],detail['tasks_summary']['completion_rate']['percent'],detail['topic_summary']['cohort_count'],detail['topic_summary']['revised_count'],detail['topic_summary']['confirmed_count']],[75,2,'50.000000',3,1,2])
 check('API_daily_source_counts',[sum(d['ordinary_count'] for d in detail['daily']),sum(d['trusted_teaching_count'] for d in detail['daily'])],[2,2])
 edge=await get('/offline-analytics/batches/'+BOUND,user=4)
 check('API_exact_199_200',edge['tasks_summary']['completion_rate']['percent'],'99.500000')
 await get('/offline-analytics/batches/'+str(uuid4()),expected=404)
 await get('/offline-analytics/batches/'+PREPARED,expected=404)
 empty_detail=await get('/offline-analytics/batches/'+EMPTY)
 check('empty_owner_NULL_and_rows',[empty_detail['daily'],empty_detail['tasks_summary']['completion_rate']['percent'],empty_detail['topic_summary']['first_review_wait_mean_minutes']],[[],None,None])
 await get('/offline-analytics/batches/'+EMPTY,user=4,expected=404)
 await get('/offline-analytics/batches/'+EMPTY,user=None,expected=401)
 for query in ('page_size=51','page=0','dataset_kind=synthetic','period_start=2026-01-01','period_start=2026-10-21&period_end=2026-10-01','period_start=2026-01-01&period_end=2026-12-01','owner_user_id=4','user_id=4'):
  await get('/offline-analytics/batches?'+query,expected=422)
 await get('/offline-analytics/batches/'+MAIN+'?period_start=2026-10-01&period_end=2026-11-01',expected=422)
 outside=await get('/offline-analytics/batches?dataset_kind=controlled&period_start=2025-01-01&period_end=2025-01-02')
 check('unmatched_window_empty',outside['items'],[])
 no_business=await get('/offline-analytics/batches')
 check('no_available_business_batch',no_business['items'],[])
 paged=await get('/offline-analytics/batches?dataset_kind=controlled&page=999')
 check('page_beyond_results_empty',paged['items'],[])
 await get('/offline-analytics/batches?dataset_kind=controlled')
 await get('/statistics/today')
 return detail
api_main=asyncio.run(permissions())
# Fault fixture clones verified metric values only to test transactions, and is explicitly labelled.
fault=p.model_copy(deep=True);fault.job_id='s05-transaction-fixture';fault.quality['transaction_fixture']=True
FAULT=None
def interrupt(batch):
 global FAULT
 FAULT=batch
 with Session(engine) as s:
  check('uncommitted_daily_not_visible',s.scalar(select(func.count()).select_from(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id==batch)),0)
 asyncio.run(get('/offline-analytics/batches/'+batch,expected=404))
 old=asyncio.run(get('/offline-analytics/batches/'+MAIN));check('old_completed_read_during_fault',old['records_summary']['known_minutes'],75)
 raise RuntimeError('injected_import_interruption')
with Session(engine) as s:
 try:AnalyticsService(AnalyticsRepository(s)).publish(fault,before_complete=interrupt)
 except RuntimeError:check('interruption_observed',True)
 else:raise AssertionError('interruption_not_triggered')
with Session(engine) as s:
 check('failed_state',s.get(AnalyticsBatch,FAULT).state,'failed')
 check('failed_no_partial_daily',s.scalar(select(func.count()).select_from(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id==FAULT)),0)
asyncio.run(get('/offline-analytics/batches/'+FAULT,expected=404))
with Session(engine) as s:
 ident,replay=AnalyticsService(AnalyticsRepository(s)).publish(fault)
 check('retry_same_failed_batch',[ident,replay],[FAULT,False])
 check('retry_exact_daily_count',s.scalar(select(func.count()).select_from(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id==FAULT)),2)
# Semantic validation failure creates an invisible failed attempt.
bad=p.model_copy(deep=True);bad.job_id='s05-validation-fixture';bad.daily[0].known_minutes+=1;bad.quality['transaction_fixture']=True
with Session(engine) as s:
 try:AnalyticsService(AnalyticsRepository(s)).publish(bad)
 except InputError:check('mismatched_totals_rejected',True)
 else:raise AssertionError('bad_totals_passed')
 INVALID=s.scalar(select(AnalyticsBatch.batch_id).where(AnalyticsBatch.artifact_ref==bad.snapshot_id+'/'+bad.job_id))
 check('validation_failed_state',s.get(AnalyticsBatch,INVALID).state,'failed')
asyncio.run(get('/offline-analytics/batches/'+INVALID,expected=404))
# Two real independent connections race on the unique logical identity.
concurrent=p.model_copy(deep=True);concurrent.job_id='s05-concurrent-fixture';concurrent.quality['transaction_fixture']=True
barrier=Barrier(2)
def worker():
 with Session(engine) as s:
  connection_id=s.connection().exec_driver_sql('SELECT CONNECTION_ID()').scalar_one();s.commit()
  barrier.wait(timeout=10)
  result=AnalyticsService(AnalyticsRepository(s)).publish(concurrent)
  return {'connection_id':connection_id,'batch_id':result[0],'replayed':result[1]}
with ThreadPoolExecutor(max_workers=2) as pool:
 futures=[pool.submit(worker) for _ in range(2)];concurrency=[f.result(timeout=30) for f in futures]
check('two_distinct_mysql_connections',len({x['connection_id'] for x in concurrency}),2)
check('concurrent_one_batch',len({x['batch_id'] for x in concurrency}),1)
check('concurrent_one_create_one_replay',sorted(x['replayed'] for x in concurrency),[False,True])
CONCURRENT=concurrency[0]['batch_id']
with Session(engine) as s:
 check('concurrent_no_duplicate_daily',s.scalar(select(func.count()).select_from(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id==CONCURRENT)),2)
 newcounts={t:s.scalar(select(func.count()).select_from(table)) for t,table in __import__('app.models',fromlist=['Base']).Base.metadata.tables.items() if not t.startswith('analytics_')}
 check('original_source_counts_preserved',newcounts,oldcounts)
 check('GET_writes',writes_during_get,[])
 states=[{'batch_id':r.batch_id,'state':r.state,'owner_user_id':r.owner_user_id,'artifact_ref':r.artifact_ref} for r in s.scalars(select(AnalyticsBatch))]
 counts={'batches':len(states),'daily_rows':s.scalar(select(func.count()).select_from(AnalyticsDailyMetric))}
 assert counts['batches']<=12 and counts['daily_rows']<=40
 save('source-counts-after.json',newcounts);save('retained-batches.json',states);save('final-counts.json',counts)
# Production allowlist and schema gates, no DB writes on rejection.
for job in ('v1-scale','v1-D07','../v2-controlled'):
 try:load_publication(job)
 except InputError:check('registry_reject_'+job,True)
 else:raise AssertionError('untrusted_job_allowed')
raw=p.model_dump(mode='json');raw['rule_version']='quality-1.1'
try:PublicationPayload.model_validate(raw)
except Exception:check('unknown_rule_version_rejected',True)
else:raise AssertionError('unknown_rule_allowed')
save('objects.json',{'main':MAIN,'boundary':BOUND,'empty_permission_fixture':EMPTY,'prepared_fixture':PREPARED,'retried_transaction_fixture':FAULT,'failed_validation_fixture':INVALID,'concurrent_fixture':CONCURRENT})
save('api-evidence.json',api_events);save('checks.json',checks);save('concurrency.json',concurrency)
save('hand-ADS-storage-API.json',{'expected':{'known_minutes':75,'missing_duration_count':2,'tasks_completed':2,'tasks_total':4,'cohort_count':3,'revised_count':1,'confirmed_count':2},'ADS':'S04-产物/jobs/v2-controlled/ads/answers.json','payload':'S05-发布输入/v2-controlled/payload.json','database':DB,'batch_id':MAIN,'api':api_main})
save('cleanup.json',{'database':DB,'completed_history_retained':True,'prepared_failed_fixtures_retained_for_evidence':True,'deleted_business_objects':0,'model_calls':0,'GET_DML':writes_during_get})
print(json.dumps({'status':'passed','requests':len(api_events),'checks':len(checks),'counts':counts,'main':MAIN,'concurrency':concurrency},ensure_ascii=False))
engine.dispose()

"""S03 已授权临时记录的真实 API / MySQL A-B 验证；不清空来源。"""
import asyncio,json,os,sys
from pathlib import Path
from secrets import token_urlsafe
from datetime import UTC,datetime
from unittest.mock import patch
from sqlalchemy import create_engine,text,event
from sqlalchemy.engine import make_url
from app.core.config import get_settings,get_security_settings
from app.core.database import get_engine,get_session_factory
from app.core.security import SecurityService
from app.models.user import User
import httpx
from scripts.export_ods_snapshot import export_snapshot,SnapshotReader
from analytics.snapshot_files import read_snapshot,write_json
from analytics.fixture_answers import calculate,assert_subset
ROOT=Path.cwd().parent
OUT=ROOT/'开发相关文档/阶段报告/AI大数据改造/V2/S03-验证证据'
OUT.mkdir(exist_ok=False)
ODS=ROOT/'开发相关文档/阶段报告/AI大数据改造/V2/S03-ODS'
DB='scholarhub_l4_s02_20261020'
url=make_url(get_settings().database_url)
assert url.host in ('localhost','127.0.0.1') and (url.port or 3306)==3306 and url.database!=DB
write_json(OUT/'authorization.json',{'stage':'S03','registered_at':datetime.now(UTC).isoformat(),'target':{'host':url.host,'port':3306,'database':DB},'initial_state':{'learning_records':4,'daily_tasks':204,'submissions':3},'user_replies':['批准临时记录验证并按标记清理（推荐）','批准9字段辅助快照（推荐）'],'scope':{'new_records':2,'owner':3,'minutes':[10,20],'update':{'10':15},'delete':'only S03 marked temporary rows; preserve S02 originals','ai_aux_fields':['id','user_id','project_id','status','requested_at','finished_at','prompt_tokens','completion_tokens','latency_ms'],'schema':'ai-request-aux-1.0'},'real_model_calls':0})
os.environ['DATABASE_URL']=url.set(database=DB).render_as_string(hide_password=False)
os.environ['JWT_SECRET']=token_urlsafe(48)
get_settings.cache_clear();get_security_settings.cache_clear();get_engine.cache_clear();get_session_factory.cache_clear()
from app.main import create_app
app=create_app()
# 导出器与 API 的引擎分开，避免只读 session 状态污染写连接。
engine=create_engine(url.set(database=DB),echo=False)
writer_connections=set()
@event.listens_for(get_engine(),'checkout')
def track_writer(dbapi,record,proxy):writer_connections.add(dbapi.thread_id())
with get_session_factory()() as s:
 u=s.get(User,3)
 assert u.username.startswith('s02_3e08a80a_')
 token=SecurityService(get_security_settings()).create_access_token(u.id,u.auth_version).value
headers={'Authorization':'Bearer '+token}
marker='s03_ab_20261020'
events=[]; created=[];remaining=set(); checks=[]
def check(name,actual,expected=True):
 checks.append({'name':name,'actual':actual,'expected':expected,'passed':actual==expected})
 if actual!=expected:raise AssertionError(name)
async def api(method,path,body=None,expected=200):
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url='http://s03-isolated') as c:
  response=await c.request(method,'/api/v1/learning'+path,headers=headers,json=body)
  # 不保存认证头、正文；仅白名单响应字段。
  data=response.json() if response.content else {}
  safe={k:data[k] for k in ('id','duration_minutes','occurred_at','project_id','task_id','record_type') if k in data}
  events.append({'method':method,'path':path,'status':response.status_code,'response':safe,'at':datetime.now(UTC).isoformat()})
  if response.status_code!=expected:raise AssertionError(f'API status {response.status_code}, expected {expected}')
  return data
async def create_rows():
 for minutes in (10,20):
  data=await api('POST','/records',{'title':marker+f'_{minutes}','record_type':'study','duration_minutes':minutes,'project_id':1,'occurred_at':datetime.now(UTC).isoformat(),'record_metadata':{'verification_marker':marker}},201)
  created.append(data['id']);remaining.add(data['id'])
  write_json(OUT/f'created-{data["id"]}.json',{'id':data['id'],'owner':3,'marker':marker,'minutes':minutes})
async def mutate():
 await api('PUT',f'/records/{created[0]}',{'duration_minutes':15})
 await api('DELETE',f'/records/{created[1]}',expected=204)
 remaining.remove(created[1])
def export(name,owner=3,hook=None):
 return export_snapshot(engine,ODS,name,owner,'2026-10-19','2026-10-20',True,after_snapshot_started=hook)
def files(path):return {p.name:p.read_bytes() for p in path.iterdir()}
base_manifest,base_tables=read_snapshot(ODS/'snapshots/s03-owner3-baseline')
base_answer=calculate(base_tables,base_manifest)
assert_subset(base_answer,{'records.valid_unique_rows':4,'records.known_minutes':75,'records.missing_duration_count':2,'tasks.total':4,'tasks.completed':2,'topic.cohort_count':3,'topic.revised_count':1,'topic.confirmed_count':2})
write_json(OUT/'baseline-independent-answer.json',base_answer)
try:
 with engine.connect() as c:
  c.exec_driver_sql('SET SESSION TRANSACTION READ ONLY');c.commit()
  check('source_initial_count',c.execute(text('SELECT COUNT(*) FROM learning_records')).scalar_one(),4)
 asyncio.run(create_rows())
 path_a,manifest_a=export('s03-owner3-A')
 a_bytes=files(path_a)
 _,a_rows=read_snapshot(path_a)
 check('A_known_minutes',calculate(a_rows,manifest_a)['records']['known_minutes'],105)
 # START CONSISTENT SNAPSHOT 已完成，而所有来源 SELECT 尚未开始；另一物理连接写入。
 held_path,held_manifest=export('s03-owner3-held-A',hook=lambda:asyncio.run(mutate()))
 _,held_rows=read_snapshot(held_path)
 check('held_snapshot_sees_preupdate_rows',held_rows,a_rows)
 check('writer_read_connection_distinct',held_manifest['transaction']['connection_id'] not in writer_connections)
 path_b,manifest_b=export('s03-owner3-B')
 _,b_rows=read_snapshot(path_b)
 b_answer=calculate(b_rows,manifest_b)
 check('B_known_minutes',b_answer['records']['known_minutes'],90)
 check('B_deleted_absent',created[1] not in {r['id'] for r in b_rows['learning_records']})
 check('B_updated_value',next(r['duration_minutes'] for r in b_rows['learning_records'] if r['id']==created[0]),15)
 check('A_files_unchanged',files(path_a)==a_bytes)
 check('A_repeated_read_stable',read_snapshot(path_a)==read_snapshot(path_a))
 try:export('s03-owner3-A')
 except FileExistsError:check('completed_overwrite_rejected',True)
 else:raise AssertionError('overwrite_allowed')
 check('A_after_rejected_overwrite_unchanged',files(path_a)==a_bytes)
 original=SnapshotReader.table
 def fail_during_read(self,name,*args,**kwargs):
  if name=='feedback':raise RuntimeError('injected_read_failure')
  return original(self,name,*args,**kwargs)
 with patch.object(SnapshotReader,'table',fail_during_read):
  try:export('s03-owner3-failure')
  except RuntimeError:check('midread_failure_seen',True)
  else:raise AssertionError('failure_missing')
 check('failed_not_published',not (ODS/'snapshots/s03-owner3-failure').exists())
 failed=list((ODS/'.incomplete').glob('s03-owner3-failure-*'))
 check('one_failed_attempt',len(failed),1)
 try:read_snapshot(failed[0])
 except ValueError:check('failed_attempt_reader_rejected',True)
 else:raise AssertionError('partial_consumed')
 retry_path,retry_manifest=export('s03-owner3-failure')
 check('retry_new_pending_succeeded',retry_path.exists() and failed[0].exists())
 check('retry_same_input',read_snapshot(retry_path)[1],b_rows)
 boundary_path,boundary_manifest=export('s03-owner4-boundary',owner=4)
 boundary_answer=calculate(read_snapshot(boundary_path)[1],boundary_manifest)
 assert_subset(boundary_answer,{'tasks.total':200,'tasks.completed':199,'tasks.completion_rate.percent':'99.500000','records.valid_unique_rows':0,'topic.cohort_count':0})
 write_json(OUT/'boundary-independent-answer.json',boundary_answer)
 write_json(OUT/'AB-independent-answers.json',{'A':calculate(a_rows,manifest_a),'B':b_answer,'expected':{'A_minutes':105,'B_minutes':90,'core_tasks':4,'core_confirmed':2}})
finally:
 # 只清理本轮创建且仍存在、标记与所有者一致的对象。
 for rid in list(remaining):
  with engine.connect() as c:
   item=c.execute(text("SELECT id,user_id,JSON_UNQUOTE(JSON_EXTRACT(record_metadata,'$.verification_marker')) AS marker FROM learning_records WHERE id=:id"),{'id':rid}).mappings().one()
   assert item['user_id']==3 and item['marker']==marker
  asyncio.run(api('DELETE',f'/records/{rid}',expected=204))
  remaining.remove(rid)
 write_json(OUT/'api-events.json',events)
 # 大型实际行集合只在快照中保留；断言记录用数量描述，不重复复制内容。
 safe_checks=[]
 for item in checks:
  item=dict(item)
  for key in ('actual','expected'):
   if isinstance(item[key],dict):item[key]={k:len(v) if isinstance(v,list) else v for k,v in item[key].items()}
  safe_checks.append(item)
 write_json(OUT/'checks.json',safe_checks)
 write_json(OUT/'cleanup.json',{'created_ids':created,'remaining_S03_ids':sorted(remaining),'scope':'only S03 marked rows','retained_S02_ids':[1,2,3,4],'no_model_calls':True})
final_path,final_manifest=export('s03-owner3-restored')
check('S02_sources_restored_exactly',read_snapshot(final_path)[1]==base_tables)
write_json(OUT/'final-check.json',{'source_restored':True,'writer_connection_ids':sorted(writer_connections),'held_read_connection_id':held_manifest['transaction']['connection_id'],'read_transaction':held_manifest['transaction'],'final_counts':final_manifest['row_counts'],'stage':'S03','spark_runs':0})
engine.dispose();get_engine().dispose()
print(json.dumps({'status':'passed','api_calls':len(events),'checks':len(checks),'created_ids':created,'cleaned':True,'source_restored':True},ensure_ascii=False))

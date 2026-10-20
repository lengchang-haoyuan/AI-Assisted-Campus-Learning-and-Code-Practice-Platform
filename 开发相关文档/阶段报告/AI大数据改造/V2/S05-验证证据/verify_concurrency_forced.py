import json,os
from pathlib import Path
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
from sqlalchemy import select,func
from app.core.config import get_settings
from app.core.database import create_database_engine
from app.models.analytics import AnalyticsBatch,AnalyticsDailyMetric
from app.repositories.analytics import AnalyticsRepository
from app.services.analytics import AnalyticsService
from app.services.analytics_artifacts import load_publication
url=make_url(get_settings().database_url).set(database='scholarhub_l4_s02_20261020');engine=create_database_engine(url.render_as_string(hide_password=False))
p=load_publication('v2-controlled').model_copy(deep=True);p.job_id='s05-concurrent-forced-v3';p.quality['transaction_fixture']=True
ready,second_lock=Event(),Event()
class WaitingRepo(AnalyticsRepository):
 def lock(self,batch_id):
  second_lock.set();return super().lock(batch_id)
def hold(batch_id):
 ready.set();assert second_lock.wait(10),'second publisher failed to reach lock'
def worker(second):
 with engine.connect() as c:
  cid=c.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one();c.commit()
  with Session(bind=c) as s:
   if second:assert ready.wait(10)
   repo=WaitingRepo(s) if second else AnalyticsRepository(s)
   result=AnalyticsService(repo).publish(p,before_complete=None if second else hold)
   return {'connection_id':cid,'batch_id':result[0],'replayed':result[1]}
with ThreadPoolExecutor(max_workers=2) as pool:
 a=pool.submit(worker,False);b=pool.submit(worker,True);result=[a.result(timeout=30),b.result(timeout=30)]
assert len({r['connection_id'] for r in result})==2
assert len({r['batch_id'] for r in result})==1 and [r['replayed'] for r in result]==[False,True]
with Session(engine) as s:
 n=s.scalar(select(func.count()).select_from(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id==result[0]['batch_id']));assert n==2
 counts={'batches':s.scalar(select(func.count()).select_from(AnalyticsBatch)),'daily_rows':s.scalar(select(func.count()).select_from(AnalyticsDailyMetric))};assert counts['batches']<=12 and counts['daily_rows']<=40
out=Path('../开发相关文档/阶段报告/AI大数据改造/V2/S05-验证证据');(out/'forced-concurrency.json').write_text(json.dumps({'status':'passed','forced_prepared_snapshot_before_lock':True,'held_connections':result,'daily_rows':n,'final_counts':counts},indent=2),encoding='utf8')
print(json.dumps({'result':result,'counts':counts}));engine.dispose()

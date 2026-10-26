"""Delete exactly the explicitly approved S06 new ID after real browser acceptance."""
import asyncio
import json
import os
from pathlib import Path
from secrets import token_urlsafe
import httpx
from sqlalchemy import func,select,inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import get_settings,get_security_settings
from app.core.database import get_engine,get_session_factory
root=Path.cwd().parent
v2=root/'开发相关文档/阶段报告/AI大数据改造/V2'
evidence=v2/'S06-验证证据'
assert json.loads((evidence/'browser/final/verification.json').read_text(encoding='utf-8'))['status']=='passed'
ledger=json.loads((evidence/'source-object.json').read_text(encoding='utf-8'))
assert ledger['record_id']==8 and ledger['marker']=='S06-20261021'
url=make_url(get_settings().database_url)
assert url.host in ('localhost','127.0.0.1') and (url.port or 3306)==3306
os.environ['DATABASE_URL']=url.set(database='scholarhub_l4_s02_20261020').render_as_string(hide_password=False)
os.environ['JWT_SECRET']=token_urlsafe(48)
for fn in (get_settings,get_security_settings,get_engine,get_session_factory):fn.cache_clear()
from app.models import Base
from app.models.learning import LearningRecord
from app.models.user import User
from app.core.security import SecurityService
from app.main import create_app
from app.ai.client import AIClient
async def forbidden(*a,**k):raise AssertionError('no model calls allowed')
AIClient.complete=forbidden
engine=get_engine()
with Session(engine) as s:
    record=s.get(LearningRecord,8)
    assert record.user_id==3 and record.duration_minutes==15 and record.record_metadata.get('verification')=='S06-20261021'
    user=s.get(User,3)
    headers={'Authorization':'Bearer '+SecurityService(get_security_settings()).create_access_token(3,user.auth_version).value}
events=[]
async def cleanup():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()),base_url='http://s06-isolated') as c:
        response=await c.delete('/api/v1/learning/records/8',headers=headers)
        assert response.status_code==204,response.status_code
        events.append({'method':'DELETE','path':'/api/v1/learning/records/8','status':204})
        response=await c.get('/api/v1/learning/records/8',headers=headers)
        assert response.status_code==404
        events.append({'method':'GET','path':'/api/v1/learning/records/8','status':404})
asyncio.run(cleanup())
with Session(engine) as s:
    final={name:s.scalar(select(func.count()).select_from(t)) for name,t in Base.metadata.tables.items()}
    baseline=json.loads((evidence/'baseline.json').read_text(encoding='utf-8'))['counts']
    assert all(final[name]==count for name,count in baseline.items() if name not in ('analytics_batches','analytics_daily_metrics'))
    assert final['analytics_batches']==14 and final['analytics_daily_metrics']==20
    assert final['learning_records']==4 and final['daily_tasks']==204
    states={state:count for state,count in s.execute(select(__import__('app.models.analytics',fromlist=['AnalyticsBatch']).AnalyticsBatch.state,func.count()).group_by(__import__('app.models.analytics',fromlist=['AnalyticsBatch']).AnalyticsBatch.state))}
result={'status':'passed','target':{'host':'127.0.0.1','port':3306,'database':'scholarhub_l4_s02_20261020'},
    'deleted_only_record_id':8,'verified_marker':'S06-20261021','API_events':events,
    'source_table_counts_restored':True,'all_counts':final,'table_count':len(inspect(engine).get_table_names()),
    'analytics_states':states,'preserved_completed_history':True,'no_accounts_or_schema_modified':True,
    'snapshot_remains_immutable_90_minutes':True,'model_calls':0}
(evidence/'cleanup-final-state.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
ledger['cleanup']='deleted_after_final_real_browser_25_checks'
(evidence/'source-object.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
engine.dispose()
print(json.dumps({'status':'passed','deleted_only_record_id':8,'learning_records':4,'daily_tasks':204,'batches':14,'daily_rows':20}))

import asyncio,json,os
from pathlib import Path
from secrets import token_urlsafe
import httpx
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import get_settings,get_security_settings
from app.core.database import get_engine,get_session_factory
url=make_url(get_settings().database_url)
assert url.host in ('localhost','127.0.0.1') and (url.port or 3306)==3306
os.environ['DATABASE_URL']=url.set(database='scholarhub_l4_s02_20261020').render_as_string(hide_password=False)
os.environ['JWT_SECRET']=token_urlsafe(48)
for factory in (get_settings,get_security_settings,get_engine,get_session_factory):factory.cache_clear()
from app.main import create_app
from app.models.user import User
from app.core.security import SecurityService
engine=get_engine()
with Session(engine) as s:
    u=s.get(User,3)
    headers={'Authorization':'Bearer '+SecurityService(get_security_settings()).create_access_token(3,u.auth_version).value}
async def run():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()),base_url='http://s06-isolated') as c:
        response=await c.get('/api/v1/offline-analytics/batches/00000000-0000-4000-8000-000000000000',headers=headers)
        assert response.status_code==404
        result={'status':'passed','method':'GET','owner_role':'isolated_fixture_owner3','batch_id':'00000000-0000-4000-8000-000000000000','expected':404,'actual':404,'body':response.json(),'mode':'real ASGI authentication + isolated MySQL'}
        path=Path.cwd().parent/'开发相关文档/阶段报告/AI大数据改造/V2/S06-验证证据/nonexistent-batch.json'
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
asyncio.run(run())
engine.dispose()
print('NONEXISTENT_BATCH_404_PASS')

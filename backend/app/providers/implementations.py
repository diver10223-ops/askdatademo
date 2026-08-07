import sqlite3
from .base import ModelProvider,DataSourceProvider
from ..config import WAREHOUSE_DB
class MockModelProvider:
 capabilities={'structured_output':True,'tasks':['L2','L7']}
 async def health_check(self): return {'status':'READY','provider':'MOCK','network':False}
 async def structured_generate(self,task,payload):
  return {'task':task,'deterministic':True,'text':payload.get('answer') or payload.get('question','').strip()}
class SQLiteDataSourceProvider:
 async def health_check(self): return {'status':'READY' if WAREHOUSE_DB.exists() else 'FAILED','provider':'SQLITE','read_only':True}
 async def execute(self,sql,parameters):
  uri=f'file:{WAREHOUSE_DB}?mode=ro'; c=sqlite3.connect(uri,uri=True); c.row_factory=sqlite3.Row
  try: return [dict(x) for x in c.execute(sql,parameters).fetchall()]
  finally: c.close()
 async def cancel(self,request_id): return True
class FixtureProvider:
 async def execute(self,key,parameters): return [{'factor':'阶段性放款节奏','contribution':'主要影响'}]
class ProviderRegistry:
 def __init__(self): self.model=MockModelProvider(); self.datasource=SQLiteDataSourceProvider(); self.fixture=FixtureProvider(); self.phase=1; self.profile_id='phase1-default'
 def status(self,kind):
  if kind in ('OPENAI_COMPATIBLE','CLICKHOUSE','MYSQL'): return {'status':'UNSUPPORTED_PHASE_1','network_attempted':False}
  return {'status':'READY'}

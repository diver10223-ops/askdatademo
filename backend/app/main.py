import asyncio,json,os,uuid
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import StreamingResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .config import PLATFORM_DB,WAREHOUSE_DB,BASELINE,ROOT
from .db import connect,restore_baseline,restore_official_config,migrate,backup,restore_backup,full_reset
from .engine import Engine
from .credentials import CredentialError,encrypt_secret,decrypt_secret
from .models import PipelineContext
from .phase2_service import build_registry,public_profile
from .providers.phase2 import network_diagnostics,OpenAICompatibleProvider,ClickHouseProvider,MySQLProvider,RetryPolicy
from .sql_security import SQLPolicy
from .runtime import RuntimeConfigError,resolve_runtime
from .runtime.publisher import publish_runtime
now=lambda:datetime.now(timezone.utc).isoformat()
app=FastAPI(title='AskData Phase 1 + Phase 2',version='2.0.0'); engine=Engine(); active_engines={}
class SessionIn(BaseModel): role_id:str=Field(pattern='^(admin|beijing|retail)$'); execution_mode:str=Field(default='PHASE1_DEMO',pattern='^(PHASE1_DEMO|PHASE2_DEMO|PHASE2_POC)$'); provider_profile_id:str|None=None
class QueryIn(BaseModel): session_id:str; question:str=Field(min_length=1,max_length=1000); scenario_id:str|None=None; parent_request_id:str|None=None
class DraftIn(BaseModel): name:str; payload:dict
class ResourceIn(BaseModel): id:str=Field(min_length=1,max_length=100); payload:dict; enabled:bool=True
class MockRowIn(BaseModel):
 stat_dt:str; org_name:str; loan_cur:float; loan_last:float; retail_cur:float; retail_last:float; corporate_cur:float; corporate_last:float
class ProviderProfileIn(BaseModel):
 name:str=Field(min_length=1,max_length=100); datasource_type:str=Field(pattern='^(CLICKHOUSE|MYSQL)$')
 model_provider:str=Field(default='OPENAI_COMPATIBLE',pattern='^(OPENAI|GEMINI|DEEPSEEK|QWEN|ZHIPU_GLM|OPENAI_COMPATIBLE)$'); model_base_url:str; model:str; model_api_key:str=Field(min_length=1); model_temperature:float=Field(default=.2,ge=0,le=2); model_top_p:float=Field(default=.9,ge=0,le=1); model_max_tokens:int=Field(default=2048,ge=128,le=32768); model_context_window:int=Field(default=32768,ge=1024); model_structured_output:bool=True; model_system_prompt:str=''
 datasource_url:str|None=None; datasource_host:str|None=None; datasource_port:int=3306; datasource_tls:bool=True; datasource_username:str; datasource_password:str=Field(min_length=1); database:str
 allowed_tables:list[str]=Field(min_length=1); datasource_read_only:bool=True; datasource_charset:str='utf8mb4'; datasource_pool_size:int=Field(default=5,ge=1,le=50); schema_sync_enabled:bool=True; max_rows:int=Field(default=1000,ge=1,le=10000); max_time_range_days:int=Field(default=366,ge=1,le=3660); timeout:float=Field(default=30,ge=1,le=120); retries:int=Field(default=2,ge=0,le=5); backoff:float=Field(default=.25,ge=0,le=10); max_concurrency:int=Field(default=4,ge=1,le=32)
class ModelConfigIn(BaseModel):
 name:str=Field(min_length=1,max_length=100); provider:str=Field(pattern='^(OPENAI|GEMINI|DEEPSEEK|QWEN|ZHIPU_GLM|OPENAI_COMPATIBLE)$'); base_url:str; model:str; api_key:str=Field(min_length=1); temperature:float=Field(default=.2,ge=0,le=2); top_p:float=Field(default=.9,ge=0,le=1); max_tokens:int=Field(default=2048,ge=128,le=32768); context_window:int=Field(default=32768,ge=1024); structured_output:bool=True; system_prompt:str=''; timeout:float=Field(default=30,ge=1,le=120); retries:int=Field(default=2,ge=0,le=5); max_concurrency:int=Field(default=4,ge=1,le=32)
class DatasourceConfigIn(BaseModel):
 name:str=Field(min_length=1,max_length=100); type:str=Field(pattern='^(CLICKHOUSE|MYSQL)$'); url:str|None=None; host:str|None=None; port:int=3306; tls:bool=True; username:str; password:str=Field(min_length=1); database:str; allowed_tables:list[str]=Field(min_length=1); read_only:bool=True; charset:str='utf8mb4'; pool_size:int=Field(default=5,ge=1,le=50); schema_sync:bool=True; max_rows:int=Field(default=1000,ge=1,le=10000); max_time_range_days:int=Field(default=366,ge=1,le=3660); timeout:float=Field(default=30,ge=1,le=120); retries:int=Field(default=2,ge=0,le=5); max_concurrency:int=Field(default=4,ge=1,le=32)
class ProviderCompositionIn(BaseModel): name:str=Field(min_length=1,max_length=100); model_config_id:str; datasource_config_id:str
@app.on_event('startup')
def startup():
 migrate()
 with connect(PLATFORM_DB) as db: db.execute("UPDATE requests SET status='FAILED',termination_reason='SERVICE_RESTARTED',completed_at=? WHERE status IN ('PENDING','RUNNING')",(now(),))
 with connect(WAREHOUSE_DB) as db: empty=db.execute('SELECT COUNT(*) FROM dws_loan_aggr_wide').fetchone()[0]==0
 restore_baseline(empty)
@app.get('/api/v1/health')
def health(): return {'status':'ok','version':'1.0.0','platform_db':PLATFORM_DB.exists()}
@app.post('/api/v1/sessions',status_code=201)
def create_session(body:SessionIn):
 if body.execution_mode.startswith('PHASE2') and not body.provider_profile_id: raise HTTPException(422,detail={'code':'INVALID_INPUT','message':'Phase 2 Session 必须指定 Provider Profile'})
 sid=str(uuid.uuid4()); ps=str(uuid.uuid4())
 with connect(PLATFORM_DB) as db:
  role=db.execute('SELECT permissions FROM roles WHERE id=? AND enabled=1',(body.role_id,)).fetchone()
  if not role: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'角色不存在或已停用'})
  cfg=db.execute("SELECT id FROM config_versions WHERE status='PUBLISHED'").fetchone()
  db.execute('INSERT INTO sessions(id,role_id,permission_snapshot_id,permission_snapshot,config_version_id,created_at) VALUES(?,?,?,?,?,?)',(sid,body.role_id,ps,role[0],cfg[0],now()))
  db.execute('INSERT INTO session_execution_modes VALUES(?,?)',(sid,body.execution_mode))
  if body.execution_mode.startswith('PHASE2'):
   profile=db.execute("SELECT 1 FROM phase2_provider_profiles WHERE id=? AND status='ENABLED'",(body.provider_profile_id,)).fetchone()
   if not profile: raise HTTPException(409,detail={'code':'INVALID_INPUT','message':'Provider Profile 未启用'})
   try:
    build_registry(body.provider_profile_id)
    if body.execution_mode=='PHASE2_POC':
     published=json.loads(db.execute('SELECT payload FROM config_versions WHERE id=?',(cfg[0],)).fetchone()[0]); profile_cfg=json.loads(db.execute('SELECT public_config FROM phase2_provider_profiles WHERE id=?',(body.provider_profile_id,)).fetchone()[0]); resolve_runtime(published,body.execution_mode,profile_cfg.get('allowed_tables',[]))
   except RuntimeConfigError as exc: raise HTTPException(409,detail={'code':'RUNTIME_CONFIG_UNAVAILABLE','message':'POC运行配置不完整，请在后台补全并发布','missing':exc.missing})
   except (CredentialError,ValueError) as exc: raise HTTPException(409,detail={'code':'PROVIDER_PROFILE_UNAVAILABLE','message':'Provider Profile 凭据不可用，请重新创建并诊断','reason':type(exc).__name__})
   db.execute('INSERT INTO phase2_session_profiles VALUES(?,?,?)',(sid,body.provider_profile_id,body.execution_mode))
 return {'id':sid,'role_id':body.role_id,'config_version_id':cfg[0],'execution_mode':body.execution_mode,'provider_profile_id':body.provider_profile_id}
@app.get('/api/v1/sessions/{sid}')
def get_session(sid:str):
 with connect(PLATFORM_DB) as db:
  s=db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone(); req=db.execute('SELECT id,question,status,parent_request_id,created_at FROM requests WHERE session_id=? ORDER BY created_at',(sid,)).fetchall()
 if not s: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'会话不存在'})
 return {**dict(s),'history':[dict(x) for x in req]}
@app.post('/api/v1/queries',status_code=202)
async def create_query(body:QueryIn):
 rid=str(uuid.uuid4()); trace=str(uuid.uuid4())
 with connect(PLATFORM_DB) as db:
  s=db.execute('SELECT * FROM sessions WHERE id=? AND active=1',(body.session_id,)).fetchone()
  if not s: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'活动会话不存在'})
  if body.parent_request_id and not db.execute('SELECT 1 FROM requests WHERE id=? AND session_id=?',(body.parent_request_id,body.session_id)).fetchone(): raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'父请求不属于当前会话'})
  ctx=json.loads(s['context']); phase2=db.execute('SELECT * FROM phase2_session_profiles WHERE session_id=?',(body.session_id,)).fetchone(); stored_mode=db.execute('SELECT execution_mode FROM session_execution_modes WHERE session_id=?',(body.session_id,)).fetchone(); mode=stored_mode['execution_mode'] if stored_mode else (phase2['execution_mode'] if phase2 else 'PHASE1_DEMO')
  version=db.execute('SELECT payload FROM config_versions WHERE id=?',(s['config_version_id'],)).fetchone(); config=json.loads(version[0]); override=config.get('scenario_overrides',{}).get(body.scenario_id,{}); config={**config,**override,**{k:{**config.get(k,{}),**override.get(k,{})} for k in ('assets','compliance','system')}}; permissions=json.loads(s['permission_snapshot'])
  try:
   selected_engine=Engine(build_registry(phase2['profile_id'])) if phase2 else engine
   profile_cfg=json.loads(db.execute('SELECT public_config FROM phase2_provider_profiles WHERE id=?',(phase2['profile_id'],)).fetchone()[0]) if phase2 else {}
   runtime=resolve_runtime(config,mode,profile_cfg.get('allowed_tables'))
  except (CredentialError,ValueError,RuntimeConfigError) as exc: raise HTTPException(409,detail={'code':'RUNTIME_CONFIG_UNAVAILABLE','message':'运行配置或Provider不可用，请检查并发布后台配置','reason':type(exc).__name__,'missing':getattr(exc,'missing',[])})
  db.execute('INSERT INTO requests(id,session_id,parent_request_id,trace_id,scenario_id,question,mode,status,config_version_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,body.session_id,body.parent_request_id,trace,body.scenario_id,body.question,mode,'PENDING',s['config_version_id'],now()))
 c=PipelineContext(body.session_id,rid,s['role_id'],s['config_version_id'],body.question,body.parent_request_id,body.scenario_id,mode=mode,parameters=ctx,permissions=permissions,config=config,runtime=runtime)
 active_engines[rid]=selected_engine
 async def execute():
  try: await selected_engine.run(c)
  finally: active_engines.pop(rid,None)
 asyncio.create_task(execute()); return {'request_id':rid,'trace_id':trace,'status':'PENDING','mode':mode}
@app.get('/api/v1/queries/{rid}')
def query_detail(rid:str):
 with connect(PLATFORM_DB) as db:
  q=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
  if not q: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'请求不存在'})
  layers=[{**dict(x),'input':json.loads(x['input_json']),'output':json.loads(x['output_json'] or '{}')} for x in db.execute('SELECT * FROM layer_executions WHERE request_id=? ORDER BY id',(rid,))]
  sql=[{**dict(x),'parameters':json.loads(x['parameters'])} for x in db.execute('SELECT * FROM sql_executions WHERE request_id=? ORDER BY sequence',(rid,))]
  snap=db.execute('SELECT * FROM result_snapshots WHERE request_id=?',(rid,)).fetchone()
 return {'request':dict(q),'layers':layers,'sql_executions':sql,'result':json.loads(snap['payload']) if snap else []}
@app.get('/api/v1/queries/{rid}/events')
async def events(rid:str,request:Request):
 try: last=int(request.headers.get('last-event-id') or request.query_params.get('last_event_id','0'))
 except ValueError: last=0
 async def stream():
  nonlocal last
  while True:
   with connect(PLATFORM_DB) as db:
    rows=db.execute('SELECT * FROM sse_events WHERE request_id=? AND event_id>? ORDER BY event_id',(rid,last)).fetchall(); q=db.execute('SELECT status FROM requests WHERE id=?',(rid,)).fetchone()
   for row in rows:
    last=row['event_id']; yield f"id: {last}\nevent: {row['event_type']}\ndata: {row['payload']}\n\n"
   if q and q['status'] not in ('PENDING','RUNNING'): break
   yield ': heartbeat\n\n'; await asyncio.sleep(.15)
 return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
@app.post('/api/v1/queries/{rid}/cancel')
async def cancel(rid:str):
 with connect(PLATFORM_DB) as db:
  q=db.execute('SELECT status,cancel_requested FROM requests WHERE id=?',(rid,)).fetchone()
  if not q: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'请求不存在'})
  if q['status'] in ('SUCCEEDED','FAILED','BLOCKED','SHORT_CIRCUITED','WAITING_INPUT','CANCELLED'): return {'request_id':rid,'status':q['status'],'idempotent':True}
  db.execute('UPDATE requests SET cancel_requested=1,cancelled_by=?,cancelled_at=? WHERE id=?',('demo-user',now(),rid))
 running=active_engines.get(rid)
 if running: await running.registry.datasource.cancel(rid)
 return {'request_id':rid,'status':'CANCELLATION_REQUESTED'}
@app.get('/api/v1/admin/baseline')
def baseline(): return json.loads(BASELINE.read_text())
@app.get('/api/v1/admin/logs')
def logs(kind:str='requests',status:str|None=None):
 if kind not in {'requests','sessions','sql','audit','model-logs','source-monitor'}: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'日志类型无效'})
 with connect(PLATFORM_DB) as db:
  if kind=='sessions': rows=db.execute("SELECT s.id,s.role_id AS operator_id,s.role_id,s.created_at,CASE WHEN s.active=1 THEN 'ACTIVE' ELSE 'CLOSED' END AS status,s.config_version_id,COUNT(r.id) AS request_count,MAX(r.completed_at) AS last_activity_at FROM sessions s LEFT JOIN requests r ON r.session_id=s.id GROUP BY s.id ORDER BY s.created_at DESC LIMIT 200").fetchall()
  elif kind=='requests': rows=db.execute("SELECT r.id,r.session_id,s.role_id AS operator_id,s.role_id,r.question,r.scenario_id,r.mode,r.status,r.last_layer,r.termination_reason,r.created_at,r.completed_at,(SELECT COUNT(*) FROM result_snapshots z WHERE z.request_id=r.id) AS has_result,(SELECT COUNT(*) FROM sql_executions q WHERE q.request_id=r.id) AS sql_count FROM requests r JOIN sessions s ON s.id=r.session_id"+(' WHERE r.status=?' if status else '')+' ORDER BY r.created_at DESC LIMIT 200',((status,) if status else ())).fetchall()
  elif kind=='sql': rows=db.execute("SELECT q.id,q.request_id,r.session_id,s.role_id AS operator_id,s.role_id,r.scenario_id,r.mode,q.sequence,q.source,q.status,q.row_count,q.elapsed_ms,q.fallback,r.created_at FROM sql_executions q JOIN requests r ON r.id=q.request_id JOIN sessions s ON s.id=r.session_id ORDER BY q.id DESC LIMIT 200").fetchall()
  elif kind=='model-logs': rows=db.execute("SELECT le.id,le.request_id,r.session_id,s.role_id AS operator_id,s.role_id,r.scenario_id,r.mode,le.layer_code,COALESCE(json_extract(pp.public_config,'$.model_provider'),'MOCK') AS model_provider,COALESCE(json_extract(pp.public_config,'$.model'),le.provider,'一期模拟模型') AS model,le.status,le.elapsed_ms,le.error_code,r.created_at FROM layer_executions le JOIN requests r ON r.id=le.request_id JOIN sessions s ON s.id=r.session_id LEFT JOIN phase2_session_profiles sp ON sp.session_id=r.session_id LEFT JOIN phase2_provider_profiles pp ON pp.id=sp.profile_id WHERE le.layer_code IN ('L2','L7') ORDER BY le.id DESC LIMIT 200").fetchall()
  elif kind=='source-monitor': rows=db.execute("SELECT q.id,q.request_id,r.session_id,s.role_id AS operator_id,s.role_id,r.scenario_id,r.mode,q.sequence,q.source,q.status,q.row_count,q.elapsed_ms,q.fallback,q.business_sql,q.actual_sql,q.error,r.created_at FROM sql_executions q JOIN requests r ON r.id=q.request_id JOIN sessions s ON s.id=r.session_id ORDER BY q.id DESC LIMIT 200").fetchall()
  else: rows=db.execute("SELECT id,actor AS operator_id,actor,action,detail,created_at,'RECORDED' AS status FROM audit_logs ORDER BY id DESC LIMIT 200").fetchall()
 return {'items':[dict(x) for x in rows]}
@app.get('/api/v1/admin/approvals')
def approvals(status:str='PENDING'):
 if status not in {'PENDING','APPROVED','REJECTED','ALL'}: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'审批状态无效'})
 with connect(PLATFORM_DB) as db: rows=db.execute('SELECT * FROM approval_tasks'+('' if status=='ALL' else ' WHERE status=?')+' ORDER BY submitted_at DESC LIMIT 20',(() if status=='ALL' else (status,))).fetchall()
 return {'items':[dict(x) for x in rows]}
@app.get('/api/v1/admin/logs/{kind}/{item_id}')
def log_detail(kind:str,item_id:str):
 if kind not in {'requests','sessions','sql','audit','model-logs','source-monitor'}: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'日志类型无效'})
 with connect(PLATFORM_DB) as db:
  if kind=='sessions':
   row=db.execute('SELECT * FROM sessions WHERE id=?',(item_id,)).fetchone()
   related=[dict(x) for x in db.execute('SELECT id,question,scenario_id,mode,status,last_layer,termination_reason,created_at,completed_at FROM requests WHERE session_id=? ORDER BY created_at DESC',(item_id,))]
   detail={'session':dict(row) if row else None,'requests':related}
  elif kind=='requests':
   row=db.execute('SELECT r.*,s.role_id AS operator_id,s.role_id FROM requests r JOIN sessions s ON s.id=r.session_id WHERE r.id=?',(item_id,)).fetchone()
   layers=[{**dict(x),'input':json.loads(x['input_json'] or '{}'),'output':json.loads(x['output_json'] or '{}')} for x in db.execute('SELECT * FROM layer_executions WHERE request_id=? ORDER BY id',(item_id,))]
   sql_rows=[{**dict(x),'parameters':json.loads(x['parameters'] or '{}')} for x in db.execute('SELECT * FROM sql_executions WHERE request_id=? ORDER BY sequence',(item_id,))]
   snapshot=db.execute('SELECT * FROM result_snapshots WHERE request_id=?',(item_id,)).fetchone(); events=[{**dict(x),'payload':json.loads(x['payload'] or '{}')} for x in db.execute('SELECT * FROM sse_events WHERE request_id=? ORDER BY event_id',(item_id,))]
   detail={'request':dict(row) if row else None,'layers':layers,'sql_executions':sql_rows,'result':json.loads(snapshot['payload']) if snapshot else [],'events':events}
  elif kind in {'sql','source-monitor'}:
   row=db.execute('SELECT q.*,r.question,r.scenario_id,r.mode,r.created_at,s.role_id AS operator_id,s.role_id FROM sql_executions q JOIN requests r ON r.id=q.request_id JOIN sessions s ON s.id=r.session_id WHERE q.id=?',(item_id,)).fetchone()
   detail={'sql':{**dict(row),'parameters':json.loads(row['parameters'] or '{}')} if row else None}
  elif kind=='model-logs':
   row=db.execute("SELECT le.*,r.question,r.scenario_id,r.mode,r.created_at,s.role_id AS operator_id,s.role_id,COALESCE(json_extract(pp.public_config,'$.model_provider'),'MOCK') AS model_provider,COALESCE(json_extract(pp.public_config,'$.model'),le.provider,'一期模拟模型') AS model FROM layer_executions le JOIN requests r ON r.id=le.request_id JOIN sessions s ON s.id=r.session_id LEFT JOIN phase2_session_profiles sp ON sp.session_id=r.session_id LEFT JOIN phase2_provider_profiles pp ON pp.id=sp.profile_id WHERE le.id=?",(item_id,)).fetchone()
   detail={'model_call':{**dict(row),'input':json.loads(row['input_json'] or '{}'),'output':json.loads(row['output_json'] or '{}')} if row else None}
  else:
   row=db.execute('SELECT * FROM audit_logs WHERE id=?',(item_id,)).fetchone(); detail={'audit':{**dict(row),'detail':json.loads(row['detail'] or '{}')} if row else None}
 if not row: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'日志不存在'})
 return detail
@app.get('/api/v1/admin/readiness')
async def readiness():
 b=json.loads(BASELINE.read_text()); return {'ready':len(b['roles'])==3 and len(b['scenarios'])==8 and PLATFORM_DB.exists(),'roles':len(b['roles']),'scenarios':len(b['scenarios']),'providers':{'mock':await engine.registry.model.health_check(),'sqlite':await engine.registry.datasource.health_check()}}
@app.post('/api/v1/admin/providers/{kind}/test')
def provider_test(kind:str): return engine.registry.status(kind.upper())
def _public_connection(row):
 item=dict(row); item['public_config']=json.loads(item['public_config']); item.pop('encrypted_credentials',None); item['credentials_configured']=True; return item
@app.get('/api/v1/admin/phase2/models')
def model_configs():
 with connect(PLATFORM_DB) as db: return {'items':[_public_connection(x) for x in db.execute('SELECT * FROM phase2_model_configs ORDER BY created_at DESC')]}
@app.post('/api/v1/admin/phase2/models',status_code=201)
def create_model_config(body:ModelConfigIn):
 if not body.base_url.startswith(('https://','http://')): raise HTTPException(422,detail={'code':'INVALID_INPUT','message':'模型 URL 协议无效'})
 rid=str(uuid.uuid4()); values=body.model_dump(); secret={'model_api_key':values.pop('api_key')}; name=values.pop('name'); provider=values.pop('provider')
 encrypted=encrypt_secret(secret)
 with connect(PLATFORM_DB) as db: db.execute('INSERT INTO phase2_model_configs VALUES(?,?,?,?,?,?,?,?)',(rid,name,provider,json.dumps(values,ensure_ascii=False),encrypted,'DRAFT',now(),now())); db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('CREATE_MODEL_CONFIG','admin',json.dumps({'id':rid,'provider':provider}),now()))
 return {'id':rid,'status':'DRAFT','credentials_encrypted':True}
@app.post('/api/v1/admin/phase2/models/{rid}/enable')
def enable_model_config(rid:str):
 with connect(PLATFORM_DB) as db:
  if not db.execute('SELECT 1 FROM phase2_model_configs WHERE id=?',(rid,)).fetchone(): raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'模型配置不存在'})
  db.execute("UPDATE phase2_model_configs SET status='ENABLED',updated_at=? WHERE id=?",(now(),rid))
 return {'id':rid,'status':'ENABLED'}
@app.post('/api/v1/admin/phase2/models/{rid}/diagnose')
async def diagnose_model_config(rid:str):
 with connect(PLATFORM_DB) as db: row=db.execute('SELECT * FROM phase2_model_configs WHERE id=?',(rid,)).fetchone()
 if not row: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'模型配置不存在'})
 cfg=json.loads(row['public_config']); secret=decrypt_secret(row['encrypted_credentials']); retry=RetryPolicy(cfg['timeout'],cfg['retries'],.25,cfg['max_concurrency']); provider=OpenAICompatibleProvider(cfg['base_url'],secret['model_api_key'],cfg['model'],retry)
 result=await provider.health_check(); return {'id':rid,'component':'MODEL','status':result['status'],'detail':result}
@app.get('/api/v1/admin/phase2/datasources')
def datasource_configs():
 with connect(PLATFORM_DB) as db: return {'items':[_public_connection(x) for x in db.execute('SELECT * FROM phase2_datasource_configs ORDER BY created_at DESC')]}
@app.post('/api/v1/admin/phase2/datasources',status_code=201)
def create_datasource_config(body:DatasourceConfigIn):
 if body.type=='CLICKHOUSE' and (not body.url or not body.url.startswith(('https://','http://'))): raise HTTPException(422,detail={'code':'INVALID_INPUT','message':'ClickHouse URL 无效'})
 rid=str(uuid.uuid4()); values=body.model_dump(); secret={'datasource_password':values.pop('password')}; name=values.pop('name'); kind=values.pop('type'); encrypted=encrypt_secret(secret)
 with connect(PLATFORM_DB) as db: db.execute('INSERT INTO phase2_datasource_configs VALUES(?,?,?,?,?,?,?,?)',(rid,name,kind,json.dumps(values,ensure_ascii=False),encrypted,'DRAFT',now(),now())); db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('CREATE_DATASOURCE_CONFIG','admin',json.dumps({'id':rid,'type':kind}),now()))
 return {'id':rid,'status':'DRAFT','credentials_encrypted':True}
@app.post('/api/v1/admin/phase2/datasources/{rid}/enable')
def enable_datasource_config(rid:str):
 with connect(PLATFORM_DB) as db:
  if not db.execute('SELECT 1 FROM phase2_datasource_configs WHERE id=?',(rid,)).fetchone(): raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'数据源配置不存在'})
  db.execute("UPDATE phase2_datasource_configs SET status='ENABLED',updated_at=? WHERE id=?",(now(),rid))
 return {'id':rid,'status':'ENABLED'}
@app.post('/api/v1/admin/phase2/datasources/{rid}/diagnose')
async def diagnose_datasource_config(rid:str):
 with connect(PLATFORM_DB) as db: row=db.execute('SELECT * FROM phase2_datasource_configs WHERE id=?',(rid,)).fetchone()
 if not row: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'数据源配置不存在'})
 cfg=json.loads(row['public_config']); secret=decrypt_secret(row['encrypted_credentials']); retry=RetryPolicy(cfg['timeout'],cfg['retries'],.25,cfg['max_concurrency']); policy=SQLPolicy(frozenset(cfg['allowed_tables']),cfg['max_rows'],cfg['max_time_range_days'],retry.timeout)
 provider=ClickHouseProvider(cfg['url'],cfg['username'],secret['datasource_password'],cfg['database'],policy,retry) if row['type']=='CLICKHOUSE' else MySQLProvider(cfg['host'],cfg['port'],cfg['username'],secret['datasource_password'],cfg['database'],policy,retry,cfg['tls'])
 health=await provider.health_check(); schema=await provider.schema_check(); status='READY' if health['status']=='READY' and schema['status']=='READY' else 'FAILED'; return {'id':rid,'component':'DATASOURCE','status':status,'detail':{'health':health,'schema':schema}}
@app.post('/api/v1/admin/phase2/providers/compose',status_code=201)
def compose_phase2_profile(body:ProviderCompositionIn):
 with connect(PLATFORM_DB) as db:
  model=db.execute("SELECT * FROM phase2_model_configs WHERE id=? AND status='ENABLED'",(body.model_config_id,)).fetchone(); source=db.execute("SELECT * FROM phase2_datasource_configs WHERE id=? AND status='ENABLED'",(body.datasource_config_id,)).fetchone()
  if not model or not source: raise HTTPException(409,detail={'code':'CONFIG_NOT_ENABLED','message':'模型和数据源必须分别启用后才能组合'})
  mc=json.loads(model['public_config']); dc=json.loads(source['public_config']); ms=decrypt_secret(model['encrypted_credentials']); ds=decrypt_secret(source['encrypted_credentials']); rid=str(uuid.uuid4())
  public={'model_provider':model['provider'],'model_base_url':mc['base_url'],'model':mc['model'],'model_temperature':mc['temperature'],'model_top_p':mc['top_p'],'model_max_tokens':mc['max_tokens'],'model_context_window':mc['context_window'],'model_structured_output':mc['structured_output'],'model_system_prompt':mc['system_prompt'],'datasource_url':dc.get('url'),'datasource_host':dc.get('host'),'datasource_port':dc.get('port',3306),'datasource_tls':dc.get('tls',True),'datasource_username':dc['username'],'database':dc['database'],'allowed_tables':dc['allowed_tables'],'datasource_read_only':dc['read_only'],'datasource_charset':dc['charset'],'datasource_pool_size':dc['pool_size'],'schema_sync_enabled':dc['schema_sync'],'max_rows':dc['max_rows'],'max_time_range_days':dc['max_time_range_days'],'timeout':max(mc['timeout'],dc['timeout']),'retries':max(mc['retries'],dc['retries']),'max_concurrency':min(mc['max_concurrency'],dc['max_concurrency']),'model_config_id':model['id'],'datasource_config_id':source['id']}
  secret=encrypt_secret({'model_api_key':ms['model_api_key'],'datasource_password':ds['datasource_password']}); db.execute('INSERT INTO phase2_provider_profiles VALUES(?,?,?,?,?,?,?,?,?)',(rid,body.name,'OPENAI_COMPATIBLE',source['type'],json.dumps(public,ensure_ascii=False),secret,'DRAFT',now(),now()))
 return {'id':rid,'status':'DRAFT','model_config_id':model['id'],'datasource_config_id':source['id']}
@app.get('/api/v1/admin/phase2/providers')
def phase2_profiles():
 with connect(PLATFORM_DB) as db:
  items=[]
  for row in db.execute('SELECT * FROM phase2_provider_profiles ORDER BY created_at DESC'):
   item=public_profile(row)
   try: decrypt_secret(row['encrypted_credentials']); item['credentials_valid']=True
   except CredentialError: item['credentials_valid']=False
   diagnostic=db.execute('SELECT status,created_at FROM provider_diagnostics WHERE profile_id=? ORDER BY id DESC LIMIT 1',(row['id'],)).fetchone()
   item['diagnostic_status']=diagnostic['status'] if diagnostic else 'NOT_TESTED'; item['selectable']=bool(item['status']=='ENABLED' and item['credentials_valid'])
   items.append(item)
  return {'items':items}
@app.post('/api/v1/admin/phase2/providers',status_code=201)
def create_phase2_profile(body:ProviderProfileIn):
 if not body.model_base_url.startswith(('https://','http://')): raise HTTPException(422,detail={'code':'INVALID_INPUT','message':'模型 URL 协议无效'})
 if body.datasource_type=='CLICKHOUSE' and (not body.datasource_url or not body.datasource_url.startswith(('https://','http://'))): raise HTTPException(422,detail={'code':'INVALID_INPUT','message':'ClickHouse URL 无效'})
 profile_id=str(uuid.uuid4()); values=body.model_dump(); secret={'model_api_key':values.pop('model_api_key'),'datasource_password':values.pop('datasource_password')}; values.pop('name'); values.pop('datasource_type')
 try: encrypted=encrypt_secret(secret)
 except CredentialError as exc: raise HTTPException(503,detail={'code':'CREDENTIAL_KEY_UNAVAILABLE','message':str(exc)})
 with connect(PLATFORM_DB) as db:
  db.execute('INSERT INTO phase2_provider_profiles VALUES(?,?,?,?,?,?,?,?,?)',(profile_id,body.name,'OPENAI_COMPATIBLE',body.datasource_type,json.dumps(values,ensure_ascii=False),encrypted,'DRAFT',now(),now()))
  db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('CREATE_PHASE2_PROFILE','admin',json.dumps({'id':profile_id,'datasource_type':body.datasource_type}),now()))
 return {'id':profile_id,'status':'DRAFT','credentials_encrypted':True}
@app.post('/api/v1/admin/phase2/providers/{profile_id}/enable')
def enable_phase2_profile(profile_id:str):
 with connect(PLATFORM_DB) as db:
  if not db.execute('SELECT 1 FROM phase2_provider_profiles WHERE id=?',(profile_id,)).fetchone(): raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'Provider Profile 不存在'})
  try: build_registry(profile_id,False)
  except (CredentialError,ValueError) as exc: raise HTTPException(409,detail={'code':'PROVIDER_PROFILE_UNAVAILABLE','message':'凭据不可用，不能启用；请重新创建Profile','reason':type(exc).__name__})
  db.execute("UPDATE phase2_provider_profiles SET status='ENABLED',updated_at=? WHERE id=?",(now(),profile_id)); db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('ENABLE_PHASE2_PROFILE','admin',json.dumps({'id':profile_id}),now()))
 return {'id':profile_id,'status':'ENABLED'}
@app.post('/api/v1/admin/phase2/providers/{profile_id}/diagnose')
async def diagnose_phase2_profile(profile_id:str):
 try:
  registry=build_registry(profile_id,False); model_url=urlparse(registry.model.base_url); model_network=await asyncio.to_thread(network_diagnostics,model_url.hostname,model_url.port or (443 if model_url.scheme=='https' else 80),model_url.scheme=='https')
  if hasattr(registry.datasource,'url'):
   data_url=urlparse(registry.datasource.url); data_network=await asyncio.to_thread(network_diagnostics,data_url.hostname,data_url.port or (443 if data_url.scheme=='https' else 80),data_url.scheme=='https')
  else: data_network=await asyncio.to_thread(network_diagnostics,registry.datasource.host,registry.datasource.port,registry.datasource.use_tls)
  model=await registry.model.health_check(); datasource=await registry.datasource.health_check(); schema=await registry.datasource.schema_check(); status='READY' if model['status']=='READY' and datasource['status']=='READY' and schema['status']=='READY' else 'FAILED'; detail={'network':{'model':model_network,'datasource':data_network},'model':model,'datasource':datasource,'schema':schema}
 except Exception as exc: status='FAILED'; detail={'error_type':type(exc).__name__,'message':'诊断失败，凭据和内部地址已隐藏'}
 with connect(PLATFORM_DB) as db: db.execute('INSERT INTO provider_diagnostics(profile_id,component,status,detail,created_at) VALUES(?,?,?,?,?)',(profile_id,'ALL',status,json.dumps(detail,ensure_ascii=False),now()))
 return {'profile_id':profile_id,'status':status,'detail':detail}
@app.get('/api/v1/admin/phase2/providers/{profile_id}/diagnostics')
def phase2_diagnostics(profile_id:str):
 with connect(PLATFORM_DB) as db: return {'items':[{**dict(x),'detail':json.loads(x['detail'])} for x in db.execute('SELECT * FROM provider_diagnostics WHERE profile_id=? ORDER BY id DESC LIMIT 50',(profile_id,))]}
@app.post('/api/v1/admin/config/drafts',status_code=201)
def draft(body:DraftIn):
 with connect(PLATFORM_DB) as db:
  version=db.execute('SELECT COALESCE(MAX(version),0)+1 FROM config_versions').fetchone()[0]; cid=str(uuid.uuid4()); db.execute('INSERT INTO config_versions VALUES(?,?,?,?,?,?,?)',(cid,body.name,'DRAFT',version,json.dumps(body.payload,ensure_ascii=False),0,now())); db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('CREATE_DRAFT','admin',json.dumps({'id':cid}),now()))
 return {'id':cid,'version':version,'status':'DRAFT'}
@app.post('/api/v1/admin/config/{cid}/publish')
def publish(cid:str):
 with connect(PLATFORM_DB) as db:
  x=db.execute("SELECT status FROM config_versions WHERE id=? AND official=0",(cid,)).fetchone()
  if not x or x['status']!='DRAFT': raise HTTPException(409,detail={'code':'INVALID_INPUT','message':'仅非官方草稿可发布'})
  db.execute("UPDATE config_versions SET status='ARCHIVED' WHERE status='PUBLISHED'"); db.execute("UPDATE config_versions SET status='PUBLISHED' WHERE id=?",(cid,)); db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('PUBLISH','admin',json.dumps({'id':cid}),now()))
 return {'id':cid,'status':'PUBLISHED','affects':'new_sessions_only'}
@app.get('/api/v1/admin/config/export')
def export_config():
 with connect(PLATFORM_DB) as db: x=db.execute("SELECT * FROM config_versions WHERE status='PUBLISHED'").fetchone()
 return dict(x)
@app.post('/api/v1/admin/reset/{scope}')
def reset(scope:str,confirm:bool=False):
 if scope=='official': restore_official_config()
 elif scope=='mock-data': restore_baseline(True)
 elif scope=='all' and confirm: full_reset()
 else: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'重置范围或确认参数无效'})
 with connect(PLATFORM_DB) as db: db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',(f'RESET_{scope}','admin','{}',now()))
 return {'status':'ok','scope':scope}
@app.get('/api/v1/admin/config/versions')
def config_versions():
 with connect(PLATFORM_DB) as db: return {'items':[dict(x) for x in db.execute('SELECT id,name,status,version,official,created_at FROM config_versions ORDER BY version DESC')]}
@app.get('/api/v1/admin/runtime-config')
def runtime_config_status():
 with connect(PLATFORM_DB) as db: row=db.execute("SELECT id,version,payload FROM config_versions WHERE status='PUBLISHED'").fetchone()
 config=json.loads(row['payload']); checks={}
 for mode in ('PHASE1_DEMO','PHASE2_DEMO','PHASE2_POC'):
  try: runtime=resolve_runtime(config,mode); checks[mode]={'ready':True,'policy':runtime.policy.__dict__}
  except RuntimeConfigError as exc: checks[mode]={'ready':False,'missing':exc.missing}
 return {'config_version_id':row['id'],'version':row['version'],'schema_version':config.get('runtime',{}).get('schema_version'),'checks':checks,'runtime':config.get('runtime',{})}
@app.post('/api/v1/admin/config/import',status_code=201)
def import_config(body:DraftIn):
 if len(body.payload.get('roles',[]))!=3 or len(body.payload.get('scenarios',[]))!=8: raise HTTPException(422,detail={'code':'INVALID_INPUT','message':'配置必须包含三个角色和八个场景'})
 return draft(body)
@app.post('/api/v1/admin/config/{cid}/rollback')
def rollback(cid:str):
 with connect(PLATFORM_DB) as db:
  x=db.execute("SELECT status FROM config_versions WHERE id=?",(cid,)).fetchone()
  if not x or x['status'] not in ('ARCHIVED','DISABLED'): raise HTTPException(409,detail={'code':'INVALID_INPUT','message':'仅已归档或停用版本可回滚'})
  db.execute("UPDATE config_versions SET status='ARCHIVED' WHERE status='PUBLISHED'"); db.execute("UPDATE config_versions SET status='PUBLISHED' WHERE id=?",(cid,)); db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('ROLLBACK','admin',json.dumps({'id':cid}),now()))
 return {'id':cid,'status':'PUBLISHED','affects':'new_sessions_only'}
@app.get('/api/v1/admin/resources/{kind}')
def list_resources(kind:str):
 if kind not in ('roles','admin-access','user-access','assets','flows','scenes','scenarios','compliance','operations','models','datasources','providers','mock'): raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'资源类型无效'})
 with connect(PLATFORM_DB) as db: return {'items':[{**dict(x),'payload':json.loads(x['payload'])} for x in db.execute('SELECT * FROM admin_resources WHERE kind=? ORDER BY id',(kind,))]}
@app.put('/api/v1/admin/resources/{kind}/{rid}')
def save_resource(kind:str,rid:str,body:ResourceIn):
 if kind not in ('roles','admin-access','user-access','assets','flows','scenes','scenarios','compliance','operations','models','datasources','providers','mock') or rid!=body.id: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'资源类型或ID无效'})
 with connect(PLATFORM_DB) as db:
  db.execute('INSERT OR REPLACE INTO admin_resources VALUES(?,?,?,?,?)',(kind,rid,json.dumps(body.payload,ensure_ascii=False),int(body.enabled),now())); db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('SAVE_RESOURCE','admin',json.dumps({'kind':kind,'id':rid}),now()))
 return {'kind':kind,'id':rid,'saved_as':'DRAFT_RESOURCE'}
@app.delete('/api/v1/admin/resources/{kind}/{rid}')
def delete_resource(kind:str,rid:str):
 if kind not in ('roles','admin-access','user-access','assets','flows','scenes','scenarios','compliance','operations','models','datasources','providers','mock'): raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'资源类型无效'})
 with connect(PLATFORM_DB) as db:
  found=db.execute('DELETE FROM admin_resources WHERE kind=? AND id=?',(kind,rid)).rowcount
  if not found: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'资源不存在'})
  db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('DELETE_RESOURCE','admin',json.dumps({'kind':kind,'id':rid}),now()))
 return {'kind':kind,'id':rid,'deleted':True}
@app.get('/api/v1/admin/mock/warehouse')
def mock_warehouse_rows():
 with connect(WAREHOUSE_DB) as db: return {'items':[dict(x) for x in db.execute('SELECT * FROM dws_loan_aggr_wide ORDER BY stat_dt DESC,org_name')]}
@app.post('/api/v1/admin/backup')
def create_backup(): return {'path':str(backup(ROOT/'backups'/'phase1.zip').relative_to(ROOT))}
@app.post('/api/v1/admin/backup/restore')
def restore_last_backup(confirm:bool=False):
 if not confirm: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'恢复备份需要确认'})
 try: restore_backup(ROOT/'backups'/'phase1.zip')
 except (FileNotFoundError,ValueError): raise HTTPException(422,detail={'code':'INVALID_INPUT','message':'备份不存在或已损坏'})
 with connect(PLATFORM_DB) as db: db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('RESTORE_BACKUP','admin','{}',now()))
 return {'status':'ok','restored':'backups/phase1.zip'}
dist=ROOT/'frontend'/'dist'
@app.put('/api/v1/admin/mock/warehouse/{stat_dt}/{org_name}')
def save_mock_warehouse_row(stat_dt:str,org_name:str,body:MockRowIn):
 if stat_dt!=body.stat_dt or org_name!=body.org_name: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'日期或机构主键不一致'})
 with connect(WAREHOUSE_DB) as db: db.execute('INSERT OR REPLACE INTO dws_loan_aggr_wide VALUES(?,?,?,?,?,?,?,?)',(body.stat_dt,body.org_name,body.loan_cur,body.loan_last,body.retail_cur,body.retail_last,body.corporate_cur,body.corporate_last))
 with connect(PLATFORM_DB) as db: db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('SAVE_MOCK_ROW','admin',json.dumps({'stat_dt':stat_dt,'org_name':org_name},ensure_ascii=False),now()))
 return {'saved':True,'stat_dt':stat_dt,'org_name':org_name}
@app.delete('/api/v1/admin/mock/warehouse/{stat_dt}/{org_name}')
def delete_mock_warehouse_row(stat_dt:str,org_name:str):
 with connect(WAREHOUSE_DB) as db:
  if not db.execute('DELETE FROM dws_loan_aggr_wide WHERE stat_dt=? AND org_name=?',(stat_dt,org_name)).rowcount: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'模拟数据不存在'})
 with connect(PLATFORM_DB) as db: db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('DELETE_MOCK_ROW','admin',json.dumps({'stat_dt':stat_dt,'org_name':org_name},ensure_ascii=False),now()))
 return {'deleted':True}
@app.post('/api/v1/admin/resources/publish')
def publish_resources():
 with connect(PLATFORM_DB) as db:
  cfg=json.loads(db.execute("SELECT payload FROM config_versions WHERE status='PUBLISHED'").fetchone()[0]); resources=[{**dict(x),'payload':json.loads(x['payload'])} for x in db.execute('SELECT * FROM admin_resources WHERE enabled=1')]; by_page={}
  for item in resources: by_page.setdefault(item['payload'].get('__page',''),[]).append(item)
  if by_page.get('metrics'): cfg['assets']['metrics']=[x['payload'].get('指标名称',x['id']) for x in by_page['metrics']]
  if by_page.get('dimensions'): cfg['assets']['dimensions']=[x['payload'].get('维度名称',x['id']) for x in by_page['dimensions']]
  if by_page.get('recommendations'):
   rec={}
   for x in by_page['recommendations']: rec.setdefault(x['payload'].get('角色','admin'),[]).append(x['payload'].get('推荐问句',''))
   cfg['assets']['recommendations']=rec
  if by_page.get('mock-scenes'):
   cfg['scenario_overrides']={}
   for x in by_page['mock-scenes']:
    try: cfg['scenario_overrides'][x['payload'].get('场景')]=json.loads(x['payload'].get('覆盖配置JSON') or '{}')
    except json.JSONDecodeError: raise HTTPException(422,detail={'code':'INVALID_INPUT','message':'场景覆盖配置JSON无效'})
  if by_page.get('intercept-wording'): cfg.setdefault('compliance',{})['intercept_message']=by_page['intercept-wording'][0]['payload'].get('提示文案')
  if by_page.get('classified'): cfg.setdefault('compliance',{})['sensitive_words']=[w for x in by_page['classified'] for w in str(x['payload'].get('对象值','')).split('|') if w]
  if by_page.get('client-roles'):
   cfg['roles']=[{'id':x['id'],'name':x['payload'].get('角色名称',x['payload'].get('名称',x['id'])),'orgs':[v.strip() for v in str(x['payload'].get('机构权限池','')).split(',') if v.strip()],'metrics':[v.strip() for v in str(x['payload'].get('指标权限池','')).split(',') if v.strip()],'features':[v.strip() for v in str(x['payload'].get('功能权益',x['payload'].get('功能权限',''))).split(',') if v.strip()]} for x in by_page['client-roles']]
  cfg['runtime']=publish_runtime(cfg.get('runtime',{}),by_page)
  version=db.execute('SELECT COALESCE(MAX(version),0)+1 FROM config_versions').fetchone()[0]; cid=str(uuid.uuid4()); db.execute('INSERT INTO config_versions VALUES(?,?,?,?,?,?,?)',(cid,'后台资源发布','DRAFT',version,json.dumps(cfg,ensure_ascii=False),0,now())); db.execute("UPDATE config_versions SET status='ARCHIVED' WHERE status='PUBLISHED'"); db.execute("UPDATE config_versions SET status='PUBLISHED' WHERE id=?",(cid,))
  for role in cfg.get('roles',[]): db.execute('INSERT OR REPLACE INTO roles VALUES(?,?,1,?)',(role['id'],role['name'],json.dumps(role,ensure_ascii=False)))
  db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('PUBLISH_RESOURCES','admin',json.dumps({'id':cid,'pages':list(by_page)},ensure_ascii=False),now()))
 return {'id':cid,'version':version,'status':'PUBLISHED','affects':'new_sessions_only','pages':list(by_page)}
if dist.exists():
 @app.get('/admin',include_in_schema=False)
 @app.get('/admin/{path:path}',include_in_schema=False)
 def admin_spa(path:str=''): return FileResponse(dist/'index.html')
 app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')

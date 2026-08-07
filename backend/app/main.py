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
from .credentials import CredentialError,encrypt_secret
from .models import PipelineContext
from .phase2_service import build_registry,public_profile
from .providers.phase2 import network_diagnostics
now=lambda:datetime.now(timezone.utc).isoformat()
app=FastAPI(title='AskData Phase 1 + Phase 2',version='2.0.0'); engine=Engine(); active_engines={}
class SessionIn(BaseModel): role_id:str=Field(pattern='^(admin|beijing|retail)$'); execution_mode:str=Field(default='PHASE1_DEMO',pattern='^(PHASE1_DEMO|PHASE2_DEMO|PHASE2_POC)$'); provider_profile_id:str|None=None
class QueryIn(BaseModel): session_id:str; question:str=Field(min_length=1,max_length=1000); scenario_id:str|None=None; parent_request_id:str|None=None
class DraftIn(BaseModel): name:str; payload:dict
class ResourceIn(BaseModel): id:str=Field(min_length=1,max_length=100); payload:dict; enabled:bool=True
class ProviderProfileIn(BaseModel):
 name:str=Field(min_length=1,max_length=100); datasource_type:str=Field(pattern='^(CLICKHOUSE|MYSQL)$')
 model_base_url:str; model:str; model_api_key:str=Field(min_length=1)
 datasource_url:str|None=None; datasource_host:str|None=None; datasource_port:int=3306; datasource_tls:bool=True; datasource_username:str; datasource_password:str=Field(min_length=1); database:str
 allowed_tables:list[str]=Field(min_length=1); max_rows:int=Field(default=1000,ge=1,le=10000); max_time_range_days:int=Field(default=366,ge=1,le=3660); timeout:float=Field(default=30,ge=1,le=120); retries:int=Field(default=2,ge=0,le=5); backoff:float=Field(default=.25,ge=0,le=10); max_concurrency:int=Field(default=4,ge=1,le=32)
@app.on_event('startup')
def startup():
 migrate()
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
  if body.execution_mode.startswith('PHASE2'):
   profile=db.execute("SELECT 1 FROM phase2_provider_profiles WHERE id=? AND status='ENABLED'",(body.provider_profile_id,)).fetchone()
   if not profile: raise HTTPException(409,detail={'code':'INVALID_INPUT','message':'Provider Profile 未启用'})
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
  ctx=json.loads(s['context']); phase2=db.execute('SELECT * FROM phase2_session_profiles WHERE session_id=?',(body.session_id,)).fetchone(); mode=phase2['execution_mode'] if phase2 else 'POC'
  version=db.execute('SELECT payload FROM config_versions WHERE id=?',(s['config_version_id'],)).fetchone(); config=json.loads(version[0]); permissions=json.loads(s['permission_snapshot'])
  db.execute('INSERT INTO requests(id,session_id,parent_request_id,trace_id,scenario_id,question,mode,status,config_version_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,body.session_id,body.parent_request_id,trace,body.scenario_id,body.question,mode,'PENDING',s['config_version_id'],now()))
 c=PipelineContext(body.session_id,rid,s['role_id'],s['config_version_id'],body.question,body.parent_request_id,body.scenario_id,mode=mode,parameters=ctx,permissions=permissions,config=config)
 selected_engine=Engine(build_registry(phase2['profile_id'])) if phase2 else engine; active_engines[rid]=selected_engine
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
 allowed={'requests':'requests','sessions':'sessions','sql':'sql_executions','audit':'audit_logs'}; table=allowed.get(kind)
 if not table: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'日志类型无效'})
 with connect(PLATFORM_DB) as db:
  rows=db.execute(f'SELECT * FROM {table}'+(' WHERE status=?' if status and table=='requests' else '')+' ORDER BY rowid DESC LIMIT 200',((status,) if status and table=='requests' else ())).fetchall()
 return {'items':[dict(x) for x in rows]}
@app.get('/api/v1/admin/readiness')
async def readiness():
 b=json.loads(BASELINE.read_text()); return {'ready':len(b['roles'])==3 and len(b['scenarios'])==8 and PLATFORM_DB.exists(),'roles':len(b['roles']),'scenarios':len(b['scenarios']),'providers':{'mock':await engine.registry.model.health_check(),'sqlite':await engine.registry.datasource.health_check()}}
@app.post('/api/v1/admin/providers/{kind}/test')
def provider_test(kind:str): return engine.registry.status(kind.upper())
@app.get('/api/v1/admin/phase2/providers')
def phase2_profiles():
 with connect(PLATFORM_DB) as db: return {'items':[public_profile(x) for x in db.execute('SELECT * FROM phase2_provider_profiles ORDER BY created_at DESC')]}
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
 if kind not in ('roles','assets','flows','scenarios','compliance','operations'): raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'资源类型无效'})
 with connect(PLATFORM_DB) as db: return {'items':[{**dict(x),'payload':json.loads(x['payload'])} for x in db.execute('SELECT * FROM admin_resources WHERE kind=? ORDER BY id',(kind,))]}
@app.put('/api/v1/admin/resources/{kind}/{rid}')
def save_resource(kind:str,rid:str,body:ResourceIn):
 if kind not in ('roles','assets','flows','scenarios','compliance','operations') or rid!=body.id: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'资源类型或ID无效'})
 with connect(PLATFORM_DB) as db:
  db.execute('INSERT OR REPLACE INTO admin_resources VALUES(?,?,?,?,?)',(kind,rid,json.dumps(body.payload,ensure_ascii=False),int(body.enabled),now())); db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('SAVE_RESOURCE','admin',json.dumps({'kind':kind,'id':rid}),now()))
 return {'kind':kind,'id':rid,'saved_as':'DRAFT_RESOURCE'}
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
if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')

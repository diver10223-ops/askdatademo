import asyncio,json,os,uuid
from datetime import datetime,timezone
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import StreamingResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .config import PLATFORM_DB,BASELINE,ROOT
from .db import connect,restore_baseline,restore_official_config,migrate,backup,full_reset
from .engine import Engine
from .models import PipelineContext
now=lambda:datetime.now(timezone.utc).isoformat()
app=FastAPI(title='AskData Phase 1',version='1.0.0'); engine=Engine()
class SessionIn(BaseModel): role_id:str=Field(pattern='^(admin|beijing|retail)$')
class QueryIn(BaseModel): session_id:str; question:str=Field(min_length=1,max_length=1000); scenario_id:str|None=None; parent_request_id:str|None=None
class DraftIn(BaseModel): name:str; payload:dict
def validate_config(payload:dict):
 roles=payload.get('roles'); scenarios=payload.get('scenarios')
 if not isinstance(roles,list) or not roles: raise HTTPException(422,detail={'code':'INVALID_CONFIG','message':'配置必须包含角色'})
 role_ids={r.get('id') for r in roles}; required={'admin','beijing','retail'}
 if role_ids!=required: raise HTTPException(422,detail={'code':'INVALID_CONFIG','message':'一期必须完整包含 admin、beijing、retail 三个角色'})
 if not isinstance(scenarios,list) or len(scenarios)!=8: raise HTTPException(422,detail={'code':'INVALID_CONFIG','message':'一期必须包含八个标准场景'})
 if len({s.get('id') for s in scenarios})!=8 or len({s.get('number') for s in scenarios})!=8: raise HTTPException(422,detail={'code':'INVALID_CONFIG','message':'场景 ID 和编号必须唯一'})
 assets=payload.get('assets',{})
 if not all(isinstance(assets.get(k),list) and assets[k] for k in ('metrics','dimensions')): raise HTTPException(422,detail={'code':'INVALID_CONFIG','message':'指标和维度字典不能为空'})
 if assets.get('table')!='dws_loan_aggr_wide': raise HTTPException(422,detail={'code':'INVALID_CONFIG','message':'一期仅允许官方只读模拟宽表'})
 template=assets.get('sql_template',''); normalized=template.strip().upper()
 if not normalized.startswith('SELECT ') or any(token in normalized for token in (';',' INSERT ',' UPDATE ',' DELETE ',' DROP ',' ALTER ',' ATTACH ',' PRAGMA ')) or not all(token in template for token in ('{metric}',':org',':date')): raise HTTPException(422,detail={'code':'INVALID_CONFIG','message':'SQL 模板必须是单条只读 SELECT，并包含指标、机构和日期参数'})
 for scene in scenarios:
  cases=scene.get('cases',[]); covered={case.get('role_id') for case in cases}
  if covered!=required: raise HTTPException(422,detail={'code':'INVALID_CONFIG','message':f"场景 {scene.get('id')} 缺少角色用例"})
  for case in cases:
   turns=case.get('turns',[])
   if not turns or [t.get('turn') for t in turns]!=list(range(1,len(turns)+1)) or any(not t.get('question') or t.get('expected_last_layer') not in {f'L{i}' for i in range(1,8)} or t.get('expected_status') not in {'SUCCEEDED','SHORT_CIRCUITED','BLOCKED','WAITING_INPUT'} for t in turns): raise HTTPException(422,detail={'code':'INVALID_CONFIG','message':f"用例 {case.get('id')} 的轮次、问句、状态或终止层无效"})
 return payload
@app.on_event('startup')
def startup(): restore_baseline(False)
@app.get('/api/v1/health')
def health(): return {'status':'ok','version':'1.0.0','platform_db':PLATFORM_DB.exists()}
@app.post('/api/v1/sessions',status_code=201)
def create_session(body:SessionIn):
 sid=str(uuid.uuid4()); ps=str(uuid.uuid4())
 with connect(PLATFORM_DB) as db:
  role=db.execute('SELECT permissions FROM roles WHERE id=? AND enabled=1',(body.role_id,)).fetchone()
  if not role: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'角色不存在或已停用'})
  cfg=db.execute("SELECT id FROM config_versions WHERE status='PUBLISHED'").fetchone()
  db.execute('INSERT INTO sessions(id,role_id,permission_snapshot_id,permission_snapshot,config_version_id,created_at) VALUES(?,?,?,?,?,?)',(sid,body.role_id,ps,role[0],cfg[0],now()))
 return {'id':sid,'role_id':body.role_id,'config_version_id':cfg[0]}
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
  ctx=json.loads(s['context']); permissions=json.loads(s['permission_snapshot']); version=db.execute('SELECT payload FROM config_versions WHERE id=?',(s['config_version_id'],)).fetchone(); config=json.loads(version['payload'])
  db.execute('INSERT INTO requests(id,session_id,parent_request_id,trace_id,scenario_id,question,mode,status,config_version_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,body.session_id,body.parent_request_id,trace,body.scenario_id,body.question,'POC','PENDING',s['config_version_id'],now()))
 c=PipelineContext(body.session_id,rid,s['role_id'],s['config_version_id'],body.question,body.parent_request_id,body.scenario_id,parameters=ctx,permissions=permissions,config=config)
 asyncio.create_task(engine.run(c)); return {'request_id':rid,'trace_id':trace,'status':'PENDING'}
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
def cancel(rid:str):
 with connect(PLATFORM_DB) as db:
  q=db.execute('SELECT status,cancel_requested FROM requests WHERE id=?',(rid,)).fetchone()
  if not q: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'请求不存在'})
  if q['status'] in ('SUCCEEDED','FAILED','BLOCKED','SHORT_CIRCUITED','WAITING_INPUT','CANCELLED'): return {'request_id':rid,'status':q['status'],'idempotent':True}
  db.execute('UPDATE requests SET cancel_requested=1,cancelled_by=?,cancelled_at=? WHERE id=?',('demo-user',now(),rid))
 return {'request_id':rid,'status':'CANCELLATION_REQUESTED'}
@app.get('/api/v1/admin/baseline')
def baseline():
 with connect(PLATFORM_DB) as db: current=db.execute("SELECT payload FROM config_versions WHERE status='PUBLISHED'").fetchone()
 return json.loads(current['payload']) if current else json.loads(BASELINE.read_text())
@app.get('/api/v1/admin/logs')
def logs(kind:str='requests',status:str|None=None):
 allowed={'requests':'requests','sessions':'sessions','sql':'sql_executions','audit':'audit_logs'}; table=allowed.get(kind)
 if not table: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'日志类型无效'})
 with connect(PLATFORM_DB) as db:
  rows=db.execute(f'SELECT * FROM {table}'+(' WHERE status=?' if status and table=='requests' else '')+' ORDER BY rowid DESC LIMIT 200',((status,) if status and table=='requests' else ())).fetchall()
 return {'items':[dict(x) for x in rows]}
@app.get('/api/v1/admin/logs/{kind}/{item_id}')
def log_detail(kind:str,item_id:str):
 allowed={'requests':('requests','id'),'sessions':('sessions','id'),'sql':('sql_executions','id'),'audit':('audit_logs','id')}; target=allowed.get(kind)
 if not target: raise HTTPException(400,detail={'code':'INVALID_INPUT','message':'日志类型无效'})
 with connect(PLATFORM_DB) as db: row=db.execute(f'SELECT * FROM {target[0]} WHERE {target[1]}=?',(item_id,)).fetchone()
 if not row: raise HTTPException(404,detail={'code':'ASSET_NOT_FOUND','message':'日志不存在'})
 detail=dict(row)
 if kind=='requests': detail['trace']=query_detail(item_id)
 return detail
@app.get('/api/v1/admin/config/versions')
def config_versions():
 with connect(PLATFORM_DB) as db: rows=db.execute('SELECT id,name,status,version,official,created_at FROM config_versions ORDER BY version DESC').fetchall()
 return {'items':[dict(row) for row in rows]}
@app.get('/api/v1/admin/readiness')
async def readiness():
 b=baseline(); return {'ready':len(b['roles'])==3 and len(b['scenarios'])==8 and PLATFORM_DB.exists(),'roles':len(b['roles']),'scenarios':len(b['scenarios']),'providers':{'mock':await engine.registry.model.health_check(),'sqlite':await engine.registry.datasource.health_check()}}
@app.post('/api/v1/admin/providers/{kind}/test')
def provider_test(kind:str): return engine.registry.status(kind.upper())
@app.post('/api/v1/admin/config/drafts',status_code=201)
def draft(body:DraftIn):
 validate_config(body.payload)
 with connect(PLATFORM_DB) as db:
  version=db.execute('SELECT COALESCE(MAX(version),0)+1 FROM config_versions').fetchone()[0]; cid=str(uuid.uuid4()); db.execute('INSERT INTO config_versions VALUES(?,?,?,?,?,?,?)',(cid,body.name,'DRAFT',version,json.dumps(body.payload,ensure_ascii=False),0,now())); db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('CREATE_DRAFT','admin',json.dumps({'id':cid}),now()))
 return {'id':cid,'version':version,'status':'DRAFT'}
@app.post('/api/v1/admin/config/{cid}/publish')
def publish(cid:str):
 with connect(PLATFORM_DB) as db:
  x=db.execute("SELECT status,payload FROM config_versions WHERE id=? AND official=0",(cid,)).fetchone()
  if not x or x['status']!='DRAFT': raise HTTPException(409,detail={'code':'INVALID_INPUT','message':'仅非官方草稿可发布'})
  payload=validate_config(json.loads(x['payload']))
  db.execute("UPDATE config_versions SET status='ARCHIVED' WHERE status='PUBLISHED'"); db.execute("UPDATE config_versions SET status='PUBLISHED' WHERE id=?",(cid,))
  for role in payload['roles']: db.execute('INSERT OR REPLACE INTO roles VALUES(?,?,?,?)',(role['id'],role['name'],int(role.get('enabled',True)),json.dumps(role,ensure_ascii=False)))
  db.execute('INSERT INTO audit_logs(action,actor,detail,created_at) VALUES(?,?,?,?)',('PUBLISH','admin',json.dumps({'id':cid,'affects':'new_sessions_only'}),now()))
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
@app.post('/api/v1/admin/backup')
def create_backup(): return {'path':str(backup(ROOT/'backups'/'phase1.zip').relative_to(ROOT))}
dist=ROOT/'frontend'/'dist'
if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')

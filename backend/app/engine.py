import asyncio,json,time
from datetime import datetime,timezone
from .db import connect
from .config import PLATFORM_DB
from .models import PipelineContext
from .providers import ProviderRegistry
from .layers import InteractionLayer,UnderstandingLayer,SemanticLayer,AssetLayer,QueryLayer,ExecutionLayer,InterpretationLayer
now=lambda:datetime.now(timezone.utc).isoformat()
class Engine:
 def __init__(self,registry=None):
  self.registry=registry or ProviderRegistry(); self.layers=[InteractionLayer(),UnderstandingLayer(self.registry),SemanticLayer(),AssetLayer(),QueryLayer(),ExecutionLayer(self.registry),InterpretationLayer(self.registry)]
 def event(self,c,event_type,payload):
  with connect(PLATFORM_DB) as db:
   n=db.execute('SELECT COALESCE(MAX(event_id),0)+1 FROM sse_events WHERE request_id=?',(c.request_id,)).fetchone()[0]
   db.execute('INSERT INTO sse_events VALUES(?,?,?,?,?)',(c.request_id,n,event_type,json.dumps(payload,ensure_ascii=False),now()))
 async def run(self,c):
  with connect(PLATFORM_DB) as db: db.execute("UPDATE requests SET status='RUNNING' WHERE id=? AND status='PENDING'",(c.request_id,))
  self.event(c,'request.created',{'request_id':c.request_id})
  for layer in self.layers:
   with connect(PLATFORM_DB) as db:
    cancelled=db.execute('SELECT cancel_requested FROM requests WHERE id=?',(c.request_id,)).fetchone()[0]
    if not cancelled:
     inp={'question':c.question,'parameters':c.parameters}; db.execute('INSERT INTO layer_executions(request_id,layer_code,status,input_json) VALUES(?,?,?,?)',(c.request_id,layer.layer_code,'STARTED',json.dumps(inp,ensure_ascii=False)))
   if cancelled:
    await self.registry.datasource.cancel(c.request_id); c.status='CANCELLED'; c.termination_reason='CANCELLED'; self.event(c,'request.cancelled',{'layer':layer.layer_code}); break
   self.event(c,'layer.started',{'layer_code':layer.layer_code,'layer_name':layer.layer_name}); start=time.perf_counter()
   try: result=await layer.execute(c)
   except Exception as exc: result=type('R',(),{'status':'FAILED','output':{'message':'执行失败'},'stop':True,'error_code':'EXECUTION_FAILED'})()
   elapsed=(time.perf_counter()-start)*1000
   with connect(PLATFORM_DB) as db:
    provider=('OPENAI_COMPATIBLE' if getattr(self.registry,'phase',1)==2 else 'MOCK') if layer.layer_code in ('L2','L7') else (type(self.registry.datasource).__name__ if layer.layer_code=='L6' else 'DETERMINISTIC')
    db.execute('UPDATE layer_executions SET status=?,output_json=?,provider=?,elapsed_ms=?,error_code=? WHERE request_id=? AND layer_code=?',(result.status,json.dumps(result.output,ensure_ascii=False),provider,elapsed,result.error_code,c.request_id,layer.layer_code))
    if layer.layer_code=='L6':
     for i,p in enumerate(c.sql_plan,1): db.execute('INSERT INTO sql_executions(request_id,sequence,business_sql,actual_sql,parameters,source,status,row_count,elapsed_ms,error,fallback) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(c.request_id,i,p['business_sql'],p['actual_sql'],json.dumps(p['parameters'],ensure_ascii=False),p['source'],p.get('execution_status','SUCCEEDED'),len(c.results),elapsed,p.get('error_type'),1 if p.get('fallback_reason') else 0))
   self.event(c,'layer.completed',{'layer_code':layer.layer_code,'status':result.status,'output':result.output})
   if result.stop: c.status=result.status; c.termination_reason=result.error_code or result.status; break
   c.status='SUCCEEDED'
   delay=max(0,min(3000,int(c.config.get('system',{}).get('simulation_speed',10))))/1000
   await asyncio.sleep(delay)
  with connect(PLATFORM_DB) as db:
   db.execute('UPDATE requests SET status=?,last_layer=?,termination_reason=?,completed_at=? WHERE id=?',(c.status,layer.layer_code,c.termination_reason,now(),c.request_id))
   if c.results:
    raw=json.dumps(c.results,ensure_ascii=False); db.execute('INSERT OR REPLACE INTO result_snapshots VALUES(?,?,?,?)',(c.request_id,raw,1,len(raw.encode())))
   if c.status=='SUCCEEDED': db.execute('UPDATE sessions SET context=? WHERE id=?',(json.dumps(c.parameters,ensure_ascii=False),c.session_id))
  self.event(c,'request.completed',{'status':c.status,'last_layer':layer.layer_code,'answer':c.answer})

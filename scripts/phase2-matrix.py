"""Phase 2 provider-backed 3-role x 8-scenario acceptance matrix."""
import asyncio, json, os, tempfile, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

os.environ['ASKDATA_DATA_DIR']=tempfile.mkdtemp(prefix='askdata-phase2-matrix-')
from app.config import PLATFORM_DB
from app.db import connect,restore_baseline
from app.engine import Engine
from app.models import PipelineContext
from app.providers.phase2 import ClickHouseProvider,OpenAICompatibleProvider,Phase2ProviderRegistry,RetryPolicy
from app.sql_security import SQLPolicy

class WireMock(BaseHTTPRequestHandler):
 def log_message(self,*_): pass
 def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b'{"data":[]}' if self.path.endswith('/models') else b'1\n')
 def do_POST(self):
  length=int(self.headers.get('content-length','0')); payload=self.rfile.read(length)
  if '/chat/completions' in self.path: body=json.dumps({'choices':[{'message':{'content':json.dumps({'answer':'Phase 2 provider interpretation'})}}]}).encode()
  else: body=json.dumps({'data':[{'org_name':'全行','stat_dt':'2026-03-31','current_value':980.5,'previous_value':900.0}]}).encode()
  self.send_response(200); self.end_headers(); self.wfile.write(body)

def main():
 restore_baseline(); server=ThreadingHTTPServer(('127.0.0.1',0),WireMock); Thread(target=server.serve_forever,daemon=True).start(); base=f'http://127.0.0.1:{server.server_port}'
 retry=RetryPolicy(2,0); registry=Phase2ProviderRegistry(OpenAICompatibleProvider(base,'test','model',retry),ClickHouseProvider(base,'u','p','default',SQLPolicy(frozenset({'dws_loan_aggr_wide'})),retry),'wire-profile'); engine=Engine(registry)
 baseline=json.loads((Path(__file__).parents[1]/'fixtures/official_baseline_v1.json').read_text()); checked=0
 try:
  for scenario in baseline['scenarios']:
   for case in scenario['cases']:
    sid=str(uuid.uuid4()); role=case['role_id']; permissions=next(x for x in baseline['roles'] if x['id']==role)
    with connect(PLATFORM_DB) as db: db.execute('INSERT INTO sessions(id,role_id,permission_snapshot_id,permission_snapshot,config_version_id,created_at) VALUES(?,?,?,?,?,?)',(sid,role,'p',json.dumps(permissions,ensure_ascii=False),'official-v1','now'))
    parent=None; context={}
    for turn in case['turns']:
     rid=str(uuid.uuid4())
     with connect(PLATFORM_DB) as db: db.execute('INSERT INTO requests(id,session_id,parent_request_id,trace_id,scenario_id,case_id,question,mode,status,config_version_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(rid,sid,parent,'t',scenario['id'],case['id'],turn['question'],'PHASE2_POC','PENDING','official-v1','now'))
     c=PipelineContext(sid,rid,role,'official-v1',turn['question'],parent,scenario['id'],case['id'],'PHASE2_POC',context.copy(),permissions=permissions,config=baseline); asyncio.run(engine.run(c))
     with connect(PLATFORM_DB) as db: request=db.execute('SELECT status,last_layer FROM requests WHERE id=?',(rid,)).fetchone(); context=json.loads(db.execute('SELECT context FROM sessions WHERE id=?',(sid,)).fetchone()[0])
     assert (request['status'],request['last_layer'])==(turn['expected_status'],turn['expected_last_layer']),(case['id'],turn['turn'],dict(request)); parent=rid; checked+=1
 finally: server.shutdown()
 print(f'OK: Phase 2 provider matrix, 3 roles x 8 scenarios x {checked} required turns')

if __name__=='__main__': main()

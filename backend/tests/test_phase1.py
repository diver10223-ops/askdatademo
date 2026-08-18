import asyncio,json,os,tempfile,uuid
from pathlib import Path
import pytest
os.environ['ASKDATA_DATA_DIR']=tempfile.mkdtemp()
from app.db import restore_baseline,connect
from app.config import PLATFORM_DB,WAREHOUSE_DB
from app.engine import Engine
from app.models import PipelineContext
from app.main import app
from fastapi.testclient import TestClient

def setup_module(): restore_baseline()
def seed_session(role='admin'):
 with connect(PLATFORM_DB) as c: c.execute("INSERT INTO sessions VALUES('s',?,'p','{}','official-v1','{}',1,'now')",(role,))
def test_databases_separate_and_idempotent():
 restore_baseline(); restore_baseline();
 with connect(WAREHOUSE_DB) as c: assert c.execute('select count(*) from dws_loan_aggr_wide').fetchone()[0]==3
 with connect(PLATFORM_DB) as c: assert not c.execute("select 1 from sqlite_master where name='dws_loan_aggr_wide'").fetchone()
def test_full_and_short_pipeline():
 seed_session(); e=Engine()
 with connect(PLATFORM_DB) as db: db.execute("INSERT INTO requests(id,session_id,trace_id,scenario_id,question,mode,status,config_version_id,created_at) VALUES('r','s','t','scenario-1','2026年3月全行贷款投放金额','POC','PENDING','official-v1','now')")
 asyncio.run(e.run(PipelineContext('s','r','admin','official-v1','2026年3月全行贷款投放金额',scenario_id='scenario-1')))
 with connect(PLATFORM_DB) as db: assert [x[0] for x in db.execute("select layer_code from layer_executions where request_id='r'")]==['L1','L2','L3','L4','L5','L6','L7']
 with connect(PLATFORM_DB) as db: db.execute("INSERT INTO requests(id,session_id,trace_id,scenario_id,question,mode,status,config_version_id,created_at) VALUES('r2','s','t2','scenario-5','身份证明细','POC','PENDING','official-v1','now')")
 asyncio.run(e.run(PipelineContext('s','r2','admin','official-v1','身份证明细',scenario_id='scenario-5')))
 with connect(PLATFORM_DB) as db: assert [x[0] for x in db.execute("select layer_code from layer_executions where request_id='r2'")]==['L1','L2']
def test_baseline_matrix():
 b=json.loads((Path(__file__).parents[2]/'fixtures/official_baseline_v1.json').read_text()); assert len(b['roles'])==3 and len(b['scenarios'])==8 and all(len(s['cases'])==3 for s in b['scenarios'])

def test_layers_use_session_config_and_permission_snapshot():
 from app.layers.l2_understanding import UnderstandingLayer
 from app.layers.l3_semantic import SemanticLayer
 config={'assets':{'recommendations':{'beijing':['自定义推荐']},'dashboard':'builtin://custom'},'compliance':{'sensitive_words':['机密指标'],'intercept_message':'自定义拦截'}}
 denied=PipelineContext('s','x','beijing','v2','查询上海分行贷款',permissions={'orgs':['北京分行'],'metrics':['贷款投放']},config=config)
 result=asyncio.run(UnderstandingLayer().execute(denied)); assert result.status=='BLOCKED' and result.error_code=='PERMISSION_DENIED'
 sensitive=PipelineContext('s','x','admin','v2','查询机密指标',permissions={'orgs':['全行'],'metrics':['贷款投放']},config=config)
 result=asyncio.run(UnderstandingLayer().execute(sensitive)); assert result.output['message']=='自定义拦截'
 dashboard=PipelineContext('s','x','beijing','v2','打开驾驶舱',config=config,scenario_id='scenario-2')
 result=asyncio.run(SemanticLayer().execute(dashboard)); assert result.output['url']=='builtin://custom'


def test_query_layer_uses_published_sql_template():
 from app.layers.l5_query import QueryLayer
 config={'assets':{'table':'dws_loan_aggr_wide','sql_template':'SELECT org_name, stat_dt, {metric} FROM dws_loan_aggr_wide WHERE org_name = :org AND stat_dt = :date ORDER BY org_name'}}
 context=PipelineContext('s','x','admin','v2','贷款',parameters={'metric':'loan_cur','org':'全行','date':'2026-03-31'},semantic_plan={'intent':'query'},config=config)
 result=asyncio.run(QueryLayer().execute(context))
 assert result.status=='SUCCEEDED' and context.sql_plan[0]['actual_sql'].endswith('ORDER BY org_name')


def test_org_comparison_followup_expands_authorized_orgs_and_queries_all_rows():
 from app.layers.l2_understanding import UnderstandingLayer
 from app.layers.l3_semantic import SemanticLayer
 from app.layers.l5_query import QueryLayer
 defaults=json.loads((Path(__file__).parents[2]/'fixtures'/'demo_runtime_defaults.json').read_text())
 permissions={'orgs':['全行','北京分行','上海分行'],'metrics':['贷款投放']}
 context=PipelineContext('s','x','admin','v2','按机构对比该指标',parameters={'metric':'loan_cur','org':'全行','date':'2026-03-31'},permissions=permissions,config={'runtime':defaults})
 asyncio.run(UnderstandingLayer().execute(context))
 asyncio.run(SemanticLayer().execute(context))
 result=asyncio.run(QueryLayer().execute(context))
 assert context.parameters['orgs']==['北京分行','上海分行']
 assert context.semantic_plan['intent']=='org_comparison'
 assert result.status=='SUCCEEDED' and 'IN (:org_0, :org_1)' in context.sql_plan[0]['actual_sql']
 assert context.sql_plan[0]['parameters']['org_1']=='上海分行'


def test_phase1_session_keeps_phase1_demo_mode():
 with TestClient(app) as client:
  session=client.post('/api/v1/sessions',json={'role_id':'admin','execution_mode':'PHASE1_DEMO'}).json()
  query=client.post('/api/v1/queries',json={'session_id':session['id'],'question':'2026年3月全行贷款投放金额','scenario_id':'scenario-1'}).json()
  with client.stream('GET',f"/api/v1/queries/{query['request_id']}/events") as response: ''.join(response.iter_text())
  detail=client.get(f"/api/v1/queries/{query['request_id']}").json()
  assert detail['request']['mode']=='PHASE1_DEMO'


@pytest.mark.parametrize(
 ('role','case_id','first_question','completion_question'),
 [
  ('admin','s7-admin','查询贷款投放同比数据','2026年3月，全行'),
  ('beijing','s7-beijing','查询贷款投放同比数据','2026年3月，北京分行'),
  ('retail','s7-retail','查询零售贷款同比数据','2026年3月，全行'),
 ],
)
def test_scenario7_waits_then_executes_for_each_role(role,case_id,first_question,completion_question):
 baseline=json.loads((Path(__file__).parents[2]/'fixtures/official_baseline_v1.json').read_text())
 permissions=next(item for item in baseline['roles'] if item['id']==role)
 session_id=f's7-session-{role}-{uuid.uuid4()}'
 first_id=f's7-first-{role}-{uuid.uuid4()}'
 second_id=f's7-second-{role}-{uuid.uuid4()}'
 with connect(PLATFORM_DB) as db:
  db.execute(
   'INSERT INTO sessions(id,role_id,permission_snapshot_id,permission_snapshot,config_version_id,created_at) VALUES(?,?,?,?,?,?)',
   (session_id,role,'p',json.dumps(permissions,ensure_ascii=False),'official-v1','now'),
  )
  db.execute(
   'INSERT INTO requests(id,session_id,trace_id,scenario_id,case_id,question,mode,status,config_version_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
   (first_id,session_id,'trace-first','scenario-7',case_id,first_question,'POC','PENDING','official-v1','now'),
  )
 engine=Engine()
 asyncio.run(engine.run(PipelineContext(
  session_id,first_id,role,'official-v1',first_question,
  scenario_id='scenario-7',case_id=case_id,permissions=permissions,config=baseline,
 )))
 with connect(PLATFORM_DB) as db:
  first=db.execute('SELECT status,last_layer FROM requests WHERE id=?',(first_id,)).fetchone()
  first_layers=[row[0] for row in db.execute('SELECT layer_code FROM layer_executions WHERE request_id=? ORDER BY id',(first_id,))]
  first_sql_count=db.execute('SELECT COUNT(*) FROM sql_executions WHERE request_id=?',(first_id,)).fetchone()[0]
  session_context=json.loads(db.execute('SELECT context FROM sessions WHERE id=?',(session_id,)).fetchone()[0])
  db.execute(
   'INSERT INTO requests(id,session_id,parent_request_id,trace_id,scenario_id,case_id,question,mode,status,config_version_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
   (second_id,session_id,first_id,'trace-second','scenario-7',case_id,completion_question,'POC','PENDING','official-v1','now'),
  )
 assert (first['status'],first['last_layer'])==('WAITING_INPUT','L2')
 assert first_layers==['L1','L2']
 assert first_sql_count==0
 assert session_context['metric']==('retail_cur' if role=='retail' else 'loan_cur')
 asyncio.run(engine.run(PipelineContext(
  session_id,second_id,role,'official-v1',completion_question,first_id,
  'scenario-7',case_id,'POC',session_context,permissions=permissions,config=baseline,
 )))
 with connect(PLATFORM_DB) as db:
  second=db.execute('SELECT status,last_layer,parent_request_id FROM requests WHERE id=?',(second_id,)).fetchone()
  second_layers=[row[0] for row in db.execute('SELECT layer_code FROM layer_executions WHERE request_id=? ORDER BY id',(second_id,))]
  second_sql_count=db.execute('SELECT COUNT(*) FROM sql_executions WHERE request_id=?',(second_id,)).fetchone()[0]
 assert (second['status'],second['last_layer'],second['parent_request_id'])==('SUCCEEDED','L7',first_id)
 assert second_layers==['L1','L2','L3','L4','L5','L6','L7']
 assert second_sql_count>=1

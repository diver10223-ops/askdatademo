import asyncio,json,os,tempfile
from pathlib import Path
os.environ['ASKDATA_DATA_DIR']=tempfile.mkdtemp()
from app.db import restore_baseline,connect
from app.config import PLATFORM_DB,WAREHOUSE_DB
from app.engine import Engine
from app.models import PipelineContext

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

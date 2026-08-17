import json
from app.config import PLATFORM_DB
from app.db import connect
from app.main import app
from fastapi.testclient import TestClient

def test_mt01_poc_vertical_slice_persists_plan_parallel_tasks_facts_and_evidence():
 with TestClient(app) as client:
  session=client.post('/api/v1/sessions',json={'role_id':'admin','execution_mode':'PHASE1_DEMO'}).json()
  accepted=client.post('/api/v1/queries',json={'session_id':session['id'],'question':'同时查询一季度贷款投放、存款余额、不良率和中收，并汇总同比','scenario_id':'MT01','execution_variant':'DEMO'}).json()
  request_id=accepted['request_id']
  with client.stream('GET',f'/api/v1/queries/{request_id}/events') as response:
   events=''.join(response.iter_text())
  detail=client.get(f'/api/v1/queries/{request_id}').json()
 assert detail['request']['status']=='SUCCEEDED'
 assert detail['plan']['plan']['maxConcurrency']==3
 assert len(detail['tasks'])==5
 assert [x['status'] for x in detail['tasks']].count('SUCCEEDED')==5
 assert len(detail['sql_executions'])==4
 assert len(detail['result'])==4
 assert 'event: task.started' in events and 'event: task.completed' in events
 assert detail['layers'][-1]['output']['completion']=='4/4'
 assert len(detail['layers'][-1]['output']['evidence'])==4
 q1=next(x for x in detail['tasks'] if x['code']=='Q1');q4=next(x for x in detail['tasks'] if x['code']=='Q4')
 from datetime import datetime
 assert (datetime.fromisoformat(q4['started_at'])-datetime.fromisoformat(q1['started_at'])).total_seconds()>=.8
 assert (datetime.fromisoformat(q4['completed_at'])-datetime.fromisoformat(q4['started_at'])).total_seconds()>=.5
 assert q4['depends_on']==['Q1']
 with connect(PLATFORM_DB) as db:
  assert db.execute('SELECT COUNT(*) FROM task_attempts').fetchone()[0]>=4
  assert db.execute('SELECT COUNT(*) FROM task_facts').fetchone()[0]>=4

def test_mt01_role_scope_changes_the_real_query_plan():
 with TestClient(app) as client:
  session=client.post('/api/v1/sessions',json={'role_id':'retail','execution_mode':'PHASE1_DEMO'}).json()
  accepted=client.post('/api/v1/queries',json={'session_id':session['id'],'question':'查询零售指标并汇总','scenario_id':'MT01','execution_variant':'DEMO'}).json()
  with client.stream('GET',f"/api/v1/queries/{accepted['request_id']}/events") as response: ''.join(response.iter_text())
  detail=client.get(f"/api/v1/queries/{accepted['request_id']}").json()
 assert detail['request']['status']=='SUCCEEDED'
 parameters=[x['parameters'] for x in detail['sql_executions']]
 assert {x['metric'] for x in parameters}=={'retail_loan_issue_amt','active_customer_count'}
 assert all(x['org']=='HQ' for x in parameters)

def test_v21_eight_scenarios_run_in_demo_and_poc_with_expected_terminal_states():
 expected={'MT01':'SUCCEEDED','MT02':'SUCCEEDED','MT03':'SUCCEEDED','MT04':'SUCCEEDED','MT05':'SUCCEEDED','MT06':'PARTIAL_SUCCESS','MT07':'FAILED','MT08':'SUCCEEDED'}
 with TestClient(app) as client:
  for variant in ('DEMO',):
   session=client.post('/api/v1/sessions',json={'role_id':'admin','execution_mode':'PHASE1_DEMO'}).json()
   for scenario,status in expected.items():
    accepted=client.post('/api/v1/queries',json={'session_id':session['id'],'question':f'{scenario} 标准问题','scenario_id':scenario,'execution_variant':variant}).json()
    if scenario=='MT03':
     import time
     for _ in range(50):
      plan=client.get(f"/api/v1/queries/{accepted['request_id']}").json().get('plan')
      if plan and plan['status']=='WAITING_CONFIRMATION': break
      time.sleep(.01)
     confirmed=client.post(f"/api/v1/queries/{accepted['request_id']}/confirm")
     assert confirmed.status_code==200
    with client.stream('GET',f"/api/v1/queries/{accepted['request_id']}/events") as response: events=''.join(response.iter_text())
    detail=client.get(f"/api/v1/queries/{accepted['request_id']}").json()
    assert detail['request']['status']==status,(variant,scenario,detail['request'])
    assert detail['request']['mode']==f'V21_{variant}'
    assert detail['plan']['scenario_id']==scenario
    if scenario!='MT08': assert 'DEMO_FIXTURE' in {x['source'] for x in detail['sql_executions']}
    else: assert 'event: task.reused' in events
    if scenario=='MT03': assert 'event: plan.waiting_confirmation' in events and 'event: plan.confirmed' in events
    if scenario=='MT06': assert detail['layers'][-1]['output']['unverified']
    if scenario=='MT07': assert detail['request']['status']=='FAILED' and detail['layers'][-1]['output']['unverified']
 with connect(PLATFORM_DB) as db:
  assert db.execute("SELECT COUNT(*) FROM task_attempts a JOIN task_nodes n ON n.id=a.node_id JOIN task_plans p ON p.id=n.plan_id WHERE p.scenario_id='MT05' AND a.attempt_no=2").fetchone()[0]>=2

def test_mt04_real_request_cancellation_propagates_to_task_terminal_state():
 import time
 with TestClient(app) as client:
  session=client.post('/api/v1/sessions',json={'role_id':'admin','execution_mode':'PHASE1_DEMO'}).json()
  accepted=client.post('/api/v1/queries',json={'session_id':session['id'],'question':'长任务取消','scenario_id':'MT04','execution_variant':'DEMO'}).json()
  time.sleep(.08)
  cancelled=client.post(f"/api/v1/queries/{accepted['request_id']}/cancel").json()
  assert cancelled['status']=='CANCELLATION_REQUESTED'
  with client.stream('GET',f"/api/v1/queries/{accepted['request_id']}/events") as response: ''.join(response.iter_text())
  detail=client.get(f"/api/v1/queries/{accepted['request_id']}").json()
 assert detail['request']['status']=='CANCELLED'
 assert any(x['status']=='CANCELLED' and x['error_code']=='CANCELLED' for x in detail['tasks'])

def test_mt03_waits_for_explicit_confirmation_before_starting_tasks():
 import time
 with TestClient(app) as client:
  session=client.post('/api/v1/sessions',json={'role_id':'admin','execution_mode':'PHASE1_DEMO'}).json()
  accepted=client.post('/api/v1/queries',json={'session_id':session['id'],'question':'先看计划再执行','scenario_id':'MT03','execution_variant':'DEMO'}).json()
  for _ in range(50):
   detail=client.get(f"/api/v1/queries/{accepted['request_id']}").json()
   if detail.get('plan') and detail['plan']['status']=='WAITING_CONFIRMATION': break
   time.sleep(.01)
  assert detail['plan']['version']==1
  assert not any(x['status']=='RUNNING' for x in detail['tasks'])
  assert client.post(f"/api/v1/queries/{accepted['request_id']}/confirm").status_code==200
  with client.stream('GET',f"/api/v1/queries/{accepted['request_id']}/events") as response: events=''.join(response.iter_text())
  final=client.get(f"/api/v1/queries/{accepted['request_id']}").json()
 assert final['request']['status']=='SUCCEEDED'
 assert final['plan']['version']==2
 assert 'event: plan.waiting_confirmation' in events and 'event: plan.confirmed' in events

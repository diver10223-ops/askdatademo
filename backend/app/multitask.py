import asyncio,hashlib,json,time,uuid
from datetime import datetime,timezone
from .config import PLATFORM_DB,WAREHOUSE_DB
from .db import connect

now=lambda:datetime.now(timezone.utc).isoformat()

class Mt01Engine:
 """V2.1 MT01-MT08 executable Demo/POC scenario engine."""
 MAX_CONCURRENCY=3
 METRICS=(('loan_issue_amt','贷款投放',True),('deposit_balance','存款余额',True),('npl_ratio','不良率',True),('fee_income','中收',False))
 def __init__(self,variant='POC',registry=None):
  self.variant,self.registry=variant,registry
  self.confirmation=asyncio.Event()
  from pathlib import Path
  fixture=json.loads((Path(__file__).parents[2]/'fixtures/demo/v2.1/baseline.json').read_text())
  self.demo_facts={(x['org'],x['metric']):x for x in fixture['quarterlyFacts']}
 async def confirm(self):
  self.confirmation.set()
 async def cancel(self):
  self.confirmation.set()
 def event(self,c,event_type,payload):
  with connect(PLATFORM_DB) as db:
   event_id=db.execute('SELECT COALESCE(MAX(event_id),0)+1 FROM sse_events WHERE request_id=?',(c.request_id,)).fetchone()[0]
   db.execute('INSERT INTO sse_events VALUES(?,?,?,?,?)',(c.request_id,event_id,event_type,json.dumps(payload,ensure_ascii=False),now()))
 def layer(self,c,code,status,output,elapsed=0,provider=None):
  with connect(PLATFORM_DB) as db:
   default_provider='REAL_DATASOURCE' if code=='L6' and self.variant=='POC' else ('SQLITE' if code=='L6' else 'DETERMINISTIC')
   db.execute('INSERT OR REPLACE INTO layer_executions(request_id,layer_code,status,input_json,output_json,provider,elapsed_ms) VALUES(?,?,?,?,?,?,?)',(c.request_id,code,status,json.dumps({'question':c.question},ensure_ascii=False),json.dumps(output,ensure_ascii=False),provider or default_provider,elapsed))
  self.event(c,'layer.completed',{'layer_code':code,'status':status,'output':output})
 def create_plan(self,c,model_understanding=None):
  plan_id=str(uuid.uuid4()); scenario=c.scenario_id or 'MT01'
  if self.variant=='POC':
   rules=c.runtime.section('understanding'); assets=c.runtime.section('assets')
   labels={code:name for name,code in rules.get('metric_codes',{}).items()}
   allowed_metrics=set(c.permissions.get('metrics',labels.values()))
   codes=[code for code in assets.get('metric_fields',{}) if labels.get(code,code) in allowed_metrics]
   available=[(code,labels.get(code,code),True if len(codes)==1 else index<len(codes)-1) for index,code in enumerate(codes)]
   requested=[]
   for target in (model_understanding or {}).get('targets',[]):
    candidate=target.get('metric') if isinstance(target,dict) else target
    code=rules.get('metric_codes',{}).get(candidate,candidate)
    if code in assets.get('metric_fields',{}) and code not in requested: requested.append(code)
   metrics=[item for item in available if item[0] in requested] or available
   org=next((x for x in rules.get('organizations',[]) if x in c.question),None) or rules.get('default_org_by_role',{}).get(c.role_id)
   date=next((value for keyword,value in rules.get('date_values',{}).items() if keyword in c.question),None) or rules.get('default_date')
   if not org or not date or not metrics: raise RuntimeError('POC_TASK_PARAMETERS_UNAVAILABLE')
   if org not in set(c.permissions.get('orgs',[org])): raise PermissionError('POC_ORGANIZATION_PERMISSION_DENIED')
  else:
   org='BJ' if c.role_id=='beijing' else 'HQ'; date='2026Q1'
   metrics=self.METRICS if c.role_id!='retail' else (('retail_loan_issue_amt','零售贷款投放',True),('active_customer_count','活跃客户数',False))
  if scenario in ('MT02','MT05','MT07'): metrics=metrics[:3]
  if scenario=='MT08': metrics=metrics[:2]
  nodes=[]
  for i,(metric,name,critical) in enumerate(metrics):
   dependencies=['Q1'] if (scenario=='MT02' and i>0) or (scenario=='MT01' and i==3) else []
   nodes.append({'code':f'Q{i+1}','type':'SQL','name':name,'metric':metric,'critical':critical,'dependsOn':dependencies})
  nodes.append({'code':'S1','type':'SUMMARY','name':'统一口径汇总','critical':True,'dependsOn':[x['code'] for x in nodes]})
  plan={'scenarioId':scenario,'version':1,'maxConcurrency':self.MAX_CONCURRENCY,'organization':org,'variant':self.variant,'nodes':nodes}
  with connect(PLATFORM_DB) as db:
   db.execute('INSERT INTO task_plans VALUES(?,?,?,?,?,?,?,NULL)',(plan_id,c.request_id,plan['version'],'EXECUTING',scenario,json.dumps(plan,ensure_ascii=False),now()))
  self.event(c,'plan.created',{'planId':plan_id,'scenarioId':scenario,'taskCount':len(nodes)-1,'maxConcurrency':self.MAX_CONCURRENCY})
  for node in nodes:
   with connect(PLATFORM_DB) as db:
    db.execute('INSERT INTO task_nodes(id,plan_id,code,type,critical,status,depends_on,input_json) VALUES(?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),plan_id,node['code'],node['type'],node['critical'],'WAITING' if node['dependsOn'] else 'READY',json.dumps(node['dependsOn']),json.dumps({'org':org,'date':date,'metric':node.get('metric')},ensure_ascii=False)))
   self.event(c,'task.created',{'planId':plan_id,'code':node['code'],'type':node['type'],'name':node['name'],'dependsOn':node['dependsOn']})
  return plan_id,plan
 def reusable_facts(self,c,tasks):
  """Return same-session, same-config facts whose org/metric/date exactly match."""
  if c.scenario_id!='MT08': return {}
  with connect(PLATFORM_DB) as db:
   rows=db.execute('''SELECT f.id fact_id,f.payload,n.input_json,r.id request_id
    FROM task_facts f JOIN task_nodes n ON n.id=f.node_id JOIN task_plans p ON p.id=n.plan_id
    JOIN requests r ON r.id=p.request_id
    WHERE r.session_id=? AND r.id<>? AND r.config_version_id=? AND r.status IN ('SUCCEEDED','PARTIAL_SUCCESS')
    ORDER BY r.created_at DESC''',(c.session_id,c.request_id,c.config_version_id)).fetchall()
  wanted={(x['org'],x['metric'],x.get('date')) for x in tasks}; reusable={}
  for row in rows:
   inp=json.loads(row['input_json']); key=(inp.get('org'),inp.get('metric'),inp.get('date'))
   if key in wanted and key not in reusable: reusable[key]={'factId':row['fact_id'],'requestId':row['request_id'],'payload':json.loads(row['payload'])}
  return reusable
 async def query_node(self,c,plan_id,node,semaphore):
  async with semaphore:
   started=time.perf_counter(); node_id=node['id']; attempt_id=str(uuid.uuid4())
   with connect(PLATFORM_DB) as db:
    db.execute("UPDATE task_nodes SET status='RUNNING',started_at=? WHERE id=?",(now(),node_id)); db.execute("INSERT INTO task_attempts VALUES(?,?,1,'RUNNING',?,NULL,NULL)",(attempt_id,node_id,now()))
   self.event(c,'task.started',{'taskId':node_id,'code':node['code'],'name':node['name'],'runningLimit':self.MAX_CONCURRENCY})
   try:
    if node.get('reused'):
     payload=node['reused']['payload']; fact_id=str(uuid.uuid4()); digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
     with connect(PLATFORM_DB) as db:
      db.execute("UPDATE task_nodes SET status='SUCCEEDED',output_json=?,completed_at=? WHERE id=?",(json.dumps(payload,ensure_ascii=False),now(),node_id)); db.execute("UPDATE task_attempts SET status='SUCCEEDED',completed_at=? WHERE id=?",(now(),attempt_id)); db.execute('INSERT INTO task_facts VALUES(?,?,?,?,?,?,?)',(fact_id,node_id,attempt_id,json.dumps(payload,ensure_ascii=False),digest,payload['period'],now()))
     self.event(c,'task.reused',{'taskId':node_id,'code':node['code'],'status':'SUCCEEDED','factId':fact_id,'reusedFromFactId':node['reused']['factId'],'reusedFromRequestId':node['reused']['requestId'],'output':payload})
     self.event(c,'task.completed',{'taskId':node_id,'code':node['code'],'status':'SUCCEEDED','factId':fact_id,'output':payload,'reused':True})
     return {'node':node,'factId':fact_id,'payload':payload,'reusedFrom':node['reused']}
    mt01_duration={'Q1':.9,'Q2':.9,'Q3':1.5,'Q4':.6}.get(node['code'],.08)
    duration=mt01_duration if c.scenario_id=='MT01' else (8 if c.scenario_id=='MT04' else .08)
    waited=0
    while waited<duration:
     await asyncio.sleep(min(.1,duration-waited)); waited+=.1
     with connect(PLATFORM_DB) as db:
      if db.execute('SELECT cancel_requested FROM requests WHERE id=?',(c.request_id,)).fetchone()[0]: raise RuntimeError('CANCELLED')
    if c.scenario_id=='MT05' and node['code']=='Q2':
     with connect(PLATFORM_DB) as db:
      db.execute("UPDATE task_attempts SET status='FAILED',error_code='TASK_TIMEOUT',completed_at=? WHERE id=?",(now(),attempt_id))
     self.event(c,'task.retrying',{'taskId':node_id,'code':node['code'],'attempt':2,'reason':'TASK_TIMEOUT'})
     attempt_id=str(uuid.uuid4())
     with connect(PLATFORM_DB) as db: db.execute("INSERT INTO task_attempts VALUES(?,?,2,'RUNNING',?,NULL,NULL)",(attempt_id,node_id,now()))
    if c.scenario_id=='MT06' and not node['critical']: raise LookupError('NON_CRITICAL_SOURCE_TIMEOUT')
    if c.scenario_id=='MT07' and node['code']=='Q1': raise LookupError('CRITICAL_SOURCE_FAILURE')
    if self.variant=='DEMO':
     value=self.demo_facts.get((node['org'],node['metric'])); row={**value,'current_value':value['current'],'previous_value':value['previous'],'period':'2026Q1'} if value else None
    else:
     assets=c.runtime.section('assets'); mapping=assets.get('metric_fields',{}).get(node['metric'])
     if not mapping or not mapping.get('previous'): raise LookupError('POC_METRIC_MAPPING_NOT_PUBLISHED')
     columns=f"{mapping['current']} AS current_value, {mapping['previous']} AS previous_value"
     sql=assets['sql_templates']['query'].format(table=assets['table'],org_field=assets['org_field'],date_field=assets['date_field'],columns=columns)
     parameters={'org':node['org'],'date':node['date']}
     self.registry.datasource.set_request_id(f'{c.request_id}-{node["code"]}')
     found=await self.registry.datasource.execute(sql,parameters,c.permissions)
     actual_sql=getattr(self.registry.datasource,'last_security',{}).get('sql',sql)
     actual_parameters=getattr(self.registry.datasource,'last_parameters',parameters)
     row={**found[0],'org':node['org'],'metric':node['metric'],'period':node['date']} if found else None
    if not row: raise LookupError('MT01_FACT_NOT_FOUND')
    payload=dict(row); digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(); fact_id=str(uuid.uuid4())
    with connect(PLATFORM_DB) as db:
     db.execute("UPDATE task_nodes SET status='SUCCEEDED',output_json=?,completed_at=? WHERE id=?",(json.dumps(payload,ensure_ascii=False),now(),node_id)); db.execute("UPDATE task_attempts SET status='SUCCEEDED',completed_at=? WHERE id=?",(now(),attempt_id)); db.execute('INSERT INTO task_facts VALUES(?,?,?,?,?,?,?)',(fact_id,node_id,attempt_id,json.dumps(payload,ensure_ascii=False),digest,payload['period'],now()))
     db.execute('INSERT INTO sql_executions(request_id,sequence,business_sql,actual_sql,parameters,source,status,row_count,elapsed_ms,fallback) VALUES(?,?,?,?,?,?,?,?,?,0)',(c.request_id,node['sequence'],'查询已发布经营指标','' if self.variant=='DEMO' else actual_sql,json.dumps(({**actual_parameters,'metric':node['metric']} if self.variant=='POC' else {'org':node['org'],'date':node.get('date'),'metric':node['metric']}),ensure_ascii=False),'DEMO_FIXTURE' if self.variant=='DEMO' else 'REAL_DATASOURCE','SUCCEEDED',1,(time.perf_counter()-started)*1000))
    self.event(c,'task.completed',{'taskId':node_id,'code':node['code'],'status':'SUCCEEDED','factId':fact_id,'output':payload})
    return {'node':node,'factId':fact_id,'payload':payload}
   except Exception as exc:
    cancelled=str(exc)=='CANCELLED'; terminal='CANCELLED' if cancelled else 'FAILED'; code='CANCELLED' if cancelled else type(exc).__name__
    with connect(PLATFORM_DB) as db: db.execute("UPDATE task_nodes SET status=?,error_code=?,completed_at=? WHERE id=?",(terminal,code,now(),node_id)); db.execute("UPDATE task_attempts SET status=?,error_code=?,completed_at=? WHERE id=?",(terminal,code,now(),attempt_id))
    self.event(c,'task.completed',{'taskId':node_id,'code':node['code'],'status':terminal,'critical':node['critical']})
    return {'node':node,'error':code}
 async def run(self,c):
  with connect(PLATFORM_DB) as db: db.execute("UPDATE requests SET status='RUNNING' WHERE id=?",(c.request_id,))
  scenario=c.scenario_id or 'MT01'; self.event(c,'request.created',{'request_id':c.request_id,'scenario_id':scenario,'variant':self.variant})
  model_understanding=None
  if self.variant=='POC':
   if not self.registry: raise RuntimeError('V21_POC_PROVIDER_REQUIRED')
   with connect(PLATFORM_DB) as db: db.execute("UPDATE requests SET last_layer='L2' WHERE id=?",(c.request_id,))
   model_understanding=await self.registry.model.structured_generate('L2',{'question':c.question,'scenario_id':scenario,'allowed_task_capabilities':['SQL_QUERY','CONTROLLED_COMPUTE','AGGREGATE'],'_system_prompt':'你是银行问数任务理解器。只返回JSON对象，包含 normalized_question、targets 数组和execution_notes；不得生成SQL，不得虚构指标。'})
   if not isinstance(model_understanding,dict): raise RuntimeError('MODEL_OUTPUT_INVALID')
  plan_id,plan=self.create_plan(c,model_understanding)
  if scenario=='MT03':
   with connect(PLATFORM_DB) as db: db.execute("UPDATE task_plans SET status='WAITING_CONFIRMATION' WHERE id=?",(plan_id,))
   self.event(c,'plan.waiting_confirmation',{'planId':plan_id,'version':1,'reason':'SCENARIO_PREVIEW'})
   await self.confirmation.wait()
   with connect(PLATFORM_DB) as db:
    cancelled=db.execute('SELECT cancel_requested FROM requests WHERE id=?',(c.request_id,)).fetchone()[0]
    if not cancelled:
     plan['version']=2
     db.execute("UPDATE task_plans SET version=2,status='EXECUTING',plan_json=? WHERE id=?",(json.dumps(plan,ensure_ascii=False),plan_id))
   if cancelled:
    with connect(PLATFORM_DB) as db:
     db.execute("UPDATE task_nodes SET status='CANCELLED',error_code='CANCELLED',completed_at=? WHERE plan_id=? AND type='SQL'",(now(),plan_id)); db.execute("UPDATE task_nodes SET status='SKIPPED',error_code='UPSTREAM_CANCELLED',completed_at=? WHERE plan_id=? AND type='SUMMARY'",(now(),plan_id)); db.execute("UPDATE task_plans SET status='CANCELLED',completed_at=? WHERE id=?",(now(),plan_id)); db.execute("UPDATE requests SET status='CANCELLED',last_layer='L7',termination_reason='CANCELLED',completed_at=? WHERE id=?",(now(),c.request_id))
    c.answer='计划确认前已取消，本次未执行任何查询任务'; c.results=[]
    self.layer(c,'L6','CANCELLED',{'completed':0,'total':len(plan['nodes'])-1,'failed':0,'cancelled':True})
    self.layer(c,'L7','CANCELLED',{'answer':c.answer,'evidence':[],'unverified':[n['code'] for n in plan['nodes'] if n['type']=='SQL'],'completion':f"0/{len(plan['nodes'])-1}"})
    self.event(c,'request.completed',{'status':'CANCELLED','answer':c.answer,'planId':plan_id}); return
   self.event(c,'plan.confirmed',{'planId':plan_id,'version':2,'actor':'demo-user'})
  asset_name=c.runtime.section('assets').get('table') if self.variant=='POC' else 'v21_quarterly_fact'
  for code,output in [('L1',{'question':c.question}),('L2',model_understanding or {'targets':[n['name'] for n in plan['nodes'] if n['type']=='SQL'],'organization':plan['organization']}),('L3',{'planId':plan_id,'tasks':len(plan['nodes'])}),('L4',{'assets':[asset_name],'permissionChecked':True,'allowedMetrics':c.permissions.get('metrics',[])}),('L5',{'dag':plan['nodes'],'maxConcurrency':3})]: self.layer(c,code,'SUCCEEDED',output,provider=type(self.registry.model).__name__ if code=='L2' and self.registry else None)
  with connect(PLATFORM_DB) as db:
   rows=[dict(x) for x in db.execute("SELECT id,code,critical,input_json,depends_on FROM task_nodes WHERE plan_id=? AND type='SQL' ORDER BY code",(plan_id,))]
  named={n['code']:n for n in plan['nodes']}; tasks=[]
  for sequence,row in enumerate(rows,1):
   inp=json.loads(row.pop('input_json')); row['depends_on']=json.loads(row['depends_on']); tasks.append({**row,**inp,'name':named[row['code']]['name'],'sequence':sequence})
  semaphore=asyncio.Semaphore(self.MAX_CONCURRENCY)
  with connect(PLATFORM_DB) as db: db.execute("UPDATE requests SET last_layer='L6' WHERE id=?",(c.request_id,))
  reusable=self.reusable_facts(c,tasks)
  for node in tasks:
   key=(node['org'],node['metric'],node.get('date'))
   if key in reusable: node['reused']=reusable[key]
  completed_events={x['code']:asyncio.Event() for x in tasks}
  async def execute_with_dependencies(node):
   for dependency in node['depends_on']: await completed_events[dependency].wait()
   try: return await self.query_node(c,plan_id,node,semaphore)
   finally: completed_events[node['code']].set()
  outcomes=await asyncio.gather(*(execute_with_dependencies(node) for node in tasks))
  failures=[x for x in outcomes if x.get('error')]; facts=[x for x in outcomes if x.get('payload')]; critical_failed=any(x['node']['critical'] for x in failures)
  cancelled=any(x.get('error')=='CANCELLED' for x in failures)
  status='CANCELLED' if cancelled else ('FAILED' if critical_failed else ('PARTIAL_SUCCESS' if failures else 'SUCCEEDED'))
  summary=[{**x['payload'],'name':x['node']['name'],'changeRate':round((x['payload']['current_value']-x['payload']['previous_value'])/x['payload']['previous_value']*100,2)} for x in facts]
  summary_node=next(n for n in plan['nodes'] if n['type']=='SUMMARY')
  with connect(PLATFORM_DB) as db:
   db.execute("UPDATE task_nodes SET status=?,output_json=?,started_at=?,completed_at=? WHERE plan_id=? AND code='S1'",('SUCCEEDED' if status in ('SUCCEEDED','PARTIAL_SUCCESS') else 'SKIPPED',json.dumps(summary,ensure_ascii=False),now(),now(),plan_id)); db.execute('UPDATE task_plans SET status=?,completed_at=? WHERE id=?',('CANCELLED' if status=='CANCELLED' else 'COMPLETED',now(),plan_id)); db.execute('UPDATE requests SET status=?,last_layer=?,termination_reason=?,completed_at=? WHERE id=?',(status,'L7',None if status=='SUCCEEDED' else status,now(),c.request_id))
  self.layer(c,'L6',status,{'completed':len(facts),'total':len(tasks),'failed':len(failures),'parallelism':self.MAX_CONCURRENCY})
  answer='；'.join(f"{x['name']} {x['current_value']:g}，同比{x['changeRate']:+g}%" for x in summary)
  if scenario=='MT01' and summary:
   rising=[x for x in summary if x['changeRate']>=0]; falling=[x for x in summary if x['changeRate']<0]
   answer=f"已按你的要求完成{len(summary)}项指标的并行查询和统一口径汇总。"+('增长指标包括'+ '、'.join(f"{x['name']}（{x['changeRate']:+g}%）" for x in rising)+'。' if rising else '')+('下降指标为'+ '、'.join(f"{x['name']}（{x['changeRate']:+g}%）" for x in falling)+'。' if falling else '')+'各指标本期值、同期值和同比结果均来自成功执行事实，详见下表。'
  if scenario=='MT02': answer='串行下钻归因完成：'+answer
  if scenario=='MT03': answer='计划 v2 已确认并执行：'+answer
  if scenario=='MT04': answer=('任务已按用户指令取消。已停止未完成节点，不再生成正常完成结论' if cancelled else '长任务已完成并持续记录节点状态；本次未收到取消指令：'+answer)
  if scenario=='MT05': answer='失败节点已定点重试成功：'+answer
  if scenario=='MT06': answer=f'非关键节点失败，当前返回部分成功（{len(facts)}/{len(tasks)}）：'+answer
  if scenario=='MT07': answer='关键事实节点执行失败，系统已安全终止总体判断。已成功取得的节点结果仅保留为执行证据，不用于生成不完整的总体结论'
  if scenario=='MT08':
   reused_count=sum(1 for x in outcomes if x.get('reusedFrom')); new_count=len(tasks)-reused_count
   self.event(c,'plan.expanded',{'planId':plan_id,'reusedFactCount':reused_count,'newTaskCount':new_count,'reason':'MATCHED_SESSION_FACTS' if reused_count else 'NO_REUSABLE_PRIOR_FACT_IN_SESSION'})
   answer=(f'已完成本轮扩展计划，复用同会话且权限、配置、机构、指标和数据时点一致的事实 {reused_count} 项，新查询 {new_count} 项：' if reused_count else '已完成本轮扩展计划。当前会话没有可验证的上一轮执行事实，因此本轮任务全部重新查询，未宣称事实复用：')+answer
  if failures: answer+=f"。未核实任务：{len(failures)}项"
  used_l7_model=False
  if self.variant=='POC' and status not in ('FAILED','CANCELLED'):
   with connect(PLATFORM_DB) as db: db.execute("UPDATE requests SET last_layer='L7' WHERE id=?",(c.request_id,))
   generated=await self.registry.model.structured_generate('L7',{'question':c.question,'deterministic_summary':answer,'verified_facts':summary,'completion':f'{len(facts)}/{len(tasks)}','unverified':[x['node']['code'] for x in failures],'_system_prompt':'你是银行问数结果解读器。只返回JSON对象 {"answer":"..."}。只能引用 verified_facts，不得补充外部原因，不得省略未核实项。'})
   if not isinstance(generated,dict) or not isinstance(generated.get('answer'),str): raise RuntimeError('MODEL_OUTPUT_INVALID')
   answer=generated['answer']; used_l7_model=True
   if status=='PARTIAL_SUCCESS': answer+=f'。本次仅核实 {len(facts)}/{len(tasks)} 项任务，未核实项：'+ '、'.join(x['node']['code'] for x in failures)
  presentation={
   'MT01':{'title':'多指标并行查询与统一汇总','resultMode':'METRIC_SUMMARY','capability':'并行查询、依赖调度与成功事实汇总'},
   'MT02':{'title':'指标下降串行下钻与关联验证','resultMode':'SERIAL_ATTRIBUTION','capability':'前置事实、串行依赖与关联指标验证；当前发布资产未配置客户类型/机构贡献度明细'},
   'MT03':{'title':'计划预览、确认与受控执行','resultMode':'PLAN_CONFIRMATION','capability':'计划版本、执行前确认与确认后执行'},
   'MT04':{'title':'长任务进度与主动取消','resultMode':'LONG_RUNNING','capability':'节点状态、SSE进度与取消传播'},
   'MT05':{'title':'失败节点定点重试','resultMode':'RETRY','capability':'attempt 1失败、attempt 2重试与成功事实保留'},
   'MT06':{'title':'非关键节点失败与部分成功','resultMode':'PARTIAL_SUCCESS','capability':'仅汇总成功事实并披露完成度与未核实项'},
   'MT07':{'title':'关键节点失败与安全终止','resultMode':'SAFE_TERMINATION','capability':'关键事实缺失时禁止生成不完整总体判断'},
   'MT08':{'title':'多轮扩展计划与事实复用检查','resultMode':'PLAN_EXTENSION','capability':'检查上一轮事实；无可复用事实时明确重新查询'}
  }[scenario]
  c.answer=answer; c.results=summary; self.layer(c,'L7',status,{'answer':answer,'evidence':[{'factId':x['factId'],'taskCode':x['node']['code'],'reusedFromFactId':x.get('reusedFrom',{}).get('factId')} for x in facts],'unverified':[x['node']['code'] for x in failures],'completion':f'{len(facts)}/{len(tasks)}','presentation':presentation},provider=type(self.registry.model).__name__ if used_l7_model else ('SAFETY_POLICY' if self.variant=='POC' else None))
  with connect(PLATFORM_DB) as db:
   raw=json.dumps(summary,ensure_ascii=False); db.execute('INSERT OR REPLACE INTO result_snapshots(request_id,payload,masked,size_bytes,classification_level,expires_at) VALUES(?,?,?,?,?,?)',(c.request_id,raw,1,len(raw.encode()),'INTERNAL',now()))
  self.event(c,'request.completed',{'status':status,'answer':answer,'planId':plan_id})

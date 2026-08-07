from ..models import LayerResult
from ..runtime import runtime_for
class UnderstandingLayer:
 layer_code='L2'; layer_name='对话理解层'
 def __init__(self,registry=None): self.registry=registry
 async def execute(self,c):
  q=c.question; role=c.role_id; permissions=c.permissions or {}; runtime=runtime_for(c); compliance=runtime.section('compliance'); rules=runtime.section('understanding')
  model_output={}
  if self.registry and getattr(self.registry,'phase',1)==2:
   model_output=await self.registry.model.structured_generate('L2',{'question':q,'role':role,'scenario_id':c.scenario_id,'context':c.parameters,'_system_prompt':runtime.require('model_prompts.L2')})
  sensitive=compliance.get('sensitive_words',[])
  if any(x in q for x in sensitive): return LayerResult('BLOCKED',{'message':runtime.require('compliance.intercept_message')},True,'COMPLIANCE_BLOCKED')
  known_orgs=set(rules.get('organizations',[])); requested_org=next((x for x in known_orgs if x in q),None)
  if permissions and requested_org and requested_org not in permissions.get('orgs',[]): return LayerResult('BLOCKED',{'message':f'当前角色无权查询{requested_org}'},True,'PERMISSION_DENIED')
  metric_names=rules.get('metric_keywords',{}); requested_metric=next((v for k,v in metric_names.items() if k in q),None)
  if permissions and requested_metric and requested_metric not in permissions.get('metrics',[]): return LayerResult('BLOCKED',{'message':f'当前角色无权查询{requested_metric}'},True,'PERMISSION_DENIED')
  if c.scenario_id==rules.get('ambiguous_scenario') or ('相关数据' in q and '投放金额' not in q):
   rec=c.config.get('assets',{}).get('recommendations',{}).get(role,[])
   return LayerResult('SHORT_CIRCUITED',{'recommendations':rec[:3],'message':rules.get('recommendation_message','请选择更明确的合规问句')},True,'AMBIGUOUS_RECOMMENDATION')
  inherited=c.parameters.copy()
  if isinstance(model_output,dict) and isinstance(model_output.get('parameters'),dict): inherited.update({k:v for k,v in model_output['parameters'].items() if v})
  if requested_org: inherited['org']=requested_org
  if requested_metric: inherited['metric']=rules.get('metric_codes',{}).get(requested_metric)
  for keyword,value in rules.get('date_values',{}).items():
   if keyword in q: inherited['date']=value; break
  semantic=runtime.section('semantic'); dashboard_intent=c.scenario_id==semantic.get('dashboard_scenario') or any(x in q for x in semantic.get('dashboard_keywords',[]))
  if dashboard_intent:
   c.parameters=inherited
   return LayerResult(output={'parameters':inherited,'provider':'OPENAI_COMPATIBLE' if model_output else 'MOCK','model_output':model_output,'deterministic':not bool(model_output)})
  completion=rules.get('completion_scenario')
  if c.scenario_id==completion and c.parent_request_id and 'metric' not in inherited and runtime.policy.allow_parameter_defaults: inherited['metric']=rules.get('default_metric_by_role',{}).get(role)
  if runtime.policy.allow_parameter_defaults:
   inherited.setdefault('org',rules.get('default_org_by_role',{}).get(role)); inherited.setdefault('date',rules.get('default_date')); inherited.setdefault('metric',rules.get('default_metric_by_role',{}).get(role))
  inherited={k:v for k,v in inherited.items() if v is not None}
  if not all(k in inherited for k in ('org','date','metric')):
   return LayerResult('WAITING_INPUT',{'message':rules.get('missing_message','请补充机构、时间和指标'),'options':rules.get('missing_options',[])},True,'MISSING_PARAMETER')
  c.parameters=inherited
  return LayerResult(output={'parameters':inherited,'provider':'OPENAI_COMPATIBLE' if model_output else 'MOCK','model_output':model_output,'deterministic':not bool(model_output)})

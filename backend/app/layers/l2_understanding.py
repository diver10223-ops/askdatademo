from ..models import LayerResult
from ..runtime import runtime_for
class UnderstandingLayer:
 layer_code='L2'; layer_name='对话理解层'
 def __init__(self,registry=None): self.registry=registry
 async def execute(self,c):
  q=c.question; role=c.role_id; permissions=c.permissions or {}; runtime=runtime_for(c); compliance=runtime.section('compliance'); rules=runtime.section('understanding')
  model_output={}
  if self.registry and getattr(self.registry,'phase',1)==2:
   try: model_output=await self.registry.model.structured_generate('L2',{'question':q,'role':role,'scenario_id':c.scenario_id,'context':c.parameters,'_system_prompt':runtime.require('model_prompts.L2')})
   except Exception: model_output={'_provider_error':True}
   if not isinstance(model_output,dict): model_output={'_provider_error':True}
  sensitive=compliance.get('sensitive_words',[])
  if any(x in q for x in sensitive): return LayerResult('BLOCKED',{'message':runtime.require('compliance.intercept_message')},True,'COMPLIANCE_BLOCKED')
  known_orgs=set(rules.get('organizations',[])); requested_org=next((x for x in known_orgs if x in q),None)
  metric_names=rules.get('metric_keywords',{}); requested_metric=next((v for k,v in metric_names.items() if k in q),None)
  if c.scenario_id==rules.get('ambiguous_scenario') or ('相关数据' in q and '投放金额' not in q):
   rec=c.config.get('assets',{}).get('recommendations',{}).get(role,[])
   return LayerResult('SHORT_CIRCUITED',{'recommendations':rec[:3],'message':rules.get('recommendation_message','请选择更明确的合规问句')},True,'AMBIGUOUS_RECOMMENDATION')
  inherited=c.parameters.copy()
  validated_model_parameters={}
  if isinstance(model_output,dict) and isinstance(model_output.get('parameters'),dict):
   candidate=model_output['parameters']; metric_codes=rules.get('metric_codes',{}); known_codes=set(metric_codes.values()); known_dates=set(rules.get('date_values',{}).values())
   if candidate.get('org') in known_orgs: validated_model_parameters['org']=candidate['org']
   model_metric=metric_codes.get(candidate.get('metric'),candidate.get('metric'))
   if model_metric in known_codes: validated_model_parameters['metric']=model_metric
   if candidate.get('date') in known_dates: validated_model_parameters['date']=candidate['date']
   inherited.update(validated_model_parameters)
  if requested_org: inherited['org']=requested_org
  if requested_metric: inherited['metric']=rules.get('metric_codes',{}).get(requested_metric)
  for keyword,value in rules.get('date_values',{}).items():
   if keyword in q: inherited['date']=value; break
  # “按机构对比” is a dimension expansion, not another single-org query.  The
  # previous turn's org remains in session context, so explicitly replace it
  # with every concrete organization in the caller's permission snapshot.
  if '按机构对比' in q or '各机构对比' in q:
   allowed_orgs=[org for org in rules.get('organizations',[]) if org in permissions.get('orgs',[]) and org!='全行']
   if not allowed_orgs: allowed_orgs=[org for org in rules.get('organizations',[]) if org in permissions.get('orgs',[])]
   inherited['orgs']=allowed_orgs
  else: inherited.pop('orgs',None)
  effective_org=inherited.get('org'); metric_by_code={code:name for name,code in rules.get('metric_codes',{}).items()}; effective_metric=metric_by_code.get(inherited.get('metric'))
  if 'orgs' in permissions and effective_org and effective_org not in permissions['orgs']: return LayerResult('BLOCKED',{'message':f'当前角色无权查询{effective_org}'},True,'PERMISSION_DENIED')
  if 'metrics' in permissions and effective_metric and effective_metric not in permissions['metrics']: return LayerResult('BLOCKED',{'message':f'当前角色无权查询{effective_metric}'},True,'PERMISSION_DENIED')
  semantic=runtime.section('semantic'); dashboard_intent=c.scenario_id==semantic.get('dashboard_scenario') or any(x in q for x in semantic.get('dashboard_keywords',[]))
  if dashboard_intent:
   c.parameters=inherited
   return LayerResult(output={'parameters':inherited,'provider':'OPENAI_COMPATIBLE' if model_output and not model_output.get('_provider_error') else 'DETERMINISTIC_FALLBACK','validated_model_parameters':validated_model_parameters,'model_status':'ERROR_FALLBACK' if model_output.get('_provider_error') else 'AVAILABLE','deterministic_final_decision':True})
  completion=rules.get('completion_scenario')
  is_completion=c.scenario_id==completion
  if is_completion and c.parent_request_id and 'metric' not in inherited and runtime.policy.allow_parameter_defaults: inherited['metric']=rules.get('default_metric_by_role',{}).get(role)
  if runtime.policy.allow_parameter_defaults and not is_completion:
   inherited.setdefault('org',rules.get('default_org_by_role',{}).get(role)); inherited.setdefault('date',rules.get('default_date')); inherited.setdefault('metric',rules.get('default_metric_by_role',{}).get(role))
  inherited={k:v for k,v in inherited.items() if v is not None}
  if not all(k in inherited for k in ('org','date','metric')):
   c.parameters=inherited
   return LayerResult('WAITING_INPUT',{'message':rules.get('missing_message','请补充机构、时间和指标'),'options':rules.get('missing_options',[])},True,'MISSING_PARAMETER')
  c.parameters=inherited
  return LayerResult(output={'parameters':inherited,'provider':'OPENAI_COMPATIBLE' if model_output and not model_output.get('_provider_error') else 'DETERMINISTIC_FALLBACK','validated_model_parameters':validated_model_parameters,'model_status':'ERROR_FALLBACK' if model_output.get('_provider_error') else 'AVAILABLE','deterministic_final_decision':True})

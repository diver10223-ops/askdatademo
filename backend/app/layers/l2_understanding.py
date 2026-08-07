from ..models import LayerResult
class UnderstandingLayer:
 layer_code='L2'; layer_name='对话理解层'
 def __init__(self,registry=None): self.registry=registry
 async def execute(self,c):
  q=c.question; role=c.role_id; permissions=c.permissions or {}; compliance=c.config.get('compliance',{})
  model_output={}
  if self.registry and getattr(self.registry,'phase',1)==2:
   model_output=await self.registry.model.structured_generate('L2',{'question':q,'role':role,'scenario_id':c.scenario_id,'context':c.parameters})
  sensitive=compliance.get('sensitive_words',['身份证','明细','涉密'])
  if any(x in q for x in sensitive): return LayerResult('BLOCKED',{'message':compliance.get('intercept_message','涉密或明细数据已按合规规则拦截')},True,'COMPLIANCE_BLOCKED')
  known_orgs={org for item in c.config.get('roles',[]) for org in item.get('orgs',[])} or {'全行','北京分行','上海分行'}; requested_org=next((x for x in known_orgs if x in q),None)
  if permissions and requested_org and requested_org not in permissions.get('orgs',[]): return LayerResult('BLOCKED',{'message':f'当前角色无权查询{requested_org}'},True,'PERMISSION_DENIED')
  metric_names={'零售':'零售贷款','对公':'对公贷款','企业贷款':'对公贷款'}; requested_metric=next((v for k,v in metric_names.items() if k in q),None)
  if permissions and requested_metric and requested_metric not in permissions.get('metrics',[]): return LayerResult('BLOCKED',{'message':f'当前角色无权查询{requested_metric}'},True,'PERMISSION_DENIED')
  if c.scenario_id=='scenario-3' or ('相关数据' in q and '投放金额' not in q):
   rec=c.config.get('assets',{}).get('recommendations',{}).get(role,[])
   return LayerResult('SHORT_CIRCUITED',{'recommendations':rec[:3],'message':'请选择更明确的合规问句'},True,'AMBIGUOUS_RECOMMENDATION')
  inherited=c.parameters.copy()
  if '北京分行' in q: inherited['org']='北京分行'
  elif '上海分行' in q: inherited['org']='上海分行'
  elif '全行' in q: inherited['org']='全行'
  if '零售' in q: inherited['metric']='retail_cur'
  elif '对公' in q: inherited['metric']='corporate_cur'
  elif '贷款' in q: inherited.setdefault('metric','loan_cur')
  if '2026' in q or '去年同期' in q or '为什么' in q: inherited.setdefault('date','2026-03-31')
  if c.scenario_id=='scenario-7' and c.parent_request_id and 'metric' not in inherited: inherited['metric']='retail_cur' if role=='retail' else 'loan_cur'
  if c.scenario_id=='scenario-7' and not all(k in inherited for k in ('org','date','metric')):
   return LayerResult('WAITING_INPUT',{'message':'请补充机构、时间和指标','options':['2026年3月','全行','北京分行','贷款投放']},True,'MISSING_PARAMETER')
  inherited.setdefault('org','全行' if role!='beijing' else '北京分行'); inherited.setdefault('date','2026-03-31'); inherited.setdefault('metric','retail_cur' if role=='retail' else 'loan_cur')
  c.parameters=inherited
  return LayerResult(output={'parameters':inherited,'provider':'OPENAI_COMPATIBLE' if model_output else 'MOCK','model_output':model_output,'deterministic':not bool(model_output)})

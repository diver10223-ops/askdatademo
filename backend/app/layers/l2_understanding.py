from ..models import LayerResult
class UnderstandingLayer:
 layer_code='L2'; layer_name='对话理解层'
 async def execute(self,c):
  q=c.question; role=c.role_id
  if any(x in q for x in ('身份证','明细','涉密')): return LayerResult('BLOCKED',{'message':'涉密或明细数据已按合规规则拦截'},True,'COMPLIANCE_BLOCKED')
  if role=='beijing' and any(x in q for x in ('上海分行','全行')): return LayerResult('BLOCKED',{'message':'当前角色仅可查询北京分行'},True,'PERMISSION_DENIED')
  if role=='retail' and any(x in q for x in ('对公','企业贷款')): return LayerResult('BLOCKED',{'message':'当前角色仅可查询零售信贷指标'},True,'PERMISSION_DENIED')
  if c.scenario_id=='scenario-3' or ('相关数据' in q and '投放金额' not in q):
   rec={'admin':['全行零售贷款投放','对公贷款规模','各分行贷款占比'],'beijing':['北京分行零售贷款投放','北京分行对公贷款规模'],'retail':['全行零售信贷投放','各分行零售贷款占比']}[role]
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
  return LayerResult(output={'parameters':inherited,'provider':'MOCK','deterministic':True})

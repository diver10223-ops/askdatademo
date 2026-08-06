from ..models import LayerResult
class SemanticLayer:
 layer_code='L3'; layer_name='语义层'
 async def execute(self,c):
  if c.scenario_id=='scenario-2' or any(x in c.question for x in ('大盘','驾驶舱')):
   target={'admin':'全行经营指标驾驶舱','beijing':'北京分行经营驾驶舱','retail':'零售信贷经营驾驶舱'}[c.role_id]
   return LayerResult('SHORT_CIRCUITED',{'dashboard':target,'url':'builtin://dashboard'},True)
  c.semantic_plan={'intent':'attribution' if any(x in c.question for x in ('同比','为什么','下降')) else 'query','parameters':c.parameters}
  return LayerResult(output=c.semantic_plan)

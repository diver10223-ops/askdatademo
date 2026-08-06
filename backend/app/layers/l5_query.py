from ..models import LayerResult
class QueryLayer:
 layer_code='L5'; layer_name='查询生成层'
 async def execute(self,c):
  metric=c.parameters['metric']; cols=f'{metric} AS current_value'
  if c.semantic_plan.get('intent')=='attribution': cols+=f', {metric.replace("_cur","_last")} AS previous_value'
  sql=f'SELECT org_name, stat_dt, {cols} FROM dws_loan_aggr_wide WHERE org_name = :org AND stat_dt = :date'
  c.sql_plan=[{'business_sql':sql,'actual_sql':sql,'parameters':{'org':c.parameters['org'],'date':c.parameters['date']},'source':'SQLITE'}]
  if c.scenario_id=='scenario-4' or '为什么' in c.question: c.sql_plan.append({'business_sql':'归因维度 Fixture','actual_sql':'','parameters':{},'source':'MOCK_FIXTURE'})
  return LayerResult(output={'queries':c.sql_plan})

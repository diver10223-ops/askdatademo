from ..models import LayerResult
class QueryLayer:
 layer_code='L5'; layer_name='查询生成层'
 async def execute(self,c):
  metric=c.parameters['metric']; cols=f'{metric} AS current_value'
  if c.semantic_plan.get('intent')=='attribution': cols+=f', {metric.replace("_cur","_last")} AS previous_value'
  table=c.config.get('assets',{}).get('table','dws_loan_aggr_wide')
  if table!='dws_loan_aggr_wide' or metric not in {'loan_cur','retail_cur','corporate_cur'}: return LayerResult('FAILED',{'message':'资产映射不在已发布白名单'},True,'SQL_GENERATION_FAILED')
  template=c.config.get('assets',{}).get('sql_template','SELECT org_name, stat_dt, {metric} FROM dws_loan_aggr_wide WHERE org_name = :org AND stat_dt = :date')
  sql=template.replace('{metric}',cols)
  source='REAL_DATASOURCE' if c.mode.startswith('PHASE2') else 'SQLITE'
  c.sql_plan=[{'business_sql':sql,'actual_sql':sql,'parameters':{'org':c.parameters['org'],'date':c.parameters['date']},'source':source}]
  if c.scenario_id=='scenario-4' or '为什么' in c.question:
   if c.mode=='PHASE2_POC': c.sql_plan.append({'business_sql':sql,'actual_sql':sql,'parameters':{'org':c.parameters['org'],'date':c.parameters['date']},'source':'REAL_DATASOURCE'})
   else: c.sql_plan.append({'business_sql':'归因维度 Fixture','actual_sql':'','parameters':{},'source':'MOCK_FIXTURE'})
  return LayerResult(output={'queries':c.sql_plan})

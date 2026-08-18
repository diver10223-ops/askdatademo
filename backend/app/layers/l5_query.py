from ..models import LayerResult
from ..runtime import runtime_for
class QueryLayer:
 layer_code='L5'; layer_name='查询生成层'
 async def execute(self,c):
  runtime=runtime_for(c); assets=runtime.section('assets'); query=runtime.section('query'); metric=c.parameters['metric']; mapping=assets.get('metric_fields',{}).get(metric)
  if not mapping: return LayerResult('FAILED',{'message':'资产映射不在已发布配置'},True,'SQL_GENERATION_FAILED')
  cols=f"{mapping['current']} AS current_value"
  if c.semantic_plan.get('intent')=='attribution':
   if not mapping.get('previous'): return LayerResult('FAILED',{'message':'指标未配置同期字段'},True,'SQL_GENERATION_FAILED')
   cols+=f", {mapping['previous']} AS previous_value"
  intent=c.semantic_plan.get('intent'); table=assets.get('table'); templates=assets.get('sql_templates',{}); template=templates.get(intent)
  if intent=='org_comparison' and not template:
   template='SELECT {org_field}, {date_field}, {columns} FROM {table} WHERE {org_field} IN ({org_placeholders}) AND {date_field} = :date ORDER BY current_value DESC'
  template=template or templates.get('query')
  if not table or not template: return LayerResult('FAILED',{'message':'数据表或SQL模板未发布'},True,'SQL_GENERATION_FAILED')
  parameters={'org':c.parameters['org'],'date':c.parameters['date']}
  if intent=='org_comparison':
   orgs=c.parameters.get('orgs',[])
   if not orgs: return LayerResult('FAILED',{'message':'没有可对比的授权机构'},True,'SQL_GENERATION_FAILED')
   placeholders=', '.join(f':org_{index}' for index in range(len(orgs)))
   parameters={'date':c.parameters['date'],**{f'org_{index}':org for index,org in enumerate(orgs)}}
  else: placeholders=':org'
  sql=template.format(table=table,org_field=assets.get('org_field'),date_field=assets.get('date_field'),columns=cols,org_placeholders=placeholders)
  source='REAL_DATASOURCE' if runtime.policy.require_real_datasource else 'SQLITE'
  c.sql_plan=[{'business_sql':sql,'actual_sql':sql,'parameters':parameters,'source':source}]
  if c.scenario_id==query.get('attribution_scenario') or c.semantic_plan.get('intent')=='attribution':
   if runtime.policy.allow_fixture_fallback: c.sql_plan.append({'business_sql':query.get('attribution_business_label'),'actual_sql':'','parameters':{},'source':'MOCK_FIXTURE'})
   else: c.sql_plan.append({'business_sql':sql,'actual_sql':sql,'parameters':{'org':c.parameters['org'],'date':c.parameters['date']},'source':'REAL_DATASOURCE'})
  return LayerResult(output={'queries':c.sql_plan})

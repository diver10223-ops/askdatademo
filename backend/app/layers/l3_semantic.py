from ..models import LayerResult
from ..runtime import runtime_for
class SemanticLayer:
 layer_code='L3'; layer_name='语义层'
 async def execute(self,c):
  runtime=runtime_for(c); semantic=runtime.section('semantic'); assets=runtime.section('assets')
  if c.scenario_id==semantic.get('dashboard_scenario') or any(x in c.question for x in semantic.get('dashboard_keywords',[])):
   target=semantic.get('dashboard_names',{}).get(c.role_id); links=semantic.get('dashboard_links',{}).get(c.role_id,[])
   return LayerResult('SHORT_CIRCUITED',{'dashboard':target,'url':links[0]['url'] if links else assets.get('dashboard_url'),'dashboards':links},True)
  if c.parameters.get('orgs'): intent='org_comparison'
  elif any(x in c.question for x in semantic.get('attribution_keywords',[])): intent='attribution'
  else: intent='query'
  c.semantic_plan={'intent':intent,'parameters':c.parameters}
  return LayerResult(output=c.semantic_plan)

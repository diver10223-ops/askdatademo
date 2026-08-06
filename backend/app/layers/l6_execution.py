from ..models import LayerResult
class ExecutionLayer:
 layer_code='L6'; layer_name='执行层'
 def __init__(self,registry): self.registry=registry
 async def execute(self,c):
  c.results=[]
  for plan in c.sql_plan:
   if plan['source']=='SQLITE': c.results.extend(await self.registry.datasource.execute(plan['actual_sql'],plan['parameters']))
   else: c.results.extend(await self.registry.fixture.execute('attribution',plan['parameters']))
  return LayerResult(output={'rows':c.results,'row_count':len(c.results),'sources':[x['source'] for x in c.sql_plan]})

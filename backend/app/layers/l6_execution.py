from ..models import LayerResult
class ExecutionLayer:
 layer_code='L6'; layer_name='执行层'
 def __init__(self,registry): self.registry=registry
 async def execute(self,c):
  c.results=[]; failures=[]
  if hasattr(self.registry.datasource,'set_request_id'): self.registry.datasource.set_request_id(c.request_id)
  for index,plan in enumerate(c.sql_plan):
   try:
    if plan['source']!='MOCK_FIXTURE': c.results.extend(await self.registry.datasource.execute(plan['actual_sql'],plan['parameters']))
    else: c.results.extend(await self.registry.fixture.execute('attribution',plan['parameters']))
    plan['execution_status']='SUCCEEDED'
   except Exception as exc:
    failures.append({'sequence':index+1,'error_type':type(exc).__name__})
    plan['execution_status']='FAILED'; plan['error_type']=type(exc).__name__
    if c.mode=='PHASE2_POC':
     status='FAILED' if index==0 else 'PARTIAL_SUCCESS'
     return LayerResult(status,{'rows':c.results,'row_count':len(c.results),'failures':failures},True,'EXECUTION_FAILED')
    c.results.extend(await self.registry.fixture.execute('attribution',plan['parameters']))
    plan['source']='MOCK_FIXTURE'; plan['fallback_reason']=type(exc).__name__
    plan['execution_status']='SUCCEEDED_WITH_FALLBACK'
  return LayerResult(output={'rows':c.results,'row_count':len(c.results),'sources':[x['source'] for x in c.sql_plan],'failures':failures})

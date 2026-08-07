from ..models import LayerResult
from ..runtime import runtime_for
class InterpretationLayer:
 layer_code='L7'; layer_name='问数解读层'
 def __init__(self,registry): self.registry=registry
 async def execute(self,c):
  runtime=runtime_for(c); wording=runtime.section('interpretation'); assets=runtime.section('assets'); row=c.results[0] if c.results else {}; cur=row.get('current_value'); prev=row.get('previous_value'); org=row.get(assets.get('org_field','org_name')); date=row.get(assets.get('date_field','stat_dt'))
  if cur is None: answer=wording.get('empty','查询已完成。')
  elif prev: answer=wording['comparison'].format(org=org,current=cur,previous=prev,rate=(cur-prev)/prev*100)
  else: answer=wording['single'].format(org=org,date=date,current=cur)
  if any('factor' in x for x in c.results): answer+=wording.get('attribution_suffix','')
  generated=await self.registry.model.structured_generate('L7',{'answer':answer,'rows':c.results,'_system_prompt':runtime.require('model_prompts.L7')})
  if getattr(self.registry,'phase',1)==2 and isinstance(generated,dict): answer=generated.get('answer',answer)
  c.answer=answer
  return LayerResult(output={'answer':answer,'table':c.results,'chart':wording.get('chart'),'guides':wording.get('guides',[])})

from ..models import LayerResult
class InterpretationLayer:
 layer_code='L7'; layer_name='问数解读层'
 def __init__(self,registry): self.registry=registry
 async def execute(self,c):
  row=c.results[0] if c.results else {}; cur=row.get('current_value'); prev=row.get('previous_value')
  if cur is None: answer='查询已完成。'
  elif prev: answer=f"{row['org_name']}本期为 {cur:.2f}，上期为 {prev:.2f}，同比 {(cur-prev)/prev*100:.2f}%。"
  else: answer=f"{row['org_name']}在 {row['stat_dt']} 的查询结果为 {cur:.2f}。"
  if any('factor' in x for x in c.results): answer+=' 主要受阶段性放款节奏影响。'
  generated=await self.registry.model.structured_generate('L7',{'answer':answer,'rows':c.results})
  if getattr(self.registry,'phase',1)==2 and isinstance(generated,dict): answer=generated.get('answer',answer)
  c.answer=answer
  return LayerResult(output={'answer':answer,'table':c.results})

from ..models import LayerResult
class InteractionLayer:
 layer_code='L1'; layer_name='交互层'
 async def execute(self,c):
  q=c.question.strip()
  if not q: return LayerResult('FAILED',{'message':'请输入问题'},True,'INVALID_INPUT')
  return LayerResult(output={'normalized_question':q,'session_id':c.session_id,'config_version_id':c.config_version_id})

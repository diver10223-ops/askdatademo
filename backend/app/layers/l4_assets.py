from ..models import LayerResult
from ..runtime import runtime_for
class AssetLayer:
 layer_code='L4'; layer_name='数据资产层'
 async def execute(self,c):
  runtime=runtime_for(c); assets=runtime.section('assets'); metric=c.parameters['metric']; mapping=assets.get('metric_fields',{}).get(metric)
  if not mapping: return LayerResult('FAILED',{'message':'已发布配置中不存在指标字段映射'},True,'ASSET_NOT_FOUND')
  return LayerResult(output={'provider':'REAL_DATASOURCE' if runtime.policy.require_real_datasource else 'SQLITE','table':assets.get('table'),'metric':metric,'mapping':mapping})

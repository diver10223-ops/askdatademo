from ..models import LayerResult
class AssetLayer:
 layer_code='L4'; layer_name='数据资产层'
 async def execute(self,c): return LayerResult(output={'provider':'SQLITE','table':'dws_loan_aggr_wide','metric':c.parameters['metric']})

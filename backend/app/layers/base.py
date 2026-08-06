from typing import Protocol
from ..models import PipelineContext,LayerResult
class LayerProcessor(Protocol):
 layer_code:str; layer_name:str
 async def execute(self,context:PipelineContext)->LayerResult: ...

from dataclasses import dataclass, field
from typing import Any
REQUEST_STATES={"PENDING","RUNNING","WAITING_INPUT","SHORT_CIRCUITED","BLOCKED","PARTIAL_SUCCESS","SUCCEEDED","FAILED","CANCELLED"}
ERROR_CODES={"INVALID_INPUT","MISSING_PARAMETER","AMBIGUOUS_RECOMMENDATION","PERMISSION_DENIED","COMPLIANCE_BLOCKED","ASSET_NOT_FOUND","SQL_GENERATION_FAILED","EXECUTION_FAILED","CANCELLED","INTERPRETATION_FAILED","UNSUPPORTED_PHASE_1"}
@dataclass
class PipelineContext:
 session_id:str; request_id:str; role_id:str; config_version_id:str; question:str
 parent_request_id:str|None=None; scenario_id:str|None=None; case_id:str|None=None; mode:str="POC"
 parameters:dict[str,Any]=field(default_factory=dict); semantic_plan:dict[str,Any]=field(default_factory=dict)
 sql_plan:list[dict[str,Any]]=field(default_factory=list); results:list[dict[str,Any]]=field(default_factory=list)
 answer:str=""; status:str="RUNNING"; termination_reason:str|None=None
 permissions:dict[str,Any]=field(default_factory=dict); config:dict[str,Any]=field(default_factory=dict)
@dataclass
class LayerResult:
 status:str="SUCCEEDED"; output:dict[str,Any]=field(default_factory=dict); stop:bool=False; error_code:str|None=None

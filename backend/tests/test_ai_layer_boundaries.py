import asyncio
import json
from pathlib import Path

from app.layers import UnderstandingLayer, InterpretationLayer
from app.models import PipelineContext
from app.runtime import resolve_runtime


ROOT = Path(__file__).resolve().parents[2]


class MaliciousModel:
    def __init__(self, outputs): self.outputs = outputs
    async def structured_generate(self, layer, payload): return self.outputs[layer]


class Registry:
    phase = 2
    def __init__(self, outputs): self.model = MaliciousModel(outputs)


def context(question='查询贷款投放', permissions=None):
    config = json.loads((ROOT / 'fixtures' / 'official_baseline_v1.json').read_text())
    return PipelineContext('s','r','admin','official-v1',question,scenario_id='scenario-1',
                           permissions=permissions or {},config=config,runtime=resolve_runtime(config,'PHASE1_DEMO'))


def test_l2_model_parameters_are_normalized_then_permission_checked_and_sql_is_ignored():
    registry=Registry({'L2':{'parameters':{'org':'上海分行','metric':'贷款投放','date':'2026-03-31'},'sql':'DROP TABLE users'}})
    value=context(permissions={'orgs':['北京分行'],'metrics':['贷款投放']})
    result=asyncio.run(UnderstandingLayer(registry).execute(value))
    assert result.status=='BLOCKED' and result.error_code=='PERMISSION_DENIED'
    assert value.sql_plan==[] and 'sql' not in result.output


def test_l2_discards_unknown_model_values_but_deterministic_question_values_win():
    registry=Registry({'L2':{'parameters':{'org':'不存在机构','metric':'任意指标','date':'2099-01-01'}}})
    value=context('2026年3月北京分行贷款投放是多少？',{'orgs':['北京分行'],'metrics':['贷款投放']})
    result=asyncio.run(UnderstandingLayer(registry).execute(value))
    assert result.status=='SUCCEEDED'
    assert value.parameters=={'org':'北京分行','metric':'loan_cur','date':'2026-03-31'}
    assert result.output['validated_model_parameters']=={}


def test_l7_rejects_invented_numbers_and_keeps_l6_facts():
    registry=Registry({'L7':{'answer':'全行贷款余额999999元，增长888%。'}})
    value=context(); value.results=[{'org_name':'全行','stat_dt':'2026-03-31','current_value':100.0}]
    result=asyncio.run(InterpretationLayer(registry).execute(value))
    assert result.output['model_validation']=='REJECTED_FACT_INCONSISTENCY'
    assert '100' in value.answer and '999999' not in value.answer and '888' not in value.answer


def test_l7_accepts_style_change_only_when_numeric_facts_are_identical():
    registry=Registry({'L7':{'answer':'截至2026-03-31，全行贷款投放为100.0元。'}})
    value=context(); value.results=[{'org_name':'全行','stat_dt':'2026-03-31','current_value':100.0}]
    result=asyncio.run(InterpretationLayer(registry).execute(value))
    assert result.output['model_validation']=='ACCEPTED_FACT_CONSISTENCY'
    assert value.answer=='截至2026-03-31，全行贷款投放为100.0元。'


def test_l7_rejects_changed_text_facts_even_when_numbers_are_identical():
    registry=Registry({'L7':{'answer':'截至2026-03-31，上海分行贷款投放为100.00元。'}})
    value=context(); value.results=[{'org_name':'全行','stat_dt':'2026-03-31','current_value':100.0}]
    result=asyncio.run(InterpretationLayer(registry).execute(value))
    assert result.output['model_validation']=='REJECTED_FACT_INCONSISTENCY'
    assert '全行' in value.answer and '上海分行' not in value.answer

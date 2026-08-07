import json
from pathlib import Path

import pytest

from app.runtime import RuntimeConfigError, resolve_runtime
from app.runtime.publisher import publish_runtime


def defaults():
    return json.loads((Path(__file__).parents[2] / "fixtures" / "demo_runtime_defaults.json").read_text())


def test_demo_uses_external_defaults_and_poc_is_strict():
    demo = resolve_runtime({}, "PHASE1_DEMO")
    assert demo.policy.allow_fixture_fallback and demo.require("assets.table") == "dws_loan_aggr_wide"
    with pytest.raises(RuntimeConfigError) as missing:
        resolve_runtime({}, "PHASE2_POC")
    assert "assets.table" in missing.value.missing


def test_poc_rejects_table_outside_provider_allowlist():
    with pytest.raises(RuntimeConfigError) as invalid:
        resolve_runtime({"runtime": defaults()}, "PHASE2_POC", ["another_table"])
    assert invalid.value.missing == ["provider.allowed_tables[dws_loan_aggr_wide]"]


def test_admin_resources_compile_to_runtime_snapshot():
    pages = {
        "metrics": [{"id": "balance", "payload": {"指标名称": "贷款余额", "英文标识": "balance", "同义词": "余额,贷款规模"}}],
        "field-mappings": [{"id": "map", "payload": {"标准指标": "贷款余额", "数据表": "loan_wide", "物理字段": "balance_cur", "同期字段": "balance_last"}}],
        "dimensions": [
            {"id": "org", "payload": {"类型": "机构维度", "物理字段": "branch_name", "成员/周期": "总行,北京分行"}},
            {"id": "date", "payload": {"类型": "时间维度", "物理字段": "biz_date"}},
        ],
        "sql-templates": [{"id": "query", "payload": {"类型": "SELECT", "SQL模板": "SELECT {org_field},{date_field},{metric} FROM {table} WHERE {org_field}=:org AND {date_field}=:date"}}],
    }
    runtime = publish_runtime(defaults(), pages)
    assert runtime["assets"]["table"] == "loan_wide"
    assert runtime["assets"]["metric_fields"]["balance"]["current"] == "balance_cur"
    assert runtime["understanding"]["metric_codes"]["贷款余额"] == "balance"
    assert runtime["assets"]["org_field"] == "branch_name"
    assert "{columns}" in runtime["assets"]["sql_templates"]["query"]

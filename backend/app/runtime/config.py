import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import ROOT


class RuntimeConfigError(ValueError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("运行配置缺失: " + ", ".join(missing))


@dataclass(frozen=True)
class ExecutionPolicy:
    allow_fixture_fallback: bool
    allow_parameter_defaults: bool
    require_real_model: bool
    require_real_datasource: bool


@dataclass(frozen=True)
class RuntimeConfig:
    data: dict[str, Any]
    mode: str
    policy: ExecutionPolicy

    def section(self, name: str) -> dict[str, Any]:
        return self.data.get(name, {})

    def require(self, path: str) -> Any:
        value: Any = self.data
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value or value[part] in (None, "", [], {}):
                raise RuntimeConfigError([path])
            value = value[part]
        return value


def _demo_defaults() -> dict[str, Any]:
    path = Path(ROOT) / "fixtures" / "demo_runtime_defaults.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        result[key] = _deep_merge(result.get(key, {}), value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


POC_REQUIRED = [
    "execution.max_snapshot_bytes",
    "execution.max_snapshot_rows",
    "understanding.organizations",
    "understanding.metric_keywords",
    "understanding.metric_codes",
    "understanding.date_values",
    "compliance.sensitive_words",
    "compliance.intercept_message",
    "semantic.dashboard_keywords",
    "semantic.dashboard_names",
    "semantic.dashboard_links",
    "assets.table",
    "assets.org_field",
    "assets.date_field",
    "assets.metric_fields",
    "assets.sql_templates.query",
    "interpretation.single",
    "interpretation.comparison",
    "interpretation.empty",
    "interpretation.chart",
    "interpretation.guides",
    "masking.fields",
    "model_prompts.L2",
    "model_prompts.L7",
    "scenario_bindings",
]


def resolve_runtime(config: dict[str, Any], mode: str, allowed_tables: list[str] | None = None) -> RuntimeConfig:
    configured = config.get("runtime", {})
    is_poc = mode == "PHASE2_POC"
    data = configured if is_poc else _deep_merge(_demo_defaults(), configured)
    if not is_poc:
        legacy = config.get("assets", {})
        legacy_assets: dict[str, Any] = {}
        if legacy.get("table"): legacy_assets["table"] = legacy["table"]
        if legacy.get("dashboard") and legacy.get("dashboard") != "builtin://dashboard":
            legacy_assets["dashboard_url"] = legacy["dashboard"]
            names=data.get("semantic",{}).get("dashboard_names",{}); data=_deep_merge(data,{"semantic":{"dashboard_links":{role:[{"name":name,"url":legacy["dashboard"]}] for role,name in names.items()}}})
        if legacy.get("sql_template"): legacy_assets["sql_templates"] = {"query": legacy["sql_template"].replace("{metric}", "{columns}")}
        if legacy_assets: data = _deep_merge(data, {"assets": legacy_assets})
        if config.get("compliance"): data = _deep_merge(data, {"compliance": config["compliance"]})
    if is_poc:
        missing = []
        probe = RuntimeConfig(data, mode, ExecutionPolicy(False, False, True, True))
        for path in POC_REQUIRED:
            try: probe.require(path)
            except RuntimeConfigError: missing.append(path)
        table = data.get("assets", {}).get("table")
        if table and allowed_tables is not None and table not in allowed_tables: missing.append(f"provider.allowed_tables[{table}]")
        metric_codes=set(data.get("understanding",{}).get("metric_codes",{}).values()); mapped=set(data.get("assets",{}).get("metric_fields",{}))
        for code in sorted(metric_codes-mapped): missing.append(f"assets.metric_fields[{code}]")
        if missing: raise RuntimeConfigError(missing)
    execution = data.get("execution", {})
    is_phase2 = mode.startswith("PHASE2")
    policy = ExecutionPolicy(
        allow_fixture_fallback=bool(execution.get("allow_fixture_fallback", not is_poc)),
        allow_parameter_defaults=bool(execution.get("allow_parameter_defaults", not is_poc)),
        require_real_model=is_phase2 or bool(execution.get("require_real_model", False)),
        require_real_datasource=is_phase2 or bool(execution.get("require_real_datasource", False)),
    )
    if is_poc:
        policy = ExecutionPolicy(False, False, True, True)
    return RuntimeConfig(data, mode, policy)


def runtime_for(context) -> RuntimeConfig:
    if context.runtime is None:
        context.runtime = resolve_runtime(context.config, context.mode)
    return context.runtime

from copy import deepcopy
from typing import Any


def _csv(value: Any) -> list[str]:
    if isinstance(value, list): return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value or "").split(",") if x.strip()]


def publish_runtime(current: dict[str, Any], by_page: dict[str, list[dict]]) -> dict[str, Any]:
    runtime = deepcopy(current)
    understanding = runtime.setdefault("understanding", {})
    assets = runtime.setdefault("assets", {})
    semantic = runtime.setdefault("semantic", {})
    interpretation = runtime.setdefault("interpretation", {})

    metrics = by_page.get("metrics", [])
    code_by_name: dict[str, str] = {}
    if metrics:
        keyword_map: dict[str, str] = {}
        code_map: dict[str, str] = {}
        for item in metrics:
            payload = item["payload"]
            name = str(payload.get("指标名称") or item["id"])
            code = str(payload.get("英文标识") or item["id"])
            code_by_name[name] = code
            code_map[name] = code
            for keyword in [name, *_csv(payload.get("同义词"))]: keyword_map[keyword] = name
        understanding["metric_keywords"] = keyword_map
        understanding["metric_codes"] = code_map

    mappings = by_page.get("field-mappings", [])
    if mappings:
        fields = {}
        for item in mappings:
            payload = item["payload"]
            metric = str(payload.get("标准指标") or item["id"])
            code = code_by_name.get(metric, metric)
            fields[code] = {"current": payload.get("物理字段"), "previous": payload.get("同期字段"), "breakdown": _csv(payload.get("分项字段"))}
            if payload.get("数据表"): assets["table"] = payload["数据表"]
        assets["metric_fields"] = fields

    dimensions = by_page.get("dimensions", [])
    if dimensions:
        for item in dimensions:
            payload = item["payload"]
            kind = str(payload.get("类型", ""))
            if "机构" in kind:
                assets["org_field"] = payload.get("物理字段")
                understanding["organizations"] = _csv(payload.get("成员/周期"))
            if "时间" in kind: assets["date_field"] = payload.get("物理字段")

    templates = by_page.get("sql-templates", [])
    if templates:
        query_templates = {}
        for item in templates:
            payload = item["payload"]
            template = str(payload.get("SQL模板") or "").replace("{metric}", "{columns}")
            if template: query_templates["attribution" if "归因" in str(payload.get("类型")) else "query"] = template
        if query_templates: assets["sql_templates"] = query_templates

    dashboards = by_page.get("dashboards", [])
    if dashboards:
        names = {}; links = {}; first_url = None
        for item in dashboards:
            payload = item["payload"]; first_url = first_url or payload.get("URL")
            for role in _csv(payload.get("角色")):
                names[role] = payload.get("名称"); links.setdefault(role,[]).append({"name":payload.get("名称"),"url":payload.get("URL")})
        if names: semantic["dashboard_names"] = names
        if links: semantic["dashboard_links"] = links
        if first_url: assets["dashboard_url"] = first_url

    intents = by_page.get("intent-rules", [])
    if intents:
        for item in intents:
            payload = item["payload"]; name = str(payload.get("模板名称", "")); keywords = [x for x in str(payload.get("触发关键词") or "").replace("|", ",").split(",") if x]
            if "驾驶舱" in name: semantic["dashboard_keywords"] = keywords
            if "归因" in name or "同比" in name: semantic["attribution_keywords"] = keywords

    parameters = by_page.get("parameter-rules", [])
    if parameters:
        for item in parameters:
            payload = item["payload"]
            if payload.get("参数") == "时间" and payload.get("缺失提示"): understanding["missing_message"] = payload["缺失提示"]

    wording = by_page.get("mock-wording", [])
    for item in wording:
        payload = item["payload"]; name = str(payload.get("名称", "")); content = payload.get("内容")
        if content and "无数据" in name: interpretation["empty"] = content

    answer_templates = by_page.get("answer-templates", [])
    for item in answer_templates:
        payload = item["payload"]; kind = payload.get("模板类型"); content = payload.get("模板内容")
        key = {"无数据": "empty", "单期查询": "single", "同比查询": "comparison", "归因后缀": "attribution_suffix"}.get(kind)
        if key and content: interpretation[key] = content

    visualizations = by_page.get("output-visualization", [])
    if visualizations:
        payload = visualizations[0]["payload"]
        interpretation["chart"] = {"type": payload.get("图表类型", "bar"), "title": payload.get("图表标题"), "category_field": payload.get("分类字段"), "series": _csv(payload.get("数值字段"))}
        interpretation["guides"] = _csv(payload.get("引导提示"))

    prompts = runtime.setdefault("model_prompts", {})
    for item in by_page.get("model-capabilities", []):
        payload = item["payload"]; name = str(payload.get("配置项", "")); prompt = payload.get("Prompt模板")
        if prompt and "理解" in name: prompts["L2"] = prompt
        if prompt and ("解读" in name or "输出" in name): prompts["L7"] = prompt

    policies = by_page.get("runtime-policy", [])
    if policies:
        demo = next((x["payload"] for x in policies if x["payload"].get("模式") in ("PHASE1_DEMO", "PHASE2_DEMO")), None)
        if demo:
            execution = runtime.setdefault("execution", {})
            execution["allow_fixture_fallback"] = demo.get("允许Fixture降级") == "是"
            execution["allow_parameter_defaults"] = demo.get("允许参数默认值") == "是"
            if demo.get("执行间隔毫秒") not in (None, ""): execution["simulation_speed_ms"] = int(demo["执行间隔毫秒"])

    bindings = by_page.get("scene-parameter-bindings", [])
    if bindings:
        runtime["scenario_bindings"] = {item["payload"].get("场景ID", item["id"]): item["payload"] for item in bindings if item["payload"].get("状态") == "启用"}

    masking = by_page.get("masking", [])
    if masking: runtime.setdefault("masking", {})["fields"] = [x["payload"].get("字段") for x in masking if x["payload"].get("字段")]
    compliance = runtime.setdefault("compliance", {})
    classified = by_page.get("classified", [])
    if classified: compliance["sensitive_words"] = [word for item in classified for word in str(item["payload"].get("对象值") or "").split("|") if word]
    intercepts = by_page.get("intercept-wording", [])
    if intercepts:
        message = next((item["payload"].get("提示文案") for item in intercepts if item["payload"].get("提示文案")), None)
        if message: compliance["intercept_message"] = message
    return runtime

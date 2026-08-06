# 一期资产清单与契约冻结

契约版本为 `1.0`，展示内容版本为不可原地覆盖的 `Official Demo Baseline v1`。三种角色是总行领导、北京分行、零售主管；八场景依次为基础查数、驾驶舱、模糊推荐、同比归因、合规拦截、多轮上下文、参数补全、取数后二次归因。完整逐角色问句、轮次、预期终止层、SQL、结果与来源位于 `fixtures/official_baseline_v1.json`。

## 统一契约

`Session` 锁定角色、权限快照和配置版本；`Request` 可通过 `parent_request_id` 表达推荐、补全与追问；每次实际启动的层才产生 `LayerExecution`；一个请求可有多个 `SQLExecution`，同时保存业务 SQL、实际参数化 SQL、SQLite/Fixture 来源与降级事实；脱敏的 `ResultSnapshot` 保存大小；`SSEEvent` 在推送前持久化并具有请求内递增序号。JSON Schema 位于 `schemas/`。

统一状态、执行模式和错误码：请求状态包括 `WAITING_INPUT/SHORT_CIRCUITED/BLOCKED/PARTIAL_SUCCESS/SUCCEEDED/FAILED/CANCELLED`；层状态包括 `STARTED/SUCCEEDED/FAILED/CANCELLED/SHORT_CIRCUITED`；模式为 `POC/OFFLINE`。错误码为 `INVALID_INPUT/MISSING_PARAMETER/AMBIGUOUS_RECOMMENDATION/PERMISSION_DENIED/COMPLIANCE_BLOCKED/ASSET_NOT_FOUND/SQL_GENERATION_FAILED/EXECUTION_FAILED/CANCELLED/INTERPRETATION_FAILED/UNSUPPORTED_PHASE_1`。

## 内容缺口

最终 Logo、少量业务数字和归因话术仍是临时演示内容而非生产口径；按既定决策使用 Baseline v1，不构成技术阻塞。来源为 `index.html`、`智能问数后台管理.html` 及仓库 NLQ Word 文档。

# 一期、二期真实性与完整性检查执行记录

> 执行日期：2026-08-07  
> 工作区：`/workspaces/askdatademo`  
> 依据：`docs/PHASE1_PHASE2_AUTHENTICITY_ACCEPTANCE_PLAN.md`  
> 结论口径：本记录只确认本次实际执行并取得证据的事项。

## 1. 执行摘要

|阶段|本次结论|证据等级|说明|
|---|---|---|---|
|一期仓库内自动验收|PASS|E2|基线、双库、33 轮矩阵、类型检查、两种构建、离线外链扫描、后端测试全部通过|
|一期人工/业务验收|BLOCKED|E4/E5 未执行|未在本次命令行会话中完成浏览器断网人工检查，也未取得业务内容签字|
|二期仓库内实现与协议仿真|PASS|E3|6 项二期测试和本地 WireMock Provider 33 轮矩阵通过|
|二期真实环境验收|BLOCKED|E4/E5 未执行|未提供真实 OpenAI-compatible、ClickHouse、MySQL 端点、凭据、批准数据集和验收人|
|一期回归|PASS|E2|二期脚本内再次完整执行一期检查并通过|

因此，准确的总体表述是：**一期仓库内技术验收通过，但人工离线复核与业务口径签字待完成；二期实现、协议仿真及一期回归通过，但真实 Provider 与业务数据尚未验收，不能认定“二期真实完整完成”。**

## 2. 实际执行命令

```bash
git status --short
bash scripts/demo-readiness-check.sh
bash scripts/phase2-readiness-check.sh
```

两个验收脚本最终退出码均为 `0`。

## 3. 一期执行结果

|检查项|结果|本次证据|
|---|---|---|
|官方基线与双库|PASS|输出 `OK: baseline, 3 roles × 8 scenarios, dual databases`|
|完整场景矩阵|PASS|3 角色 × 8 场景，共 33 个必要轮次|
|前端类型检查|PASS|`vue-tsc -b` 零退出|
|POC 构建|PASS|Vite 构建 31 个模块成功|
|Offline 构建|PASS|生成 `frontend/offline-dist/askdata-offline.html`|
|Offline 外部资源扫描|PASS|脚本未发现外部 link/script/fetch/WebSocket/EventSource|
|后端测试|PASS|11 项通过|
|格式检查|PASS|`git diff --check` 未报错|
|脚本总门禁|PASS|`READY: Phase 1 acceptance checks passed`|

尚未完成：

- 在物理断网、无后端服务的浏览器中人工双击 Offline 文件并完成八场景操作；
- 浏览器刷新后的 IndexedDB 恢复、导入导出及停止按钮人工取证；
- 由业务方确认临时演示数字、Logo 和归因话术；
- 从独立发布包而非当前工作树做一次冷启动复验。

## 4. 二期执行结果

|检查项|结果|本次证据|
|---|---|---|
|二期自动测试|PASS|6 项通过，覆盖当前测试文件中的加密、SQL 安全、Provider 协议、Profile/API 和失败策略|
|Provider 矩阵|PASS（仿真）|本地 `ThreadingHTTPServer` WireMock 支撑 3×8×33 轮|
|前端类型与 POC 构建|PASS|类型检查和 Vite 构建成功|
|一期完整回归|PASS|一期 33 轮、Offline 构建、11 项测试再次通过|
|脚本总门禁|PASS（E3）|`READY: Phase 2 checks passed; Phase 1 regression passed`|
|真实 OpenAI-compatible|BLOCKED|未提供端点和凭据|
|真实 ClickHouse|BLOCKED|未提供端点、凭据和批准 Schema|
|真实 MySQL|BLOCKED|未提供端点、凭据和批准 Schema；当前矩阵不能替代 MySQL 真连|
|真实 33 轮端到端|BLOCKED|当前使用 WireMock，不是客户环境|
|业务结果对账|BLOCKED|未提供黄金问题、标准 SQL、数据版本和业务验收人|

## 5. 发现与风险

1. 旧二期报告中“仓库内可实现、可自动验证的工作已完成”可以保留，但不得简化传播为“二期真实环境已完成”。
2. `scripts/phase2-matrix.py` 明确启动本地 WireMock，并主要配置 OpenAI-compatible 与 ClickHouse；它是 E3 协议证据，不是 MySQL E4 证据。
3. 自动检查运行时出现 FastAPI `on_event` 弃用警告。当前不影响验收，但应迁移至 lifespan，避免后续框架升级导致启动失败。
4. 执行前工作树已有大量修改和未跟踪文件，本次未清理或覆盖这些用户变更。正式发布前必须冻结提交 SHA，并从干净检出目录复验。
5. 本次脚本会重建前端构建产物；构建后的文件属于当前工作树状态，正式发布需生成 SHA256 清单。

## 6. 后续关闭条件

|优先级|待办|关闭证据|
|---|---|---|
|P0|提供三类真实 Provider 的验收端点、网络路径和专用凭据|脱敏诊断记录|
|P0|提供批准数据集、黄金问题和标准 SQL|版本化对账基线|
|P0|执行真实 Provider 3×8×33 矩阵，禁止 Stub/Fixture 静默替代|真实矩阵 JSON、Trace、原始日志|
|P0|完成 ClickHouse、MySQL 源库直查对账|对账表和业务签字|
|P1|完成一期 Offline 断网浏览器人工验收|人工检查表、截图/录屏、签字|
|P1|从冻结 SHA 的独立交付包执行冷启动与恢复演练|发布包摘要、演练记录|
|P1|完成凭据、日志脱敏、SQL 安全专项复核|安全报告|
|P2|将 FastAPI startup/shutdown 迁移到 lifespan|代码变更和回归日志|

## 7. 当前放行建议

- 一期：可作为 Mock POC/Offline 演示技术包进入人工验收；对外必须保留“Mock/模拟数据/临时业务口径”标识。
- 二期：可进入客户真实环境联调，不可按“真实完整验收通过”发布。
- 正式签字：待本记录第 6 节 P0 项全部关闭，并满足验收计划中的 E4/E5 门槛后再生成。

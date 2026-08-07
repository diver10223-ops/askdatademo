# 一期、二期输出文件计划

> 版本：v1.0  
> 日期：2026-08-07

## 1. 输出原则

交付分为“产品包、配置与契约、验收证据、运维文档、签字材料”五类。正式发布包使用版本号和提交 SHA，原始日志只追加不覆盖；所有凭据、令牌、客户数据明细和临时数据库必须排除。Markdown 是仓库内事实源，需要对外流转时再生成 PDF，不维护内容不一致的双份正文。

## 2. 一期输出文件

|编号|文件/目录|类型|内容|生成/责任方|放行条件|
|---|---|---|---|---|---|
|P1-O01|`release/phase1/<version>/source/`|产品包|前后端源码、脚本、锁文件|研发/发布脚本|从干净环境可构建|
|P1-O02|`release/phase1/<version>/askdata-offline.html`|产品包|单文件离线演示版|`npm run build:offline`|无外链、断网可运行、摘要已记录|
|P1-O03|`release/phase1/<version>/poc-dist/`|产品包|Vue POC 静态构建物|`npm run build`|由 FastAPI 同源提供且冒烟通过|
|P1-O04|`fixtures/official_baseline_v1.json`|配置/数据|三角色、八场景、模拟数据与预期|产品+业务|Schema 校验通过，临时内容已标识|
|P1-O05|`schemas/phase1-contract.schema.json`|契约|一期请求、轨迹、SQL、结果契约|研发|Schema 解析与契约测试通过|
|P1-O06|`schemas/baseline.schema.json`|契约|官方基线 Schema|研发|Fixture 校验通过|
|P1-O07|`docs/PHASE1_ASSET_INVENTORY.md`|清单|资产、版本、限制与来源|配置管理员|与发布包逐项一致|
|P1-O08|`docs/PHASE1_RUNBOOK.md`|运维|安装、启动、停止、诊断、重置、备份恢复|研发+运维|由非开发人员复现一次|
|P1-O09|`evidence/phase1/<run-id>/commands.log`|证据|命令、时间、SHA、退出码、完整输出|测试|只追加、脱敏、可追溯|
|P1-O10|`evidence/phase1/<run-id>/matrix-results.json`|证据|33 轮逐项状态、层数、来源、父请求|测试脚本|机器可读且全部通过|
|P1-O11|`evidence/phase1/<run-id>/offline-checklist.pdf`|证据|断网、刷新恢复、导入导出、停止人工记录|测试|执行人签字|
|P1-O12|`docs/PHASE1_ACCEPTANCE_REPORT.md`|报告|范围、环境、结果、限制、缺陷、结论|测试负责人|引用证据而非只写结论|
|P1-O13|`docs/PHASE1_BUSINESS_CONTENT_SIGNOFF.md`|签字|Logo、数字、口径、话术确认|业务负责人|生产口径发布前必须签字|
|P1-O14|`release/phase1/<version>/SHA256SUMS`|清单|发布文件摘要|发布负责人|与最终包一致|

## 3. 二期输出文件

|编号|文件/目录|类型|内容|生成/责任方|放行条件|
|---|---|---|---|---|---|
|P2-O01|`release/phase2/<version>/source/`|产品包|一期基线加真实 Provider、安全及诊断实现|研发|干净环境构建和一期回归通过|
|P2-O02|`docs/PHASE2_PROVIDER_CONFIG_TEMPLATE.md`|配置|模型、ClickHouse、MySQL 非敏感配置模板|研发+运维|无真实密钥，可按环境填写|
|P2-O03|`.env.example`|配置|环境变量名称和安全说明|研发|不含凭据和可用令牌|
|P2-O04|`docs/PHASE2_DEPLOYMENT_RUNBOOK.md`|运维|部署、密钥生成/轮换、迁移、启停、回滚|运维|目标环境演练通过|
|P2-O05|`docs/PHASE2_PROVIDER_DIAGNOSTICS.md`|运维|DNS/TCP/TLS/鉴权/Schema/最小查询诊断|研发+运维|覆盖三种 Provider|
|P2-O06|`docs/PHASE2_SQL_SECURITY_BASELINE.md`|安全|允许/拒绝规则、白名单、限制和攻击用例|安全负责人|安全复核签字|
|P2-O07|`evidence/phase2/<run-id>/protocol-tests.log`|证据|Stub 协议、解析、重试与错误映射|测试|E3 测试全部通过|
|P2-O08|`evidence/phase2/<run-id>/real-connectivity.json`|证据|真实端点的脱敏诊断结果|测试+运维|模型、ClickHouse、MySQL 均为 E4|
|P2-O09|`evidence/phase2/<run-id>/real-matrix-results.json`|证据|真实 Provider 33 轮、Trace、数据源和降级事实|测试|不得由 Stub/Fixture 冒充|
|P2-O10|`evidence/phase2/<run-id>/reconciliation.xlsx`|证据|黄金问题、平台值、源库值、差异、容差|数据/业务|差异通过且业务签字|
|P2-O11|`evidence/phase2/<run-id>/security-review.pdf`|证据|凭据、日志、权限与 SQL 安全复核|安全|无高危未关闭项|
|P2-O12|`evidence/phase2/<run-id>/recovery-drill.pdf`|证据|部署、备份、恢复、回滚演练|运维|恢复目标达到并签字|
|P2-O13|`docs/PHASE2_ACCEPTANCE_REPORT.md`|报告|区分 E3 仿真与 E4 真连的最终结论|测试负责人|所有 BLOCKED/FAIL 如实列出|
|P2-O14|`docs/PHASE2_ACCEPTANCE_SIGNOFF.md`|签字|研发、测试、业务、安全、运维、项目签字|项目负责人|全部门禁满足或书面拒绝放行|
|P2-O15|`release/phase2/<version>/SHA256SUMS`|清单|发布文件摘要|发布负责人|与最终包一致|

## 4. 本次立即落地的规划文件

本次先在仓库中落地以下事实源：

- `docs/PHASE1_PHASE2_AUTHENTICITY_ACCEPTANCE_PLAN.md`：真实性与完整性验收方法、矩阵和门禁；
- `docs/PHASE1_PHASE2_OUTPUT_FILE_PLAN.md`：一期、二期输出文件及责任划分；
- `docs/PHASE1_PHASE2_ACCEPTANCE_EXECUTION_2026-08-07.md`：本次实际执行结果和未完成阻塞项。

## 5. 文件生命周期

`draft` 由责任方编制，`reviewed` 由测试/安全/业务复核，`approved` 由项目负责人签字，`released` 后只允许新增修订版。每份正式材料头部必须包含版本、日期、提交 SHA、环境和审批状态。证据目录按 run-id 隔离；禁止用后一次成功日志覆盖前一次失败记录。

## 6. 建议生成顺序

1. 冻结源码后生成 source、POC 构建物和 Offline 文件。
2. 校验 Schema/Fixture，生成资产清单和 SHA256SUMS。
3. 执行自动矩阵并生成机器可读结果与原始日志。
4. 完成人工断网、真连、对账、安全和恢复记录。
5. 最后生成验收报告与签字页；报告中的每个 PASS 必须链接到对应证据。

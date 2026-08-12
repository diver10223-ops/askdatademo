# 产品V2.0唯一执行计划

> 文件：`PRODUCT_V2_EXECUTION_PLAN.md`  
> 版本：V1.0  
> 日期：2026-08-12  
> 状态：执行中（M1）
> 目标分支：`release/product-v2-test`  
> 稳定基线分支：`release/v1-v2-test`

## 1. 文件定位

本文是产品V2.0唯一的分步骤执行入口。产品V2.0的启动、任务顺序、完成状态、质量门禁、分支流转、客户适配和交付判定均以本文为准。

其他文档只作为设计依据：

- `DEVELOPMENT_PLAN.md`：总体需求、技术路线与阶段边界；
- `系统管理信息存储与数据库表设计-V1.0.md`：系统管理数据逻辑模型与容量设计；
- `CODEX_SKILLS_DESIGN.md`：内部研发、验收、恢复和交付自动化设计；
- `PHASE1_PHASE2_AUTHENTICITY_ACCEPTANCE_PLAN.md`：一期、二期真实性证据标准；
- `PHASE2_SQL_SECURITY_BASELINE.md`：第二阶段 SQL 安全基线。

如果其他文档与本文的执行顺序、阶段状态或完成口径冲突，应先修订本文并记录原因，再继续实施。设计事实本身发生变化时，同时修订对应设计文档。

## 2. 产品V2.0目标与边界

产品V2.0建设 Java + Python 企业版：

- Spring Boot 承担身份权限、系统管理、配置发布、审批审计、会话和平台运维；
- Python 保留七层 NLQ、模型适配、数据源适配和结果解读；
- 系统管理信息由前端种子、通用 JSON 和单机 SQLite 迁移到规范化平台数据库；
- Java/Python 之间使用版本化 API、服务鉴权、幂等、超时、错误码和 Trace；
- 完成企业级 SQL 安全、测试、可观测、部署、备份和恢复能力。

客户环境未知不阻塞环境中立的产品基线研发。数据库品牌、统一认证、KMS、基础设施、高可用、灾备和生产容量等客户相关事项，在目标客户信息明确后进入适配与生产验收。

产品V2.0有两个不同的完成状态：

1. **产品基线完成**：环境中立的企业版功能、系统管理信息入库、适配接口和仓库内测试通过；
2. **客户交付完成**：指定客户环境的选型落地、真实联调、性能安全验证、灾备演练和签字验收完成。

客户环境未明确时，可以达到“产品基线完成”，不得声明“客户交付完成”。

## 3. 不可破坏的原则

1. `release/v1-v2-test`始终保持可获取、可恢复、可演示、可运行 POC；
2. 产品V2.0开发不得直接修改稳定标签或依赖稳定演示目录中的运行数据；
3. Offline Demo 和一期/二期 POC 不得强制依赖 Spring Boot、MySQL、Redis或消息队列；
4. 产品V2.0使用独立分支、工作树、端口、数据目录和数据库；
5. 一期/二期稳定修复必须同时回流产品V2.0，产品V2.0未完成能力不得反向污染稳定分支；
6. Skill 及其提示词属于内部工程资产，不进入客户产品提交包；
7. 真实凭据、客户原始数据、未脱敏日志、本地数据库和密钥不得提交 Git；
8. 未获得真实环境证据的事项保持 `BLOCKED` 或 `NOT RUN`，不得用 Fixture、Stub 或文档声明代替；
9. 在线七层链路不依赖 Codex Skill；大模型只在受控边界内参与 L2/L7，并可辅助 L3/L5；
10. 所有生产迁移、发布、回滚和重置必须明确目标、备份和人工授权。

## 4. 状态、证据和更新规则

每个任务只允许使用以下状态：

- `NOT STARTED`：尚未开始；
- `IN PROGRESS`：正在实施，必须注明负责人和分支；
- `PASS`：产物、自动检查和证据全部满足退出条件；
- `CONDITIONAL PASS`：产品能力完成，但存在已记录且经批准的非生产限制；
- `BLOCKED`：缺少客户环境、凭据、业务口径或外部批准；
- `FAIL`：已验证行为不符合要求。

完成任务时必须在本文的执行记录中填写：任务ID、状态、提交SHA、执行日期、验证命令、证据路径、遗留问题和批准人。没有证据的任务不得标记为`PASS`。

## 5. 分支、标签和工作树策略

### 5.1 长期分支

从产品V2.0开始，分支按产品版本命名，不再使用“第几阶段”作为分支名。当前版本使用`release/product-v2-test`和`feature/product-v2-*`；未来产品V3.0使用`release/product-v3-test`和`feature/product-v3-*`。阶段编号只保留为历史规划说明。

| 分支 | 用途 | 允许变更 |
|---|---|---|
| `release/v1-v2-test` | 稳定演示与 POC 基线 | 严重缺陷、演示/POC修复、安全修复、交付文档 |
| `release/product-v2-test` | 产品V2.0集成 | 已通过局部验证的V2.0功能 |
| `feature/product-v2-*` | V2.0短期开发 | 单一任务或同一依赖链的功能 |
| `hotfix/v1-v2-*` | 稳定基线修复 | 最小修复及对应回归测试 |

### 5.2 稳定标签

第一份产品V2.0基线来源标签建议为：

~~~text
v1-v2-poc-baseline-20260812
~~~

标签必须带注释、不可覆盖，并记录提交SHA、验收结果和交付物SHA256。后续稳定版本使用新的日期或语义版本标签。

### 5.3 并行工作目录

建议使用 Git worktree 保证演示和开发互不占用：

~~~text
工作目录A：release/v1-v2-test 或稳定标签  → 演示/POC
工作目录B：release/product-v2-test           → V2.0集成
工作目录C：feature/product-v2-*              → 单项开发（按需）
~~~

各目录必须设置不同的`ASKDATA_DATA_DIR`、端口和产品V2.0数据库名。任何恢复脚本不得对含未提交修改的目录执行清理或强制切换。

## 6. 总体里程碑

| 里程碑 | 内容 | 依赖 | 完成结果 |
|---|---|---|---|
| M0 | 冻结一期/二期稳定基线 | 无 | 可恢复标签和干净V2.0分支 |
| M1 | 产品V2.0骨架与契约 | M0 | Spring Boot/Python最小闭环 |
| M2 | 系统管理数据底座 | M1 | 规范化平台库和版本化迁移 |
| M3 | 身份权限与审批审计 | M2 | 企业管理与安全闭环 |
| M4 | 配置、资产、场景与Provider管理 | M2、M3 | 管理信息全面入库 |
| M5 | 七层集成与完整SQL安全 | M1、M3、M4 | Java/Python企业问数闭环 |
| M6 | 运行态、队列、可观测与可靠性 | M5 | 并发、取消、事件和审计闭环 |
| M7 | 产品基线测试与迁移切换 | M2—M6 | 产品V2.0基线完成 |
| M8 | 客户环境适配 | M7、客户输入 | 指定客户技术环境可运行 |
| M9 | 客户验收与交付 | M8 | 真实环境和业务签字完成 |

M0—M7可以在客户环境尚未明确时推进；M8—M9按客户项目分别执行。

## 7. 分步骤执行计划

## M0：冻结一期/二期稳定基线

### P300 修复场景7缺参流程

**状态：**`PASS`（待P302提交后补充最终提交SHA）

执行：

1. 场景7首轮缺少机构、时间或指标时禁止自动补默认值；
2. 首轮必须在L2返回`WAITING_INPUT`，且不生成L3—L7、SQL或数据源访问记录；
3. 用户点击选项或自然语言补齐后创建关联的新Request；
4. 补全Request从L1重新执行，第一条Request轨迹保持不变；
5. 三个角色均覆盖首轮等待与第二轮成功。

退出条件：专项测试通过，`scripts/phase1-matrix.py`不再在`s7-admin`首轮失败。

### P301 重跑一期/二期仓库内门禁

**状态：**`PASS`（待P302提交后补充最终提交SHA）

至少执行：

~~~bash
bash scripts/diagnose.sh
bash scripts/demo-readiness-check.sh
bash scripts/phase2-readiness-check.sh
~~~

退出条件：后端测试、前端类型检查、在线构建、Offline构建、三角色八场景33轮矩阵及协议级二期测试全部通过；不能执行的真实环境项按事实记录，不伪造通过。

### P302 固化稳定分支和标签

**状态：**`PASS`（最终提交SHA以不可移动标签`v1-v2-poc-baseline-20260812`解析结果为准）

执行：

1. 安装并验证`gh`，确认GitHub认证与远端仓库；
2. 扫描全部待提交文件中的凭据、客户数据、数据库、缓存和超大文件；
3. 更新交付文档中的实际验收结论；
4. 将批准的当前变更提交并推送到`release/v1-v2-test`；
5. 创建并推送带注释的稳定标签；
6. 从该标签在全新临时目录完成一次恢复验证；
7. 创建并推送`release/product-v2-test`，切换到该分支继续工作。

退出条件：远端稳定分支、标签和V2.0分支均存在；恢复验证通过；V2.0工作区干净。

### P303 建立演示与开发隔离

**状态：**`PASS`

执行：建立稳定演示worktree和V2.0开发worktree；配置独立端口和数据目录；形成最短恢复命令；确认V2.0服务停止、失败或数据库迁移时，稳定演示仍可启动。

退出条件：在两个目录分别启动/构建，文件、端口和数据无相互覆盖。

### M0门禁

P300—P303全部`PASS`后才能开始会影响Java/Python边界或平台数据模型的编码。设计和任务细化可以提前进行，但不得宣称产品V2.0已经建立可迁移基线。

## M1：产品V2.0骨架与契约

### P310 冻结服务职责

**状态：**`PASS`

- Java：身份、权限、管理配置、审批发布、审计、会话入口和运维；
- Python：L1—L7引擎、模型与数据源Provider、SQL计划执行和结果解读；
- 禁止长期维护两套可写后台；兼容期内旧Python管理API只读或受控双读，不做无审计双写。

退出条件：形成服务边界、调用方向、数据所有权和迁移期读写矩阵。

设计基线见`PRODUCT_V2_SERVICE_BOUNDARY.md`。

### P311 建立Spring Boot工程骨架

**状态：**`PASS`

建立模块、配置加载、健康检查、结构化日志、统一错误体、测试框架和数据库迁移框架。不得写死客户数据库、认证、域名和凭据。

退出条件：Java服务在本地基线环境启动，健康检查和最小测试通过。

### P312 固化Java/Python内部契约

**状态：**`PASS`

覆盖API版本、服务鉴权、Session、Request、Parent Request、权限快照、配置版本、幂等键、超时、取消、错误码、Trace和SSE事件。

退出条件：OpenAPI/JSON Schema可解析；Java消费者与Python提供者契约测试通过；破坏性变更检测生效。

### P313 建立兼容入口

**状态：**`PASS`

稳定演示保持原入口；产品V2.0通过独立端口或显式模式启用。未完成Java服务不得成为一期/二期启动的强依赖。

退出条件：稳定入口回归通过，V2.0最小请求可贯穿Java入口与Python健康/模拟接口。

## M2：系统管理数据底座

### P320 冻结逻辑模型与客户可变项

**状态：**`PASS`

依据数据库设计文档冻结身份权限、数据资产、模型运行、流程场景、安全合规、运维配置、配置生命周期、运行记录、审批审计和演示管理等领域。客户未知项保留为适配决策，不阻塞逻辑模型。

退出条件：实体、关系、唯一性、状态机、敏感级别、保留策略占位和数据所有权评审通过。

### P321 建立版本化DDL和账号边界

**状态：**`PASS`

使用正式迁移工具管理DDL；区分迁移账号、应用读写账号和只读查询账号；开发基线方言与客户方言适配分离。

退出条件：空库升级、样例数据验证、降级/前滚恢复演练通过；应用账号不能任意DDL。

### P322 实现基础平台表

**状态：**`PASS`

优先实现配置版本、秘密引用、操作审计、用户/机构/角色/权限、数据源/表/字段、指标/维度、场景/参数/SQL模板和运行请求主表。

退出条件：核心表迁移、约束、索引和Repository测试通过；秘密明文不落库、不回显。

### P323 建立种子与旧数据迁移

**状态：**`PASS`

将`official_baseline_v1.json`、`demo_runtime_defaults.json`、前端seeds和`admin_resources`转换为可重复、幂等、可对账的迁移输入。官方JSON保留为初始化/灾备种子，不再作为日常编辑事实源。

退出条件：数量、编码、关联、权限、场景轮次和SHA256对账一致；重复执行不产生重复记录。

## M3：身份权限与审批审计

### P330 身份与组织模型

**状态：**`PASS`

实现本地用户影子记录、机构、岗位、外部身份提供方及主体映射；认证协议通过适配器接入。客户协议未知时使用测试身份Provider，不实现客户专属字段硬编码。

### P331 权限与数据范围

**状态：**`PASS`

实现角色、权限、用户/组映射、机构/指标/表/字段数据范围、显式拒绝、权限版本和缓存失效。权限最终裁决必须是确定性代码。

### P332 审批与配置发布

**状态：**`PASS`

实现草稿、变更项、审批模板、步骤、候选人、会签、动作、发布快照和回滚。客户审批人未知时使用可配置模板，不写死个人或部门。

### P333 不可变审计

**状态：**`PASS`

覆盖登录、授权、配置、审批、发布、秘密操作、敏感访问和运维动作；应用层禁止更新/删除审计事实；敏感前后值脱敏。

M3退出条件：身份、权限、审批、发布、回滚和审计端到端测试通过，越权路径无数据、SQL或结果泄露。

## M4：配置、资产、场景与Provider管理

### P340 数据资产与指标配置入库

**状态：**`NOT STARTED`

迁移数据源、表、字段、指标、维度、同义词、映射、优先级、血缘和敏感分级；管理API只读写规范化表。

### P341 流程场景配置入库

**状态：**`NOT STARTED`

迁移意图、参数、补全选项、SQL模板、场景、用例、轮次、快捷问题、Fixture和话术；发布版本影响新Session，不修改活动Session快照。

### P342 模型、数据源和秘密管理

**状态：**`NOT STARTED`

拆分非敏感Profile和密文/秘密引用；实现创建、轮换、禁用、诊断和审计；主密钥永不进入平台数据库、日志、导出或快照。

### P343 配置兼容切换

**状态：**`NOT STARTED`

按“数据库读写→旧资源只读→停止旧写路径→保留灾备种子”切换。禁止无对账的双写。

M4退出条件：后台管理功能由数据库驱动；配置发布、回滚和缓存失效正确；旧资源下线计划明确。

## M5：七层集成与完整SQL安全

### P350 Java入口与Python七层集成

**状态：**`NOT STARTED`

请求身份、权限快照、配置版本和Trace由Java入口传递到Python；Python返回状态、层轨迹、SQL事实和结果引用。重试必须幂等。

### P351 保持七层AI边界

**状态：**`NOT STARTED`

- L1：确定性交互与请求控制；
- L2：模型可抽取意图和参数，代码完成标准化、权限和缺参裁决；
- L3：模型/向量可召回候选，已发布语义配置最终裁决；
- L4：元数据与权限确定性选取资产；
- L5：模型最多生成候选计划，模板/AST和安全策略生成可执行SQL；
- L6：确定性执行、取消、限流、超时和结果脱敏；
- L7：模型只基于L6结果解读，不查库、不补数、不改数、不生成执行SQL。

### P352 完整SQL安全

**状态：**`NOT STARTED`

实现AST、多方言、只读与单语句、表列白名单、数据权限注入、时间/行数限制、成本/Explain、扫描量、复杂子查询和绕过测试。安全组件拥有最终拒绝权。

### P353 七层回归矩阵

**状态：**`NOT STARTED`

覆盖正常、缺参、推荐、拦截、多轮、多SQL、部分成功、取消、重试、模型异常、数据源异常和上下文污染。

M5退出条件：Java/Python企业链路矩阵通过；原一期/二期33轮矩阵继续通过；L7数值一致性检查通过。

## M6：运行态、队列、可观测与可靠性

### P360 会话、请求和事件持久化

**状态：**`NOT STARTED`

实现Session、Request、层执行、SQL/Provider执行、结果快照和SSE事件；大表按时间分区或归档；结果按数据等级过期。

### P361 队列、并发和超载

**状态：**`NOT STARTED`

初始基线：全局执行并发30—50、单用户2、等待队列50、最大排队5秒、超载1秒内返回429/503。最终值由压测定标。

### P362 SSE与取消

**状态：**`NOT STARTED`

支持Event ID、心跳、断线续传、共享事件存储、重连退避和取消传播；不依赖单机内存恢复。

### P363 可观测与告警

**状态：**`NOT STARTED`

建立请求、模型、SQL、队列和发布Trace；指标与日志不得泄露凭据或未脱敏业务数据；告警渠道通过适配器配置。

### P364 备份、恢复与灾难演练

**状态：**`NOT STARTED`

覆盖平台库、配置快照、密钥引用、迁移版本和发布包；验证匹配版本恢复，禁止只恢复数据库而遗漏密钥或配置版本。

M6退出条件：故障、取消、重连、积压和恢复测试通过；客户级HA/RPO/RTO留到M8定标。

## M7：产品基线测试与迁移切换

### P370 完整测试体系

**状态：**`NOT STARTED`

建立Java与Python单元测试、数据库集成测试、契约、E2E、安全、性能冒烟和回归测试；所有测试可在无客户凭据环境运行。

### P371 迁移演练

**状态：**`NOT STARTED`

从一期/二期官方基线和样例管理库升级到产品V2.0；验证数据数量、关联、权限、发布版本、审计和回滚/前滚恢复。

### P372 产品基线容量验证

**状态：**`NOT STARTED`

使用可控测试环境执行阶梯、200QPS短突发、30/50执行并发、1300 SSE、30分钟峰值和8小时长稳；结果作为产品参考，不冒充客户生产容量。

### P373 安全与发布审查

**状态：**`NOT STARTED`

执行依赖、凭据、权限、SQL绕过、日志脱敏、配置发布、备份恢复和交付包扫描；严重缺陷清零。

### P374 产品基线候选发布

**状态：**`NOT STARTED`

生成版本、迁移包、部署模板、OpenAPI、架构/运维/用户/管理员/安全/测试文档和SHA256。内部`skills/`、`CODEX_SKILLS_DESIGN.md`、提示词和内部测试样例排除在客户产品包之外。

### M7门禁：产品V2.0基线完成

以下条件全部满足才可声明：

- M1—M6全部产品任务通过；
- 系统管理信息已由数据库作为事实源；
- Java/Python契约与企业七层链路通过；
- 一期/二期稳定演示和POC无回归；
- 空环境安装、升级、回滚和恢复可复现；
- 客户未知项已参数化并登记；
- 发布包不含凭据、客户数据、内部Skill资产和本地运行数据。

## M8：客户环境适配

### P380 客户信息采集与差距分析

**状态：**`BLOCKED`（等待具体客户输入，按客户项目单独复制记录）

采集数据库、认证、网络、KMS、部署、高可用、灾备、容量、合规保留和审批组织。未知项明确标记`UNKNOWN`。

### P381 技术适配与部署

**状态：**`BLOCKED`

完成目标数据库方言和物理DDL、认证属性映射、KMS、Redis/消息队列、证书网络和部署拓扑。

### P382 真实联调与对账

**状态：**`BLOCKED`

连接客户真实模型和业务数据源，执行诊断、黄金问题、33轮或批准的扩展矩阵，并与源库SQL对账。

### P383 客户容量、安全和灾备验证

**状态：**`BLOCKED`

按客户SLA完成压测、安全测试、故障演练、备份恢复和RPO/RTO验证。

M8退出条件：目标环境E4证据齐全，所有重大差距关闭或获得书面豁免。

## M9：客户验收与交付

### P390 业务验收

**状态：**`BLOCKED`

业务方确认指标、维度、机构、时间、单位、舍入、空值、归因和回答话术；形成E5签字。

### P391 正式交付包

**状态：**`BLOCKED`

从批准标签生成客户产品包、迁移、配置模板、文档、OpenAPI、证据索引和SHA256；排除真实凭据、客户原始数据、内部Skill和临时文件。

### P392 上线与回滚窗口

**状态：**`BLOCKED`

确认备份、变更窗口、责任人、观察指标、回滚条件和旧版本保留期，完成上线或受控试运行。

### M9门禁：产品V2.0客户交付完成

只有E4真实环境验证、E5业务签字、交付签收和上线/回滚记录齐全时才能声明完成。

## 8. 稳定版本维护与修复回流

稳定演示发现缺陷时：

~~~text
release/v1-v2-test
    └── hotfix/v1-v2-问题
          ├── 验证后合回 release/v1-v2-test 并创建新标签
          └── 同步合入 release/product-v2-test
~~~

产品V2.0代码默认不得反向合入`release/v1-v2-test`。只有不引入Java、平台数据库或新增基础设施依赖的通用修复，经过一期/二期完整门禁后才允许选择性回流。

## 9. 内部Skill实施位置

Skill建设不是M1—M7产品功能的完成条件，但优先用于降低重复操作风险：

1. P0：验收运行、演示恢复、稳定基线发布；
2. P1：数据库迁移、Java/Python契约、配置生命周期；
3. P2：客户环境采集和交付成册。

Skill源文件可以在内部源码仓库版本化，但必须从客户产品包排除。Skill故障不得影响在线问数、管理后台和生产运维。

## 10. 当前执行看板

| 顺序 | 任务 | 当前状态 | 下一动作 |
|---:|---|---|---|
| 1 | P300 场景7修复 | PASS | 稳定标签已固化专项测试证据 |
| 2 | P301 一二期门禁 | PASS | 稳定标签已固化全量仓库门禁证据 |
| 3 | P302 稳定提交、标签和V2.0分支 | PASS | 以稳定标签作为V2.0开发起点 |
| 4 | P303 工作树隔离 | PASS | 稳定标签工作树已建立并复验 |
| 5 | P310 服务职责冻结 | PASS | Java控制面、Python执行面及唯一写入所有权已冻结 |
| 6 | M1—M7 产品基线 | IN PROGRESS | M3已通过，下一步P340实现数据资产与指标配置入库 |
| 7 | M8—M9 客户交付 | BLOCKED | 等待具体客户环境和验收输入 |

P300—P303已完成，M0门禁通过。稳定演示工作树位于`/workspaces/askdatademo-v1-v2-demo`，V2.0开发工作树位于`/workspaces/askdatademo`；P310—P311已完成，下一步执行P312。

## 11. 执行记录模板

每完成或阻塞一个任务，在本节追加记录：

| 字段 | 内容 |
|---|---|
| 任务ID | 例如P300 |
| 状态 | PASS / CONDITIONAL PASS / BLOCKED / FAIL |
| 分支与提交 | 分支名、完整SHA |
| 日期与执行人 | UTC日期、责任人 |
| 验证命令 | 实际执行命令 |
| 证据 | 日志、报告、截图或构建物路径 |
| 遗留问题 | 缺陷、风险、未知项和期限 |
| 批准 | 审核人或批准记录 |

### P300执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P300 |
| 状态 | PASS |
| 分支与提交 | `release/v1-v2-test`；稳定标签`v1-v2-poc-baseline-20260812` |
| 日期与执行人 | 2026-08-12；Codex执行，项目负责人确认需求口径 |
| 验证命令 | `PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests/test_phase1.py -k scenario7`；`PYTHONPATH=backend .venv/bin/python scripts/phase1-matrix.py`；`PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests` |
| 证据 | 场景7专项：3 passed；完整矩阵：3角色×8场景×33轮通过；后端：29 passed、2个既有弃用警告 |
| 遗留问题 | FastAPI `on_event`弃用警告进入V2.0技术债 |
| 批准 | 待稳定基线批准 |

### P301执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P301 |
| 状态 | PASS（真实客户环境项仍按计划待执行） |
| 分支与提交 | `release/v1-v2-test`；稳定标签`v1-v2-poc-baseline-20260812` |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `bash scripts/demo-readiness-check.sh`；`bash scripts/phase2-readiness-check.sh`；`sha256sum -c docs/deliverables/SHA256SUMS`；`git diff --check` |
| 证据 | 一期READY；二期READY且一期回归通过；一期33轮、二期协议仿真33轮；后端29 passed；二期专项7 passed；前端/Offline构建通过；4份PDF摘要通过 |
| 遗留问题 | 2个FastAPI `on_event`弃用警告；真实模型、ClickHouse/MySQL、真实33轮与对账、性能、安全、恢复和业务签字待目标环境 |
| 批准 | 待稳定基线批准 |

### P302执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P302 |
| 状态 | PASS |
| 分支与提交 | `release/v1-v2-test`；不可移动标签`v1-v2-poc-baseline-20260812`；V2.0分支`release/product-v2-test` |
| 日期与执行人 | 2026-08-12；Codex执行，GitHub账号`diver10223-ops` |
| 验证命令 | `gh auth status`；`git fetch origin --prune --tags`；敏感信息扫描；`git push`；`git push origin v1-v2-poc-baseline-20260812`；`git push -u origin release/product-v2-test` |
| 证据 | 远端稳定分支、带注释标签和V2.0分支；最终SHA由`git rev-list -n 1 v1-v2-poc-baseline-20260812`读取 |
| 遗留问题 | P303需完成双工作树和独立运行目录验证 |
| 批准 | 用户已明确授权提交全部当前产品变更并创建版本分支 |

### P303执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P303 |
| 状态 | PASS |
| 分支与提交 | 演示：标签`v1-v2-poc-baseline-20260812`（`5db61e3ce04ffb7dc87882cef67ad09cf70da755`）；开发：`release/product-v2-test` |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `git worktree add --detach /workspaces/askdatademo-v1-v2-demo v1-v2-poc-baseline-20260812`；从稳定工作树运行`phase1-matrix.py`；检查Offline单文件存在且无外部资源引用 |
| 证据 | 两个worktree指向独立目录；稳定标签工作树干净；稳定工作树3角色×8场景×33轮通过；Offline产物检查通过 |
| 遗留问题 | 正式并行启动时分别设置独立`ASKDATA_DATA_DIR`和端口；V2.0 Java环境在P311配置 |
| 批准 | M0技术门禁通过 |

### P310执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P310 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证 | 对照当前FastAPI API、SQLite表、前端适配器和V2.0数据库设计完成职责审计 |
| 证据 | `docs/PRODUCT_V2_SERVICE_BOUNDARY.md` |
| 结论 | Java为平台控制面和外部入口；Python为七层执行面；生产表唯一写入所有者；迁移期禁止业务双写 |
| 遗留问题 | P312冻结具体OpenAPI/事件Schema；客户认证和数据库产品在M8适配 |
| 批准 | 作为P311、P312实施基线 |

### P311执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P311 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH ./platform-service/mvnw -f platform-service/pom.xml -q clean verify`；`git diff --check` |
| 证据 | Surefire报告`platform-service/target/surefire-reports/TEST-com.askdata.platform.PlatformServiceApplicationTests.xml`：2 tests、0 failures、0 errors；测试启动随机端口并验证`/api/v2/health`；Flyway从空库执行V1迁移 |
| 结论 | 建立Java 21、Spring Boot 4.1、Maven Wrapper、配置加载、Actuator、统一错误体、Trace、结构化日志、Flyway、H2开发基线与PostgreSQL驱动；客户数据库、域名和凭据均由环境注入 |
| 遗留问题 | 当前交互Shell尚未加载Dev Container Java Feature，仓库测试已用隔离Temurin JDK 21通过；容器再次重建后复核全局`java -version` |
| 批准 | 满足P311退出条件，作为P312契约实施基线 |

### P312执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P312 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `python scripts/check-contract-compatibility.py`；`PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests`；`JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH ./platform-service/mvnw -f platform-service/pom.xml -q test` |
| 证据 | `contracts/internal-execution-v1.openapi.json`及冻结兼容基线；Python 31 passed；Java 4 tests、0 failures；未鉴权内部健康请求返回401，正确服务令牌返回200 |
| 结论 | 契约覆盖版本、服务鉴权、Session/Request/Parent Request、主体与角色、权限快照、配置版本、Provider、幂等键、超时、取消、错误码、Trace及可续传SSE事件；Java DTO和Python Pydantic模型受同一契约测试约束 |
| 遗留问题 | 本地默认服务令牌仅用于开发；非开发环境必须通过秘密引用注入，轮换与KMS适配在M3/M8验证 |
| 批准 | 满足P312退出条件，作为P313联调基线 |

### P313执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P313 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH bash scripts/v2-p313-smoke.sh`；`PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests`；`./platform-service/mvnw -f platform-service/pom.xml -q verify`；从稳定工作树运行`phase1-matrix.py` |
| 证据 | 双进程脚本输出`P313 READY: Java control plane -> Python execution plane`；Java控制面在独立18080端口通过服务令牌调用Python执行面18000端口并透传Trace和幂等键；Python 32 passed；Java 4 tests、0 failures；稳定标签33轮矩阵退出码0 |
| 结论 | V1.x演示继续使用原FastAPI入口且不依赖Java；产品V2.0使用独立Java入口；Python提供带鉴权、幂等、状态、取消和可续传SSE的P313模拟执行接口 |
| 遗留问题 | P313执行结果为明确标记的模拟L1闭环；真实七层企业链路在M5接入，不能把本项证据用于宣称真实数据源联调 |
| 批准 | M1门禁通过，可进入M2平台数据底座 |

### P320执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P320 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证 | 对照`系统管理信息存储与数据库表设计-V1.0.md`、服务职责矩阵和P312内部契约逐域审查 |
| 证据 | `docs/PRODUCT_V2_LOGICAL_DATA_MODEL.md`：12个领域、核心关系与不变量、9类状态机、5级敏感分级、保留策略占位、7类客户可变项及P321—P323验收映射 |
| 结论 | 逻辑模型与Java/Python数据所有权冻结；数据库、统一认证、KMS、Redis、队列、对象存储和客户保留期通过适配点隔离，不阻塞产品基线 |
| 遗留问题 | 客户生产选型及合规值继续保持M8/M9 BLOCKED；P321将开发方言定为PostgreSQL兼容并验证H2测试方言 |
| 批准 | 满足P320退出条件，作为Flyway DDL唯一逻辑基线 |

### P321执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P321 |
| 状态 | PASS（客户数据库真实恢复演练仍归M8） |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH ./platform-service/mvnw -f platform-service/pom.xml -q test` |
| 证据 | `DatabaseMigrationTests`：空库Flyway升级、二次执行0迁移、validate成功、样例元数据可读；应用账号获授权DML/查询但`CREATE TABLE`抛出SQL权限异常；总计Java 6 tests、0 failures |
| 结论 | Spring应用连接与Flyway迁移连接由独立环境变量注入；PostgreSQL角色模板区分迁移、应用和只读账号且不含默认生产密码；迁移只追加，失败采用快照恢复后修正迁移前滚 |
| 遗留问题 | H2仅证明产品账号边界语义；客户数据库品牌、真实授权、备份恢复、主从及方言证据在M8执行并保持BLOCKED |
| 批准 | 满足P321产品基线退出条件，可进入P322核心表迁移 |

### P322执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P322 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH ./platform-service/mvnw -f platform-service/pom.xml -q test` |
| 证据 | Flyway V2从空库创建24张核心表及关键索引；`CorePlatformSchemaTests`验证16张必需表、唯一键、外键、状态检查约束和秘密公共视图；Java总计9 tests、0 failures、0 errors |
| 结论 | 发布/当前指针/变更项、秘密引用、不可变审计、机构用户角色权限、数据源表字段、指标维度、参数/SQL模板/场景关联、会话和请求主表已落库；秘密仓库API不返回外部引用、密文、值或密码字段 |
| 遗留问题 | M3/M4继续补齐外部身份、细粒度范围、审批流程、Provider及全部管理API；P323导入官方种子并对账 |
| 批准 | 满足P322退出条件，可进入P323旧数据迁移 |

### P323执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P323 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH ./platform-service/mvnw -f platform-service/pom.xml -q test`；专项`-Dtest=LegacySeedImporterTests test` |
| 证据 | 两次幂等导入后：3机构、3用户、3角色、9角色权限、3指标、2维度、8场景、24角色场景关系、24用例、33轮、4来源账本、6发布明细（运行默认值+5旧后台资源）；官方基线SHA256=`9f89eab9d1b646ce725af37c4d4ba0316fce24f6f212f150a8f5c8bc12bd604d`，运行默认值SHA256=`f6fd5ebb027986021d3290954bb225e3c7ee77583768292a116ae59484a7dab0` |
| 结论 | 官方JSON、前端共用种子、运行默认值及当前旧`admin_resources`均进入规范化实体、发布明细和来源账本；导入默认关闭，仅在初始化/恢复时显式启用，JSON不再被设计为日常编辑事实源 |
| 遗留问题 | M4完成管理API切换前，旧FastAPI后台仍服务V1.x演示；禁止在兼容期无对账双写 |
| 批准 | M2门禁通过，可进入M3身份权限与审批审计 |

### P330执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P330 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH ./platform-service/mvnw -f platform-service/pom.xml -q test` |
| 证据 | Flyway V4建立认证源、外部主体、外部组/角色映射和认证事件；`IdentityProvisioningTests`证明同一外部主体两次JIT登录只创建一个影子用户/映射、追加两条登录事件，禁用认证源后拒绝登录；Java总计11 tests、0 failures |
| 结论 | 认证协议通过`IdentityProviderAdapter`隔离；测试Provider仅在显式属性启用；外部唯一主体、机构映射、属性摘要和认证审计已入库，不保存测试凭据 |
| 遗留问题 | 客户OIDC/SAML/LDAP元数据、组/机构Claim和登出撤销联调归M8；M3后续补权限缓存失效和审批 |
| 批准 | 满足P330退出条件，可进入P331权限与数据范围 |

### P331执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P331 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH ./platform-service/mvnw -f platform-service/pom.xml -q test` |
| 证据 | Flyway V5建立机构/指标/表/字段范围、用户临时覆盖、强制合规拒绝及权限版本事件；`PermissionDecisionTests`逐步验证默认拒绝→角色允许→用户拒绝→角色拒绝→强制合规拒绝，并验证版本+1和失效事件；Java总计12 tests、0 failures |
| 结论 | 权限最终裁决为确定性Java代码，拒绝优先级固定；Session可取得带版本的角色快照，授权变更产生精确失效事件，不由大模型决定权限 |
| 遗留问题 | 分布式Redis权限缓存与消息广播在M6接入；客户实际组织/组同步与敏感授权矩阵在M8验证 |
| 批准 | 满足P331退出条件，可进入P332审批与配置发布 |

### P332执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P332 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH ./platform-service/mvnw -f platform-service/pom.xml -q test` |
| 证据 | Flyway V6建立流程定义/步骤、审批实例、候选人和动作；`ApprovalReleaseWorkflowTests`完成两个版本的草稿→两级审批→发布，再回滚至首版；当前指针正确、4次审批动作齐全、回滚生成第三个新发布且原快照不变；Java总计13 tests、0 failures |
| 结论 | 审批实例固定流程版本，支持ANY/ALL/SEQUENTIAL模型和候选人快照；未批准或目标不匹配不能发布；回滚通过新发布记录实现，不覆盖历史快照 |
| 遗留问题 | 客户实际审批人、会签模板、超时升级和通知渠道在M8配置联调；P333增加篡改可检测审计链 |
| 批准 | 满足P332退出条件，可进入P333不可变审计 |

### P333执行记录

| 字段 | 内容 |
|---|---|
| 任务ID | P333 |
| 状态 | PASS |
| 分支与提交 | `release/product-v2-test`；提交SHA以本记录所在提交为准 |
| 日期与执行人 | 2026-08-12；Codex执行 |
| 验证命令 | `JAVA_HOME=/tmp/askdata-jdk21 PATH=/tmp/askdata-jdk21/bin:$PATH ./platform-service/mvnw -f platform-service/pom.xml -q test`；专项`-Dtest=TamperEvidentAuditTests test` |
| 证据 | Flyway V7建立审计链头和完整性链；测试追加登录、授权、配置发布、审批、秘密轮换、敏感访问、重置7类事件，初次校验7/7有效；密码/API Key落库为`***`；直接SQL篡改首条日志后校验返回首个破坏ID；Java总计14 tests、0 failures |
| 结论 | 审计服务仅暴露append/verify；PostgreSQL应用角色模板撤销审计事实UPDATE/DELETE；身份登录、权限失效、审批、发布和回滚服务已接入链式审计，敏感前后值先脱敏后哈希 |
| 遗留问题 | 客户WORM归档、SIEM、数据库超级管理员审计及法务冻结在M8联调；本产品链用于篡改检测，不替代客户外部不可变存储 |
| 批准 | M3门禁通过，可进入M4配置、资产、场景与Provider管理 |

## 12. 下一步

M0已经完成。当前执行链为：

~~~text
P313 建立兼容入口
  ↓
P320 冻结逻辑模型与客户可变项
~~~

后续V2.0开发不得修改稳定标签工作树；稳定缺陷按hotfix回流规则处理。

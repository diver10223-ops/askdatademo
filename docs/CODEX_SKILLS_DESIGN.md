# NLQ 智能银行问数平台：Codex Skills 设计

> 版本：V1.0  
> 日期：2026-08-12  
> 适用范围：一期/二期稳定演示与 POC、第三阶段企业版研发及客户适配  
> 定位：研发与交付自动化能力，不属于平台生产运行时

## 1. 设计结论

Skill 适合封装“由研发、测试、实施或交付人员触发，步骤重复、输入输出明确、需要读取项目知识并调用工具”的工作。在线问数、权限裁决、SQL 执行、审批引擎、审计落库和生产监控仍必须由正式系统服务实现，不能依赖 Codex Skill 运行。

本项目建议建设八个项目级 Skill：

| 优先级 | Skill | 主要作用 | 适用阶段 |
|---|---|---|---|
| P0 | `askdata-demo-restore` | 获取、恢复、启动稳定演示/POC版本 | 一期、二期、三期并行期间 |
| P0 | `askdata-acceptance-runner` | 执行验收矩阵并生成可追溯报告 | 全阶段 |
| P0 | `askdata-release-baseline` | 固化、校验、打包和发布稳定基线 | 一期、二期维护 |
| P1 | `askdata-customer-discovery` | 采集客户环境信息并输出适配差距 | 第三阶段客户适配 |
| P1 | `askdata-config-lifecycle` | 校验配置、发布、回滚和对账 | 二期、三期 |
| P1 | `askdata-schema-migration` | 管理平台表设计、迁移和回滚检查 | 产品V2.0基线 |
| P1 | `askdata-java-python-contract` | 校验 Java/Python API 与契约兼容性 | 产品V2.0基线 |
| P2 | `askdata-delivery-packager` | 生成交付文档、截图、OpenAPI和摘要 | 项目交付 |

## 2. Skill 与正式系统能力的边界

### 2.1 适合用 Skill 实现

- 检出指定标签、初始化依赖、恢复官方基线并启动演示；
- 执行健康检查、三角色八场景矩阵、构建、安全扫描和报告汇总；
- 采集客户数据库、认证、网络、KMS、部署和灾备信息；
- 比较客户环境与产品基线，生成缺口、风险和待确认清单；
- 检查配置 Schema、引用完整性、发布影响、版本差异和回滚条件；
- 从逻辑模型生成候选迁移文件，检查迁移顺序、兼容性和回滚脚本；
- 对 Java/Python OpenAPI、JSON Schema、错误码和事件契约做差异检测；
- 生成交付文档、实际截图、OpenAPI、SHA256和签收清单；
- 协助定位失败原因和提出修复建议；经用户明确授权后修改代码。

### 2.2 不应用 Skill 替代

- 面向最终用户的实时问数七层执行；
- 生产环境的身份认证、授权和数据权限裁决；
- 生产 SQL 安全网关、限流、排队、取消和熔断；
- 配置审批流、审计日志和发布状态的正式事实源；
- 生产数据库迁移执行器、持续监控和自动故障切换；
- 密钥保存、解密或跨系统搬运；
- 无人审批的生产发布、删库、重置或回滚。

Skill 可以调用正式 API 或脚本辅助上述流程，但不能成为生产系统正确性和可用性的必要依赖。

## 3. Skill 详细设计

### 3.1 `askdata-demo-restore`

**触发示例：**“恢复可演示版本”“启动一期 POC”“从稳定标签恢复演示环境”。

**输入：**版本标签或稳定分支、运行形态（Offline/POC）、可选数据目录。  
**输出：**检出版本、依赖与环境诊断、恢复结果、访问地址、版本提交号和失败处置建议。

**固定流程：**

1. 禁止在有未提交变更的目录中强制切换或清理；
2. 获取远端和标签，默认选择经批准的稳定标签；
3. 创建独立工作树或独立目录，不占用第三阶段开发目录；
4. 排除真实 `.env`、凭据和客户数据，使用环境模板；
5. 初始化官方基线，运行诊断和就绪检查；
6. Offline 验证无外部资源，POC 输出唯一访问入口；
7. 记录标签、提交、依赖版本和校验结果。

**复用资源：**`scripts/start-poc.sh`、`scripts/diagnose.sh`、`scripts/init-db.sh`、稳定标签规则和恢复操作手册。

### 3.2 `askdata-acceptance-runner`

**触发示例：**“跑完整验收”“验证场景7”“确认当前版本能否演示”。

**输入：**验收层级（冒烟/完整/专项）、运行模式、可选真实 Provider Profile 名称。  
**输出：**机器可读结果、Markdown报告、失败断言、证据路径和是否允许发布的结论。

**固定流程：**

1. 使用临时数据目录，避免污染演示和开发数据；
2. 依次执行 Schema、诊断、后端测试、前端类型检查与构建；
3. 执行三角色、八场景、33个必要轮次并核对状态、终止层和SQL事实；
4. 明确区分 Fixture、SQLite和真实 Provider，不用模拟结果冒充真连证据；
5. 对失败项保留原始输出并归类为代码、基线、环境或外部依赖问题；
6. 只有全部发布门禁通过时才输出 `READY`。

**复用资源：**`scripts/demo-readiness-check.sh`、`scripts/phase1-matrix.py`、`scripts/phase2-matrix.py`、`scripts/phase2-readiness-check.sh`、验收报告模板。

### 3.3 `askdata-release-baseline`

**触发示例：**“固化当前演示基线”“生成可恢复版本”“发布一期二期稳定包”。

**输入：**目标分支、版本号、发布说明和批准人。  
**输出：**提交、不可移动标签、发布包、SHA256、验证记录和恢复命令。

**固定流程：**

1. 确认当前分支、变更范围和远端状态；
2. 扫描凭据、客户数据、运行数据库、缓存和超大文件；
3. 调用完整验收 Skill，失败时禁止打标签；
4. 生成 Offline、POC源码/构建物、文档和摘要；
5. 提交并推送稳定分支，创建带注释标签；
6. 从标签在全新临时目录执行一次恢复验证；
7. 输出标签、提交、SHA256和最短恢复步骤。

**安全约束：**禁止覆盖已有标签；禁止把开发中的三阶段代码直接合入稳定基线；生产发布必须人工批准。

### 3.4 `askdata-customer-discovery`

**触发示例：**“整理客户环境确认表”“评估这个客户能否部署”“生成技术差距清单”。

**输入：**客户填写表、访谈记录或已有架构资料；允许部分未知。  
**输出：**已确认项、未知项、产品基线差距、阻塞项、风险、适配任务和建议验证命令。

**采集领域：**

- 操作系统、CPU架构、虚拟机/容器/Kubernetes；
- 平台数据库、业务数据源、Redis和消息队列；
- OIDC、SAML、LDAP及身份属性；
- DNS、代理、VPN、TLS、证书、端口和出口规则；
- KMS、凭据交付、日志审计和数据保留；
- 高可用、灾备、RPO/RTO、备份与恢复；
- 用户规模、QPS、并发、SSE、SLA和数据规模。

未知信息必须标记为 `UNKNOWN`，不得自行补成已确认事实。Skill 只生成建议，不连接客户系统或处理真实凭据，除非用户另行明确授权并提供受控工具。

### 3.5 `askdata-config-lifecycle`

**触发示例：**“检查这份配置能否发布”“比较两个配置版本”“制定回滚方案”。

**输入：**草稿、当前发布版本、Schema和目标运行模式。  
**输出：**Schema结果、引用错误、影响对象、敏感字段检查、差异摘要、发布或回滚建议。

**检查内容：**角色与资源引用、场景轮次、指标字段映射、SQL模板参数、Provider白名单、模式策略、凭据占位符、版本号和SHA256。发布和回滚通过正式管理 API 执行，Skill 不直接修改生产事实表。

### 3.6 `askdata-schema-migration`

**触发示例：**“为系统管理信息生成迁移”“审查这次DDL”“检查能否回滚”。

**输入：**逻辑模型、目标数据库方言、当前 Schema 版本和兼容窗口。  
**输出：**候选迁移、回滚迁移、影响分析、数据迁移步骤和验证 SQL。

**固定流程：**

1. 默认依据《系统管理信息存储与数据库表设计-V1.0》；
2. 客户数据库未知时只冻结逻辑模型和数据库中立约束；
3. 检查主键、唯一键、外键、索引、状态机、审计和敏感字段；
4. 禁止普通应用账号获得 DDL 权限；
5. 禁止自动执行生产迁移；
6. 在临时数据库完成 upgrade、数据校验和 downgrade 演练；
7. 输出需要客户确认的方言、分区、HA和保留周期差异。

### 3.7 `askdata-java-python-contract`

**触发示例：**“检查Java和Python接口是否兼容”“比较两版OpenAPI”“验证错误码和SSE事件”。

**输入：**Java/Python OpenAPI、JSON Schema、事件 Schema和版本策略。  
**输出：**破坏性变化、兼容变化、缺失字段、错误码冲突、契约测试结果和升级建议。

**重点检查：**API版本、身份传递、权限快照、Session/Request父子关系、幂等键、超时、取消、Trace、SSE Event ID、分页、错误体和时间格式。Skill 可生成契约测试骨架，但正式接口必须由服务测试验证。

### 3.8 `askdata-delivery-packager`

**触发示例：**“生成客户交付包”“更新操作手册和截图”“输出发布摘要”。

**输入：**批准标签、文档版本、交付范围和目标环境证据。  
**输出：**PDF/HTML、截图、OpenAPI、SHA256、交付清单、已知风险和签收页。

**固定流程：**

1. 只从已批准标签生成，不从脏工作树生成正式交付包；
2. 截图必须来自实际页面并检查敏感信息；
3. 自动结果与客户目标环境证据分开标记；
4. 未执行事项保持“待执行”，禁止生成虚假通过结论；
5. 发布前扫描凭据、客户原始数据、数据库文件和本地日志；
6. 为所有交付物生成SHA256并记录来源提交。

**复用资源：**`scripts/capture-manual-screenshots.py`、`scripts/generate-delivery-docs.py`和`docs/deliverables/`模板。

## 4. 推荐目录结构

Skill 应作为项目源码的一部分版本化，建议放在仓库的 `skills/` 下，再按需安装到 Codex Skill 目录。每个 Skill 保持独立，避免一个巨型 Skill 在每次触发时加载全部项目知识。

~~~text
skills/
├── askdata-demo-restore/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── scripts/restore-demo.sh
│   └── references/recovery-policy.md
├── askdata-acceptance-runner/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── scripts/run-acceptance.sh
│   └── references/acceptance-matrix.md
├── askdata-release-baseline/
├── askdata-customer-discovery/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/environment-fields.md
│   └── assets/customer-environment-template.md
├── askdata-config-lifecycle/
├── askdata-schema-migration/
├── askdata-java-python-contract/
└── askdata-delivery-packager/
~~~

`SKILL.md`只保存触发范围、固定流程、安全边界和资源导航；详细Schema、验收矩阵和环境字段放入`references/`；确定性、重复且易出错的步骤放入`scripts/`；客户填写表和交付模板放入`assets/`。

## 5. 组合工作流

### 5.1 随时演示与POC

~~~text
askdata-demo-restore
        ↓
askdata-acceptance-runner
        ↓
输出访问地址、版本、状态和证据
~~~

该流程使用稳定标签的独立工作树，不读取或修改第三阶段开发目录。

### 5.2 稳定基线发布

~~~text
askdata-acceptance-runner
        ↓ 通过
askdata-release-baseline
        ↓
askdata-delivery-packager
~~~

### 5.3 第三阶段客户适配

~~~text
askdata-customer-discovery
        ├── askdata-schema-migration
        ├── askdata-java-python-contract
        └── askdata-config-lifecycle
                         ↓
              目标环境验收与交付成册
~~~

## 6. 权限与安全等级

| 等级 | 操作 | 默认策略 |
|---|---|---|
| L0 | 读取文档、比较Schema、生成计划 | 可直接执行 |
| L1 | 本地临时目录构建、测试、生成报告 | 可直接执行并保留证据 |
| L2 | 修改源码、配置草稿、迁移文件 | 需用户已明确要求变更 |
| L3 | 提交、推送、打标签、创建发布 | 需用户明确授权且门禁通过 |
| L4 | 目标环境发布、数据库迁移、回滚、重置 | 必须再次确认目标和备份，不得由Skill自行决定 |

任何 Skill 均不得输出、保存或提交真实密码、令牌、API Key、客户原始数据和未脱敏日志。遇到权限、认证或目标环境不明确时，应停止对应写操作并输出待确认项。

## 7. 实施顺序与验收

本节只定义Skill自身的建设优先级。产品V2.0项目任务、分支操作和里程碑门禁统一从`PRODUCT_V2_EXECUTION_PLAN.md`执行。

### 第一批：保证演示和POC不受第三阶段影响

1. 创建 `askdata-acceptance-runner`；
2. 修复场景7并让33轮矩阵通过；
3. 创建 `askdata-demo-restore`；
4. 创建 `askdata-release-baseline`；
5. 从稳定标签执行一次全新恢复演练。

### 第二批：支撑产品V2.0基线

1. 创建 `askdata-schema-migration`；
2. 创建 `askdata-java-python-contract`；
3. 创建 `askdata-config-lifecycle`；
4. 在临时数据库和契约样例上做正向、失败和回滚测试。

### 第三批：支撑客户适配和交付

1. 创建 `askdata-customer-discovery`；
2. 创建 `askdata-delivery-packager`；
3. 使用一份信息不完整的模拟客户表验证`UNKNOWN`和阻塞判断；
4. 使用批准标签验证交付物来源、敏感扫描和SHA256。

每个 Skill 必须使用标准初始化工具创建，包含有效的 `SKILL.md` 和 `agents/openai.yaml`，通过 Skill 结构校验；所带脚本必须实际运行测试。涉及复杂判断的 Skill 应使用不包含预期答案的真实任务样例做独立前向验证。

## 8. 完成定义

- 八个 Skill 均有清晰且不重叠的触发描述；
- 演示恢复与第三阶段开发使用不同工作树和数据目录；
- 稳定发布只能来源于验收通过的提交和不可移动标签；
- 客户信息未知时能继续产品基线开发，同时准确输出未知项；
- 所有写操作符合权限等级，生产变更不自动执行；
- Skill 故障不会影响正式系统在线运行；
- Skill、脚本和参考资料随仓库版本化，可与对应项目标签一起恢复。

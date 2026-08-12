# 产品V2.0平台逻辑数据模型基线

> 版本：1.0  
> 冻结日期：2026-08-12  
> 适用任务：P320—P343  
> 物理实现：由Flyway迁移定义；本文不绑定客户数据库品牌

## 1. 冻结原则

1. Java平台控制面是平台管理数据、身份权限、审批发布、会话入口和运行主记录的唯一写入所有者；Python执行面写七层执行事实，禁止无审计双写。
2. 平台库只存系统管理元数据、配置快照和运行证据，不存客户贷款、客户、交易等业务事实。
3. 主键、稳定业务编码、关系、状态、检索维度和敏感级别必须列化；JSON只用于发布快照、不可预知扩展和脱敏后的输入输出证据。
4. 发布资源不可物理级联删除；审计、审批动作和运行事实只追加或按保留策略归档。
5. 金额使用定点数；时间统一UTC且保留毫秒；编码发布后不可修改；所有外键和常用状态/时间游标建立索引。
6. 数据库品牌、统一认证协议、KMS、Redis、队列、对象存储、分区语法、HA和保留期最终值属于适配决策，不改变本逻辑模型。

## 2. 领域、实体与数据所有权

| 领域 | 聚合根及主要实体 | 唯一性/关键关系 | 写入所有者 |
|---|---|---|---|
| 身份组织 | `iam_org`、`iam_user`、`iam_identity_provider`、`iam_external_identity`、外部组 | `org.code`；`(provider,external_subject)`；机构树；用户归属机构 | Java IAM |
| 权限范围 | `iam_role`、`iam_permission`、用户角色、角色权限、机构/指标/表/字段范围、用户覆盖 | 角色/权限编码；关联表复合键；DENY优先 | Java IAM |
| 数据资产 | `meta_data_source`、`meta_data_table`、`meta_data_field`、`meta_metric`、`meta_dimension`及映射 | `(source,schema,table)`；`(table,field)`；指标/维度编码 | Java Asset |
| 模型秘密 | `ai_secret`、`ai_model_config`、能力、限额、`ai_runtime_profile`、诊断、轮换日志 | 秘密指纹；模型/Profile编码；Profile关联一个模型和一个数据源 | Java Provider |
| 流程场景 | 意图、参数、层配置、SQL模板、场景、角色/参数/资产/SQL关联、用例、轮次、快捷问题 | 规则/模板/场景编码；`(case,turn_no)`；`(scenario,sql_sequence)` | Java Flow |
| 安全合规 | 分级、白名单、脱敏、限流、拦截话术、SQL策略、表/字段访问 | 规则编码；资源与角色复合键 | Java Security |
| 运维展示 | 系统参数、UI/交互、任务、告警、通知、回答模板、可视化 | 参数/模板/任务/告警编码 | Java Ops |
| 配置生命周期 | `cfg_release`、`cfg_release_item`、`cfg_current_release` | `release_no`；每环境唯一当前发布；快照SHA256 | Java Config |
| 审批审计 | 流程定义/步骤、审批实例/候选人/动作、操作审计 | 流程编码+版本；审批编号；动作只追加；Trace可检索 | Java Audit |
| 会话请求 | `run_session`、`run_request` | Session固定权限与发布快照；父请求同Session；Trace唯一；主体幂等键窗口唯一 | Java Runtime |
| 七层事实 | 层执行、SQL、模型调用、数据源调用、SSE、结果引用 | `(request,sequence/layer/event_id)`；请求外键 | Python产生，Java/异步写入器受控落库 |
| 演示管理 | 场景覆盖、开关、话术 | 开关/话术编码；演示事实在独立库 | Java Demo；POC/PROD强制忽略Fixture |

## 3. 核心关系与不变量

```text
identity provider -> external identity -> user -> org
                                      \-> user role -> role -> permission/data scopes

data source -> table -> field <- metric/dimension mappings
      \-> runtime profile <- model config -> secret reference

release -> release items -> published resources
       \-> current release(environment)
       \-> session(permission snapshot + release snapshot) -> request -> L1..L7 facts
                                                     \-> parent request (same session)

workflow definition(version) -> approval -> candidate/action
actor + trace -> immutable operation audit
```

强制不变量：

- 已启用子资源只能引用已启用父资源；已撤销秘密不能被启用的模型或数据源引用。
- 运行Profile只有在模型、数据源均启用且诊断成功后才能供新Session选择；POC/PRODUCTION禁止Fixture降级。
- 场景、指标映射、SQL模板及资产必须来自同一发布快照；发布只影响新Session。
- 权限裁决顺序固定为：合规强制拒绝 → 用户拒绝 → 角色拒绝 → 用户临时允许 → 角色允许 → 默认拒绝。
- 首轮缺参请求与补全请求通过`parent_request_id`关联，旧请求轨迹不可改写。
- 业务管理员不能更新或删除审计事实；敏感前后值、SQL参数和结果在落库前按等级脱敏。

## 4. 状态机

| 聚合 | 允许状态 | 关键转换约束 |
|---|---|---|
| 通用可发布资源 | DRAFT、ENABLED、DISABLED、DELETED | DELETED为软删除；被引用资源先DISABLED；发布后编码不变 |
| 用户 | ENABLED、FROZEN、DISABLED | FROZEN/DISABLED立即撤销Session并使权限缓存失效 |
| 外部身份 | ACTIVE、DISABLED、UNLINKED | `(provider,subject)`不可重复绑定活动用户 |
| 秘密 | ACTIVE、REVOKED、EXPIRED | REVOKED/EXPIRED禁止新调用；轮换只新增版本和日志 |
| Provider/Profile | DRAFT、ENABLED、DISABLED | ENABLED前必须诊断成功；引用失效时自动不可选 |
| 发布 | DRAFT、REVIEWING、PUBLISHED、ARCHIVED、ROLLED_BACK | PUBLISHED须审批通过、快照哈希有效；每环境仅一个当前指针 |
| 审批 | DRAFT、PENDING、APPROVED、REJECTED、CANCELLED、EXPIRED | 实例固定流程版本；动作记录from/to；终态不可逆改写 |
| 请求 | PENDING、RUNNING、WAITING_INPUT、SHORT_CIRCUITED、BLOCKED、PARTIAL_SUCCESS、SUCCEEDED、FAILED、CANCELLATION_REQUESTED、CANCELLED、TIMED_OUT | 终态不可重新执行；重试生成新请求或命中幂等结果；取消向下游传播 |
| 告警/任务 | PENDING、RUNNING、SUCCEEDED、FAILED、ACKNOWLEDGED、CLOSED | 原始事件只追加；确认与关闭保存操作者和时间 |

状态转换由确定性代码校验，数据库以检查约束、唯一键和乐观锁防止明显非法写入。

## 5. 敏感等级与秘密边界

| 等级 | 示例 | 存储/输出规则 |
|---|---|---|
| PUBLIC | 产品名称、公开场景说明 | 可进入发布包和普通日志 |
| INTERNAL | 资源编码、非敏感配置、执行耗时 | 平台库可存；按权限输出 |
| SENSITIVE | 手机、邮箱、问题文本、SQL参数、业务结果 | 字段级加密/脱敏；日志和导出默认遮蔽；精确检索用HMAC摘要 |
| SECRET | API Key、数据库密码、OIDC客户端秘密 | 仅存秘密引用或应用层密文；主密钥不入库；API永不回显明文 |
| RESTRICTED | 客户业务明细、最高分级字段 | 不作为平台元数据复制；结果短期保存或对象引用；访问必须审批审计 |

平台数据库密码、服务令牌、根加密密钥、KMS凭据、目录绑定密码、永久对象存储签名只能通过部署秘密注入。`.env.example`只允许变量名。

## 6. 保留策略占位

| 数据 | 产品基线默认 | 客户适配项 |
|---|---:|---|
| Session | 90天 | 90–180天或客户制度 |
| 请求、层、SQL、模型/数据源调用 | 180天 | 3–6个月在线，历史归档周期 |
| SSE事件 | 7天 | 7–30天，至少覆盖续传窗口 |
| 结果快照/引用 | 7天 | 按等级7–90天；大结果用对象存储 |
| 登录事件、操作审计、审批动作 | 365天占位 | 合规制度、WORM期限和法务冻结 |
| 任务/告警 | 90天 | 运维制度 |

删除由受审计的归档/清理任务执行；审计和审批动作不得由普通业务API清除。客户保留期未确定时使用产品基线测试值，不宣称满足客户合规要求。

## 7. 客户可变项登记

| 决策项 | 产品基线 | 适配时必须提供的证据 |
|---|---|---|
| 平台数据库 | PostgreSQL兼容逻辑模型；本地H2验证 | 品牌/版本、方言、驱动、HA、备份恢复、账号授权 |
| 统一认证 | 测试身份Provider + OIDC/SAML/LDAP适配接口 | 协议、Issuer/元数据、主体/机构/组映射、退出与撤销 |
| 秘密管理 | 环境注入+秘密引用接口 | KMS/Vault产品、轮换、权限、审计和恢复 |
| Redis/队列/对象存储 | 接口和内存/单机测试实现 | 产品版本、拓扑、TLS、容量、持久化、故障切换 |
| 数据源 | ClickHouse/MySQL只读适配器 | 版本、网络、TLS、只读账号、白名单、超时和取消能力 |
| 保留/分级/审批 | 本文占位和可配置模板 | 客户制度、数据责任人、审批人、归档和销毁证明 |
| 容量与SLA | 入口短突发200 QPS；执行30–50；SSE 1000 | 实际用户、峰值、数据量、模型/数据源限额和压测报告 |

上述信息缺失不阻塞M2—M7产品基线，但对应M8/M9保持`BLOCKED`，不得用H2、Fixture或模拟Provider证据替代客户生产证据。

## 8. 物理实现验收映射

- P321：Flyway版本、账号边界、空库升级、前滚恢复和方言隔离。
- P322：优先落地发布、秘密引用、审计、IAM、资产、场景、SQL模板和请求主表，并验证唯一键/外键/索引。
- P323：官方JSON、运行默认值、前端种子和旧管理资源幂等导入并按数量、编码、关系和SHA256对账。
- M3/M4：管理API只写规范化表，旧JSON降为只读灾备种子。
- M6/M7：运行明细异步化、归档、备份恢复、容量和安全门禁。

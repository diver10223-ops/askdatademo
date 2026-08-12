# AskData产品V2.0可观测与告警基线

> 适用范围：产品V2.0基线；客户监控平台、通知渠道、SLA和阈值在M8适配。

## 1. Trace关联

- HTTP入口接受合法的`X-Trace-Id`，仅允许1—128位字母、数字、点、下划线、冒号和连字符；非法值替换为UUID，防止日志注入。
- `run_request.trace_id`是问数请求的唯一Trace。层执行、SQL执行、模型/数据源Provider执行、事件和结果通过`request_id`关联，不在每张表重复复制高基数字段。
- 配置发布、回滚及管理操作使用`audit_operation_log.trace_id`，审计载荷经过字段级掩码并进入完整性哈希链。
- 告警使用独立的`alert-<UUID>` Trace，只包含规则、指标、阈值、观测值和样本数。

## 2. 指标出口

Prometheus出口为`/actuator/prometheus`，管理摘要为`/api/v2/admin/observability/summary`。主要产品指标：

| 指标 | 标签 | 含义 |
|---|---|---|
| `askdata.execution.active` | 无 | 已准入且未完成的执行数 |
| `askdata.execution.queue.depth` | 无 | 当前准入等待数 |
| `askdata.execution.requests` | `status`固定枚举 | 各状态请求总数 |
| `askdata.provider.executions/failures` | `kind=MODEL/DATA_SOURCE` | Provider执行和失败数 |
| `askdata.sql.executions/failures` | 无 | SQL执行和失败数 |
| `askdata.config.published` | 无 | 已发布配置版本数 |
| `askdata.alerts.delivery_failed` | 无 | 告警发送失败数 |

禁止把用户ID、Request ID、Trace ID、问题、SQL、表字段、Provider名称/地址、错误消息、结果或秘密引用作为指标标签。

## 3. 告警规则与渠道

Flyway V15提供队列积压、执行失败率、Provider失败率、SQL失败率和配置发布失败五类规则。规则包含最小样本、比较符、阈值、严重级别、冷却时间和适配器代码；事件及发送状态持久化到`ops_alert_event`，同规则在冷却期内去重。

产品默认使用`ASKDATA_ALERT_ADAPTER=logging`，只记录安全的运维数值。客户短信、邮件、Webhook或监控平台不得写入核心服务逻辑，应实现`AlertAdapter`并通过配置选用；未配置或发送失败会落为`DELIVERY_FAILED`，不会影响在线问数。

## 4. 数据保护

- 管理摘要和告警接口只输出聚合数值及低敏运维元数据。
- 通用异常日志只记录异常类型和Trace，不打印可能包含SQL、URL、驱动值或凭据的异常消息和堆栈。
- 控制台日志是单行结构化JSON；业务问题、执行结果和未掩码SQL不进入日志。
- Actuator及管理接口的网络暴露、认证和授权属于部署安全边界；产品交付时必须置于管理网络或受认证网关之后。

## 5. 客户条件项

M8需要确认监控系统、采集协议、告警渠道、代理超时、保留期、值班升级路径和SLA，再调整阈值与适配器。当前阈值仅为产品测试基线，不代表客户生产承诺。

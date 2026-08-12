# 产品 V2.0 基线测试策略

## 1. 唯一入口

产品基线的完整测试入口是：

```bash
bash scripts/v2-test-gate.sh
```

入口要求 Python 3.12、Java 21、Node.js 22，并使用独立临时数据目录。脚本会重新执行自身并清除客户数据库、迁移账号、Provider 凭据、执行服务地址和服务令牌等环境变量，因此不需要、也不会使用客户凭据。

## 2. 测试分层

| 层级 | 自动化证据 | 主要范围 |
|---|---|---|
| Python 单元与集成 | `pytest backend/tests` | 七层执行、管理接口、SQLite 双库、Provider 边界、AST SQL 安全、取消与异常 |
| Java 单元与数据库集成 | Maven 全量测试 | Flyway 迁移、平台事实源、身份权限、审批发布、队列、SSE、审计、告警和恢复 |
| 契约 | `check-contract-compatibility.py` | 冻结的 Java/Python OpenAPI 路径、字段和枚举不被删除或收窄 |
| 跨服务 E2E | `v2-p313-smoke.sh` | Java 控制面连通 Python 执行面并完成真实 L1—L7、SQL 与结果快照 |
| 一期/二期回归 | 两个 matrix 脚本 | 三角色、八场景、33 个必需轮次及场景 7 两轮补参 |
| 用户端与离线包 | typecheck、build、offline build、外链扫描 | 前端类型、生产构建、单文件离线演示无外部运行时依赖 |
| 性能冒烟 | `v2-performance-smoke.py` | 12 次串行 DEMO 七层执行，默认 p95 不超过 3 秒且总时长不超过 30 秒 |
| 恢复回归 | `v2-disaster-recovery-drill.sh` | 数据库、配置、秘密引用、发布 JAR、Manifest 和摘要的一致恢复 |

性能冒烟只用于发现灾难性退化，不代表产品容量结论。200 QPS、30/50 执行并发、1300 SSE、30 分钟峰值和 8 小时长稳由 P372 单独验证。

## 3. 判定规则

- 任一层失败即门禁失败，不允许跳过后声明 P370 通过。
- 真实客户模型、数据库、认证、KMS、网络和告警渠道不属于 P370 通过证据，继续保留到 M8。
- 测试不得写入仓库默认运行数据；每次运行使用新的临时目录。
- 门禁输出以 `V2_TEST_GATE_PASS all customer_credentials=absent` 作为完整成功标志。
- 发布候选必须从干净提交重新执行本门禁，P374 再固化日志、提交 SHA 和构建物摘要。

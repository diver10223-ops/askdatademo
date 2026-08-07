# 第二期开发任务与验收边界

## 隔离原则

第二期只能通过显式 `PHASE2_DEMO` 或 `PHASE2_POC` Session 启用。默认 Session 始终是 `PHASE1_DEMO`，继续使用 Mock Model、SQLite 和 Fixture；Offline Adapter、单文件构建和 Official Demo Baseline v1 不加载任何真实 Provider 或凭据。

## 任务

1. P201：冻结 Phase 2 Profile、Session 模式、诊断及审计契约。
2. P202：使用服务端主密钥加密 Provider 凭据，API、日志、导出和前端列表均不得回显。
3. P203：实现 OpenAI-compatible Model Provider，仅用于 L2 和 L7，具备超时、重试、并发限制和健康检查。
4. P204：实现 ClickHouse HTTP 与 MySQL Provider，具备健康检查、只读执行、超时和协作式取消接口。
5. P205：实现基础 SQL 安全：单语句、SELECT/CTE、DDL/DML 禁止、表白名单、行数限制和执行超时。
6. P206：实现 DNS/TCP/TLS/鉴权/最小查询诊断，失败结果脱敏并持久化。
7. P207：Phase 2 Demo 允许有审计的 Fixture 降级；Phase 2 POC 主查询失败必须失败，后续归因查询失败返回 `PARTIAL_SUCCESS`。
8. P208：后台可加密保存、启用、列出和诊断 Profile；新 Session 可显式选择二期模式与已启用 Profile。
9. P209：执行协议级 Provider 测试与 3 角色 × 8 场景 × 33 必要轮次完整矩阵。
10. P210：完整运行一期就绪检查，证明默认 POC 与 Offline Demo 无回归。

## 外部环境验收

仓库内自动验收使用本地协议级服务验证真实 HTTP 请求、鉴权头、结构化模型响应、ClickHouse 参数和结果解析。连接客户真实模型、ClickHouse 或 MySQL 时，管理员需提供网络可达地址、账号和凭据；这些环境值不写入仓库。真实环境验收执行相同 Profile 诊断及矩阵，不允许用 Fixture 掩盖 `PHASE2_POC` 失败。

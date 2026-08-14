# AskData产品V2.0部署模板

本目录是环境中立模板，不是可直接用于客户生产的配置。客户数据库、统一认证、KMS/Vault、模型与数据源、域名/TLS、网关、监控、HA及灾备必须在M8确认并复验。

## 启动顺序

1. 使用独立迁移账号执行Flyway迁移，并核对目标库、备份点和迁移清单；
2. 从秘密管理系统注入应用账号密码、迁移账号密码、至少32随机字节的内部服务令牌和独立的平台API令牌；
3. 使用同一个`ASKDATA_INTERNAL_SERVICE_TOKEN`启动Python执行面和Java控制面；
4. 先检查Python`/internal/v1/health`（必须带内部令牌），再检查Java`/api/v2/health`和Actuator健康端点；
5. 部署静态前端，并由受控网关路由用户入口；内部`/internal/v1/**`不得暴露到公网；
6. 完成黄金问题、权限拒绝、取消、SSE重连、审计、告警和备份恢复验证后才切流。

本地产品基线可使用H2验证机制，但H2不属于客户生产数据库结论。数据库角色模板位于`deploy/database/postgresql/create-roles.sql.example`，迁移与恢复步骤分别见产品数据库迁移和恢复手册。

## 安全约束

- `application.env.example`中的`REQUIRED_*`只是占位符；发布包扫描会拒绝真实凭据；
- Java和Python均不再提供默认内部服务令牌，漏配时不能建立内部调用；
- 除平台/Actuator健康检查外，V2 API和Prometheus默认要求平台Bearer令牌；客户身份协议接入后再由M8适配器替换；
- 迁移账号、应用账号和业务查询只读账号必须分离；
- 管理和Actuator端点应位于管理网络，并由客户认证与网关策略保护；
- Offline Demo及V1.x POC继续使用冻结基线，不依赖本部署。

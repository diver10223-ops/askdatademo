# 第二期验收报告

## 范围

第二期提供 OpenAI-compatible、ClickHouse 和 MySQL Provider、加密凭据、诊断、弹性策略、基础 SQL 安全、明确失败策略和后台 Profile 管理。默认模式保持一期，Offline 仍完全离线。

## 自动验收证据

- Provider 协议测试：模型 `/models`、`/chat/completions` 和 ClickHouse HTTP 查询真实发起并解析。
- SQL 安全测试：拒绝 DDL/DML、多语句和非白名单表，自动增加行数限制。
- 凭据测试：缺少主密钥时拒绝保存；密文、列表和审计不出现明文凭据。
- Profile/Session 测试：默认 Session 为一期；二期 Session 必须绑定已启用 Profile。
- 完整矩阵：三角色、八场景、33 个必要轮次使用 Phase 2 Provider Registry 执行。
- 回归：`scripts/demo-readiness-check.sh` 必须整体通过，证明一期 Mock POC 和 Offline 单文件未受影响。

客户真实环境的 DNS、TCP、TLS、鉴权、Schema 和数据结果依赖客户提供可达端点与凭据；仓库不保存这些值。未提供外部环境时，不能把协议级验收描述为客户生产连接成功。

## 2026-08-06 执行结果

- `backend/tests/test_phase2.py`：6 项通过，覆盖加密、SQL 安全、OpenAI-compatible、ClickHouse、Profile API、真实 HTTP Query/SSE 和失败策略。
- `scripts/phase2-matrix.py`：3 角色 × 8 场景 × 33 必要轮次通过，使用 Phase 2 Provider Registry 与协议级 HTTP 服务。
- Vue 类型检查、POC 构建和 Offline 单文件构建通过。
- 一期完整回归：33 必要轮次、Offline 构建及后端 11 项测试通过。
- 最终命令输出：`READY: Phase 2 checks passed; Phase 1 regression passed`。

因此仓库内可实现、可自动验证的第二期工作已完成。客户真实端点联通属于部署环境验收；当前没有提供端点或凭据，报告没有将其虚构为成功。

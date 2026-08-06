# 一期精确检查命令

```bash
bash scripts/init-db.sh
PYTHONPATH=backend pytest -q backend/tests
python -m json.tool schemas/phase1-contract.schema.json >/dev/null
python -m json.tool schemas/baseline.schema.json >/dev/null
python -m json.tool fixtures/official_baseline_v1.json >/dev/null
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run build:offline
bash scripts/demo-readiness-check.sh
git diff --check
git status --short
```

自动化矩阵检查 Baseline 角色/场景引用、双库隔离、重复迁移、L1—L7 正常链路和 L2 短路不产生后续层。就绪脚本再检查构建、离线资源扫描和官方快照。API 的 SSE 支持事件先入库、请求内递增 ID、`Last-Event-ID` 补发、完成回放与不重复执行；取消接口对终态请求幂等。

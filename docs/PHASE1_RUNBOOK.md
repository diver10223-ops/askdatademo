# 一期演示运行手册

状态：可执行草案（2026-08-07）

1. 在仓库根目录执行 `scripts/start-poc.sh` 启动服务。
2. 用户端访问 `/`，管理端访问 `/admin`。
3. 选择一期演示模式，按八个场景逐项验证问题、七层轨迹、SQL、结果、推荐与中断输出。
4. 执行 `cd backend && ../.venv/bin/python -m pytest -q` 和 `cd frontend && npm run build`。
5. 业务口径确认记录填写到 `PHASE1_BUSINESS_CONTENT_SIGNOFF.md`。

异常处理：端口占用时先确认现有进程和健康状态；不得直接删除数据目录。日志入口位于查询日志、模型调用日志和数据源运维监控。

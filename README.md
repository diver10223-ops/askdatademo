# 智能银行问数平台 · Phase 1

一期同时提供 Vue 3 + FastAPI Mock POC 和单文件 Offline Demo。模型、外部数仓与登录均不在一期范围。

## Codespaces / 本地 POC

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend ci
bash scripts/init-db.sh
npm --prefix frontend run build
bash scripts/start-poc.sh
```

只访问 `http://localhost:8000`。健康检查为 `/api/v1/health`；诊断运行 `bash scripts/diagnose.sh`。所有前端 API 均为同源相对路径。

## Offline Demo

```bash
npm --prefix frontend run build:offline
```

双击 `frontend/offline-dist/askdata-offline.html`。文件不需要服务、CDN 或网络；会话和配置通过 IndexedDB 留在当前浏览器。界面会明确标识 Offline 模拟执行。

## 推荐演示顺序

依次点击场景 1—5 展示查数、驾驶舱、推荐、同比归因和拦截；场景 6 追问“去年同期呢”；场景 7 补齐机构/时间；场景 8 在首轮后追问“为什么下降”。切换三个角色观察机构与指标权限差异。后台入口位于顶部导航。

## 恢复与验收

后台 API 提供恢复官方配置、仅重置 Mock 数据和二次确认的完全重置。命令行恢复数据可运行 `bash scripts/init-db.sh`。完整一期检查：

```bash
bash scripts/demo-readiness-check.sh
```

若启动失败，先运行诊断脚本；数据库异常可恢复官方数据；端口占用可通过 `ASKDATA_PORT=8001` 改端口。验收详情见 `docs/PHASE1_ACCEPTANCE_REPORT.md`。

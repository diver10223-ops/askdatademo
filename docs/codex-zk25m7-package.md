# codex-zk25m7 修改文件下载包

## 包含文件（共 10 个）

| 文件路径 | 说明 |
|---|---|
| `backend/app/layers/l2_understanding.py` | 语义理解层 |
| `backend/app/layers/l3_semantic.py` | 语义映射层 |
| `backend/app/layers/l5_query.py` | 查询生成层 |
| `backend/app/layers/l7_interpretation.py` | 结果解读层 |
| `backend/app/runtime/publisher.py` | 运行时发布器 |
| `backend/tests/test_phase1.py` | 阶段一测试 |
| `backend/tests/test_phase2.py` | 阶段二测试 |
| `fixtures/demo_runtime_defaults.json` | 演示运行时默认配置 |
| `frontend/src/App.vue` | 前端主应用组件 |
| `frontend/src/App.vue.js` | 前端主应用逻辑 |

## 下载方式

### 方式 1：直接从 GitHub 下载 ZIP

合并 PR 后，在仓库根目录可以直接下载文件：

```
https://github.com/diver10223-ops/askdatademo/raw/main/codex-zk25m7-modified-files.zip
```

### 方式 2：本地重新打包

克隆仓库后运行：

```bash
bash scripts/create_zip.sh
```

即可在根目录生成 `codex-zk25m7-modified-files.zip`。

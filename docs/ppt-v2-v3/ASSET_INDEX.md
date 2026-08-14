# PPT视觉资产索引

## 使用规则

- `*-prototype.png`：当前产品原型的真实截图，PPT中应标注“演示环境/演示数据”。不得用它证明客户生产环境已经联调。
- `.svg`：为本次PPT制作的可编辑矢量图，画布均为1600×900，白底宋体，可直接插入PowerPoint。
- 架构图优先使用SVG；产品功能页优先使用真实PNG截图。截图在PPT中按比例裁切，不拉伸。
- 截图建议加1pt浅灰描边和轻阴影；不得叠加会遮挡产品关键字段的装饰图形。

## 架构与方案图

| 文件 | 类型 | 主要用途 | 标准版页码 | 领导版页码 | 客户版页码 |
|---|---|---|---:|---:|---:|
| `01-business-architecture.svg` | 可编辑方案图 | 业务架构 | 8 | 4 | 5 |
| `02-technical-architecture.svg` | 可编辑方案图 | Java/Python技术协作及V2.0边界 | 9、27 | 11 | 14、19 |
| `03-network-deployment.svg` | 可编辑方案图 | 网络部署参考 | 10 | — | 15 |
| `04-query-sequence.svg` | 可编辑时序图 | 问数执行流程 | 13 | — | 7 |
| `13-product-evolution.svg` | 可编辑路线图 | V1.x—V3.0演进 | 6、32 | 16 | — |
| `14-solution-overview.svg` | 可编辑方案图 | 端到端流程与五中心 | 7 | — | 4 |
| `15-seven-layer-overview.svg` | 可编辑分层图 | 七层机制总览 | 11 | 5 | 6 |
| `16-scenario-matrix.svg` | 可编辑场景图 | 八类业务场景 | 16 | — | 9 |
| `17-admin-capability-map.svg` | 可编辑能力图 | 管理端六域能力 | 19 | 7 | 11 |
| `18-security-gates.svg` | 可编辑门禁图 | 安全可信机制 | 14 | — | 13 |
| `19-implementation-roadmap.svg` | 可编辑路线图 | 客户实施验收 | 26 | — | 18 |
| `20-v3-capability-map.svg` | 可编辑能力图 | V3.0演进 | 31 | 15 | 23 |
| `21-v3-seven-layer-architecture.svg` | 可编辑分层图 | V3.0七层规划架构与治理边界 | 30 | 14 | 22 |

## 产品原型截图

| 文件 | 截图内容 | 建议展示方式 | 标准版页码 | 领导版页码 | 客户版页码 |
|---|---|---|---:|---:|---:|
| `05-user-home-prototype.png` | 用户端首页与八大场景入口 | 裁切顶部导航、欢迎区和场景按钮 | 15 | — | 8 |
| `06-user-query-result-prototype.png` | 七层轨迹、回答、图表、表格和追问 | 保留结果卡，必要时裁去重复导航 | 15、17 | 6 | 8、10 |
| `07-admin-home-prototype.png` | 管理首页、指标卡、趋势和通知 | 全屏展示或裁切主内容区 | 19、23 | — | 11、16 |
| `08-admin-users-prototype.png` | 用户、角色和机构关系 | 裁切侧栏与用户表格 | 20 | — | 13 |
| `09-admin-metrics-prototype.png` | 指标字典和数据资产关系 | 重点保留指标、口径、数据源、表 | 21 | — | 12 |
| `10-admin-models-prototype.png` | 模型Provider与参数 | 与数据源截图并排使用 | 22 | — | 可选 |
| `11-admin-datasources-prototype.png` | 数据源、环境与关联数据表 | 与模型截图并排使用 | 22 | — | 可选 |
| `12-admin-query-logs-prototype.png` | 执行轨迹、状态和终止层 | 重点保留筛选区与状态列 | 23 | — | 16 |

## 不需要单独生成图片的页面

以下页面应使用PowerPoint原生文本框、圆角矩形和表格制作，以便现场修改，不建议把整页固化成图片：

- 封面、目录、建设背景、目标用户、产品定位。
- 七层职责表、方案优势、业务价值指标。
- 当前执行结果、产品基线与客户交付边界、待确认事项。
- 决策建议、总结页和所有需要临场修改的数据页。

## 来源说明

- 原型截图源自 `docs/deliverables/assets`，复制到本目录后未修改产品内容。
- 方案图根据 `reference-pic` 的白底、章节编号、圆角卡片、浅色分区和重点橙色样式重新绘制。

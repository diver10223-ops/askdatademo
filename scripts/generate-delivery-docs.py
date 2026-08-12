from pathlib import Path
from datetime import date
import hashlib, html, json, urllib.request
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'deliverables'; ASSETS=OUT/'assets'; OUT.mkdir(parents=True,exist_ok=True)
TODAY=date.today().isoformat()
CSS="""
@page{size:A4;margin:18mm 16mm 18mm 18mm;@top-left{content:"NLQ智能银行问数平台 · 第二阶段交付文档";color:#64748b;font-size:8.5pt}@bottom-center{content:"第 " counter(page) " 页 / 共 " counter(pages) " 页";color:#64748b;font-size:8.5pt}}
@page cover{@top-left{content:none}@bottom-center{content:none}}
*{box-sizing:border-box}body{font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif;color:#1f2937;font-size:10pt;line-height:1.62}
.cover{page:cover;page-break-after:always;min-height:250mm;padding:42mm 16mm 15mm;background:linear-gradient(145deg,#eff6ff,#fff 55%,#e0f2fe);border-top:8mm solid #2563eb}
.cover .kicker{color:#2563eb;letter-spacing:2px;font-weight:700}.cover h1{font-size:29pt;line-height:1.25;color:#0f172a;margin:22mm 0 5mm}.cover h2{font-size:15pt;font-weight:400;color:#475569;border:0}.cover .meta{margin-top:45mm;border-left:4px solid #2563eb;padding-left:8mm}
h1{font-size:22pt;color:#0f172a;page-break-before:always;margin:0 0 8mm}h1:first-of-type{page-break-before:auto}h2{font-size:15pt;color:#1d4ed8;border-bottom:1px solid #bfdbfe;padding-bottom:2mm;margin:8mm 0 3mm}h3{font-size:12pt;color:#0f172a;margin:5mm 0 2mm}
p{margin:1.5mm 0 3mm}ul,ol{margin:2mm 0 4mm 6mm;padding-left:5mm}li{margin:1mm 0}table{border-collapse:collapse;width:100%;margin:3mm 0 6mm;font-size:8.5pt}thead{display:table-header-group}tr{page-break-inside:avoid}th{background:#dbeafe;color:#1e3a8a}th,td{border:.35mm solid #cbd5e1;padding:1.7mm 2mm;vertical-align:top;overflow-wrap:anywhere}
code,pre{font-family:"DejaVu Sans Mono",monospace;background:#f1f5f9}code{padding:.2mm 1mm;color:#9f1239}pre{white-space:pre-wrap;padding:3mm;border-left:1mm solid #3b82f6;font-size:8pt;line-height:1.45}.toc a{color:#1e40af;text-decoration:none}.note,.warn,.ok{padding:3mm 4mm;margin:4mm 0;border-left:1.2mm solid;background:#f8fafc}.note{border-color:#2563eb}.warn{border-color:#f59e0b;background:#fffbeb}.ok{border-color:#10b981;background:#ecfdf5}
.figure{margin:5mm 0 7mm;page-break-inside:avoid;text-align:center}.figure img{width:100%;max-height:165mm;object-fit:contain;border:.35mm solid #cbd5e1}.caption{color:#64748b;font-size:8.5pt;margin-top:1.5mm}.small{font-size:8.5pt;color:#64748b}.approval td{height:13mm}.pass{color:#047857;font-weight:700}.fail{color:#b91c1c;font-weight:700}
"""
def esc(x): return html.escape(str(x),quote=True)
def cover(title,sub): return f"""<section class="cover"><div class="kicker">PHASE 2 · DELIVERY DOCUMENT</div><h1>{title}</h1><h2>{sub}</h2><div class="meta"><p><b>项目：</b>NLQ智能银行问数平台</p><p><b>版本：</b>V1.0</p><p><b>状态：</b>交付草案</p><p><b>发布日期：</b>{TODAY}</p><p><b>文档信息：</b>中性信息模板</p></div></section>"""
def front(toc):
    links=''.join(f'<li><a href="#{a}">{b}</a></li>' for a,b in toc)
    return f"""<h1>文档控制</h1><table><tr><th>版本</th><th>日期</th><th>变更说明</th><th>编制</th></tr><tr><td>V1.0</td><td>{TODAY}</td><td>第二阶段首次成册</td><td>项目交付组</td></tr></table><div class="note"><b>依据：</b>当前源码、配置、实际POC页面及Debian 12隔离安装演练。客户真实模型、数据库和生产服务器须在目标环境复验。</div><h2>目录</h2><ol class="toc">{links}</ol>"""
def approval(): return """<h1 id="approval">审批与验收</h1><table class="approval"><tr><th>环节</th><th>姓名/部门</th><th>意见</th><th>签字</th><th>日期</th></tr><tr><td>编制</td><td></td><td></td><td></td><td></td></tr><tr><td>审核</td><td></td><td></td><td></td><td></td></tr><tr><td>批准</td><td></td><td></td><td></td><td></td></tr><tr><td>交付验收</td><td></td><td></td><td></td><td></td></tr></table>"""
def fig(name,cap): return f'<div class="figure"><img src="{ASSETS/name}"><div class="caption">{cap}</div></div>'
def make(title,sub,toc,body): return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{title}</title><style>{CSS}</style></head><body>{cover(title,sub)}{front(toc)}{body}{approval()}</body></html>'

user_toc=[('scope','1. 手册说明'),('user','2. 第一部分：使用者操作'),('scenes','3. 八大标准场景'),('admin','4. 第二部分：系统管理员操作'),('ops','5. 运维、安全与常见问题'),('approval','6. 审批与验收')]
user=f"""
<h1 id="scope">1. 手册说明</h1><h2>1.1 适用范围</h2><p>本手册面向业务使用者和系统管理员，适用于PHASE1_DEMO、PHASE2_DEMO、PHASE2_POC。用户端为 <code>http://服务器IP:8000/</code>，管理端为 <code>/admin</code>。</p>
<h2>1.2 角色与权限</h2><table><tr><th>角色</th><th>身份</th><th>范围</th><th>限制</th></tr><tr><td>admin</td><td>总行行长</td><td>全机构、全指标</td><td>仍受涉密、SQL安全与限流控制</td></tr><tr><td>beijing</td><td>分行行长</td><td>北京分行授权指标</td><td>不可访问其他分行</td></tr><tr><td>retail</td><td>业务负责人</td><td>零售信贷授权范围</td><td>不可访问对公及未授权明细</td></tr></table>
<div class="warn"><b>边界：</b>当前角色切换属于演示功能，不等同于生产认证。生产前应接入统一身份认证并实施服务端管理员鉴权。</div>
<h1 id="user">2. 第一部分：使用者操作</h1><h2>2.1 进入系统</h2><ol><li>打开用户端地址。</li><li>确认执行模式、二期Provider Profile和当前身份。</li><li>欢迎语出现且输入框可用，表示Session创建成功。</li></ol>{fig('01-user-home.png','图2-1 用户问数首页（实际POC页面）')}
<h2>2.2 执行模式</h2><table><tr><th>模式</th><th>用途</th><th>Provider</th><th>失败策略</th></tr><tr><td>PHASE1_DEMO</td><td>确定性演示</td><td>Mock + SQLite/Fixture</td><td>按一期基线</td></tr><tr><td>PHASE2_DEMO</td><td>二期连接演示</td><td>已启用组合</td><td>允许有审计的Fixture兜底</td></tr><tr><td>PHASE2_POC</td><td>真实POC</td><td>真实模型和数据源</td><td>主查询失败即失败，不静默降级</td></tr></table>
<h2>2.3 发起问数</h2><ol><li>选择角色；切换会新建会话并清空聊天区。</li><li>点击快捷场景，或输入包含指标、机构和时间的问题。</li><li>观察L1—L7轨迹；执行中可停止。</li><li>查看回答、图表、结果表格、SQL日志和后续提问。</li></ol>{fig('02-user-query-result.png','图2-2 基础查数执行结果（实际操作截图）')}
<h2>2.4 多轮与补参</h2><p>追问“去年同期呢”“为什么下降”时通过父请求和Session继承参数。场景7首轮缺少机构、指标或时间时进入WAITING_INPUT并显示权限过滤后的候选项，不执行SQL、不访问数据源；选择或自然语言补齐后创建关联Request并从L1执行至L7。上下文失效时重新输入完整问题。</p>
<h2>2.5 结果状态</h2><table><tr><th>状态</th><th>含义</th><th>动作</th></tr><tr><td>SUCCEEDED</td><td>完整成功</td><td>核对口径和来源</td></tr><tr><td>PARTIAL_SUCCESS</td><td>主结果成功，后续部分失败</td><td>使用主结果并检查日志</td></tr><tr><td>WAITING_INPUT</td><td>缺参数</td><td>选择或补充</td></tr><tr><td>BLOCKED</td><td>权限/合规拦截</td><td>按流程申请，禁止绕过</td></tr><tr><td>SHORT_CIRCUITED</td><td>驾驶舱等提前完成</td><td>使用返回链接</td></tr><tr><td>FAILED/CANCELLED</td><td>失败/取消</td><td>记录请求ID联系管理员</td></tr></table>
<h1 id="scenes">3. 八大标准场景</h1><table><tr><th>场景</th><th>操作</th><th>预期</th></tr><tr><td>1 基础查数</td><td>机构+指标+时间</td><td>表格/图表和SQL轨迹</td></tr><tr><td>2 驾驶舱</td><td>询问经营大盘</td><td>按角色返回链接，不执行SQL</td></tr><tr><td>3 模糊问句</td><td>不完整业务表达</td><td>权限内标准问题推荐</td></tr><tr><td>4 同比归因</td><td>问同比变化/原因</td><td>主查询及受控归因</td></tr><tr><td>5 越权拦截</td><td>问未授权范围</td><td>前置拦截，不访问数据源</td></tr><tr><td>6 上下文追问</td><td>追问去年同期</td><td>继承父请求参数</td></tr><tr><td>7 缺失参数</td><td>省略机构/时间</td><td>补参或按发布规则处理</td></tr><tr><td>8 二次归因</td><td>查数后问原因</td><td>同会话连续执行</td></tr></table>
<h1 id="admin">4. 第二部分：系统管理员操作</h1><h2>4.1 管理首页</h2><p>检查请求量、成功率、平均响应、趋势、审批和通知；异常跳转就绪检查、日志或数据源监控。</p>{fig('03-admin-home.png','图4-1 管理首页')}
<h2>4.2 后台、用户与权限</h2><ol><li>后台权限维护角色、管理员和菜单/操作权限。</li><li>用户权限维护业务角色、用户、机构池、指标池和权益。</li><li>保存资源后发布；发布只影响新Session。</li><li>用三角色验证允许与拒绝路径。</li></ol>{fig('04-admin-users.png','图4-2 用户管理')}
<h2>4.3 数据字典与流程</h2><p>先接入数据源/表，再建立字段映射和指标口径，最后绑定角色。意图规则、SQL模板、会话、参数校验及七层处理器变更后须回归。</p>{fig('05-admin-metrics.png','图4-3 指标字典')}
<h2>4.4 场景管理</h2><p>维护标准场景、参数关联、快捷提问和驾驶舱。触发词、终止层、表、SQL、输出或降级策略变化后，重跑三角色八场景矩阵。</p>
<h2>4.5 模型配置</h2><ol><li>模型配置→模型对接→新增。</li><li>填写提供商、Base URL、模型、API Key、参数、超时、重试和并发。</li><li>保存、启用、诊断；密钥不回显。</li><li>在模型能力管理L2/L7 Prompt。</li></ol>{fig('06-admin-models.png','图4-4 模型配置')}
<h2>4.6 数据源配置</h2><ol><li>数据源配置→数据源对接。</li><li>ClickHouse填HTTP URL；MySQL填主机、端口、库和字符集。</li><li>使用只读账号，设置允许表、最大行数、范围、超时和并发。</li><li>保存、启用、诊断及Schema同步。</li></ol>{fig('07-admin-datasources.png','图4-5 数据源配置')}
<h2>4.7 运行组合</h2><ol><li>模型、数据源分别诊断并启用。</li><li>系统运维→运行组合，选择二者创建组合。</li><li>启用并诊断组合。</li><li>用户端选择二期模式和组合，新建Session验证。</li></ol>
<h2>4.8 日志与监控</h2><p>用户会话、执行轨迹、SQL审计、操作日志、模型日志及数据源监控可按关键词、角色、状态、模式、场景和日期筛选。</p>{fig('08-admin-query-logs.png','图4-6 执行轨迹日志')}
<h2>4.9 发布、备份、恢复与重置</h2><ol><li>发布前备份并记录版本。</li><li>导入JSON先形成草稿，审核后发布。</li><li>回滚选择归档/禁用版本。</li><li>恢复官方配置、重置Mock、完全重置在维护窗口执行；完全重置二次确认。</li></ol>{fig('09-admin-recovery.png','图4-7 备份与重置')}
<h1 id="ops">5. 运维、安全与常见问题</h1><table><tr><th>问题</th><th>检查</th><th>处理</th></tr><tr><td>页面打不开</td><td>服务、端口、防火墙、health</td><td>启动或调整网络</td></tr><tr><td>二期无组合</td><td>启用/诊断状态</td><td>完成配置和组合诊断</td></tr><tr><td>查询失败</td><td>轨迹、模型、SQL、数据源日志</td><td>按错误层定位</td></tr><tr><td>权限不符</td><td>角色、发布版本、Session时间</td><td>发布并新建Session</td></tr><tr><td>密钥不可用</td><td>凭证加密密钥是否匹配</td><td>安全恢复或重录凭据</td></tr></table><div class="warn">删除、完全重置、恢复和密钥轮换均为高风险操作。先备份数据库及密钥，确认目标与维护窗口，保留审计。</div>
"""

install_toc=[('overview','1. 范围与架构'),('prereq','2. 环境准备'),('single','3. 单机部署'),('multi','4. 多服务器部署'),('providers','5. Provider配置'),('service','6. 服务托管'),('verify','7. 实际验证'),('maintain','8. 运维升级回滚'),('approval','9. 审批与验收')]
install=f"""
<h1 id="overview">1. 范围与架构</h1><p>无Docker、无反向代理、无域名、无HTTPS。FastAPI同源提供Vue静态文件与API；平台和演示数据默认SQLite，二期连接ClickHouse或MySQL。</p><table><tr><th>方案</th><th>节点</th><th>适用</th></tr><tr><td>单机</td><td>应用、静态文件、SQLite同机</td><td>POC/演示</td></tr><tr><td>多服务器</td><td>应用 + 独立数据库 + 外部模型</td><td>网络/资源隔离</td></tr></table><div class="warn">无HTTPS时流量明文，仅限受控内网并限制来源，禁止直接暴露互联网。</div>
<h1 id="prereq">2. 环境准备</h1><table><tr><th>项目</th><th>建议</th><th>实测</th></tr><tr><td>Linux</td><td>Debian/Ubuntu或RHEL系列64位</td><td>Debian 12</td></tr><tr><td>资源</td><td>4核/8GB/20GB可用</td><td>目标环境复核</td></tr><tr><td>Python</td><td>3.11+</td><td>3.12.11</td></tr><tr><td>Node/npm</td><td>20+/10+</td><td>22.23.2/10.9.8</td></tr><tr><td>端口</td><td>8000及Provider端口</td><td>演练18080</td></tr></table>
<h2>2.1 Ubuntu/Debian</h2><pre>sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm curl git</pre><h2>2.2 RHEL/CentOS/Rocky/Alma</h2><pre>sudo dnf install -y python3 python3-pip nodejs npm curl git
# Node过低时使用组织批准的软件源安装Node 20+</pre>
<h2>2.3 网络</h2><pre>ss -lntp | grep ':8000' || true
curl -I --max-time 5 MODEL_BASE_URL
curl -I --max-time 5 CLICKHOUSE_HTTP_URL
nc -vz MYSQL_HOST 3306</pre><p>应用需访问模型、ClickHouse HTTP（常见8123/8443）或MySQL 3306；数据库仅向应用IP开放。</p>
<h1 id="single">3. 单机部署（实际顺序）</h1><ol><li>创建低权限用户和目录。</li><li>上传并核对摘要。</li><li>创建venv、安装后端依赖。</li><li>安装前端依赖并构建。</li><li>生成并保管凭证加密密钥。</li><li>初始化SQLite。</li><li>前台启动并健康检查。</li><li>配置systemd。</li><li>后台配置模型、数据源、组合。</li><li>诊断、冒烟、自动测试和矩阵。</li></ol><pre>sudo useradd --system --create-home --shell /usr/sbin/nologin askdata
sudo mkdir -p /opt/askdata /var/lib/askdata /var/log/askdata /etc/askdata
sudo chown -R askdata:askdata /opt/askdata /var/lib/askdata /var/log/askdata
cd /opt/askdata
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend ci
bash scripts/init-db.sh
npm --prefix frontend run build
umask 077
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" | sudo tee /etc/askdata/credential-key >/dev/null
sudo chmod 600 /etc/askdata/credential-key</pre><div class="note">不得在历史、截图、工单或PDF记录真实API Key、密码或ASKDATA_CREDENTIAL_KEY。密钥丢失会使已加密Provider凭据不可用。</div>
<h1 id="multi">4. 多服务器部署</h1><table><tr><th>节点</th><th>内容</th><th>入站</th><th>出站</th></tr><tr><td>应用</td><td>Python、Vue、平台SQLite</td><td>客户端→8000</td><td>模型/数据库</td></tr><tr><td>ClickHouse</td><td>宽表/明细、只读账号</td><td>应用IP→HTTP</td><td>按策略</td></tr><tr><td>MySQL</td><td>业务库、只读账号</td><td>应用IP→3306</td><td>按策略</td></tr><tr><td>模型</td><td>OpenAI-compatible</td><td>应用IP→服务端口</td><td>按供应商</td></tr></table><p>当前不建议多应用实例共享本地SQLite。高可用须先完成平台库外置、共享Session/事件、负载均衡和一致性改造。</p>
<h1 id="providers">5. Provider配置</h1><h2>5.1 ClickHouse</h2><p>使用HTTP地址、库、账号密码；只授予允许表SELECT。配置allowed_tables、最大行数、时间范围、超时、重试和并发，执行DNS/TCP/TLS/鉴权/最小查询诊断。</p><pre>CREATE USER askdata_ro IDENTIFIED WITH sha256_password BY '由密码库生成';
GRANT SELECT ON askdata_poc.dws_loan_aggr_wide TO askdata_ro;</pre><h2>5.2 MySQL</h2><pre>CREATE USER 'askdata_ro'@'APP_SERVER_IP' IDENTIFIED BY '由密码库生成';
GRANT SELECT ON business_db.allowed_table TO 'askdata_ro'@'APP_SERVER_IP';
FLUSH PRIVILEGES;</pre><p>字符集utf8mb4；禁止FILE、SUPER、CREATE、ALTER、DROP、INSERT、UPDATE、DELETE。</p><h2>5.3 模型</h2><p>配置OpenAI-compatible Base URL、模型、API Key、结构化输出、温度、Top P、Token、上下文、超时、重试和并发。诊断成功不替代完整场景验收。</p>
<h1 id="service">6. systemd服务托管</h1><pre>[Unit]
Description=NLQ AskData Service
After=network-online.target
[Service]
Type=simple
User=askdata
Group=askdata
WorkingDirectory=/opt/askdata
EnvironmentFile=/etc/askdata/askdata.env
ExecStart=/opt/askdata/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target</pre><p>环境文件写入ASKDATA_CREDENTIAL_KEY并设600权限。</p><pre>sudo systemctl daemon-reload
sudo systemctl enable --now askdata
sudo systemctl status askdata
journalctl -u askdata -n 200 --no-pager
curl -fsS http://127.0.0.1:8000/api/v1/health</pre>
<h1 id="verify">7. 实际安装演练</h1><p>日期：{TODAY}；隔离副本；Debian 12；端口18080；未使用客户真实凭据。</p><table><tr><th>步骤</th><th>结果</th><th>证据</th></tr><tr><td>venv/后端依赖</td><td class="pass">通过</td><td>requirements完成</td></tr><tr><td>npm ci/Vue build</td><td class="pass">通过</td><td>31 modules，dist生成</td></tr><tr><td>数据库初始化</td><td class="pass">通过</td><td>platform.db、mock_warehouse.db</td></tr><tr><td>健康/诊断</td><td class="pass">通过</td><td>status=ok；Schema/Fixture/双库OK</td></tr><tr><td>后端测试</td><td class="pass">通过</td><td>29 passed；2个on_event弃用警告</td></tr><tr><td>一期readiness</td><td class="pass">通过</td><td>3角色×8场景×33轮；场景7首轮WAITING_INPUT/L2、补全轮SUCCEEDED/L7</td></tr><tr><td>二期仓库内检查</td><td class="pass">通过</td><td>7项协议/安全测试及Provider仿真33轮；一期回归通过</td></tr><tr><td>真实Provider</td><td>待目标环境</td><td>不伪造</td></tr></table><div class="warn">仓库内自动检查及协议仿真已通过；客户真实模型、ClickHouse/MySQL仍须在目标环境执行真连、真实33轮、对账、安全和恢复。</div>
<h1 id="maintain">8. 运维、升级与回滚</h1><h2>8.1 日常</h2><pre>sudo systemctl restart askdata
sudo systemctl stop askdata
curl -fsS http://127.0.0.1:8000/api/v1/health
bash scripts/diagnose.sh</pre><h2>8.2 备份</h2><p>备份发布版本、data、后台导出、credential-key和环境文件；密钥与数据库分权、加密并测试恢复。</p><h2>8.3 升级</h2><ol><li>冻结并备份。</li><li>新目录解压、核对SHA256。</li><li>装依赖、构建和测试。</li><li>停止旧服务，迁移经批准的数据和密钥。</li><li>切换目录、启动和验证。</li></ol><h2>8.4 回滚</h2><p>停止新版本，恢复旧目录、数据库和匹配的加密密钥；检查健康、配置版本和黄金问题。禁止只回滚数据库不匹配密钥。</p>
"""

with urllib.request.urlopen('http://127.0.0.1:18081/openapi.json',timeout=10) as response:
    schema=json.load(response)
(OUT/'openapi.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
methods=('get','post','put','patch','delete'); rows=[]
for path,spec in schema['paths'].items():
    for method in methods:
        if method not in spec: continue
        op=spec[method]; params=[]
        for p in op.get('parameters',[]): params.append(f"{p['name']}({p.get('in')},{'必填' if p.get('required') else '可选'})")
        ref=op.get('requestBody',{}).get('content',{}).get('application/json',{}).get('schema',{}).get('$ref','').split('/')[-1]
        if ref: params.append('JSON:'+ref)
        rows.append(f"<tr><td>{method.upper()}</td><td><code>{esc(path)}</code></td><td>{esc(op.get('summary',''))}</td><td>{esc('；'.join(params) or '-')}</td><td>{esc('、'.join(op.get('responses',{}).keys()))}</td></tr>")
endpoint_table='<table><thead><tr><th>方法</th><th>路径</th><th>用途</th><th>参数/请求体</th><th>响应码</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
mrows=[]
for name,model in sorted(schema.get('components',{}).get('schemas',{}).items()):
    if name in ('HTTPValidationError','ValidationError'): continue
    req=set(model.get('required',[])); fields=[]
    for key,val in model.get('properties',{}).items():
        typ=val.get('type') or val.get('$ref','').split('/')[-1] or ('array' if 'items' in val else 'object')
        fields.append(f"{key}:{typ}{'*' if key in req else ''}")
    mrows.append(f"<tr><td>{esc(name)}</td><td>{esc('；'.join(fields))}</td></tr>")
model_table='<table><tr><th>模型</th><th>字段（*必填）</th></tr>'+''.join(mrows)+'</table>'

api_toc=[('intro','1. 接口约定'),('sequence','2. 调用流程'),('endpoints','3. 接口清单'),('models','4. 数据模型'),('examples','5. 调用示例'),('errors','6. 状态、错误与安全'),('integration','7. 第三方联调'),('approval','8. 审批与验收')]
api=f"""
<h1 id="intro">1. 接口约定</h1><table><tr><th>项目</th><th>约定</th></tr><tr><td>名称/版本</td><td>{esc(schema['info']['title'])} / {esc(schema['info']['version'])}</td></tr><tr><td>基础地址</td><td>http://服务器IP:8000</td></tr><tr><td>内容类型</td><td>application/json；SSE为text/event-stream</td></tr><tr><td>字符集/时间</td><td>UTF-8；ISO 8601 UTC</td></tr><tr><td>接口数量</td><td>{len(rows)}个OpenAPI操作</td></tr><tr><td>契约</td><td>/openapi.json、/docs</td></tr></table><div class="warn"><b>认证边界：</b>当前源码未对API实施登录令牌或管理员服务端鉴权，取消接口操作者为演示值。生产前必须增加统一认证、角色授权、真实审计身份、网络边界和传输加密；当前无HTTPS时仅限受控内网。</div><h2>1.1 通用响应</h2><p>成功为JSON对象或items列表。参数校验通常422；业务错误为 <code>{{"detail":{{"code":"...","message":"..."}}}}</code>。同时处理HTTP状态和detail.code。</p>
<h1 id="sequence">2. 调用流程</h1><h2>2.1 问数</h2><ol><li>POST /api/v1/sessions创建Session。</li><li>POST /api/v1/queries取得request_id。</li><li>GET /queries/{{rid}}/events订阅SSE，断线用Last-Event-ID。</li><li>GET /queries/{{rid}}取最终轨迹、SQL和结果。</li><li>POST /queries/{{rid}}/cancel取消；重复取消幂等。</li></ol><h2>2.2 二期配置</h2><ol><li>分别创建模型和数据源。</li><li>启用并诊断。</li><li>组合Profile、启用并诊断。</li><li>创建二期Session时传provider_profile_id。</li></ol>
<h1 id="endpoints">3. 接口清单</h1><p>由当前FastAPI OpenAPI契约自动生成；管理端前缀/api/v1/admin。</p>{endpoint_table}
<h1 id="models">4. 请求数据模型</h1>{model_table}<p class="small">精确枚举、长度和数值范围以交付版本openapi.json为准。</p>
<h1 id="examples">5. 调用示例</h1><h2>5.1 Session与查询</h2><pre>curl -sS -X POST http://SERVER:8000/api/v1/sessions -H 'Content-Type: application/json' -d '{{"role_id":"admin","execution_mode":"PHASE1_DEMO"}}'
curl -sS -X POST http://SERVER:8000/api/v1/queries -H 'Content-Type: application/json' -d '{{"session_id":"SESSION_ID","question":"2026年3月上海分行对公贷款投放金额","scenario_id":"scenario-1"}}'</pre><h2>5.2 SSE</h2><pre>curl -N http://SERVER:8000/api/v1/queries/REQUEST_ID/events
curl -N -H 'Last-Event-ID: 12' http://SERVER:8000/api/v1/queries/REQUEST_ID/events</pre><p>事件含递增id、event类型、JSON data及heartbeat；终态后结束。</p><h2>5.3 二期Session</h2><pre>{{"role_id":"admin","execution_mode":"PHASE2_POC","provider_profile_id":"PROFILE_ID"}}</pre><h2>5.4 资源</h2><pre>PUT /api/v1/admin/resources/assets/metric-retail-loan
{{"id":"metric-retail-loan","payload":{{"__page":"metrics","指标名称":"零售贷款余额"}},"enabled":true}}</pre>
<h1 id="errors">6. 状态、错误与安全</h1><h2>6.1 状态</h2><p>PENDING、RUNNING、WAITING_INPUT、SHORT_CIRCUITED、BLOCKED、PARTIAL_SUCCESS、SUCCEEDED、FAILED、CANCELLED。客户端应识别全部终态。</p><h2>6.2 错误</h2><table><tr><th>错误码</th><th>建议</th></tr><tr><td>INVALID_INPUT</td><td>修正参数、ID或确认标志</td></tr><tr><td>MISSING_PARAMETER / AMBIGUOUS_RECOMMENDATION</td><td>补充或选择</td></tr><tr><td>PERMISSION_DENIED / COMPLIANCE_BLOCKED</td><td>停止，不得绕过</td></tr><tr><td>ASSET_NOT_FOUND</td><td>检查角色、Session、请求或资源</td></tr><tr><td>SQL_GENERATION_FAILED / EXECUTION_FAILED</td><td>检查模板、安全、数据源和日志</td></tr><tr><td>CANCELLED / INTERPRETATION_FAILED</td><td>按终态处理</td></tr><tr><td>RUNTIME_CONFIG_UNAVAILABLE / PROVIDER_PROFILE_UNAVAILABLE</td><td>补配置或重录/诊断Provider</td></tr></table><h2>6.3 安全</h2><ul><li>API Key和密码仅写服务端加密字段，不回显、不导出、不记日志。</li><li>SQL仅单条SELECT/CTE，执行表白名单、行数、时间和超时限制；账号只读。</li><li>诊断脱敏；凭据不得进URL、客户端代码或示例。</li><li>写操作、重置和恢复须增加强认证、重放防护和审批。</li></ul>
<h1 id="integration">7. 第三方联调清单</h1><ol><li>确认网络、地址、版本。</li><li>获取批准的认证方式；无认证版不得用于非受控网络。</li><li>冻结openapi.json。</li><li>验证Session、查询、SSE续传、详情、取消。</li><li>验证三角色允许/拒绝。</li><li>验证超时、重复取消和断线恢复。</li><li>确认日志无凭据。</li><li>二期执行真实诊断、33轮和源库对账。</li></ol>
"""

inv_toc=[('principles','1. 交付原则'),('list','2. 交付内容'),('docs','3. 文档与截图'),('evidence','4. 验收与缺口'),('security','5. 排除与安全'),('sign','6. 签收清单'),('approval','7. 审批与验收')]
inventory=f"""
<h1 id="principles">1. 交付原则</h1><p>按产品包、配置契约、运维、证据和文档分类。发布绑定版本和Git SHA，生成SHA256SUMS；密钥、令牌、客户明细、临时库和缓存不入包。</p>
<h1 id="list">2. 交付内容</h1><table><tr><th>编号</th><th>内容</th><th>路径</th><th>状态/条件</th></tr><tr><td>D01</td><td>后端源码</td><td>backend/</td><td>已存在；测试可运行</td></tr><tr><td>D02</td><td>前端源码</td><td>frontend/</td><td>已存在；build通过</td></tr><tr><td>D03</td><td>部署诊断脚本</td><td>scripts/</td><td>目标环境复验</td></tr><tr><td>D04</td><td>基线与Schema</td><td>fixtures/、schemas/</td><td>JSON/契约校验</td></tr><tr><td>D05</td><td>环境模板</td><td>.env.example</td><td>不得含凭据</td></tr><tr><td>D06</td><td>POC构建物</td><td>frontend/dist/</td><td>已构建</td></tr><tr><td>D07</td><td>离线单文件</td><td>frontend/offline-dist/</td><td>发布前重建断网验证</td></tr><tr><td>D08-D11</td><td>四份交付文档</td><td>PDF + HTML</td><td>本次生成</td></tr><tr><td>D12</td><td>实际页面截图</td><td>docs/deliverables/assets/</td><td>9张，1440×920</td></tr></table>
<h2>2.1 建议发布结构</h2><pre>release/phase2/VERSION/
├── source/
├── dist/
├── docs/
├── evidence/
├── openapi.json
└── SHA256SUMS</pre>
<h1 id="docs">3. 文档与截图</h1><table><tr><th>文件</th><th>覆盖</th></tr><tr><td>01-用户操作手册-V1.0</td><td>使用者、管理员、八场景、配置、日志、恢复</td></tr><tr><td>02-安装部署手册-V1.0</td><td>双Linux族、单机/多机、systemd、ClickHouse/MySQL</td></tr><tr><td>03-技术接口手册-V1.0</td><td>全部OpenAPI操作、模型、示例、错误、安全、联调</td></tr><tr><td>04-交付内容清单-V1.0</td><td>产品、配置、证据、缺口、签收</td></tr></table><p>截图覆盖用户首页、查询结果、管理首页、用户、指标、模型、数据源、日志和恢复；无密钥/密码。</p>
<h1 id="evidence">4. 验收结果与缺口</h1><table><tr><th>事项</th><th>结果</th><th>处置</th></tr><tr><td>隔离安装、依赖、初始化、构建</td><td class="pass">通过</td><td>Debian 12已执行</td></tr><tr><td>健康/诊断</td><td class="pass">通过</td><td>status=ok</td></tr><tr><td>后端测试</td><td class="pass">29 passed</td><td>2个弃用警告</td></tr><tr><td>一期完整矩阵</td><td class="pass">通过</td><td>3角色×8场景×33轮；场景7两轮通过</td></tr><tr><td>二期协议与仿真矩阵</td><td class="pass">通过</td><td>7项测试及Provider仿真33轮；不等同真实环境</td></tr><tr><td>真实模型/ClickHouse/MySQL</td><td>待执行</td><td>目标环境真连</td></tr><tr><td>真实Provider 33轮与对账</td><td>待执行</td><td>禁止Fixture或Stub冒充</td></tr><tr><td>性能、安全、恢复、业务签字</td><td>待执行</td><td>目标环境形成证据</td></tr><tr><td>生产认证/HTTPS</td><td>未包含</td><td>仅受控内网或整改</td></tr></table><div class="warn">“仓库内自动验收通过”不等于“客户生产验收”。未完成项应作为发布和签收门禁。</div>
<h1 id="security">5. 排除项与安全检查</h1><h2>5.1 排除</h2><ul><li>data/.credential-key、真实.env、API Key、密码、令牌。</li><li>客户原始数据、未脱敏结果和生产日志。</li><li>.venv、node_modules、缓存、临时目录、本地PID。</li><li>个人配置及无关历史包。</li></ul><h2>5.2 发布前</h2><pre>git status --short
bash scripts/diagnose.sh
cd backend && ../.venv/bin/python -m pytest -q
cd .. && npm --prefix frontend ci && npm --prefix frontend run build
bash scripts/demo-readiness-check.sh
find release/phase2/VERSION -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS</pre>
<h1 id="sign">6. 交付签收清单</h1><table class="approval"><tr><th>序号</th><th>签收项</th><th>数量/版本</th><th>结果</th><th>签收人/日期</th></tr><tr><td>1</td><td>源码和脚本</td><td></td><td></td><td></td></tr><tr><td>2</td><td>构建物和摘要</td><td></td><td></td><td></td></tr><tr><td>3</td><td>四份PDF和HTML</td><td>各1/V1.0</td><td></td><td></td></tr><tr><td>4</td><td>OpenAPI与模板</td><td></td><td></td><td></td></tr><tr><td>5</td><td>测试和目标环境证据</td><td></td><td></td><td></td></tr><tr><td>6</td><td>已知问题/风险接受</td><td></td><td></td><td></td></tr></table>
"""

documents=[
('01-用户操作手册-V1.0',make('用户操作手册','使用者操作 · 系统管理员操作',user_toc,user)),
('02-安装部署手册-V1.0',make('用户安装部署手册','Linux · 单机与多服务器 · 非Docker部署',install_toc,install)),
('03-技术接口手册-V1.0',make('技术接口手册','第三方独立对接标准 · OpenAPI事实源',api_toc,api)),
('04-交付内容清单-V1.0',make('交付内容清单','产品包 · 文档 · 证据 · 签收',inv_toc,inventory))]
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    page=browser.new_page()
    for stem,src in documents:
        hp=OUT/(stem+'.html'); pp=OUT/(stem+'.pdf'); hp.write_text(src,encoding='utf-8')
        page.goto(hp.as_uri(),wait_until='load')
        page.pdf(path=str(pp),format='A4',print_background=True,prefer_css_page_size=True)
    browser.close()
manifest=[]
for p in sorted(OUT.glob('*.pdf')): manifest.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
(OUT/'SHA256SUMS').write_text('\n'.join(manifest)+'\n',encoding='utf-8')
print(json.dumps({'documents':len(documents),'endpoints':len(rows),'output':str(OUT)},ensure_ascii=False))

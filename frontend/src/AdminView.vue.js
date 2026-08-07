import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { adminApi } from './admin-api';
import { isOffline } from './runtime';
const p = (id, label, fields, help, readonly = false) => ({ id, label, fields, help, readonly });
const menus = [
    { id: 'home', label: '管理首页', icon: 'H' },
    { id: 'admin-access', label: '后台权限', icon: 'B', children: [p('admin-roles', '后台角色', ['角色名称', '角色编码', '菜单权限', '操作权限', '数据管理范围', '状态'], '后台角色与菜单、按钮操作权限分离配置'), p('administrators', '管理员管理', ['管理员账号', '姓名', '管理员角色', '手机号', '邮箱', '最近登录', '状态'], '后台管理员账号新增、编辑、冻结及角色分配'), p('admin-permissions', '后台权限', ['权限名称', '权限编码', '权限类型', '菜单/功能', '操作权限', '状态'], '菜单权限和新增、编辑、删除、发布等操作权限')] },
    { id: 'user-access', label: '用户权限', icon: 'U', children: [p('client-roles', '用户角色', ['角色名称', '角色编码', '职责说明', '机构权限池', '指标权限池', '功能权益', '状态'], '总行行长、分行行长、业务负责人三类业务角色'), p('client-users', '用户管理', ['用户姓名', '登录账号', '用户角色', '所属机构', '职务', '手机号', '状态'], '张总、李总、王总与业务角色、机构归属关系'), p('client-permissions', '功能权限', ['权限名称', '用户角色', '机构权限', '指标权限', '可用场景', '可访问驾驶舱', '明细权限', '导出权限', '状态'], '机构、指标、场景、驾驶舱、明细和导出功能权限'), p('permission-priority', '权限优先级', ['规则', '优先级', '动作', '状态'], '非法闲聊 > 涉密 > 跨机构 > 无权限指标')] },
    { id: 'assets', label: '数据字典', icon: 'A', children: [p('metrics', '指标字典', ['指标名称', '英文标识', '业务口径', '单位', '分类', '数据源', '数据表', '可访问角色', '状态'], '指标增删改查、数据源/数据表关联、分类与权限绑定'), p('dimensions', '维度字典', ['维度名称', '类型', '成员/周期', '数据源', '数据表', '物理字段', '状态'], '机构、客户、时间与同比周期'), p('warehouse-assets', '数仓管理', ['名称', '数据源', '类型', '库名', '表名', '优先级', '状态'], '从已接入数据源选择并维护字段映射、宽表优先级'), p('field-mappings', '字段映射', ['数据源', '数据表', '标准指标', '物理字段', '同期字段', '分项字段', '状态'], '指标与已接入数据表字段绑定'), p('recommendations', '模糊推荐', ['角色', '关键词', '标准指标', '推荐问句', '状态'], '角色推荐列表与口语映射')] },
    { id: 'flows', label: '流程配置', icon: 'P', children: [p('intent-rules', '意图规则', ['模板名称', '触发关键词', '终止层', '优先级', '状态'], '六大意图模板与触发词'), p('sql-templates', 'SQL模板', ['模板名称', '类型', 'SQL模板', '行数上限', '超时秒', '语法校验', '状态'], '单期、同比、多机构模板与安全规则'), p('conversation', '会话配置', ['配置项', '值', '说明', '状态'], '缓存时效、参数继承、清空策略'), p('parameter-rules', '参数校验', ['参数', '是否必填', '校验规则', '缺失提示', '可选值', '状态'], '指标、机构、时间强制校验'), p('seven-layers', '七层配置', ['层级', '名称', '处理器', 'Provider', '状态'], '固定 L1—L7 顺序', true)] },
    { id: 'scenes', label: '场景管理', icon: 'S', children: [p('standard-scenes', '标准场景', ['场景名称', '触发问句', '意图模板', 'Mock数据', '预设SQL', '状态'], '八大场景增删改与 Mock 维护'), p('scene-parameter-bindings', '参数关联', ['场景ID', '场景名称', '适用角色', '可用模式', '意图规则', '必填参数', '默认指标', '数据源', '数据表', 'SQL模板', '终止层', 'L7输出模板', '图表配置', '降级策略', '状态'], '场景到角色、参数、资产、SQL、输出和模式策略的完整关联'), p('quick-buttons', '快捷提问', ['按钮名称', '场景ID', '预设问句', '标签', '排序', '角色', '状态'], '快捷栏按钮、排序和角色范围'), p('dashboards', '驾驶舱管理', ['名称', 'URL', '角色', '标签', '状态'], '总行、分行、业务负责人驾驶舱链接与权限')] },
    { id: 'logs', label: '查询日志', icon: 'L', children: [p('sessions', '用户会话', [], '会话检索、筛选、详情与导出', true), p('requests', '执行轨迹', [], '每层入参出参和拦截分类', true), p('sql', 'SQL审计', [], 'SQL、耗时、行数、数据源和慢查询', true), p('audit', '操作日志', [], '管理员增删改与配置变更', true)] },
    { id: 'compliance', label: '安全管控', icon: 'C', children: [p('classified', '涉密管控', ['名称', '对象类型', '对象值', '白名单', '拦截动作', '状态'], '涉密指标/机构与明细白名单'), p('rate-limits', '访问限流', ['名称', '范围', '每分钟次数', '行数限制', '高频动作', '状态'], '用户频率和批量行数限制'), p('masking', '数据脱敏', ['字段', '角色', '脱敏等级', '规则', '状态'], '姓名、身份证、手机号分角色脱敏'), p('intercept-wording', '拦截话术', ['原因', '提示文案', '语言', '状态'], '权限、缺参、不匹配与非法闲聊话术')] },
    { id: 'operations', label: '系统运维', icon: 'O', children: [p('ui-config', '界面配置', ['配置项', '值', '说明', '状态'], '标题、角色、提示、气泡、表格和轨迹'), p('interaction', '消息交互', ['配置项', '值', '样式', '状态'], '语音、参数弹窗、推荐/场景标签'), p('scheduled-jobs', '定时任务', ['任务名称', 'Cron', '动作', '保留天数', '状态'], '字典/元数据同步与日志/会话清理'), p('system-params', '系统参数', ['参数名', '值', '单位', '说明', '状态'], '连接/SQL超时、缓存、分页和导出'), p('runtime-policy', '执行策略', ['模式', '允许Fixture降级', '允许参数默认值', '强制真实模型', '强制真实数据源', '执行间隔毫秒', '状态'], '演示允许配置兜底，POC固定强制真实Provider且禁止降级'), p('runtime-profiles', '运行组合', ['组合名称', '模型配置', '数据源配置', '状态'], '引用已启用的独立模型和数据源，供二期运行会话选择'), p('answer-templates', '结果模板', ['模板名称', '模板类型', '模板内容', '状态'], 'L7单期、同比、无数据和归因话术配置'), p('output-visualization', '输出图表', ['图表类型', '图表标题', '分类字段', '数值字段', '引导提示', '状态'], '结果图表规格和2-3个用户后续提问引导'), p('alerts', '告警配置', ['告警名称', '条件', '渠道', '接收人', '状态'], '越权、断连、SQL异常和消息推送'), p('readiness', '就绪检查', ['组件', '模式', '状态', '说明'], 'Provider与三种执行模式运行配置完整性', true), p('recovery', '备份重置', [], '官方配置、Mock数据与备份恢复', true)] },
    { id: 'models', label: '模型配置', icon: 'M', children: [p('model-connect', '模型对接', ['配置名称', '模型提供商', '模型名称', '接口地址', '模型版本', '温度', 'Top P', '最大Token', '上下文窗口', '结构化输出', '超时秒', '连接状态', '状态'], '提供商与模型联动选择、密钥加密、生成参数、上下文、结构化输出和连通诊断'), p('model-capabilities', '模型能力', ['配置项', '任务层级', '启用能力', 'Prompt模板', '输出约束', '状态'], 'L2理解、L7解读、归因、推荐和安全Prompt'), p('model-limits', '调用管控', ['范围', '每分钟次数', '每日次数', '状态'], '基础限流'), p('model-logs', '调用日志', [], '按模型、层级、角色、状态和耗时查看真实调用记录与详情', true)] },
    { id: 'datasources', label: '数据源配置', icon: 'D', children: [p('source-connect', '数据源对接', ['名称', '类型', '环境', '地址/库名', '关联数据表', '表数量', '只读模式', '字符集', '连接池', 'Schema同步', '最大行数', '查询超时', '连接状态', '状态'], 'ClickHouse/MySQL/SQLite连接、已关联表、安全、池化、超时和元数据同步'), p('source-tables', '数据表管理', ['数据源', '库/Schema', '表名', '表类型', '时间字段', '机构字段', '主键字段', '关联指标', '可查询角色', '状态'], '宽表、明细表、字段和角色白名单'), p('source-security', '数据权限', ['数据源/表', '角色', '涉密隔离', '字段脱敏', '缓存', '状态'], '角色绑定、涉密和缓存配置'), p('source-monitor', '运维监控', [], '按数据源查看SQL、耗时、行数、降级、错误和查询详情', true)] },
    { id: 'mock', label: '演示管理', icon: 'K', children: [p('mock-data', '模拟数据', ['stat_dt', 'org_name', 'loan_cur', 'loan_last', 'retail_cur', 'retail_last', 'corporate_cur', 'corporate_last'], 'POC SQLite 模拟宽表数据'), p('mock-scenes', '场景配置', ['场景', '角色', '输入问句', '返回数据', '话术', 'SQL', '覆盖配置JSON', '状态'], '确定性场景与角色数据'), p('demo-switches', '演示开关', ['开关名称', '配置键', '值', '说明', '状态'], 'Fixture降级、轨迹、动画和模式'), p('mock-wording', '演示话术', ['名称', '场景', '内容', '状态'], '欢迎、加载、成功、错误话术')] }
];
const pages = menus.flatMap(g => g.children || []), router = useRouter(), collapsed = ref(false), expanded = ref(new Set()), active = ref('home'), tabs = ref([{ id: 'home', label: '管理首页' }]), baseline = ref({}), ready = ref({}), rows = ref([]), editing = ref(null), search = ref(''), message = ref(''), busy = ref(false), versions = ref([]), sourceCatalog = ref([]), tableCatalog = ref([]), metricCatalog = ref([]), modelConfigCatalog = ref([]), datasourceConfigCatalog = ref([]), homeRequests = ref([]), homeAudits = ref([]), homeProfiles = ref([]), homeApprovals = ref([]), page = ref(1);
const current = computed(() => active.value === 'home' ? { id: 'home', label: '管理首页', fields: [], help: '关键运营指标、待办事项与最新通知' } : pages.find(x => x.id === active.value)), group = computed(() => menus.find(g => g.children?.some(x => x.id === active.value))), kind = computed(() => group.value?.id || 'operations'), filtered = computed(() => rows.value.filter(x => !search.value || JSON.stringify(x).toLowerCase().includes(search.value.toLowerCase())));
const modelConfigPage = computed(() => active.value === 'model-connect'), datasourceConfigPage = computed(() => active.value === 'source-connect'), compositionPage = computed(() => active.value === 'runtime-profiles'), providerPage = computed(() => modelConfigPage.value || datasourceConfigPage.value || compositionPage.value);
const logPage = computed(() => ['sessions', 'requests', 'sql', 'audit', 'model-logs', 'source-monitor'].includes(active.value));
const logFilters = ref({ keyword: '', role: '', status: '', mode: '', scenario: '', from: '', to: '' }), logDetailData = ref(null);
const logColumnMap = { sessions: [{ key: 'id', label: '会话ID' }, { key: 'operator_id', label: '操作人ID' }, { key: 'role_id', label: '角色' }, { key: 'created_at', label: '创建时间' }, { key: 'last_activity_at', label: '最后活动时间' }, { key: 'status', label: '状态' }, { key: 'request_count', label: '请求数' }], requests: [{ key: 'id', label: '查询ID' }, { key: 'session_id', label: '会话ID' }, { key: 'operator_id', label: '操作人ID' }, { key: 'role_id', label: '角色' }, { key: 'question', label: '提问内容' }, { key: 'scenario_id', label: '场景' }, { key: 'mode', label: '模式' }, { key: 'status', label: '结果状态' }, { key: 'last_layer', label: '终止层' }, { key: 'has_result', label: '结果数据' }, { key: 'created_at', label: '开始时间' }, { key: 'completed_at', label: '完成时间' }], sql: [{ key: 'id', label: 'SQL日志ID' }, { key: 'request_id', label: '查询ID' }, { key: 'operator_id', label: '操作人ID' }, { key: 'role_id', label: '角色' }, { key: 'scenario_id', label: '场景' }, { key: 'source', label: '数据源' }, { key: 'status', label: '执行结果' }, { key: 'row_count', label: '返回行数' }, { key: 'elapsed_ms', label: '耗时ms' }, { key: 'fallback', label: '降级' }, { key: 'created_at', label: '时间' }], audit: [{ key: 'id', label: '审计ID' }, { key: 'operator_id', label: '操作人ID' }, { key: 'action', label: '操作类型' }, { key: 'detail', label: '操作摘要' }, { key: 'status', label: '记录状态' }, { key: 'created_at', label: '操作时间' }], 'model-logs': [{ key: 'id', label: '调用ID' }, { key: 'request_id', label: '查询ID' }, { key: 'operator_id', label: '操作人ID' }, { key: 'role_id', label: '角色' }, { key: 'layer_code', label: '调用层级' }, { key: 'model_provider', label: '模型提供商' }, { key: 'model', label: '模型名称' }, { key: 'mode', label: '执行模式' }, { key: 'status', label: '调用结果' }, { key: 'elapsed_ms', label: '耗时ms' }, { key: 'error_code', label: '错误码' }, { key: 'created_at', label: '调用时间' }], 'source-monitor': [{ key: 'id', label: '执行ID' }, { key: 'request_id', label: '查询ID' }, { key: 'operator_id', label: '操作人ID' }, { key: 'role_id', label: '角色' }, { key: 'source', label: '数据源' }, { key: 'mode', label: '执行模式' }, { key: 'status', label: '执行结果' }, { key: 'row_count', label: '返回行数' }, { key: 'elapsed_ms', label: '耗时ms' }, { key: 'fallback', label: '是否降级' }, { key: 'error', label: '错误摘要' }, { key: 'created_at', label: '执行时间' }] };
const logColumns = computed(() => logColumnMap[active.value] || []), logStatuses = computed(() => Array.from(new Set(rows.value.map(x => String(x.status || '')).filter(Boolean))));
const logFiltered = computed(() => rows.value.filter(x => { const f = logFilters.value, t = String(x.created_at || ''); return (!f.keyword || JSON.stringify(x).toLowerCase().includes(f.keyword.toLowerCase())) && (!f.role || x.role_id === f.role || x.operator_id === f.role) && (!f.status || x.status === f.status) && (!f.mode || x.mode === f.mode) && (!f.scenario || x.scenario_id === f.scenario) && (!f.from || t >= f.from) && (!f.to || t <= f.to + 'T23:59:59'); }));
const PAGE_SIZE = 20, totalPages = computed(() => Math.max(1, Math.ceil((logPage.value ? logFiltered.value.length : active.value === 'recovery' ? versions.value.length : filtered.value.length) / PAGE_SIZE))), pagedFiltered = computed(() => filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE)), pagedLogs = computed(() => logFiltered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE)), pagedVersions = computed(() => versions.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE));
const statusNames = { ACTIVE: '活跃', CLOSED: '已关闭', SUCCEEDED: '成功', FAILED: '失败', BLOCKED: '权限拦截', SHORT_CIRCUITED: '短路完成', WAITING_INPUT: '待补参数', CANCELLED: '已取消', RECORDED: '已记录', RUNNING: '执行中', PENDING: '等待中' };
const successfulStatuses = new Set(['SUCCEEDED', 'SHORT_CIRCUITED', 'BLOCKED', 'WAITING_INPUT']);
const homeMetrics = computed(() => { const all = homeRequests.value, done = all.filter(x => !['PENDING', 'RUNNING'].includes(String(x.status))), success = done.filter(x => successfulStatuses.has(String(x.status))), elapsed = done.map(x => x.created_at && x.completed_at ? new Date(x.completed_at).getTime() - new Date(x.created_at).getTime() : 0).filter(x => x >= 0); return [{ label: '累计问数', value: all.length, unit: '次', note: '会话查询总量', tone: 'blue' }, { label: '执行成功率', value: done.length ? Math.round(success.length / done.length * 100) : 100, unit: '%', note: `成功 ${success.length} / 完成 ${done.length}`, tone: 'green' }, { label: '平均响应', value: elapsed.length ? (elapsed.reduce((a, b) => a + b, 0) / elapsed.length / 1000).toFixed(2) : '0.00', unit: '秒', note: '已完成请求平均耗时', tone: 'orange' }]; });
const auditActionNames = { CREATE_MODEL_CONFIG: '新建了模型配置', CREATE_DATASOURCE_CONFIG: '新建了数据源配置', CREATE_PHASE2_PROFILE: '新建了运行组合', ENABLE_PHASE2_PROFILE: '启用了运行组合', SAVE_RESOURCE: '更新了后台配置', DELETE_RESOURCE: '删除了后台配置', PUBLISH: '发布了配置版本', RESTORE_OFFICIAL: '恢复了官方配置' };
const homeNotices = computed(() => { const items = []; for (const [name, value] of Object.entries(ready.value.providers || {}))
    if (!value.ready)
        items.push({ category: '告警通知', title: `${name}服务连接异常`, detail: '健康检查未通过，请及时检查网络、凭据和服务状态。', time: '刚刚', target: 'readiness', targetLabel: '查看就绪检查' }); for (const x of homeProfiles.value)
    if (x.status === 'DRAFT' || x.diagnostic_status !== 'READY')
        items.push({ category: '告警通知', title: `运行组合“${x.name || x.id}”尚未就绪`, detail: x.status === 'DRAFT' ? '该组合尚未启用，暂不能用于二期问数。' : '最近一次诊断未通过，请查看诊断结果。', time: x.updated_at ? new Date(x.updated_at).toLocaleString('zh-CN', { hour12: false }) : '今天', target: 'runtime-profiles', targetLabel: '查看运行组合' }); for (const x of homeAudits.value.slice(0, 6)) {
    const action = String(x.action || 'SYSTEM_NOTICE');
    items.push({ category: '操作通知', title: auditActionNames[action] || '后台配置发生变更', detail: `操作人：${x.operator_id || x.actor || 'admin'}；${auditActionNames[action] || '详细信息已记录到操作日志'}。`, time: x.created_at ? new Date(x.created_at).toLocaleString('zh-CN', { hour12: false }) : '-', target: 'audit', targetLabel: '查看操作日志' });
} return items.slice(0, 6); });
const homeTrend = computed(() => { const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - 6 + i); return d.toISOString().slice(0, 10); }); const rows = days.map(day => { const requests = homeRequests.value.filter(x => String(x.created_at || '').slice(0, 10) === day), done = requests.filter(x => x.completed_at), success = requests.filter(x => successfulStatuses.has(String(x.status))).length, elapsed = done.map(x => new Date(x.completed_at).getTime() - new Date(x.created_at).getTime()).filter(x => x >= 0); return { day: day.slice(5), total: requests.length, success, avg: elapsed.length ? elapsed.reduce((a, b) => a + b, 0) / elapsed.length / 1000 : 0 }; }); return { rows, maxTotal: Math.max(1, ...rows.map(x => x.total)), maxAvg: Math.max(1, ...rows.map(x => x.avg)) }; });
const detailNames = { session: '会话摘要', request: '查询摘要', requests: '关联查询', layers: '七层执行轨迹', sql_executions: 'SQL执行记录', result: '结果数据', events: '事件流', sql: 'SQL详情', model_call: '模型调用详情', audit: '审计详情', detail: '操作内容' };
function detailLabel(key) { return detailNames[key] || key; }
function statusClass(value) { return ['FAILED', 'BLOCKED', 'CANCELLED'].includes(String(value)) ? 'status-error' : ['WAITING_INPUT', 'PENDING', 'RUNNING'].includes(String(value)) ? 'status-warning' : 'status-success'; }
function logValue(row, key) { if (key === 'has_result')
    return row.has_result ? '有结果' : '无结果'; if (key === 'fallback')
    return row.fallback ? '已降级' : '未降级'; const value = row[key]; if (value == null || value === '')
    return '-'; if (key === 'status')
    return statusNames[String(value)] || String(value); if (key === 'mode')
    return { POC: 'POC模式', PHASE1_DEMO: '一期演示', PHASE2_DEMO: '二期演示', PHASE2_POC: '二期POC' }[String(value)] || String(value); if (key.endsWith('_at') || key === 'created_at')
    return new Date(String(value)).toLocaleString('zh-CN', { hour12: false }); return typeof value === 'object' ? JSON.stringify(value) : String(value); }
async function viewLog(row) { busy.value = true; try {
    logDetailData.value = row.__demo ? row.__detail : await adminApi.logDetail(active.value, row.id);
}
catch (e) {
    message.value = String(e);
}
finally {
    busy.value = false;
} }
function resetLogFilters() { logFilters.value = { keyword: '', role: '', status: '', mode: '', scenario: '', from: '', to: '' }; page.value = 1; }
function openHomeTarget(id) { const target = pages.find(x => x.id === id); if (target)
    open(target); }
const modelProviders = {
    'OpenAI': { code: 'OPENAI', baseUrl: 'https://api.openai.com/v1', models: ['gpt-5.4', 'gpt-5.4-mini'] },
    'Google Gemini': { code: 'GEMINI', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', models: ['gemini-3.6-flash', 'gemini-3.1-pro-preview', 'gemini-3.1-flash-lite-preview'] },
    'DeepSeek': { code: 'DEEPSEEK', baseUrl: 'https://api.deepseek.com', models: ['deepseek-v4-flash', 'deepseek-v4-pro'] },
    '阿里通义千问': { code: 'QWEN', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', models: ['qwen3.7-plus', 'qwen3.6-flash', 'qwen-plus'] },
    '智谱 GLM': { code: 'ZHIPU_GLM', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', models: ['glm-5.2', 'glm-5', 'glm-4.5-flash'] },
    '自定义兼容服务': { code: 'OPENAI_COMPATIBLE', baseUrl: 'https://', models: [] }
};
const modelFields = ['配置名称', '模型提供商', '模型名称', '模型接口地址', '模型API Key', '模型温度', '模型Top P', '模型最大Token', '模型上下文窗口', '模型结构化输出', '模型系统Prompt', '超时秒', '重试次数', '最大并发数'];
const datasourceFields = ['配置名称', '数据源类型', '数据源HTTP地址', '数据源主机', '数据源端口', '启用TLS', '数据源用户名', '数据源密码', '数据库', '允许访问表', '数据源只读', '数据源字符集', '连接池大小', 'Schema同步', '最大返回行数', '最大时间范围天数', '超时秒', '重试次数', '最大并发数'];
const editorFields = computed(() => modelConfigPage.value ? modelFields : datasourceConfigPage.value ? datasourceFields : compositionPage.value ? ['组合名称', '模型配置', '数据源配置'] : (current.value?.fields || []));
const multiFields = new Set(['机构权限池', '指标权限池', '功能权限', '功能权益', '可用场景', '可访问驾驶舱', '适用角色', '可用模式', '必填参数', '可访问角色', '关联指标', '接收人', '允许访问表', '白名单', '分项字段', '成员/周期', '菜单权限', '操作权限', '菜单/功能', '机构权限', '指标权限', '引导提示', '数值字段']);
const multiRolePages = new Set(['quick-buttons', 'dashboards', 'source-security', 'masking']);
const optionMap = { 状态: ['启用', '停用'], 模式: ['PHASE1_DEMO', 'PHASE2_DEMO', 'PHASE2_POC'], 允许Fixture降级: ['是', '否'], 允许参数默认值: ['是', '否'], 强制真实模型: ['是', '否'], 强制真实数据源: ['是', '否'], 模板类型: ['无数据', '单期查询', '同比查询', '归因后缀'], 图表类型: ['bar', 'line', 'pie', 'table'], 结构化输出: ['是', '否'], 模型结构化输出: ['是', '否'], 只读模式: ['是', '否'], 数据源只读: ['是', '否'], Schema同步: ['是', '否'], 明细权限: ['允许（脱敏）', '不允许'], 导出权限: ['允许', '允许本机构', '允许本业务', '不允许'], 表类型: ['指标宽表', '业务明细表', '维度表'], 任务层级: ['L2', 'L7', '通用'], 启用能力: ['结构化理解', '结果解读', '同比归因', '问题推荐', '输出安全'], 可访问角色: ['admin', 'beijing', 'retail'], 机构权限池: ['全行', '北京分行', '上海分行'], 机构权限: ['全行', '北京分行', '上海分行'], 指标权限池: ['贷款投放', '零售贷款', '对公贷款'], 指标权限: ['全部', '贷款投放', '零售贷款', '对公贷款'], 功能权限: ['问数', '驾驶舱', '归因', '导出', '后台'], 数据范围: ['全行', '本机构', '专项条线'], 动作: ['放行', 'L2拦截', '告警'], 是否必填: ['是', '否'], 语法校验: ['开启', '关闭'], 默认模型: ['是', '否'], 默认源: ['是', '否'], 环境: ['演示', '测试', 'POC', '生产'], 数据源类型: ['CLICKHOUSE', 'MYSQL'], 启用TLS: ['是', '否'], 脱敏等级: ['高', '中', '低'], 语言: ['zh-CN', 'en-US'], 渠道: ['内部消息', '邮件', '短信'], 对象类型: ['指标', '机构', '字段', '明细'], 拦截动作: ['L2强制拦截', '告警', '脱敏'], 涉密隔离: ['开启', '关闭'], 字段脱敏: ['开启', '关闭'], 缓存: ['开启', '关闭'], 单位: ['元', '万元', '亿元', '笔', '户', '%'], 分类: ['信贷', '零售信贷', '对公信贷', '存款', '客户', '经营分析'], 参数: ['时间', '机构', '指标', '维度'], 终止层: ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7'], 层级: ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7'], Provider: ['DETERMINISTIC', 'MOCK', 'OPENAI_COMPATIBLE', 'SQLITE', 'CLICKHOUSE', 'MYSQL'], 范围: ['单用户', '角色', '数据源', '全部用户'], 高频动作: ['拦截并告警', '仅告警', '限速'], 原因: ['权限不足', '参数缺失', '指标不匹配', '非法闲聊', '涉密查询'], 样式: ['默认蓝色', '警告黄色', '拦截红色'], Mock数据: ['SQLITE', 'FIXTURE', 'NONE'], 预设SQL: ['参数化模板', '无'], 值: ['开启', '关闭', 'true', 'false'], 规则: ['前3后4', '仅显示末4位', '全量掩码'] };
const numberFields = new Set(['优先级', '排序', '行数上限', '超时秒', '每分钟次数', '每日次数', '保留天数', '行数限制', '数据源端口', '最大返回行数', '最大时间范围天数', '重试次数', '最大并发数', '执行间隔毫秒', '模型温度', '模型Top P', '模型最大Token', '模型上下文窗口', '连接池大小', '连接池', '最大行数', '查询超时']);
const secretFields = new Set(['模型API Key', '数据源密码']);
function optionsFor(field) {
    if (field === '模型提供商')
        return Object.keys(modelProviders);
    if (field === '模型名称' && providerPage.value)
        return modelProviders[String(editing.value?.模型提供商)]?.models || [];
    if (field === '模型配置')
        return modelConfigCatalog.value.map(x => String(x.id));
    if (field === '数据源配置')
        return datasourceConfigCatalog.value.map(x => String(x.id));
    if (field === '角色' || field === '用户角色')
        return ['总行行长', '分行行长', '业务负责人'];
    if (field === '管理员角色')
        return ['超级管理员', '配置管理员', '审计管理员'];
    if (field === '菜单权限' || field === '菜单/功能')
        return ['管理首页', '后台权限', '用户权限', '数据字典', '流程配置', '场景管理', '查询日志', '安全管控', '系统运维', '模型配置', '数据源配置', '演示管理'];
    if (field === '操作权限')
        return ['查看', '新增', '编辑', '删除', '导入', '导出', '发布', '启用/停用', '诊断', '重置'];
    if (field === '可用场景')
        return Array.from({ length: 8 }, (_, i) => `场景${i + 1}`);
    if (field === '可访问驾驶舱')
        return ['总行行长经营驾驶舱', '分行行长经营驾驶舱', '业务负责人专项驾驶舱'];
    if (field === '适用角色')
        return ['admin', 'beijing', 'retail'];
    if (field === '可用模式')
        return ['PHASE1_DEMO', 'PHASE2_DEMO', 'PHASE2_POC'];
    if (field === '必填参数')
        return ['机构', '时间', '指标', '维度'];
    if (field === '意图规则')
        return ['基础取数', '驾驶舱跳转', '模糊推荐', '同比归因', '权限拦截', '多轮追问', '参数补全', '二次归因'];
    if (field === '默认指标')
        return metricCatalog.value.map(x => String(x.id));
    if (field === 'SQL模板')
        return ['single-period', 'attribution', 'NONE'];
    if (field === 'L7输出模板')
        return ['answer-single', 'answer-comparison', 'answer-empty', 'NONE'];
    if (field === '图表配置')
        return ['l7-default-chart', 'NONE'];
    if (field === '降级策略')
        return ['演示允许Fixture', '禁止降级', '语义层短路', '权限层拦截', '等待用户补参'];
    if (['接收人', '白名单'].includes(field))
        return ['admin', 'beijing', 'retail'];
    if (field === '机构权限池')
        return ['全行', '北京分行', '上海分行'];
    if (field === '指标权限池')
        return ['贷款投放', '零售贷款', '对公贷款'];
    if (field === '功能权限')
        return ['query', 'dashboard', 'attribution', 'export', 'admin'];
    if (field === '成员/周期')
        return active.value === 'dimensions' ? ['全行', '北京分行', '上海分行', '月', '季', '年', '同比', '环比'] : [];
    if (field === '类型') {
        if (active.value === 'client-roles')
            return ['总行全权限', '分行专属', '专项条线'];
        if (active.value === 'dimensions')
            return ['机构维度', '时间维度', '指标维度', '客户维度'];
        if (active.value === 'sql-templates')
            return ['SELECT', '同比', '归因', '多机构'];
        if (['warehouse-assets', 'source-connect'].includes(active.value))
            return ['SQLITE', 'CLICKHOUSE', 'MYSQL'];
    }
    if (field === '权限类型')
        return ['菜单权限', '操作权限', '数据权限'];
    if (field === '数据源')
        return sourceCatalog.value.map(x => String(x.id));
    if (field === '数据表' || field === '表名')
        return tableCatalog.value.filter(x => !editing.value?.数据源 || x.source === editing.value?.数据源).map(x => String(x.name));
    if (field === '数据源/表')
        return tableCatalog.value.map(x => `${x.source}/${x.name}`);
    if (['标准指标', '关联指标'].includes(field))
        return metricCatalog.value.map(x => String(x.id));
    if (['物理字段', '同期字段', '分项字段'].includes(field))
        return ['org_name', 'stat_dt', 'loan_cur', 'loan_last', 'retail_cur', 'retail_last', 'corporate_cur', 'corporate_last'];
    if (field === '场景')
        return Array.from({ length: 8 }, (_, i) => `scenario-${i + 1}`);
    if (field === '场景ID')
        return Array.from({ length: 11 }, (_, i) => `scenario-${i + 1}`);
    if (field === '意图模板')
        return ['基础取数', '同比归因', '驾驶舱跳转', '模糊查询', '参数补全', '权限拦截'];
    return optionMap[field] || [];
}
function isMulti(field) { return multiFields.has(field) || (field === '角色' && multiRolePages.has(active.value)); }
function newModel() { return { id: 'model-' + Date.now(), 配置名称: '', 模型提供商: 'Google Gemini', 模型接口地址: modelProviders['Google Gemini'].baseUrl, 模型名称: modelProviders['Google Gemini'].models[0], 模型温度: .2, '模型Top P': .9, 模型最大Token: 2048, 模型上下文窗口: 32768, 模型结构化输出: '是', 模型系统Prompt: '根据银行问数任务返回严格JSON。', 超时秒: 30, 重试次数: 2, 最大并发数: 4 }; }
function newDatasource() { return { id: 'source-' + Date.now(), 配置名称: '', 数据源类型: 'CLICKHOUSE', 数据源HTTP地址: 'https://', 数据源主机: '', 数据源端口: 3306, 启用TLS: '是', 数据源用户名: '', 数据源密码: '', 数据库: 'default', 允许访问表: ['dws_loan_aggr_wide'], 数据源只读: '是', 数据源字符集: 'utf8mb4', 连接池大小: 5, Schema同步: '是', 最大返回行数: 1000, 最大时间范围天数: 366, 超时秒: 30, 重试次数: 2, 最大并发数: 4 }; }
const sceneBindingNames = ['基础查数', 'BI驾驶舱跳转', '模糊问句推荐', '同比归因分析', '越权权限拦截', '多轮上下文追问', '缺失参数补全', '二次归因会话', '客户画像分析（规划）', '风险预警归因（规划）', '经营趋势预测（规划）'];
const sceneBindings = sceneBindingNames.map((场景名称, i) => { const active = i < 8, short = i === 1 || i === 2 || i === 4 || i === 6; return { id: `scene-binding-${i + 1}`, 场景ID: `scenario-${i + 1}`, 场景名称, 适用角色: 'admin,beijing,retail', 可用模式: 'PHASE1_DEMO,PHASE2_DEMO,PHASE2_POC', 意图规则: ['基础取数', '驾驶舱跳转', '模糊推荐', '同比归因', '权限拦截', '多轮追问', '参数补全', '二次归因', '客户画像', '风险预警', '趋势预测'][i], 必填参数: short ? '无' : '机构,时间,指标', 默认指标: i === 1 ? 'NONE' : 'loan_cur', 数据源: short ? 'NONE' : 'clickhouse-poc', 数据表: short ? 'NONE' : 'dws_loan_aggr_wide', SQL模板: short ? 'NONE' : i === 3 || i === 7 ? 'attribution' : 'single-period', 终止层: i === 1 ? 'L3' : i === 2 || i === 4 || i === 6 ? 'L2' : 'L7', L7输出模板: short ? 'NONE' : i === 3 || i === 7 ? 'answer-comparison' : 'answer-single', 图表配置: short ? 'NONE' : 'l7-default-chart', 降级策略: i === 1 ? '语义层短路' : i === 4 ? '权限层拦截' : i === 6 ? '等待用户补参' : active ? '演示允许Fixture' : '禁止降级', 状态: active ? '启用' : '停用' }; });
const seeds = {
    'scene-parameter-bindings': sceneBindings,
    'admin-roles': [{ id: 'super-admin', 角色名称: '超级管理员', 角色编码: 'SUPER_ADMIN', 菜单权限: '管理首页,后台权限,用户权限,数据字典,流程配置,场景管理,查询日志,安全管控,系统运维,模型配置,数据源配置,演示管理', 操作权限: '查看,新增,编辑,删除,导入,导出,发布,启用/停用,诊断,重置', 数据管理范围: '全平台', 状态: '启用' }, { id: 'audit-admin', 角色名称: '审计管理员', 角色编码: 'AUDIT_ADMIN', 菜单权限: '查询日志,安全管控', 操作权限: '查看,导出', 数据管理范围: '审计数据', 状态: '启用' }],
    'administrators': [{ id: 'admin', 管理员账号: 'admin', 姓名: '系统管理员', 管理员角色: '超级管理员', 手机号: '138****0000', 邮箱: 'admin@example.local', 最近登录: '2026-08-07 09:00:00', 状态: '启用' }],
    'admin-permissions': [{ id: 'permission-config', 权限名称: '配置管理', 权限编码: 'CONFIG_MANAGE', 权限类型: '菜单权限', '菜单/功能': '数据字典,流程配置,场景管理,模型配置,数据源配置', 操作权限: '查看,新增,编辑,删除,发布', 状态: '启用' }],
    'client-users': [{ id: 'zhang-president', 用户姓名: '张总', 登录账号: 'zhang.zong', 用户角色: '总行行长', 所属机构: '总行', 职务: '总行行长', 手机号: '138****0001', 状态: '启用' }, { id: 'li-president', 用户姓名: '李总', 登录账号: 'li.zong', 用户角色: '分行行长', 所属机构: '北京分行', 职务: '分行行长', 手机号: '138****0002', 状态: '启用' }, { id: 'wang-owner', 用户姓名: '王总', 登录账号: 'wang.zong', 用户角色: '业务负责人', 所属机构: '零售信贷部', 职务: '零售信贷业务负责人', 手机号: '138****0003', 状态: '启用' }],
    'client-permissions': [{ id: 'rights-head', 权限名称: '总行行长权限', 用户角色: '总行行长', 机构权限: '全行,北京分行,上海分行', 指标权限: '全部', 可用场景: '场景1,场景2,场景3,场景4,场景5,场景6,场景7,场景8', 可访问驾驶舱: '总行行长经营驾驶舱', 明细权限: '允许（脱敏）', 导出权限: '允许', 状态: '启用' }, { id: 'rights-branch', 权限名称: '分行行长权限', 用户角色: '分行行长', 机构权限: '北京分行', 指标权限: '贷款投放,零售贷款,对公贷款', 可用场景: '场景1,场景2,场景3,场景4,场景5,场景6,场景7,场景8', 可访问驾驶舱: '分行行长经营驾驶舱', 明细权限: '不允许', 导出权限: '允许本机构', 状态: '启用' }, { id: 'rights-owner', 权限名称: '业务负责人权限', 用户角色: '业务负责人', 机构权限: '全行,北京分行,上海分行', 指标权限: '零售贷款', 可用场景: '场景1,场景2,场景3,场景4,场景5,场景6,场景7,场景8', 可访问驾驶舱: '业务负责人专项驾驶舱', 明细权限: '不允许', 导出权限: '允许本业务', 状态: '启用' }],
    'permission-priority': ['非法闲聊', '涉密指标', '跨机构', '无权限指标', '正常查询'].map((规则, i) => ({ id: 'priority-' + (i + 1), 规则, 优先级: i + 1, 动作: i === 4 ? '放行' : 'L2拦截', 状态: '启用' })),
    'metrics': [{ id: 'loan_cur', 指标名称: '贷款投放', 英文标识: 'loan_cur', 业务口径: '贷款投放金额合计', 单位: '万元', 分类: '信贷', 数据源: 'sqlite', 数据表: 'dws_loan_aggr_wide', 可访问角色: 'admin,beijing', 状态: '启用' }, { id: 'retail_cur', 指标名称: '零售贷款', 英文标识: 'retail_cur', 业务口径: '零售贷款投放金额', 单位: '万元', 分类: '零售信贷', 数据源: 'sqlite', 数据表: 'dws_loan_aggr_wide', 可访问角色: 'admin,beijing,retail', 状态: '启用' }, { id: 'corporate_cur', 指标名称: '对公贷款', 英文标识: 'corporate_cur', 业务口径: '对公贷款投放金额', 单位: '万元', 分类: '对公信贷', 数据源: 'sqlite', 数据表: 'dws_loan_aggr_wide', 可访问角色: 'admin,beijing', 状态: '启用' }, { id: 'deposit_balance', 指标名称: '存款余额', 英文标识: 'deposit_balance', 业务口径: '期末各项存款余额', 单位: '万元', 分类: '存款', 数据源: 'clickhouse-poc', 数据表: 'dws_loan_aggr_wide', 可访问角色: 'admin', 状态: '停用' }, { id: 'customer_count', 指标名称: '客户数量', 英文标识: 'customer_count', 业务口径: '期末有效客户数量', 单位: '户', 分类: '客户', 数据源: 'clickhouse-poc', 数据表: 'dwd_loan_detail', 可访问角色: 'admin,beijing', 状态: '停用' }, { id: 'nonperforming_rate', 指标名称: '不良贷款率', 英文标识: 'nonperforming_rate', 业务口径: '不良贷款余额占贷款余额比例', 单位: '%', 分类: '经营分析', 数据源: 'clickhouse-poc', 数据表: 'dws_loan_aggr_wide', 可访问角色: 'admin', 状态: '停用' }, { id: 'interest_income', 指标名称: '利息收入', 英文标识: 'interest_income', 业务口径: '报告期贷款利息收入', 单位: '万元', 分类: '经营分析', 数据源: 'clickhouse-poc', 数据表: 'dws_loan_aggr_wide', 可访问角色: 'admin,beijing', 状态: '停用' }, { id: 'loan_customer_avg', 指标名称: '户均贷款', 英文标识: 'loan_customer_avg', 业务口径: '贷款余额除以贷款客户数', 单位: '万元', 分类: '经营分析', 数据源: 'clickhouse-poc', 数据表: 'dwd_loan_detail', 可访问角色: 'admin', 状态: '停用' }],
    'dimensions': [{ id: 'org', 维度名称: '机构', 类型: '机构维度', '成员/周期': '全行,北京分行,上海分行', 数据源: 'sqlite', 数据表: 'dws_loan_aggr_wide', 物理字段: 'org_name', 状态: '启用' }, { id: 'date', 维度名称: '统计时间', 类型: '时间维度', '成员/周期': '月,季,年,同比', 数据源: 'sqlite', 数据表: 'dws_loan_aggr_wide', 物理字段: 'stat_dt', 状态: '启用' }, { id: 'customer-type', 维度名称: '客户类型', 类型: '客户维度', '成员/周期': '个人客户,企业客户', 数据源: 'clickhouse-poc', 数据表: 'dwd_loan_detail', 物理字段: 'customer_type', 状态: '停用' }, { id: 'product-type', 维度名称: '产品类型', 类型: '指标维度', '成员/周期': '零售贷款,对公贷款', 数据源: 'clickhouse-poc', 数据表: 'dwd_loan_detail', 物理字段: 'product_type', 状态: '停用' }, { id: 'risk-level', 维度名称: '风险等级', 类型: '客户维度', '成员/周期': '低风险,中风险,高风险', 数据源: 'clickhouse-poc', 数据表: 'dwd_loan_detail', 物理字段: 'risk_level', 状态: '停用' }],
    'warehouse-assets': [{ id: 'wide-table', 名称: '贷款指标宽表', 数据源: 'sqlite', 类型: 'SQLITE', 库名: 'default', 表名: 'dws_loan_aggr_wide', 优先级: 1, 状态: '启用' }, { id: 'poc-wide-table', 名称: 'POC贷款宽表', 数据源: 'clickhouse-poc', 类型: 'CLICKHOUSE', 库名: 'askdata_poc', 表名: 'dws_loan_aggr_wide', 优先级: 2, 状态: '启用' }, { id: 'poc-detail-table', 名称: '贷款业务明细', 数据源: 'clickhouse-poc', 类型: 'CLICKHOUSE', 库名: 'askdata_poc', 表名: 'dwd_loan_detail', 优先级: 3, 状态: '停用' }],
    'field-mappings': [{ id: 'map-loan', 数据源: 'sqlite', 数据表: 'dws_loan_aggr_wide', 标准指标: 'loan_cur', 物理字段: 'loan_cur', 同期字段: 'loan_last', 分项字段: 'retail_cur,corporate_cur', 状态: '启用' }, { id: 'map-retail', 数据源: 'sqlite', 数据表: 'dws_loan_aggr_wide', 标准指标: 'retail_cur', 物理字段: 'retail_cur', 同期字段: 'retail_last', 分项字段: '', 状态: '启用' }, { id: 'map-corporate', 数据源: 'sqlite', 数据表: 'dws_loan_aggr_wide', 标准指标: 'corporate_cur', 物理字段: 'corporate_cur', 同期字段: 'corporate_last', 分项字段: '', 状态: '启用' }, { id: 'map-deposit', 数据源: 'clickhouse-poc', 数据表: 'dws_loan_aggr_wide', 标准指标: 'deposit_balance', 物理字段: 'deposit_balance', 同期字段: 'deposit_last', 分项字段: '', 状态: '停用' }],
    'recommendations': [{ id: 'rec-admin', 角色: 'admin', 关键词: '贷款数据', 标准指标: '贷款投放', 推荐问句: '查询2026年3月全行贷款投放金额', 状态: '启用' }, { id: 'rec-retail', 角色: 'retail', 关键词: '零售投放', 标准指标: '零售贷款', 推荐问句: '查询2026年3月零售贷款投放金额', 状态: '启用' }, { id: 'rec-branch', 角色: 'beijing', 关键词: '分行贷款', 标准指标: '贷款投放', 推荐问句: '查询2026年3月北京分行贷款投放金额', 状态: '启用' }, { id: 'rec-risk', 角色: 'admin', 关键词: '资产质量', 标准指标: '不良贷款率', 推荐问句: '查询全行不良贷款率变化', 状态: '停用' }],
    'intent-rules': ['基础取数', '同比归因', '驾驶舱跳转', '模糊查询', '参数补全', '权限拦截'].map((模板名称, i) => ({ id: 'intent-' + (i + 1), 模板名称, 触发关键词: ['多少|金额', '同比|归因', '大盘|驾驶舱', '相关数据', '缺少参数', '涉密|明细'][i], 终止层: [7, 7, 3, 2, 2, 2][i], 优先级: i + 1, 状态: '启用' })),
    'sql-templates': [{ id: 'single-period', 模板名称: '单期取数模板', 类型: 'SELECT', SQL模板: 'SELECT org_name,stat_dt,{metric} FROM dws_loan_aggr_wide WHERE org_name=:org AND stat_dt=:date', 行数上限: 200, 超时秒: 30, 语法校验: '开启', 状态: '启用' }, { id: 'year-on-year', 模板名称: '同比查询模板', 类型: '同比', SQL模板: 'SELECT org_name,{metric},{metric_last} FROM dws_loan_aggr_wide WHERE org_name=:org AND stat_dt=:date', 行数上限: 200, 超时秒: 30, 语法校验: '开启', 状态: '启用' }, { id: 'multi-org', 模板名称: '多机构对比模板', 类型: '多机构', SQL模板: 'SELECT org_name,{metric} FROM dws_loan_aggr_wide WHERE org_name IN (:orgs) AND stat_dt=:date ORDER BY {metric} DESC', 行数上限: 200, 超时秒: 30, 语法校验: '开启', 状态: '启用' }, { id: 'attribution', 模板名称: '指标归因模板', 类型: '归因', SQL模板: 'SELECT org_name,retail_cur,corporate_cur FROM dws_loan_aggr_wide WHERE org_name=:org AND stat_dt=:date', 行数上限: 200, 超时秒: 30, 语法校验: '开启', 状态: '启用' }, { id: 'detail-drill', 模板名称: '贷款明细下钻', 类型: 'SELECT', SQL模板: 'SELECT loan_id,org_name,customer_type,loan_amount FROM dwd_loan_detail WHERE org_name=:org AND stat_dt=:date LIMIT :limit', 行数上限: 100, 超时秒: 20, 语法校验: '开启', 状态: '停用' }],
    'conversation': [{ id: 'context-ttl', 配置项: '上下文缓存时效', 值: '30', 说明: '分钟', 状态: '启用' }, { id: 'role-clear', 配置项: '角色切换清空', 值: 'true', 说明: '防止越权上下文继承', 状态: '启用' }],
    'parameter-rules': [{ id: 'date-required', 参数: '时间', 是否必填: '是', 校验规则: 'YYYY年MM月', 缺失提示: '请补充查询时间', 可选值: '月/季/年', 状态: '启用' }],
    'quick-buttons': [{ id: 'quick-1', 按钮名称: '贷款投放', 场景ID: 'scenario-1', 预设问句: '2026年3月全行贷款投放金额', 标签: '基础查数', 排序: 1, 角色: 'admin', 状态: '启用' }],
    'dashboards': [{ id: 'dashboard-head-office', 名称: '总行行长经营驾驶舱', URL: '/dashboards/head-office.html', 角色: 'admin', 标签: '全行经营决策', 状态: '启用' }, { id: 'dashboard-branch', 名称: '分行行长经营驾驶舱', URL: '/dashboards/branch-president.html', 角色: 'beijing', 标签: '分行经营管理', 状态: '启用' }, { id: 'dashboard-business', 名称: '业务负责人专项驾驶舱', URL: '/dashboards/business-owner.html', 角色: 'retail', 标签: '零售信贷专项', 状态: '启用' }],
    'classified': [{ id: 'secret-detail', 名称: '客户明细', 对象类型: '指标', 对象值: '身份证|手机号|明细', 白名单: 'admin', 拦截动作: 'L2强制拦截', 状态: '启用' }],
    'rate-limits': [{ id: 'user-minute', 名称: '单用户限流', 范围: '全部用户', 每分钟次数: 30, 行数限制: 200, 高频动作: '拦截并告警', 状态: '启用' }],
    'masking': [{ id: 'id-mask', 字段: '身份证', 角色: 'beijing,retail', 脱敏等级: '高', 规则: '前3后4', 状态: '启用' }],
    'intercept-wording': [{ id: 'no-permission', 原因: '权限不足', 提示文案: '当前角色无权查询该机构或指标', 语言: 'zh-CN', 状态: '启用' }],
    'ui-config': [{ id: 'page-title', 配置项: '页面标题', 值: '智能银行问数平台', 说明: '用户端标题', 状态: '启用' }, { id: 'trace-open', 配置项: '七层轨迹默认展开', 值: 'true', 说明: 'POC技术详情', 状态: '启用' }],
    'interaction': [{ id: 'recommend-tag', 配置项: '推荐标签显示', 值: 'true', 样式: '默认蓝色', 状态: '启用' }],
    'scheduled-jobs': [{ id: 'cleanup', 任务名称: '过期日志清理', Cron: '0 2 * * *', 动作: '清理', 保留天数: 90, 状态: '停用' }],
    'system-params': [{ id: 'sql-timeout', 参数名: 'SQL最大执行时长', 值: 30, 单位: '秒', 说明: '只读查询超时', 状态: '启用' }],
    'runtime-policy': [{ id: 'phase1-demo-policy', 模式: 'PHASE1_DEMO', 允许Fixture降级: '是', 允许参数默认值: '是', 强制真实模型: '否', 强制真实数据源: '否', 执行间隔毫秒: 120, 状态: '启用' }, { id: 'phase2-demo-policy', 模式: 'PHASE2_DEMO', 允许Fixture降级: '是', 允许参数默认值: '是', 强制真实模型: '是', 强制真实数据源: '是', 执行间隔毫秒: 120, 状态: '启用' }, { id: 'phase2-poc-policy', 模式: 'PHASE2_POC', 允许Fixture降级: '否', 允许参数默认值: '否', 强制真实模型: '是', 强制真实数据源: '是', 执行间隔毫秒: 0, 状态: '启用' }],
    'answer-templates': [{ id: 'answer-empty', 模板名称: '无数据结果', 模板类型: '无数据', 模板内容: '查询已完成。', 状态: '启用' }, { id: 'answer-single', 模板名称: '单期结果', 模板类型: '单期查询', 模板内容: '{org}在 {date} 的查询结果为 {current:.2f}。', 状态: '启用' }, { id: 'answer-comparison', 模板名称: '同比结果', 模板类型: '同比查询', 模板内容: '{org}本期为 {current:.2f}，上期为 {previous:.2f}，同比 {rate:.2f}%。', 状态: '启用' }, { id: 'answer-attribution', 模板名称: '归因补充', 模板类型: '归因后缀', 模板内容: ' 主要受阶段性放款节奏影响。', 状态: '启用' }],
    'output-visualization': [{ id: 'l7-default-chart', 图表类型: 'bar', 图表标题: '经营指标查询结果', 分类字段: 'org_name', 数值字段: 'current_value,previous_value', 引导提示: '查看该指标的同比变化,按机构对比该指标,打开当前角色经营驾驶舱', 状态: '启用' }],
    'alerts': [{ id: 'source-down', 告警名称: '数据源断连', 条件: '健康检查失败', 渠道: '内部消息', 接收人: 'admin', 状态: '启用' }],
    'model-connect': [{ id: 'mock-model', 配置名称: '一期内置模型', 模型提供商: '内置模拟', 模型名称: '一期Mock Model', 接口地址: '本地Fixture', 模型版本: 'deterministic-v1', 温度: 0, 'Top P': 1, 最大Token: 2048, 上下文窗口: 32768, 结构化输出: '是', 超时秒: 30, 连接状态: '正常', 状态: 'READY' }, { id: 'phase2-model', 配置名称: '二期模型模板', 模型提供商: 'OpenAI兼容', 模型名称: '多厂商可选', 接口地址: '通过独立模型配置', 模型版本: '由配置设置', 温度: .2, 'Top P': .9, 最大Token: 2048, 上下文窗口: 32768, 结构化输出: '是', 超时秒: 30, 连接状态: '待诊断', 状态: '待配置' }],
    'model-capabilities': [{ id: 'l2-understanding', 配置项: '对话理解与参数提取', 任务层级: 'L2', 启用能力: '结构化理解', Prompt模板: '你是银行经营问数语义解析器。根据问题、角色权限和会话上下文，仅返回JSON；识别intent、org、date、metric，不得编造无权限参数。', 输出约束: 'JSON对象；参数缺失时返回missing_parameters', 状态: '启用' }, { id: 'l7-interpretation', 配置项: '结果解读与引导', 任务层级: 'L7', 启用能力: '结果解读,同比归因,问题推荐', Prompt模板: '你是银行经营分析助手。基于实际查询数据生成简洁中文结论，突出本期、同期、变化率和异常点；禁止修改数值，仅返回JSON。', 输出约束: 'answer、highlights、guides字段', 状态: '启用' }, { id: 'output-risk', 配置项: '输出安全控制', 任务层级: '通用', 启用能力: '输出安全', Prompt模板: '识别敏感字段并遵循角色脱敏和明细权限，不输出未授权信息。', 输出约束: '不得泄露姓名、证件号、手机号原文', 状态: '启用' }],
    'model-limits': [{ id: 'model-rate', 范围: '单用户', 每分钟次数: 10, 每日次数: 500, 状态: '启用' }],
    'source-connect': [{ id: 'sqlite', 名称: '一期模拟数仓', 类型: 'SQLITE', 环境: '演示', '地址/库名': 'mock_warehouse.db', 关联数据表: 'dws_loan_aggr_wide', 表数量: 1, 只读模式: '是', 字符集: 'UTF-8', 连接池: 5, Schema同步: '是', 最大行数: 1000, 查询超时: 30, 连接状态: '正常', 状态: 'READY' }, { id: 'clickhouse-poc', 名称: '本地POC业务库', 类型: 'CLICKHOUSE', 环境: 'POC', '地址/库名': 'http://127.0.0.1:8123/askdata_poc', 关联数据表: 'dws_loan_aggr_wide,dwd_loan_detail', 表数量: 2, 只读模式: '是', 字符集: 'UTF-8', 连接池: 5, Schema同步: '是', 最大行数: 1000, 查询超时: 30, 连接状态: '正常', 状态: 'READY' }],
    'source-tables': [{ id: 'loan-wide', 数据源: 'sqlite', '库/Schema': 'main', 表名: 'dws_loan_aggr_wide', 表类型: '指标宽表', 时间字段: 'stat_dt', 机构字段: 'org_name', 主键字段: 'stat_dt,org_name', 关联指标: 'loan_cur,retail_cur,corporate_cur', 可查询角色: 'admin,beijing,retail', 状态: '启用' }, { id: 'clickhouse-loan-wide', 数据源: 'clickhouse-poc', '库/Schema': 'askdata_poc', 表名: 'dws_loan_aggr_wide', 表类型: '指标宽表', 时间字段: 'stat_dt', 机构字段: 'org_name', 主键字段: 'stat_dt,org_name', 关联指标: 'loan_cur,retail_cur,corporate_cur', 可查询角色: 'admin,beijing,retail', 状态: '启用' }, { id: 'clickhouse-loan-detail', 数据源: 'clickhouse-poc', '库/Schema': 'askdata_poc', 表名: 'dwd_loan_detail', 表类型: '业务明细表', 时间字段: 'stat_dt', 机构字段: 'org_name', 主键字段: 'loan_id', 关联指标: 'loan_cur,retail_cur,corporate_cur', 可查询角色: 'admin', 状态: '启用' }],
    'source-security': [{ id: 'wide-security', '数据源/表': 'sqlite/dws_loan_aggr_wide', 角色: 'admin,beijing,retail', 涉密隔离: '开启', 字段脱敏: '开启', 缓存: '关闭', 状态: '启用' }, { id: 'clickhouse-wide-security', '数据源/表': 'clickhouse-poc/dws_loan_aggr_wide', 角色: 'admin,beijing,retail', 涉密隔离: '开启', 字段脱敏: '开启', 缓存: '关闭', 状态: '启用' }, { id: 'clickhouse-detail-security', '数据源/表': 'clickhouse-poc/dwd_loan_detail', 角色: 'admin', 涉密隔离: '开启', 字段脱敏: '开启', 缓存: '关闭', 状态: '启用' }],
    'mock-scenes': [{ id: 'mock-s1', 场景: 'scenario-1', 角色: 'admin', 输入问句: '2026年3月上海分行对公贷款投放金额', 返回数据: 'SQLite确定性结果', 话术: '基础查数', SQL: '参数化模板', 覆盖配置JSON: '{"system":{"simulation_speed":60}}', 状态: '启用' }],
    'demo-switches': [{ id: 'fixture-fallback', 开关名称: '演示Fixture降级', 配置键: 'fixture_fallback', 值: 'true', 说明: '仅PHASE1/PHASE2_DEMO', 状态: '启用' }],
    'mock-wording': [{ id: 'welcome', 名称: '欢迎语', 场景: '首页', 内容: '今天想了解什么经营数据？', 状态: '启用' }]
};
const demoLogSeeds = {
    'model-logs': [
        { id: 'ML-20260807-001', request_id: 'REQ-DEMO-001', operator_id: 'zhangzong', role_id: 'admin', scenario_id: 'scenario-1', layer_code: 'L2', model_provider: '内置模拟', model: '一期Mock Model', mode: 'PHASE1_DEMO', status: 'SUCCEEDED', elapsed_ms: 86, error_code: '', created_at: '2026-08-07T09:18:12Z' },
        { id: 'ML-20260807-002', request_id: 'REQ-POC-002', operator_id: 'lizong', role_id: 'beijing', scenario_id: 'scenario-4', layer_code: 'L7', model_provider: 'Google Gemini', model: 'gemini-3.1-pro-preview', mode: 'PHASE2_POC', status: 'SUCCEEDED', elapsed_ms: 742, error_code: '', created_at: '2026-08-07T09:26:35Z' },
        { id: 'ML-20260807-003', request_id: 'REQ-POC-003', operator_id: 'wangzong', role_id: 'retail', scenario_id: 'scenario-7', layer_code: 'L2', model_provider: 'DeepSeek', model: 'deepseek-chat', mode: 'PHASE2_POC', status: 'FAILED', elapsed_ms: 30002, error_code: 'MODEL_TIMEOUT', created_at: '2026-08-07T09:41:08Z' }
    ],
    'source-monitor': [
        { id: 'DS-20260807-001', request_id: 'REQ-DEMO-001', operator_id: 'zhangzong', role_id: 'admin', scenario_id: 'scenario-1', source: '一期模拟数仓', mode: 'PHASE1_DEMO', status: 'SUCCEEDED', row_count: 3, elapsed_ms: 12, fallback: 0, error: '', created_at: '2026-08-07T09:18:13Z' },
        { id: 'DS-20260807-002', request_id: 'REQ-POC-002', operator_id: 'lizong', role_id: 'beijing', scenario_id: 'scenario-4', source: '本地POC业务库', mode: 'PHASE2_POC', status: 'SUCCEEDED', row_count: 8, elapsed_ms: 44, fallback: 0, error: '', created_at: '2026-08-07T09:26:36Z' },
        { id: 'DS-20260807-003', request_id: 'REQ-POC-003', operator_id: 'wangzong', role_id: 'retail', scenario_id: 'scenario-7', source: '本地POC业务库', mode: 'PHASE2_POC', status: 'FAILED', row_count: 0, elapsed_ms: 30000, fallback: 0, error: '查询超时，已终止执行', created_at: '2026-08-07T09:41:39Z' }
    ]
};
for (const item of demoLogSeeds['model-logs']) {
    item.__demo = true;
    item.__detail = { model_call: { ...item, question: '演示日志：经营指标查询', input: { intent: 'metric_query', authorized: true }, output: item.status === 'SUCCEEDED' ? { answer: '模型调用完成，结构化结果已返回。' } : {}, error: item.error_code || null } };
}
for (const item of demoLogSeeds['source-monitor']) {
    item.__demo = true;
    item.__detail = { sql: { ...item, business_sql: 'SELECT stat_dt, org_name, loan_cur FROM dws_loan_aggr_wide WHERE stat_dt = :stat_dt', actual_sql: 'SELECT stat_dt, org_name, loan_cur FROM dws_loan_aggr_wide WHERE stat_dt = ?', parameters: { stat_dt: '2026-03-31' } } };
}
function toggle(g) { if (!g.children)
    return open({ id: g.id, label: g.label }); expanded.value = expanded.value.has(g.id) ? new Set() : new Set([g.id]); }
async function open(x) { active.value = x.id; const owner = menus.find(g => g.children?.some(c => c.id === x.id)); expanded.value = owner ? new Set([owner.id]) : new Set(); if (!tabs.value.some(t => t.id === x.id))
    tabs.value.push(x); editing.value = null; logDetailData.value = null; search.value = ''; resetLogFilters(); await load(); }
function close(id) { if (id === 'home')
    return; tabs.value = tabs.value.filter(x => x.id !== id); if (active.value === id)
    open(tabs.value.at(-1)); }
const unpack = (x) => x.payload ? { id: x.id, ...x.payload } : x;
function normalizeRow(row) { const r = { ...row }; if (r['成员/周期'] == null && r.成员周期 != null)
    r['成员/周期'] = r.成员周期; if (r['地址/库名'] == null && r.地址库名 != null)
    r['地址/库名'] = r.地址库名; if (r['数据源/表'] == null && r.数据源表 != null)
    r['数据源/表'] = r.数据源表; if (['metrics', 'dimensions', 'warehouse-assets', 'field-mappings'].includes(String(r.__page || active.value))) {
    r.数据源 ||= 'sqlite';
    if (r.数据表 == null && r.表名 == null)
        r.数据表 = 'dws_loan_aggr_wide';
} return r; }
async function refreshCatalogs() {
    const sources = [{ id: 'sqlite', name: '一期模拟数仓', type: 'SQLITE' }, { id: 'clickhouse-poc', name: '本地POC业务库', type: 'CLICKHOUSE' }], tables = [{ source: 'sqlite', name: 'dws_loan_aggr_wide' }, { source: 'clickhouse-poc', name: 'dws_loan_aggr_wide' }, { source: 'clickhouse-poc', name: 'dwd_loan_detail' }], metrics = (seeds.metrics || []).map(x => ({ id: x.id, name: x.指标名称 }));
    try {
        const savedSources = (await adminApi.resources('datasources')).items.map(unpack);
        for (const x of savedSources) {
            if (x.__page === 'source-connect')
                sources.push({ id: x.id, name: x.名称, type: x.类型 });
            if (x.__page === 'source-tables')
                tables.push({ source: x.数据源, name: x.表名 });
        }
        const savedAssets = (await adminApi.resources('assets')).items.map(unpack);
        for (const x of savedAssets)
            if (x.__page === 'metrics')
                metrics.push({ id: x.id, name: x.指标名称 });
        if (!isOffline) {
            for (const x of (await adminApi.phase2Profiles()).items) {
                sources.push({ id: x.id, name: x.name, type: x.datasource_type });
                for (const name of x.public_config?.allowed_tables || [])
                    tables.push({ source: x.id, name });
            }
        }
    }
    catch { }
    sourceCatalog.value = Array.from(new Map(sources.map(x => [String(x.id), x])).values());
    tableCatalog.value = Array.from(new Map(tables.map(x => [`${x.source}/${x.name}`, x])).values());
    metricCatalog.value = Array.from(new Map(metrics.map(x => [String(x.id), x])).values());
}
async function load() {
    busy.value = true;
    message.value = '';
    try {
        if (active.value === 'home') {
            const [requests, audits, profiles, approvals] = await Promise.all([adminApi.logs('requests'), adminApi.logs('audit'), adminApi.phase2Profiles(), adminApi.approvals()]);
            homeRequests.value = requests.items || [];
            homeAudits.value = audits.items || [];
            homeProfiles.value = profiles.items || [];
            homeApprovals.value = approvals.items || [];
            return;
        }
        if (logPage.value) {
            let items = [];
            try {
                items = (await adminApi.logs(active.value)).items || [];
            }
            catch { }
            rows.value = items.length ? items : (demoLogSeeds[active.value] || []);
            return;
        }
        if (modelConfigPage.value) {
            let items = [];
            if (!isOffline)
                try {
                    items = (await adminApi.phase2Models()).items.map((x) => ({ id: x.id, __kind: 'model', 配置名称: x.name, 模型提供商: x.provider, 模型名称: x.public_config.model, 接口地址: x.public_config.base_url, 模型版本: x.public_config.model, 温度: x.public_config.temperature, 'Top P': x.public_config.top_p, 最大Token: x.public_config.max_tokens, 上下文窗口: x.public_config.context_window, 结构化输出: x.public_config.structured_output ? '是' : '否', 超时秒: x.public_config.timeout, 连接状态: x.status === 'ENABLED' ? '已启用/可诊断' : '待启用', 状态: x.status, 凭据: '已加密配置' }));
                }
                catch { }
            if (!items.length && !isOffline)
                try {
                    items = (await adminApi.phase2Profiles()).items.map((x) => ({ id: 'legacy-model-' + x.id, __kind: 'legacy-model', 配置名称: `${x.name}（历史组合）`, 模型提供商: x.public_config.model_provider || x.model_type, 模型名称: x.public_config.model, 接口地址: x.public_config.model_base_url, 模型版本: x.public_config.model, 温度: x.public_config.model_temperature ?? '-', 'Top P': x.public_config.model_top_p ?? '-', 最大Token: x.public_config.model_max_tokens ?? '-', 上下文窗口: x.public_config.model_context_window ?? '-', 结构化输出: x.public_config.model_structured_output ? '是' : '否', 超时秒: x.public_config.timeout, 连接状态: x.selectable ? '诊断正常' : '需重新诊断', 状态: x.status }));
                }
                catch { }
            rows.value = [...(seeds[active.value] || []), ...items];
            return;
        }
        if (datasourceConfigPage.value) {
            let items = [];
            if (!isOffline)
                try {
                    items = (await adminApi.phase2Datasources()).items.map((x) => { const tables = x.public_config.allowed_tables || []; return { id: x.id, __kind: 'datasource', 名称: x.name, 类型: x.type, 环境: 'Phase 2', '地址/库名': x.public_config.url || `${x.public_config.host || ''}:${x.public_config.port}/${x.public_config.database}`, 关联数据表: tables.join(','), 表数量: tables.length, 只读模式: x.public_config.read_only ? '是' : '否', 字符集: x.public_config.charset, 连接池: x.public_config.pool_size, Schema同步: x.public_config.schema_sync ? '是' : '否', 最大行数: x.public_config.max_rows, 查询超时: x.public_config.timeout, 连接状态: x.status === 'ENABLED' ? '已启用/可诊断' : '待启用', 状态: x.status, 凭据: '已加密配置' }; });
                }
                catch { }
            if (!items.length && !isOffline)
                try {
                    items = (await adminApi.phase2Profiles()).items.map((x) => { const tables = x.public_config.allowed_tables || []; return { id: 'legacy-source-' + x.id, __kind: 'legacy-datasource', 名称: `${x.name}（历史组合）`, 类型: x.datasource_type, 环境: 'Phase 2', '地址/库名': x.public_config.datasource_url || `${x.public_config.datasource_host || ''}:${x.public_config.datasource_port || ''}/${x.public_config.database || ''}`, 关联数据表: tables.join(','), 表数量: tables.length, 只读模式: '是', 字符集: x.public_config.datasource_charset || 'UTF-8', 连接池: x.public_config.datasource_pool_size || '-', Schema同步: x.public_config.schema_sync_enabled === false ? '否' : '是', 最大行数: x.public_config.max_rows, 查询超时: x.public_config.timeout, 连接状态: x.selectable ? '诊断正常' : '需重新诊断', 状态: x.status }; });
                }
                catch { }
            rows.value = [...(seeds[active.value] || []), ...items];
            return;
        }
        if (compositionPage.value && !isOffline) {
            const [profiles, models, sources] = await Promise.all([adminApi.phase2Profiles(), adminApi.phase2Models(), adminApi.phase2Datasources()]);
            modelConfigCatalog.value = models.items.filter((x) => x.status === 'ENABLED');
            datasourceConfigCatalog.value = sources.items.filter((x) => x.status === 'ENABLED');
            rows.value = profiles.items.map((x) => ({ id: x.id, 组合名称: x.name, 模型配置: x.public_config?.model_config_id || '历史内嵌配置', 数据源配置: x.public_config?.datasource_config_id || '历史内嵌配置', 状态: `${x.status}/${x.diagnostic_status}`, 凭据: '已加密配置' }));
            return;
        }
        if (active.value === 'mock-data') {
            rows.value = (await adminApi.mockWarehouse()).items.map((x) => ({ id: x.stat_dt + '|' + x.org_name, ...x }));
            return;
        }
        if (active.value === 'client-roles') {
            const saved = (await adminApi.resources('user-access')).items.map(unpack).map(normalizeRow).filter((r) => r.__page === 'client-roles');
            rows.value = saved.length ? saved : (baseline.value.roles || []).map((r) => ({ id: r.id, 角色名称: r.id === 'admin' ? '总行行长' : r.id === 'beijing' ? '分行行长' : '业务负责人', 角色编码: r.id.toUpperCase(), 职责说明: r.id === 'admin' ? '全行经营决策' : r.id === 'beijing' ? '分行经营管理' : '零售信贷业务管理', 机构权限池: r.orgs?.join(','), 指标权限池: r.metrics?.join(','), 功能权益: r.features?.join(','), 状态: '启用' }));
            return;
        }
        if (active.value === 'standard-scenes') {
            rows.value = (baseline.value.scenarios || []).map((s) => ({ id: s.id, 场景名称: s.name, 触发问句: s.cases?.[0]?.turns?.[0]?.question, 意图模板: '场景' + s.number, Mock数据: s.cases?.[0]?.turns?.[0]?.execution, 预设SQL: s.number === 1 || s.number === 4 || s.number === 8 ? '参数化模板' : '无', 状态: '启用' }));
            return;
        }
        if (active.value === 'seven-layers') {
            rows.value = ['交互', '对话理解', '语义', '数据资产', '查询生成', '执行', '问数解读'].map((名称, i) => ({ id: 'L' + (i + 1), 层级: 'L' + (i + 1), 名称, 处理器: 'LayerProcessor', Provider: [1, 6].includes(i) ? 'Mock/真实Model' : '确定性代码', 状态: '启用' }));
            return;
        }
        if (active.value === 'readiness') {
            const runtime = await adminApi.runtimeConfig();
            const providers = Object.entries(ready.value.providers || {}).map(([id, v]) => ({ id: 'provider-' + id, 组件: id, 模式: 'Provider', 状态: v.ready ? 'READY' : 'FAILED', 说明: v.ready ? '连接正常' : '连接异常' }));
            const modes = Object.entries(runtime.checks || {}).map(([mode, v]) => ({ id: 'runtime-' + mode, 组件: 'RuntimeConfig', 模式: mode, 状态: v.ready ? 'READY' : 'FAILED', 说明: v.ready ? '已发布配置完整' : `缺少：${(v.missing || []).join(', ')}` }));
            rows.value = [...providers, ...modes];
            return;
        }
        const saved = (await adminApi.resources(kind.value)).items.map(unpack).map(normalizeRow).filter((r) => r.__page === active.value);
        rows.value = saved.length ? saved : (seeds[active.value] || []).map(normalizeRow);
    }
    catch (e) {
        message.value = String(e);
    }
    finally {
        busy.value = false;
    }
}
function add() { if (modelConfigPage.value) {
    editing.value = newModel();
    return;
} if (datasourceConfigPage.value) {
    editing.value = newDatasource();
    return;
} if (compositionPage.value) {
    editing.value = { id: 'composition-' + Date.now(), 组合名称: '', 模型配置: '', 数据源配置: '' };
    return;
} const r = { id: active.value + '-' + Date.now() }; editing.value = r; current.value?.fields.forEach(f => r[f] = isMulti(f) ? [] : (optionsFor(f)[0] || '')); }
function edit(r) { if (providerPage.value) {
    message.value = r.凭据 ? '安全Profile不回显凭据；如需变更请新增Profile并重新启用' : '一期内置Provider为只读项，请通过“新增”创建Phase 2安全Profile';
    return;
} const value = JSON.parse(JSON.stringify(normalizeRow(r))); for (const f of multiFields)
    if (typeof value[f] === 'string')
        value[f] = value[f].split(',').filter(Boolean); if (multiRolePages.has(active.value) && typeof value.角色 === 'string')
    value.角色 = value.角色.split(',').filter(Boolean); editing.value = value; }
function fieldChanged(field) { if (field === '模型提供商' && editing.value) {
    const preset = modelProviders[String(editing.value.模型提供商)];
    editing.value.模型接口地址 = preset?.baseUrl || 'https://';
    editing.value.模型名称 = preset?.models[0] || '';
} if (field === '数据源' && editing.value && '数据表' in editing.value) {
    const choices = optionsFor('数据表');
    if (!choices.includes(editing.value.数据表))
        editing.value.数据表 = choices[0] || '';
} }
async function saveRow() {
    if (!editing.value?.id)
        return message.value = '资源ID不能为空';
    busy.value = true;
    try {
        if (modelConfigPage.value) {
            const e = editing.value;
            if (!e['模型API Key'])
                throw new Error('模型API Key为必填项');
            await adminApi.createPhase2Model({ name: e.配置名称, provider: modelProviders[String(e.模型提供商)]?.code || 'OPENAI_COMPATIBLE', base_url: e.模型接口地址, model: e.模型名称, api_key: e['模型API Key'], temperature: Number(e.模型温度 ?? .2), top_p: Number(e['模型Top P'] ?? .9), max_tokens: Number(e.模型最大Token || 2048), context_window: Number(e.模型上下文窗口 || 32768), structured_output: e.模型结构化输出 === '是', system_prompt: e.模型系统Prompt || '', timeout: Number(e.超时秒), retries: Number(e.重试次数), max_concurrency: Number(e.最大并发数) });
            editing.value = null;
            message.value = '模型配置已独立保存，API Key已加密';
            await load();
            return;
        }
        if (datasourceConfigPage.value) {
            const e = editing.value;
            if (!e.数据源密码)
                throw new Error('数据源密码为必填项');
            await adminApi.createPhase2Datasource({ name: e.配置名称, type: e.数据源类型, url: e.数据源类型 === 'CLICKHOUSE' ? e.数据源HTTP地址 : null, host: e.数据源类型 === 'MYSQL' ? e.数据源主机 : null, port: Number(e.数据源端口 || 3306), tls: e.启用TLS === '是', username: e.数据源用户名, password: e.数据源密码, database: e.数据库, allowed_tables: Array.isArray(e.允许访问表) ? e.允许访问表 : String(e.允许访问表 || '').split(',').filter(Boolean), read_only: e.数据源只读 === '是', charset: e.数据源字符集 || 'utf8mb4', pool_size: Number(e.连接池大小 || 5), schema_sync: e.Schema同步 === '是', max_rows: Number(e.最大返回行数), max_time_range_days: Number(e.最大时间范围天数), timeout: Number(e.超时秒), retries: Number(e.重试次数), max_concurrency: Number(e.最大并发数) });
            editing.value = null;
            message.value = '数据源配置已独立保存，密码已加密';
            await refreshCatalogs();
            await load();
            return;
        }
        if (compositionPage.value) {
            const e = editing.value;
            await adminApi.composePhase2Profile({ name: e.组合名称, model_config_id: e.模型配置, datasource_config_id: e.数据源配置 });
            editing.value = null;
            message.value = '运行组合已创建，请启用并诊断';
            await load();
            return;
        }
        if (active.value === 'mock-data') {
            await adminApi.saveMockRow(editing.value);
            editing.value = null;
            message.value = 'Mock数据保存成功';
            await load();
            return;
        }
        const { id, ...payload } = editing.value;
        for (const f of multiFields)
            if (Array.isArray(payload[f]))
                payload[f] = payload[f].join(',');
        if (Array.isArray(payload.角色))
            payload.角色 = payload.角色.join(',');
        payload.__page = active.value;
        await adminApi.saveResource(kind.value, String(id), payload, true);
        editing.value = null;
        message.value = '保存成功，操作已审计';
        if (['metrics', 'source-connect', 'source-tables'].includes(active.value))
            await refreshCatalogs();
        await load();
    }
    catch (e) {
        message.value = String(e);
    }
    finally {
        busy.value = false;
    }
}
async function remove(r) { if (!confirm('确认删除 ' + (r.id || r.org_name) + '？'))
    return; try {
    if (active.value === 'mock-data')
        await adminApi.deleteMockRow(r);
    else
        await adminApi.deleteResource(kind.value, String(r.id));
    rows.value = rows.value.filter(x => x.id !== r.id);
    message.value = '删除成功，操作已审计';
}
catch (e) {
    message.value = String(e);
} }
async function enableProfile(id) { message.value = JSON.stringify(await adminApi.enablePhase2Profile(id)); await load(); }
async function enableConnection(id) { message.value = JSON.stringify(modelConfigPage.value ? await adminApi.enablePhase2Model(id) : await adminApi.enablePhase2Datasource(id)); await load(); }
async function diagnoseConnection(id) { message.value = JSON.stringify(modelConfigPage.value ? await adminApi.diagnosePhase2Model(id) : await adminApi.diagnosePhase2Datasource(id)); }
async function diagnoseProfile(id) { message.value = JSON.stringify(await adminApi.diagnosePhase2Profile(id)); }
function duplicate(r) { editing.value = { ...JSON.parse(JSON.stringify(r)), id: r.id + '-copy-' + Date.now() }; }
function exportRows() { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(filtered.value, null, 2)], { type: 'application/json' })); a.download = active.value + '.json'; a.click(); }
async function recovery(scope) { if (scope === 'all' && !confirm('完全重置将恢复官方配置、Mock数据并清理日志，确认继续？'))
    return; message.value = JSON.stringify(scope === 'backup' ? await adminApi.backup() : await adminApi.reset(scope)); }
async function publishResources() { message.value = JSON.stringify(await adminApi.publishResources()); baseline.value = await adminApi.baseline(); }
async function loadVersions() { versions.value = (await adminApi.versions()).items; }
function goPage(next) { page.value = Math.min(totalPages.value, Math.max(1, next)); }
watch([search, active, () => JSON.stringify(logFilters.value)], () => { page.value = 1; });
watch(totalPages, n => { if (page.value > n)
    page.value = n; });
async function rollbackVersion(id) { await adminApi.rollback(id); message.value = '已回滚，仅影响新Session'; await loadVersions(); }
async function importFile(e) { const file = e.target.files?.[0]; if (!file)
    return; const payload = JSON.parse(await file.text()); const d = await adminApi.importConfig(file.name, payload); message.value = '已导入为草稿 ' + d.id; await loadVersions(); }
onMounted(async () => { [baseline.value, ready.value] = await Promise.all([adminApi.baseline(), adminApi.readiness()]); await refreshCatalogs(); await load(); });
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_elements;
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "admin-shell" },
});
__VLS_asFunctionalElement(__VLS_elements.aside, __VLS_elements.aside)({
    ...{ class: "admin-sidebar" },
    ...{ class: ({ collapsed: __VLS_ctx.collapsed }) },
});
// @ts-ignore
[collapsed,];
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "side-logo" },
});
__VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
__VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.collapsed = !__VLS_ctx.collapsed;
            // @ts-ignore
            [collapsed, collapsed,];
        } },
    ...{ class: "collapse" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "menu-list" },
});
for (const [g] of __VLS_getVForSourceType((__VLS_ctx.menus))) {
    // @ts-ignore
    [menus,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        key: (g.id),
        ...{ class: "menu-group" },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.toggle(g);
                // @ts-ignore
                [toggle,];
            } },
        ...{ class: "menu-parent" },
        ...{ class: ({ active: __VLS_ctx.active === g.id || g.children?.some(x => x.id === __VLS_ctx.active) }) },
    });
    // @ts-ignore
    [active, active,];
    __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({});
    (g.icon);
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    (g.label);
    if (g.children) {
        __VLS_asFunctionalElement(__VLS_elements.em, __VLS_elements.em)({});
        (__VLS_ctx.expanded.has(g.id) ? '▼' : '▶');
        // @ts-ignore
        [expanded,];
    }
    if (g.children && __VLS_ctx.expanded.has(g.id)) {
        // @ts-ignore
        [expanded,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "sub-menu" },
        });
        for (const [x] of __VLS_getVForSourceType((g.children))) {
            __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(g.children && __VLS_ctx.expanded.has(g.id)))
                            return;
                        __VLS_ctx.open(x);
                        // @ts-ignore
                        [open,];
                    } },
                key: (x.id),
                ...{ class: ({ active: __VLS_ctx.active === x.id }) },
            });
            // @ts-ignore
            [active,];
            (x.label);
        }
    }
}
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "admin-main" },
});
__VLS_asFunctionalElement(__VLS_elements.header, __VLS_elements.header)({
    ...{ class: "admin-top" },
});
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.router.push('/');
            // @ts-ignore
            [router,];
        } },
});
__VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({
    ...{ class: "mode" },
});
(__VLS_ctx.isOffline ? 'OFFLINE' : 'POC');
// @ts-ignore
[isOffline,];
__VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
__VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "tabs" },
});
for (const [t] of __VLS_getVForSourceType((__VLS_ctx.tabs))) {
    // @ts-ignore
    [tabs,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.open(t);
                // @ts-ignore
                [open,];
            } },
        key: (t.id),
        ...{ class: ({ active: __VLS_ctx.active === t.id }) },
    });
    // @ts-ignore
    [active,];
    (t.label);
    if (t.id !== 'home') {
        __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
            ...{ onClick: (...[$event]) => {
                    if (!(t.id !== 'home'))
                        return;
                    __VLS_ctx.close(t.id);
                    // @ts-ignore
                    [close,];
                } },
        });
    }
}
__VLS_asFunctionalElement(__VLS_elements.a, __VLS_elements.a)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.tabs = [__VLS_ctx.tabs[0]];
            __VLS_ctx.open(__VLS_ctx.tabs[0]);
            // @ts-ignore
            [open, tabs, tabs, tabs,];
        } },
});
__VLS_asFunctionalElement(__VLS_elements.main, __VLS_elements.main)({
    ...{ class: "admin-content" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
__VLS_asFunctionalElement(__VLS_elements.h1, __VLS_elements.h1)({});
(__VLS_ctx.current?.label || '首页');
// @ts-ignore
[current,];
__VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
(__VLS_ctx.current?.help);
// @ts-ignore
[current,];
if (__VLS_ctx.message) {
    // @ts-ignore
    [message,];
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({
        ...{ class: "message" },
    });
    (__VLS_ctx.message);
    // @ts-ignore
    [message,];
}
if (__VLS_ctx.active === 'home') {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "admin-dashboard" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "metric-cards" },
    });
    for (const [m] of __VLS_getVForSourceType((__VLS_ctx.homeMetrics))) {
        // @ts-ignore
        [homeMetrics,];
        __VLS_asFunctionalElement(__VLS_elements.article, __VLS_elements.article)({
            ...{ class: ('metric-' + m.tone) },
        });
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
        __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
        (m.label);
        __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
        (m.value);
        __VLS_asFunctionalElement(__VLS_elements.em, __VLS_elements.em)({});
        (m.unit);
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
        (m.note);
        __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({});
        (m.tone === 'blue' ? '问' : m.tone === 'green' ? '✓' : '时');
    }
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "trend-columns" },
    });
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel trend-panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.header, __VLS_elements.header)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "trend-bars" },
    });
    for (const [x] of __VLS_getVForSourceType((__VLS_ctx.homeTrend.rows))) {
        // @ts-ignore
        [homeTrend,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "bar-pair" },
        });
        __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
            ...{ style: ({ height: (x.total / __VLS_ctx.homeTrend.maxTotal * 100) + '%' }) },
            title: "请求量",
        });
        // @ts-ignore
        [homeTrend,];
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({
            ...{ style: ({ height: (x.success / __VLS_ctx.homeTrend.maxTotal * 100) + '%' }) },
            title: "成功量",
        });
        // @ts-ignore
        [homeTrend,];
        __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
        (x.day);
    }
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "trend-legend" },
    });
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
        ...{ class: "total" },
    });
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
        ...{ class: "success" },
    });
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel trend-panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.header, __VLS_elements.header)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "trend-bars response-bars" },
    });
    for (const [x] of __VLS_getVForSourceType((__VLS_ctx.homeTrend.rows))) {
        // @ts-ignore
        [homeTrend,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "bar-pair" },
        });
        __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
            ...{ style: ({ height: (x.avg / __VLS_ctx.homeTrend.maxAvg * 100) + '%' }) },
            title: (x.avg.toFixed(2) + '秒'),
        });
        // @ts-ignore
        [homeTrend,];
        __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
        (x.avg ? x.avg.toFixed(1) : '-');
        __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
        (x.day);
    }
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "trend-legend" },
    });
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
        ...{ class: "response" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "dashboard-columns" },
    });
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel todo-panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.header, __VLS_elements.header)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    (__VLS_ctx.homeApprovals.length);
    // @ts-ignore
    [homeApprovals,];
    if (__VLS_ctx.homeApprovals.length) {
        // @ts-ignore
        [homeApprovals,];
        __VLS_asFunctionalElement(__VLS_elements.ul, __VLS_elements.ul)({});
        for (const [x] of __VLS_getVForSourceType((__VLS_ctx.homeApprovals))) {
            // @ts-ignore
            [homeApprovals,];
            __VLS_asFunctionalElement(__VLS_elements.li, __VLS_elements.li)({});
            __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
            (x.type);
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
            __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
            (x.title);
            __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
            (x.applicant_name);
            (new Date(x.submitted_at).toLocaleString('zh-CN', { hour12: false }));
            __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                disabled: true,
                title: "审批流程入口暂未启用",
            });
        }
    }
    else {
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "dashboard-empty" },
        });
    }
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel notice-panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.header, __VLS_elements.header)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.active === 'home'))
                    return;
                __VLS_ctx.openHomeTarget('audit');
                // @ts-ignore
                [openHomeTarget,];
            } },
    });
    if (__VLS_ctx.homeNotices.length) {
        // @ts-ignore
        [homeNotices,];
        __VLS_asFunctionalElement(__VLS_elements.ul, __VLS_elements.ul)({});
        for (const [x] of __VLS_getVForSourceType((__VLS_ctx.homeNotices))) {
            // @ts-ignore
            [homeNotices,];
            __VLS_asFunctionalElement(__VLS_elements.li, __VLS_elements.li)({});
            __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
                ...{ class: ({ 'alarm-dot': x.category === '告警通知' }) },
            });
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
            __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
            (x.category);
            __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
            (x.title);
            __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
            (x.detail);
            __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
            (x.time);
            __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.active === 'home'))
                            return;
                        if (!(__VLS_ctx.homeNotices.length))
                            return;
                        __VLS_ctx.openHomeTarget(x.target);
                        // @ts-ignore
                        [openHomeTarget,];
                    } },
            });
            (x.targetLabel);
        }
    }
    else {
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "dashboard-empty" },
        });
    }
}
else if (__VLS_ctx.active === 'recovery') {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "actions lifecycle-actions" },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.publishResources) },
    });
    // @ts-ignore
    [publishResources,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.loadVersions) },
    });
    // @ts-ignore
    [loadVersions,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({
        ...{ class: "file-button" },
    });
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        ...{ onChange: (__VLS_ctx.importFile) },
        type: "file",
        accept: "application/json",
    });
    // @ts-ignore
    [importFile,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.active === 'home'))
                    return;
                if (!(__VLS_ctx.active === 'recovery'))
                    return;
                __VLS_ctx.recovery('backup');
                // @ts-ignore
                [recovery,];
            } },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.active === 'home'))
                    return;
                if (!(__VLS_ctx.active === 'recovery'))
                    return;
                __VLS_ctx.recovery('official');
                // @ts-ignore
                [recovery,];
            } },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.active === 'home'))
                    return;
                if (!(__VLS_ctx.active === 'recovery'))
                    return;
                __VLS_ctx.recovery('mock-data');
                // @ts-ignore
                [recovery,];
            } },
        ...{ class: "danger" },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.active === 'home'))
                    return;
                if (!(__VLS_ctx.active === 'recovery'))
                    return;
                __VLS_ctx.recovery('all');
                // @ts-ignore
                [recovery,];
            } },
        ...{ class: "danger" },
    });
    if (__VLS_ctx.versions.length) {
        // @ts-ignore
        [versions,];
        __VLS_asFunctionalElement(__VLS_elements.table, __VLS_elements.table)({});
        __VLS_asFunctionalElement(__VLS_elements.thead, __VLS_elements.thead)({});
        __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
        __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
        __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
        __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
        __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
        __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
        __VLS_asFunctionalElement(__VLS_elements.tbody, __VLS_elements.tbody)({});
        for (const [v] of __VLS_getVForSourceType((__VLS_ctx.pagedVersions))) {
            // @ts-ignore
            [pagedVersions,];
            __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
            __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
            (v.version);
            __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
            (v.name);
            __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
            (v.status);
            __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
            (v.official ? '是' : '否');
            __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
            if (['ARCHIVED', 'DISABLED'].includes(v.status)) {
                __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.active === 'home'))
                                return;
                            if (!(__VLS_ctx.active === 'recovery'))
                                return;
                            if (!(__VLS_ctx.versions.length))
                                return;
                            if (!(['ARCHIVED', 'DISABLED'].includes(v.status)))
                                return;
                            __VLS_ctx.rollbackVersion(v.id);
                            // @ts-ignore
                            [rollbackVersion,];
                        } },
                });
            }
        }
    }
    if (__VLS_ctx.versions.length) {
        // @ts-ignore
        [versions,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "pagination" },
        });
        __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
        (__VLS_ctx.versions.length);
        // @ts-ignore
        [versions,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home'))
                        return;
                    if (!(__VLS_ctx.active === 'recovery'))
                        return;
                    if (!(__VLS_ctx.versions.length))
                        return;
                    __VLS_ctx.goPage(__VLS_ctx.page - 1);
                    // @ts-ignore
                    [goPage, page,];
                } },
            disabled: (__VLS_ctx.page === 1),
        });
        // @ts-ignore
        [page,];
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
        (__VLS_ctx.page);
        (__VLS_ctx.totalPages);
        // @ts-ignore
        [page, totalPages,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home'))
                        return;
                    if (!(__VLS_ctx.active === 'recovery'))
                        return;
                    if (!(__VLS_ctx.versions.length))
                        return;
                    __VLS_ctx.goPage(__VLS_ctx.page + 1);
                    // @ts-ignore
                    [goPage, page,];
                } },
            disabled: (__VLS_ctx.page === __VLS_ctx.totalPages),
        });
        // @ts-ignore
        [page, totalPages,];
    }
}
else if (__VLS_ctx.logPage) {
    // @ts-ignore
    [logPage,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel log-workbench" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "log-filters" },
    });
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        placeholder: "ID、提问、操作内容关键词",
    });
    (__VLS_ctx.logFilters.keyword);
    // @ts-ignore
    [logFilters,];
    if (__VLS_ctx.active !== 'audit') {
        // @ts-ignore
        [active,];
        __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
            value: (__VLS_ctx.logFilters.role),
        });
        // @ts-ignore
        [logFilters,];
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: "",
        });
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: "admin",
        });
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: "beijing",
        });
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: "retail",
        });
    }
    __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
        value: (__VLS_ctx.logFilters.status),
    });
    // @ts-ignore
    [logFilters,];
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "",
    });
    for (const [s] of __VLS_getVForSourceType((__VLS_ctx.logStatuses))) {
        // @ts-ignore
        [logStatuses,];
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: (s),
        });
        (__VLS_ctx.statusNames[s] || s);
        // @ts-ignore
        [statusNames,];
    }
    if (['requests', 'sql', 'model-logs', 'source-monitor'].includes(__VLS_ctx.active)) {
        // @ts-ignore
        [active,];
        __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
            value: (__VLS_ctx.logFilters.mode),
        });
        // @ts-ignore
        [logFilters,];
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: "",
        });
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
    }
    if (['requests', 'sql', 'model-logs', 'source-monitor'].includes(__VLS_ctx.active)) {
        // @ts-ignore
        [active,];
        __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
            value: (__VLS_ctx.logFilters.scenario),
        });
        // @ts-ignore
        [logFilters,];
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: "",
        });
        for (const [i] of __VLS_getVForSourceType((8))) {
            __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
                value: ('scenario-' + i),
            });
            (i);
        }
    }
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        type: "date",
    });
    (__VLS_ctx.logFilters.from);
    // @ts-ignore
    [logFilters,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        type: "date",
    });
    (__VLS_ctx.logFilters.to);
    // @ts-ignore
    [logFilters,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.resetLogFilters) },
    });
    // @ts-ignore
    [resetLogFilters,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.load) },
    });
    // @ts-ignore
    [load,];
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    (__VLS_ctx.logFiltered.length);
    (__VLS_ctx.rows.length);
    // @ts-ignore
    [logFiltered, rows,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "table-wrap" },
    });
    __VLS_asFunctionalElement(__VLS_elements.table, __VLS_elements.table)({
        ...{ class: "log-table" },
    });
    __VLS_asFunctionalElement(__VLS_elements.thead, __VLS_elements.thead)({});
    __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
    for (const [c] of __VLS_getVForSourceType((__VLS_ctx.logColumns))) {
        // @ts-ignore
        [logColumns,];
        __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({
            key: (c.key),
        });
        (c.label);
    }
    __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
    __VLS_asFunctionalElement(__VLS_elements.tbody, __VLS_elements.tbody)({});
    for (const [r] of __VLS_getVForSourceType((__VLS_ctx.pagedLogs))) {
        // @ts-ignore
        [pagedLogs,];
        __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({
            key: (r.id),
        });
        for (const [c] of __VLS_getVForSourceType((__VLS_ctx.logColumns))) {
            // @ts-ignore
            [logColumns,];
            __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({
                key: (c.key),
                title: (__VLS_ctx.logValue(r, c.key)),
                ...{ class: ([c.key === 'status' ? __VLS_ctx.statusClass(r[c.key]) : '', { 'status-cell': c.key === 'status', 'question-cell': c.key === 'question' }]) },
            });
            // @ts-ignore
            [logValue, statusClass,];
            (__VLS_ctx.logValue(r, c.key).slice(0, 80));
            // @ts-ignore
            [logValue,];
        }
        __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home'))
                        return;
                    if (!!(__VLS_ctx.active === 'recovery'))
                        return;
                    if (!(__VLS_ctx.logPage))
                        return;
                    __VLS_ctx.viewLog(r);
                    // @ts-ignore
                    [viewLog,];
                } },
        });
    }
    if (!__VLS_ctx.logFiltered.length) {
        // @ts-ignore
        [logFiltered,];
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
            ...{ class: "empty" },
        });
    }
    if (__VLS_ctx.logFiltered.length) {
        // @ts-ignore
        [logFiltered,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "pagination" },
        });
        __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
        (__VLS_ctx.logFiltered.length);
        // @ts-ignore
        [logFiltered,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home'))
                        return;
                    if (!!(__VLS_ctx.active === 'recovery'))
                        return;
                    if (!(__VLS_ctx.logPage))
                        return;
                    if (!(__VLS_ctx.logFiltered.length))
                        return;
                    __VLS_ctx.goPage(__VLS_ctx.page - 1);
                    // @ts-ignore
                    [goPage, page,];
                } },
            disabled: (__VLS_ctx.page === 1),
        });
        // @ts-ignore
        [page,];
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
        (__VLS_ctx.page);
        (__VLS_ctx.totalPages);
        // @ts-ignore
        [page, totalPages,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home'))
                        return;
                    if (!!(__VLS_ctx.active === 'recovery'))
                        return;
                    if (!(__VLS_ctx.logPage))
                        return;
                    if (!(__VLS_ctx.logFiltered.length))
                        return;
                    __VLS_ctx.goPage(__VLS_ctx.page + 1);
                    // @ts-ignore
                    [goPage, page,];
                } },
            disabled: (__VLS_ctx.page === __VLS_ctx.totalPages),
        });
        // @ts-ignore
        [page, totalPages,];
    }
}
else {
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel resource-page" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "resource-tools" },
    });
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        placeholder: "搜索本功能数据",
    });
    (__VLS_ctx.search);
    // @ts-ignore
    [search,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.load) },
    });
    // @ts-ignore
    [load,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.exportRows) },
    });
    // @ts-ignore
    [exportRows,];
    if (!__VLS_ctx.current?.readonly && __VLS_ctx.active !== 'mock-data' && !__VLS_ctx.providerPage) {
        // @ts-ignore
        [active, current, providerPage,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (__VLS_ctx.publishResources) },
        });
        // @ts-ignore
        [publishResources,];
    }
    if (!__VLS_ctx.current?.readonly) {
        // @ts-ignore
        [current,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (__VLS_ctx.add) },
            ...{ class: "primary" },
        });
        // @ts-ignore
        [add,];
    }
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    (__VLS_ctx.filtered.length);
    // @ts-ignore
    [filtered,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "table-wrap" },
    });
    __VLS_asFunctionalElement(__VLS_elements.table, __VLS_elements.table)({});
    __VLS_asFunctionalElement(__VLS_elements.thead, __VLS_elements.thead)({});
    __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
    __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
    for (const [f] of __VLS_getVForSourceType((__VLS_ctx.current?.fields))) {
        // @ts-ignore
        [current,];
        __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({
            key: (f),
        });
        (f);
    }
    if (!__VLS_ctx.current?.readonly) {
        // @ts-ignore
        [current,];
        __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
    }
    __VLS_asFunctionalElement(__VLS_elements.tbody, __VLS_elements.tbody)({});
    for (const [r] of __VLS_getVForSourceType((__VLS_ctx.pagedFiltered))) {
        // @ts-ignore
        [pagedFiltered,];
        __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({
            key: (r.id),
        });
        __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
        __VLS_asFunctionalElement(__VLS_elements.code, __VLS_elements.code)({});
        (r.id);
        for (const [f] of __VLS_getVForSourceType((__VLS_ctx.current?.fields))) {
            // @ts-ignore
            [current,];
            __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({
                key: (f),
                title: (String(r[f] ?? '')),
            });
            (String(r[f] ?? '').slice(0, 100));
        }
        if (!__VLS_ctx.current?.readonly) {
            // @ts-ignore
            [current,];
            __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
            if (__VLS_ctx.providerPage) {
                // @ts-ignore
                [providerPage,];
                if (r.凭据) {
                    if (__VLS_ctx.compositionPage) {
                        // @ts-ignore
                        [compositionPage,];
                        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                            ...{ onClick: (...[$event]) => {
                                    if (!!(__VLS_ctx.active === 'home'))
                                        return;
                                    if (!!(__VLS_ctx.active === 'recovery'))
                                        return;
                                    if (!!(__VLS_ctx.logPage))
                                        return;
                                    if (!(!__VLS_ctx.current?.readonly))
                                        return;
                                    if (!(__VLS_ctx.providerPage))
                                        return;
                                    if (!(r.凭据))
                                        return;
                                    if (!(__VLS_ctx.compositionPage))
                                        return;
                                    __VLS_ctx.enableProfile(String(r.id));
                                    // @ts-ignore
                                    [enableProfile,];
                                } },
                        });
                    }
                    else {
                        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                            ...{ onClick: (...[$event]) => {
                                    if (!!(__VLS_ctx.active === 'home'))
                                        return;
                                    if (!!(__VLS_ctx.active === 'recovery'))
                                        return;
                                    if (!!(__VLS_ctx.logPage))
                                        return;
                                    if (!(!__VLS_ctx.current?.readonly))
                                        return;
                                    if (!(__VLS_ctx.providerPage))
                                        return;
                                    if (!(r.凭据))
                                        return;
                                    if (!!(__VLS_ctx.compositionPage))
                                        return;
                                    __VLS_ctx.enableConnection(String(r.id));
                                    // @ts-ignore
                                    [enableConnection,];
                                } },
                        });
                    }
                    if (__VLS_ctx.compositionPage) {
                        // @ts-ignore
                        [compositionPage,];
                        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                            ...{ onClick: (...[$event]) => {
                                    if (!!(__VLS_ctx.active === 'home'))
                                        return;
                                    if (!!(__VLS_ctx.active === 'recovery'))
                                        return;
                                    if (!!(__VLS_ctx.logPage))
                                        return;
                                    if (!(!__VLS_ctx.current?.readonly))
                                        return;
                                    if (!(__VLS_ctx.providerPage))
                                        return;
                                    if (!(r.凭据))
                                        return;
                                    if (!(__VLS_ctx.compositionPage))
                                        return;
                                    __VLS_ctx.diagnoseProfile(String(r.id));
                                    // @ts-ignore
                                    [diagnoseProfile,];
                                } },
                        });
                    }
                    else {
                        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                            ...{ onClick: (...[$event]) => {
                                    if (!!(__VLS_ctx.active === 'home'))
                                        return;
                                    if (!!(__VLS_ctx.active === 'recovery'))
                                        return;
                                    if (!!(__VLS_ctx.logPage))
                                        return;
                                    if (!(!__VLS_ctx.current?.readonly))
                                        return;
                                    if (!(__VLS_ctx.providerPage))
                                        return;
                                    if (!(r.凭据))
                                        return;
                                    if (!!(__VLS_ctx.compositionPage))
                                        return;
                                    __VLS_ctx.diagnoseConnection(String(r.id));
                                    // @ts-ignore
                                    [diagnoseConnection,];
                                } },
                        });
                    }
                }
                else {
                    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({
                        ...{ class: "builtin-tag" },
                    });
                }
            }
            else {
                __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.active === 'home'))
                                return;
                            if (!!(__VLS_ctx.active === 'recovery'))
                                return;
                            if (!!(__VLS_ctx.logPage))
                                return;
                            if (!(!__VLS_ctx.current?.readonly))
                                return;
                            if (!!(__VLS_ctx.providerPage))
                                return;
                            __VLS_ctx.edit(r);
                            // @ts-ignore
                            [edit,];
                        } },
                });
                __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.active === 'home'))
                                return;
                            if (!!(__VLS_ctx.active === 'recovery'))
                                return;
                            if (!!(__VLS_ctx.logPage))
                                return;
                            if (!(!__VLS_ctx.current?.readonly))
                                return;
                            if (!!(__VLS_ctx.providerPage))
                                return;
                            __VLS_ctx.duplicate(r);
                            // @ts-ignore
                            [duplicate,];
                        } },
                });
                __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.active === 'home'))
                                return;
                            if (!!(__VLS_ctx.active === 'recovery'))
                                return;
                            if (!!(__VLS_ctx.logPage))
                                return;
                            if (!(!__VLS_ctx.current?.readonly))
                                return;
                            if (!!(__VLS_ctx.providerPage))
                                return;
                            __VLS_ctx.remove(r);
                            // @ts-ignore
                            [remove,];
                        } },
                    ...{ class: "danger" },
                });
            }
        }
    }
    if (!__VLS_ctx.filtered.length) {
        // @ts-ignore
        [filtered,];
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
            ...{ class: "empty" },
        });
        (__VLS_ctx.current?.readonly ? '' : '，可点击“新增”创建');
        // @ts-ignore
        [current,];
    }
    if (__VLS_ctx.filtered.length) {
        // @ts-ignore
        [filtered,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "pagination" },
        });
        __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
        (__VLS_ctx.filtered.length);
        // @ts-ignore
        [filtered,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home'))
                        return;
                    if (!!(__VLS_ctx.active === 'recovery'))
                        return;
                    if (!!(__VLS_ctx.logPage))
                        return;
                    if (!(__VLS_ctx.filtered.length))
                        return;
                    __VLS_ctx.goPage(__VLS_ctx.page - 1);
                    // @ts-ignore
                    [goPage, page,];
                } },
            disabled: (__VLS_ctx.page === 1),
        });
        // @ts-ignore
        [page,];
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
        (__VLS_ctx.page);
        (__VLS_ctx.totalPages);
        // @ts-ignore
        [page, totalPages,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home'))
                        return;
                    if (!!(__VLS_ctx.active === 'recovery'))
                        return;
                    if (!!(__VLS_ctx.logPage))
                        return;
                    if (!(__VLS_ctx.filtered.length))
                        return;
                    __VLS_ctx.goPage(__VLS_ctx.page + 1);
                    // @ts-ignore
                    [goPage, page,];
                } },
            disabled: (__VLS_ctx.page === __VLS_ctx.totalPages),
        });
        // @ts-ignore
        [page, totalPages,];
    }
}
if (__VLS_ctx.logDetailData) {
    // @ts-ignore
    [logDetailData,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.logDetailData))
                    return;
                __VLS_ctx.logDetailData = null;
                // @ts-ignore
                [logDetailData,];
            } },
        ...{ class: "modal-mask" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "edit-modal log-modal" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    (__VLS_ctx.current?.label);
    // @ts-ignore
    [current,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "log-detail-sections" },
    });
    for (const [value, key] of __VLS_getVForSourceType((__VLS_ctx.logDetailData))) {
        // @ts-ignore
        [logDetailData,];
        __VLS_asFunctionalElement(__VLS_elements.details, __VLS_elements.details)({
            key: (key),
            open: true,
        });
        __VLS_asFunctionalElement(__VLS_elements.summary, __VLS_elements.summary)({});
        (__VLS_ctx.detailLabel(String(key)));
        // @ts-ignore
        [detailLabel,];
        if (Array.isArray(value)) {
            __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
            (value.length);
        }
        __VLS_asFunctionalElement(__VLS_elements.pre, __VLS_elements.pre)({});
        (JSON.stringify(value, null, 2));
    }
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "actions" },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.logDetailData))
                    return;
                __VLS_ctx.logDetailData = null;
                // @ts-ignore
                [logDetailData,];
            } },
        ...{ class: "primary" },
    });
}
if (__VLS_ctx.editing) {
    // @ts-ignore
    [editing,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.editing))
                    return;
                __VLS_ctx.editing = null;
                // @ts-ignore
                [editing,];
            } },
        ...{ class: "modal-mask" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "edit-modal" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    (__VLS_ctx.rows.some(x => x.id === __VLS_ctx.editing?.id) ? '查看/编辑' : '新增');
    (__VLS_ctx.current?.label);
    // @ts-ignore
    [current, rows, editing,];
    if (__VLS_ctx.modelConfigPage) {
        // @ts-ignore
        [modelConfigPage,];
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
            ...{ class: "security-tip" },
        });
    }
    if (__VLS_ctx.datasourceConfigPage) {
        // @ts-ignore
        [datasourceConfigPage,];
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
            ...{ class: "security-tip" },
        });
    }
    if (__VLS_ctx.compositionPage) {
        // @ts-ignore
        [compositionPage,];
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
            ...{ class: "security-tip" },
        });
    }
    if (!__VLS_ctx.providerPage) {
        // @ts-ignore
        [providerPage,];
        __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
        __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
            disabled: (__VLS_ctx.rows.some(x => x.id === __VLS_ctx.editing?.id)),
        });
        (__VLS_ctx.editing.id);
        // @ts-ignore
        [rows, editing, editing,];
    }
    for (const [f] of __VLS_getVForSourceType((__VLS_ctx.editorFields))) {
        // @ts-ignore
        [editorFields,];
        __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({
            key: (f),
        });
        (f);
        if (['SQL模板', '业务口径', '提示文案', 'Prompt模板', '返回数据', '话术', '模型系统Prompt'].includes(f)) {
            __VLS_asFunctionalElement(__VLS_elements.textarea, __VLS_elements.textarea)({
                value: (__VLS_ctx.editing[f]),
            });
            // @ts-ignore
            [editing,];
        }
        else if (__VLS_ctx.isMulti(f)) {
            // @ts-ignore
            [isMulti,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "checkbox-group" },
            });
            for (const [o] of __VLS_getVForSourceType((__VLS_ctx.optionsFor(f)))) {
                // @ts-ignore
                [optionsFor,];
                __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({
                    key: (o),
                });
                __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
                    type: "checkbox",
                    value: (o),
                });
                (__VLS_ctx.editing[f]);
                // @ts-ignore
                [editing,];
                (o);
            }
            if (!__VLS_ctx.optionsFor(f).length) {
                // @ts-ignore
                [optionsFor,];
                __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
            }
        }
        else if (__VLS_ctx.optionsFor(f).length) {
            // @ts-ignore
            [optionsFor,];
            __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
                ...{ onChange: (...[$event]) => {
                        if (!(__VLS_ctx.editing))
                            return;
                        if (!!(['SQL模板', '业务口径', '提示文案', 'Prompt模板', '返回数据', '话术', '模型系统Prompt'].includes(f)))
                            return;
                        if (!!(__VLS_ctx.isMulti(f)))
                            return;
                        if (!(__VLS_ctx.optionsFor(f).length))
                            return;
                        __VLS_ctx.fieldChanged(f);
                        // @ts-ignore
                        [fieldChanged,];
                    } },
                value: (__VLS_ctx.editing[f]),
            });
            // @ts-ignore
            [editing,];
            __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
                value: "",
                disabled: true,
            });
            for (const [o] of __VLS_getVForSourceType((__VLS_ctx.optionsFor(f)))) {
                // @ts-ignore
                [optionsFor,];
                __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
                    value: (o),
                });
                (o);
            }
        }
        else {
            __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
                type: (__VLS_ctx.secretFields.has(f) ? 'password' : __VLS_ctx.numberFields.has(f) ? 'number' : f.includes('日期') ? 'date' : 'text'),
                autocomplete: (__VLS_ctx.secretFields.has(f) ? 'new-password' : 'off'),
                placeholder: (__VLS_ctx.secretFields.has(f) ? '必填，保存后不回显' : ''),
            });
            (__VLS_ctx.editing[f]);
            // @ts-ignore
            [editing, secretFields, secretFields, secretFields, numberFields,];
        }
    }
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "actions" },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.editing))
                    return;
                __VLS_ctx.editing = null;
                // @ts-ignore
                [editing,];
            } },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.saveRow) },
        ...{ class: "primary" },
        disabled: (__VLS_ctx.busy),
    });
    // @ts-ignore
    [saveRow, busy,];
}
/** @type {__VLS_StyleScopedClasses['admin-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['admin-sidebar']} */ ;
/** @type {__VLS_StyleScopedClasses['collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['side-logo']} */ ;
/** @type {__VLS_StyleScopedClasses['collapse']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-list']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-group']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-parent']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['sub-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['admin-main']} */ ;
/** @type {__VLS_StyleScopedClasses['admin-top']} */ ;
/** @type {__VLS_StyleScopedClasses['mode']} */ ;
/** @type {__VLS_StyleScopedClasses['tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['admin-content']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['admin-dashboard']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['trend-columns']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['trend-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['trend-bars']} */ ;
/** @type {__VLS_StyleScopedClasses['bar-pair']} */ ;
/** @type {__VLS_StyleScopedClasses['trend-legend']} */ ;
/** @type {__VLS_StyleScopedClasses['total']} */ ;
/** @type {__VLS_StyleScopedClasses['success']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['trend-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['trend-bars']} */ ;
/** @type {__VLS_StyleScopedClasses['response-bars']} */ ;
/** @type {__VLS_StyleScopedClasses['bar-pair']} */ ;
/** @type {__VLS_StyleScopedClasses['trend-legend']} */ ;
/** @type {__VLS_StyleScopedClasses['response']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-columns']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['todo-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['notice-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['alarm-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['lifecycle-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['file-button']} */ ;
/** @type {__VLS_StyleScopedClasses['danger']} */ ;
/** @type {__VLS_StyleScopedClasses['danger']} */ ;
/** @type {__VLS_StyleScopedClasses['pagination']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['log-workbench']} */ ;
/** @type {__VLS_StyleScopedClasses['log-filters']} */ ;
/** @type {__VLS_StyleScopedClasses['table-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['log-table']} */ ;
/** @type {__VLS_StyleScopedClasses['status-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['question-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['pagination']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['resource-page']} */ ;
/** @type {__VLS_StyleScopedClasses['resource-tools']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['table-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['builtin-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['danger']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['pagination']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-mask']} */ ;
/** @type {__VLS_StyleScopedClasses['edit-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['log-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['log-detail-sections']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-mask']} */ ;
/** @type {__VLS_StyleScopedClasses['edit-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['security-tip']} */ ;
/** @type {__VLS_StyleScopedClasses['security-tip']} */ ;
/** @type {__VLS_StyleScopedClasses['security-tip']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-group']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            isOffline: isOffline,
            menus: menus,
            router: router,
            collapsed: collapsed,
            expanded: expanded,
            active: active,
            tabs: tabs,
            rows: rows,
            editing: editing,
            search: search,
            message: message,
            busy: busy,
            versions: versions,
            homeApprovals: homeApprovals,
            page: page,
            current: current,
            filtered: filtered,
            modelConfigPage: modelConfigPage,
            datasourceConfigPage: datasourceConfigPage,
            compositionPage: compositionPage,
            providerPage: providerPage,
            logPage: logPage,
            logFilters: logFilters,
            logDetailData: logDetailData,
            logColumns: logColumns,
            logStatuses: logStatuses,
            logFiltered: logFiltered,
            totalPages: totalPages,
            pagedFiltered: pagedFiltered,
            pagedLogs: pagedLogs,
            pagedVersions: pagedVersions,
            statusNames: statusNames,
            homeMetrics: homeMetrics,
            homeNotices: homeNotices,
            homeTrend: homeTrend,
            detailLabel: detailLabel,
            statusClass: statusClass,
            logValue: logValue,
            viewLog: viewLog,
            resetLogFilters: resetLogFilters,
            openHomeTarget: openHomeTarget,
            editorFields: editorFields,
            numberFields: numberFields,
            secretFields: secretFields,
            optionsFor: optionsFor,
            isMulti: isMulti,
            toggle: toggle,
            open: open,
            close: close,
            load: load,
            add: add,
            edit: edit,
            fieldChanged: fieldChanged,
            saveRow: saveRow,
            remove: remove,
            enableProfile: enableProfile,
            enableConnection: enableConnection,
            diagnoseConnection: diagnoseConnection,
            diagnoseProfile: diagnoseProfile,
            duplicate: duplicate,
            exportRows: exportRows,
            recovery: recovery,
            publishResources: publishResources,
            loadVersions: loadVersions,
            goPage: goPage,
            rollbackVersion: rollbackVersion,
            importFile: importFile,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
    },
});
; /* PartiallyEnd: #4569/main.vue */

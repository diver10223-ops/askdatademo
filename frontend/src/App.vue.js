import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { PocApiAdapter } from './adapters/poc';
import { OfflineAdapter } from './adapters/offline';
const route = useRoute(), router = useRouter(), offline = location.protocol === 'file:' || new URLSearchParams(location.search).has('offline');
const adapter = offline ? new OfflineAdapter() : new PocApiAdapter();
const roles = [['admin', '张总｜总行领导'], ['beijing', '李总｜北京分行'], ['retail', '王总｜零售主管']];
const scenes = ['基础查数', 'BI 驾驶舱', '模糊推荐', '同比归因', '权限合规拦截', '多轮上下文', '参数补全', '二次归因'];
const defaults = { admin: ['2026年3月上海分行对公贷款投放金额', '查看全行经营指标分析大盘', '查一下2026年3月银行贷款相关数据', '2026年3月北京分行贷款投放同比去年变化', '查询客户身份证号和贷款明细', '2026年3月北京分行零售贷款投放金额', '查询贷款投放同比数据', '2026年3月全行对公贷款投放金额'], beijing: ['2026年3月北京分行对公贷款投放金额', '查看北京分行经营指标分析大盘', '查一下2026年3月北京分行贷款相关数据', '2026年3月北京分行贷款投放同比去年变化', '查询上海分行2026年3月对公贷款数据', '2026年3月北京分行零售贷款投放金额', '查询贷款投放同比数据', '2026年3月北京分行对公贷款投放金额'], retail: ['2026年3月全行零售贷款投放金额', '查看零售信贷专项经营驾驶舱', '查一下2026年3月零售贷款相关数据', '2026年3月全行零售贷款同比去年变化', '查询2026年3月对公贷款投放', '2026年3月全行零售贷款投放金额', '查询零售贷款同比数据', '2026年3月全行零售贷款投放金额'] };
const role = ref('admin'), session = ref(), question = ref(''), active = ref(0), busy = ref(false), events = ref([]), detail = ref(), error = ref(''), parent = ref();
const isAdmin = computed(() => route.path.startsWith('/admin'));
const technical = ref(false);
const ready = ref();
const adminKind = ref('assets'), adminId = ref('demo-item'), adminJson = ref('{\n  "name": "演示配置项"\n}'), adminMessage = ref('');
const executionMode = ref('PHASE1_DEMO'), providerProfiles = ref([]), providerProfileId = ref('');
const phase2Json = ref(JSON.stringify({ name: 'Phase 2 Profile', datasource_type: 'CLICKHOUSE', model_base_url: 'https://model.example/v1', model: 'model-name', model_api_key: '', datasource_url: 'https://clickhouse.example:8443', datasource_host: null, datasource_port: 3306, datasource_username: 'default', datasource_password: '', database: 'default', allowed_tables: ['dws_loan_aggr_wide'], max_rows: 1000, timeout: 30, retries: 2 }, null, 2));
async function loadProfiles() { if (!offline) {
    providerProfiles.value = (await adapter.admin('/phase2/providers')).items;
    providerProfileId.value ||= providerProfiles.value.find(x => x.status === 'ENABLED')?.id || '';
} }
async function newSession() { session.value = await adapter.createSession(role.value, offline ? {} : { execution_mode: executionMode.value, provider_profile_id: executionMode.value.startsWith('PHASE2') ? providerProfileId.value : undefined }); events.value = []; detail.value = undefined; parent.value = undefined; }
async function roleChanged() { await newSession(); }
async function run(text) { if (!session.value)
    return; question.value = text || question.value; if (!question.value.trim())
    return; busy.value = true; error.value = ''; events.value = []; detail.value = undefined; try {
    const id = await adapter.query(session.value.id, question.value, `scenario-${active.value + 1}`, parent.value);
    parent.value = id;
    await adapter.events(id, e => events.value.push(e));
    detail.value = await adapter.detail(id);
}
catch (e) {
    error.value = String(e);
}
finally {
    busy.value = false;
} }
async function stop() { if (parent.value)
    await adapter.cancel(parent.value); }
async function follow(text) { question.value = text; await run(); }
onMounted(async () => { await loadProfiles(); await newSession(); ready.value = await adapter.readiness(); });
async function saveAdmin() { try {
    const payload = JSON.parse(adminJson.value);
    await adapter.admin(`/resources/${adminKind.value}/${adminId.value}`, { method: 'PUT', body: JSON.stringify({ id: adminId.value, payload, enabled: true }) });
    adminMessage.value = '草稿资源已保存并写入审计';
}
catch (e) {
    adminMessage.value = `保存失败：${e}`;
} }
async function copyDraft() { const payload = await adapter.admin('/baseline'); await adapter.admin('/config/drafts', { method: 'POST', body: JSON.stringify({ name: 'Baseline 副本', payload }) }); adminMessage.value = '已复制为草稿'; }
async function restoreOfficial() { await adapter.admin('/reset/official', { method: 'POST' }); adminMessage.value = '已恢复官方配置（历史会话保留）'; }
async function exportConfig() { const data = await adapter.admin('/config/export'); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); a.download = 'askdata-config.json'; a.click(); URL.revokeObjectURL(a.href); adminMessage.value = '配置已导出'; }
async function createProvider() { try {
    const created = await adapter.admin('/phase2/providers', { method: 'POST', body: JSON.stringify(JSON.parse(phase2Json.value)) });
    await adapter.admin(`/phase2/providers/${created.id}/enable`, { method: 'POST' });
    const result = await adapter.admin(`/phase2/providers/${created.id}/diagnose`, { method: 'POST' });
    adminMessage.value = `Provider 已加密保存并启用，诊断：${result.status}`;
    await loadProfiles();
}
catch (e) {
    adminMessage.value = `Provider 配置失败：${e}`;
} }
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_elements;
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "app" },
});
__VLS_asFunctionalElement(__VLS_elements.header, __VLS_elements.header)({});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "brand" },
});
__VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({
    ...{ class: "logo" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
__VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
__VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
(__VLS_ctx.adapter.mode);
// @ts-ignore
[adapter,];
__VLS_asFunctionalElement(__VLS_elements.nav, __VLS_elements.nav)({});
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.router.push('/');
            // @ts-ignore
            [router,];
        } },
    ...{ class: ({ active: !__VLS_ctx.isAdmin }) },
});
// @ts-ignore
[isAdmin,];
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.router.push('/admin');
            // @ts-ignore
            [router,];
        } },
    ...{ class: ({ active: __VLS_ctx.isAdmin }) },
});
// @ts-ignore
[isAdmin,];
if (!__VLS_ctx.offline) {
    // @ts-ignore
    [offline,];
    __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
        ...{ onChange: (__VLS_ctx.newSession) },
        value: (__VLS_ctx.executionMode),
        'aria-label': "执行模式",
    });
    // @ts-ignore
    [newSession, executionMode,];
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "PHASE1_DEMO",
    });
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "PHASE2_DEMO",
    });
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "PHASE2_POC",
    });
}
if (!__VLS_ctx.offline && __VLS_ctx.executionMode.startsWith('PHASE2')) {
    // @ts-ignore
    [offline, executionMode,];
    __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
        ...{ onChange: (__VLS_ctx.newSession) },
        value: (__VLS_ctx.providerProfileId),
        'aria-label': "Provider Profile",
    });
    // @ts-ignore
    [newSession, providerProfileId,];
    for (const [p] of __VLS_getVForSourceType((__VLS_ctx.providerProfiles.filter(x => x.status === 'ENABLED')))) {
        // @ts-ignore
        [providerProfiles,];
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: (p.id),
        });
        (p.name);
    }
}
__VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
    ...{ onChange: (__VLS_ctx.roleChanged) },
    value: (__VLS_ctx.role),
    'aria-label': "演示角色",
});
// @ts-ignore
[roleChanged, role,];
for (const [r] of __VLS_getVForSourceType((__VLS_ctx.roles))) {
    // @ts-ignore
    [roles,];
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: (r[0]),
    });
    (r[1]);
}
if (!__VLS_ctx.isAdmin) {
    // @ts-ignore
    [isAdmin,];
    __VLS_asFunctionalElement(__VLS_elements.main, __VLS_elements.main)({});
    __VLS_asFunctionalElement(__VLS_elements.aside, __VLS_elements.aside)({});
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    for (const [s, i] of __VLS_getVForSourceType((__VLS_ctx.scenes))) {
        // @ts-ignore
        [scenes,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(!__VLS_ctx.isAdmin))
                        return;
                    __VLS_ctx.active = i;
                    __VLS_ctx.question = __VLS_ctx.defaults[__VLS_ctx.role][i];
                    // @ts-ignore
                    [role, active, question, defaults,];
                } },
            ...{ class: ({ picked: __VLS_ctx.active === i }) },
        });
        // @ts-ignore
        [active,];
        __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
        (i + 1);
        (s);
    }
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "notice" },
    });
    (__VLS_ctx.offline ? '离线模拟执行，数据保存在本浏览器' : 'POC 真实七层执行与 SQLite 查询');
    // @ts-ignore
    [offline,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "workspace" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "hero" },
    });
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    (__VLS_ctx.roles.find(r => r[0] === __VLS_ctx.role)?.[1]);
    // @ts-ignore
    [role, roles,];
    __VLS_asFunctionalElement(__VLS_elements.h1, __VLS_elements.h1)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "chips" },
    });
    for (const [s, i] of __VLS_getVForSourceType((__VLS_ctx.scenes))) {
        // @ts-ignore
        [scenes,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(!__VLS_ctx.isAdmin))
                        return;
                    __VLS_ctx.active = i;
                    __VLS_ctx.run(__VLS_ctx.defaults[__VLS_ctx.role][i]);
                    // @ts-ignore
                    [role, active, defaults, run,];
                } },
        });
        (s);
    }
    if (__VLS_ctx.events.length) {
        // @ts-ignore
        [events,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "trace" },
        });
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "trace-head" },
        });
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
        if (!__VLS_ctx.offline) {
            // @ts-ignore
            [offline,];
            __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
            __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
                type: "checkbox",
            });
            (__VLS_ctx.technical);
            // @ts-ignore
            [technical,];
        }
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "steps" },
        });
        for (const [e] of __VLS_getVForSourceType((__VLS_ctx.events.filter(x => x.type === 'layer.completed')))) {
            // @ts-ignore
            [events,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "step" },
            });
            __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({});
            __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
            (e.layer_code);
            __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
            (e.status);
        }
    }
    if (__VLS_ctx.detail) {
        // @ts-ignore
        [detail,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "answer" },
        });
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
        (__VLS_ctx.detail.layers.at(-1)?.output?.answer || __VLS_ctx.detail.request.status);
        // @ts-ignore
        [detail, detail,];
        if (__VLS_ctx.detail.result.length) {
            // @ts-ignore
            [detail,];
            __VLS_asFunctionalElement(__VLS_elements.table, __VLS_elements.table)({});
            __VLS_asFunctionalElement(__VLS_elements.thead, __VLS_elements.thead)({});
            __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
            for (const [_, k] of __VLS_getVForSourceType((__VLS_ctx.detail.result[0]))) {
                // @ts-ignore
                [detail,];
                __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
                (k);
            }
            __VLS_asFunctionalElement(__VLS_elements.tbody, __VLS_elements.tbody)({});
            for (const [r] of __VLS_getVForSourceType((__VLS_ctx.detail.result))) {
                // @ts-ignore
                [detail,];
                __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
                for (const [v] of __VLS_getVForSourceType((r))) {
                    __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
                    (v);
                }
            }
        }
        if (__VLS_ctx.detail.request.status === 'WAITING_INPUT') {
            // @ts-ignore
            [detail,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "chips" },
            });
            __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(!__VLS_ctx.isAdmin))
                            return;
                        if (!(__VLS_ctx.detail))
                            return;
                        if (!(__VLS_ctx.detail.request.status === 'WAITING_INPUT'))
                            return;
                        __VLS_ctx.follow('2026年3月，全行贷款投放');
                        // @ts-ignore
                        [follow,];
                    } },
            });
        }
        if (__VLS_ctx.technical) {
            // @ts-ignore
            [technical,];
            __VLS_asFunctionalElement(__VLS_elements.pre, __VLS_elements.pre)({});
            (JSON.stringify(__VLS_ctx.detail, null, 2));
            // @ts-ignore
            [detail,];
        }
    }
    if (__VLS_ctx.error) {
        // @ts-ignore
        [error,];
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
            ...{ class: "error" },
        });
        (__VLS_ctx.error);
        // @ts-ignore
        [error,];
    }
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "composer" },
    });
    __VLS_asFunctionalElement(__VLS_elements.textarea, __VLS_elements.textarea)({
        ...{ onKeydown: (...[$event]) => {
                if (!(!__VLS_ctx.isAdmin))
                    return;
                __VLS_ctx.run();
                // @ts-ignore
                [run,];
            } },
        value: (__VLS_ctx.question),
        placeholder: "输入经营数据问题…",
        'aria-label': "问数输入",
    });
    // @ts-ignore
    [question,];
    if (__VLS_ctx.busy) {
        // @ts-ignore
        [busy,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (__VLS_ctx.stop) },
            ...{ class: "stop" },
        });
        // @ts-ignore
        [stop,];
    }
    else {
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(!__VLS_ctx.isAdmin))
                        return;
                    if (!!(__VLS_ctx.busy))
                        return;
                    __VLS_ctx.run();
                    // @ts-ignore
                    [run,];
                } },
        });
    }
}
else {
    __VLS_asFunctionalElement(__VLS_elements.main, __VLS_elements.main)({
        ...{ class: "admin" },
    });
    __VLS_asFunctionalElement(__VLS_elements.aside, __VLS_elements.aside)({});
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    for (const [x] of __VLS_getVForSourceType((['角色与权限', '数据资产', '七层流程', '场景用例', '日志与审计', '合规规则', 'Provider', '备份与重置']))) {
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({});
        (x);
    }
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "workspace" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "admin-title" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
    __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
    __VLS_asFunctionalElement(__VLS_elements.h1, __VLS_elements.h1)({});
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({
        ...{ class: "badge" },
    });
    (__VLS_ctx.ready?.ready ? '已就绪' : '检查中');
    // @ts-ignore
    [ready,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "cards" },
    });
    __VLS_asFunctionalElement(__VLS_elements.article, __VLS_elements.article)({});
    __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
    __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
    (__VLS_ctx.ready?.roles || 3);
    // @ts-ignore
    [ready,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.article, __VLS_elements.article)({});
    __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
    __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
    (__VLS_ctx.ready?.scenarios || 8);
    // @ts-ignore
    [ready,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.article, __VLS_elements.article)({});
    __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
    __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "row" },
    });
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "row" },
    });
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "row" },
    });
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    __VLS_asFunctionalElement(__VLS_elements.em, __VLS_elements.em)({});
    (__VLS_ctx.offline ? 'POC 中配置' : '二期已支持');
    // @ts-ignore
    [offline,];
    if (!__VLS_ctx.offline) {
        // @ts-ignore
        [offline,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "panel" },
        });
        __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
        __VLS_asFunctionalElement(__VLS_elements.textarea, __VLS_elements.textarea)({
            value: (__VLS_ctx.phase2Json),
            'aria-label': "Phase 2 Provider JSON",
        });
        // @ts-ignore
        [phase2Json,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "actions" },
        });
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (__VLS_ctx.createProvider) },
        });
        // @ts-ignore
        [createProvider,];
    }
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "actions" },
    });
    __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
        value: (__VLS_ctx.adminKind),
        'aria-label': "资源类型",
    });
    // @ts-ignore
    [adminKind,];
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "roles",
    });
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "assets",
    });
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "flows",
    });
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "scenarios",
    });
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "compliance",
    });
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "operations",
    });
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        'aria-label': "资源ID",
        placeholder: "资源 ID",
    });
    (__VLS_ctx.adminId);
    // @ts-ignore
    [adminId,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.saveAdmin) },
    });
    // @ts-ignore
    [saveAdmin,];
    __VLS_asFunctionalElement(__VLS_elements.textarea, __VLS_elements.textarea)({
        value: (__VLS_ctx.adminJson),
        'aria-label': "配置 JSON",
    });
    // @ts-ignore
    [adminJson,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    (__VLS_ctx.adminMessage);
    // @ts-ignore
    [adminMessage,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "actions" },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.copyDraft) },
    });
    // @ts-ignore
    [copyDraft,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.exportConfig) },
    });
    // @ts-ignore
    [exportConfig,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.restoreOfficial) },
    });
    // @ts-ignore
    [restoreOfficial,];
}
/** @type {__VLS_StyleScopedClasses['app']} */ ;
/** @type {__VLS_StyleScopedClasses['brand']} */ ;
/** @type {__VLS_StyleScopedClasses['logo']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['picked']} */ ;
/** @type {__VLS_StyleScopedClasses['notice']} */ ;
/** @type {__VLS_StyleScopedClasses['workspace']} */ ;
/** @type {__VLS_StyleScopedClasses['hero']} */ ;
/** @type {__VLS_StyleScopedClasses['chips']} */ ;
/** @type {__VLS_StyleScopedClasses['trace']} */ ;
/** @type {__VLS_StyleScopedClasses['trace-head']} */ ;
/** @type {__VLS_StyleScopedClasses['steps']} */ ;
/** @type {__VLS_StyleScopedClasses['step']} */ ;
/** @type {__VLS_StyleScopedClasses['answer']} */ ;
/** @type {__VLS_StyleScopedClasses['chips']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['stop']} */ ;
/** @type {__VLS_StyleScopedClasses['admin']} */ ;
/** @type {__VLS_StyleScopedClasses['workspace']} */ ;
/** @type {__VLS_StyleScopedClasses['admin-title']} */ ;
/** @type {__VLS_StyleScopedClasses['badge']} */ ;
/** @type {__VLS_StyleScopedClasses['cards']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['row']} */ ;
/** @type {__VLS_StyleScopedClasses['row']} */ ;
/** @type {__VLS_StyleScopedClasses['row']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            router: router,
            offline: offline,
            adapter: adapter,
            roles: roles,
            scenes: scenes,
            defaults: defaults,
            role: role,
            question: question,
            active: active,
            busy: busy,
            events: events,
            detail: detail,
            error: error,
            isAdmin: isAdmin,
            technical: technical,
            ready: ready,
            adminKind: adminKind,
            adminId: adminId,
            adminJson: adminJson,
            adminMessage: adminMessage,
            executionMode: executionMode,
            providerProfiles: providerProfiles,
            providerProfileId: providerProfileId,
            phase2Json: phase2Json,
            newSession: newSession,
            roleChanged: roleChanged,
            run: run,
            stop: stop,
            follow: follow,
            saveAdmin: saveAdmin,
            copyDraft: copyDraft,
            restoreOfficial: restoreOfficial,
            exportConfig: exportConfig,
            createProvider: createProvider,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
    },
});
; /* PartiallyEnd: #4569/main.vue */

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { adminApi } from './admin-api';
import { isOffline } from './runtime';
const menus = [
    { id: 'home', label: '首页', icon: 'H' },
    { id: 'permission', label: '权限管理', icon: 'R', children: [{ id: 'roles', label: '角色管理' }, { id: 'accounts', label: '账号管理' }, { id: 'permissions', label: '权限配置' }] },
    { id: 'assets', label: '资产管理', icon: 'A', children: [{ id: 'metrics', label: '指标字典' }, { id: 'dimensions', label: '维度字典' }, { id: 'recommendations', label: '推荐词库' }, { id: 'mappings', label: '字段映射' }] },
    { id: 'process', label: '流程配置', icon: 'P', children: [{ id: 'intent', label: '意图规则' }, { id: 'sql-templates', label: 'SQL模板' }, { id: 'conversation', label: '会话配置' }, { id: 'parameters', label: '参数校验' }, { id: 'layers', label: '七层配置' }] },
    { id: 'scenes', label: '场景管理', icon: 'S', children: [{ id: 'scenarios', label: '标准场景' }, { id: 'shortcuts', label: '快捷按钮' }, { id: 'dashboards', label: '驾驶舱' }, { id: 'fixtures', label: 'Fixture' }] },
    { id: 'logs', label: '日志管理', icon: 'L', children: [{ id: 'sessions', label: '会话记录' }, { id: 'requests', label: '执行轨迹' }, { id: 'sql', label: 'SQL审计' }, { id: 'audit', label: '操作日志' }] },
    { id: 'compliance', label: '合规管控', icon: 'C', children: [{ id: 'sensitive', label: '涉密管控' }, { id: 'limits', label: '访问限流' }, { id: 'masking', label: '数据脱敏' }, { id: 'intercepts', label: '拦截话术' }] },
    { id: 'operations', label: '运维配置', icon: 'O', children: [{ id: 'interface', label: '界面配置' }, { id: 'system', label: '系统参数' }, { id: 'readiness', label: '就绪检查' }, { id: 'recovery', label: '备份与重置' }] },
    { id: 'models', label: '大模型配置', icon: 'M' }, { id: 'datasources', label: '数据源配置', icon: 'D' },
    { id: 'mock', label: 'Mock管理', icon: 'K', children: [{ id: 'mock-data', label: '模拟数据' }, { id: 'demo-switch', label: '演示开关' }, { id: 'wording', label: '话术维护' }] }
];
const router = useRouter(), collapsed = ref(false), expanded = ref(new Set(['permission'])), active = ref('home'), tabs = ref([{ id: 'home', label: '首页' }]), config = ref({}), ready = ref({}), rows = ref([]), busy = ref(false), message = ref(''), dirty = ref(false), draft = ref(), filter = ref(''), selected = ref();
const phase2Profiles = ref([]), phase2Json = ref(JSON.stringify({ name: 'Phase 2 Profile', datasource_type: 'CLICKHOUSE', model_base_url: 'https://model.example/v1', model: 'model-name', model_api_key: '', datasource_url: 'https://clickhouse.example:8443', datasource_username: 'default', datasource_password: '', database: 'default', allowed_tables: ['dws_loan_aggr_wide'], timeout: 30, retries: 2 }, null, 2));
const labels = computed(() => Object.fromEntries(menus.flatMap(x => [{ id: x.id, label: x.label }, ...(x.children || [])]).map(x => [x.id, x.label]))), title = computed(() => labels.value[active.value] || '管理页面');
function toggle(g) { if (!g.children) {
    open({ id: g.id, label: g.label });
    return;
} const next = new Set(expanded.value); next.has(g.id) ? next.delete(g.id) : next.add(g.id); expanded.value = next; }
async function open(item) { active.value = item.id; if (!tabs.value.some(x => x.id === item.id))
    tabs.value.push(item); message.value = ''; if (['sessions', 'requests', 'sql', 'audit'].includes(item.id))
    await loadLogs(); }
function close(id) { if (id === 'home')
    return; tabs.value = tabs.value.filter(x => x.id !== id); if (active.value === id)
    open(tabs.value.at(-1)); }
function changed() { dirty.value = true; message.value = '存在未保存变更'; }
function updateList(target, key, event) { target[key] = event.target.value.split(/[，,]/).map(x => x.trim()).filter(Boolean); changed(); }
function addValue(list) { list.push('新条目'); changed(); }
function removeValue(list, index) { list.splice(index, 1); changed(); }
async function inspect(row) { try {
    selected.value = await adminApi.logDetail(active.value, row.id);
}
catch (e) {
    message.value = String(e);
} }
function exportRows() { const blob = new Blob([JSON.stringify(rows.value, null, 2)], { type: 'application/json' }), a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${active.value}-logs.json`; a.click(); URL.revokeObjectURL(a.href); }
async function loadLogs() { busy.value = true; try {
    rows.value = (await adminApi.logs(active.value, filter.value)).items;
}
catch (e) {
    message.value = String(e);
}
finally {
    busy.value = false;
} }
async function save() { busy.value = true; try {
    const saved = await adminApi.saveDraft(`管理端草稿 ${new Date().toLocaleString()}`, config.value);
    draft.value = saved;
    dirty.value = false;
    message.value = `草稿 v${saved.version} 已保存，尚未影响活动会话`;
}
catch (e) {
    message.value = String(e);
}
finally {
    busy.value = false;
} }
async function publish() { if (!draft.value)
    return message.value = '请先保存草稿'; busy.value = true; try {
    await adminApi.publish(draft.value.id);
    message.value = '发布成功，仅新建 Session 使用新版本';
    draft.value = undefined;
}
catch (e) {
    message.value = String(e);
}
finally {
    busy.value = false;
} }
async function provider(kind) { try {
    message.value = JSON.stringify(await adminApi.testProvider(kind));
}
catch (e) {
    message.value = String(e);
} }
async function createPhase2() { busy.value = true; try {
    const created = await adminApi.createPhase2Profile(JSON.parse(phase2Json.value));
    await adminApi.enablePhase2Profile(created.id);
    const result = await adminApi.diagnosePhase2Profile(created.id);
    phase2Profiles.value = (await adminApi.phase2Profiles()).items;
    message.value = `已加密保存并启用，诊断：${result.status}`;
}
catch (e) {
    message.value = String(e);
}
finally {
    busy.value = false;
} }
async function recovery(action) { try {
    message.value = action === 'backup' ? JSON.stringify(await adminApi.backup()) : JSON.stringify(await adminApi.reset(action));
    if (action === 'official')
        config.value = await adminApi.baseline();
}
catch (e) {
    message.value = String(e);
} }
function download() { const blob = new Blob([JSON.stringify(config.value, null, 2)], { type: 'application/json' }), a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'askdata-config.json'; a.click(); URL.revokeObjectURL(a.href); }
onMounted(async () => { try {
    [config.value, ready.value] = await Promise.all([adminApi.baseline(), adminApi.readiness()]);
    if (!isOffline)
        phase2Profiles.value = (await adminApi.phase2Profiles()).items;
    config.value.compliance ??= { sensitive_words: ['身份证', '明细', '涉密'], intercept_message: '涉密或明细数据已按合规规则拦截', max_rows: 200, masking: true };
    config.value.system ??= { title: '智能银行问数平台', welcome: '今天想了解什么经营数据？', default_role: 'admin', simulation_speed: 120, show_trace: true };
}
catch (e) {
    message.value = String(e);
} });
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
        for (const [item] of __VLS_getVForSourceType((g.children))) {
            __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(g.children && __VLS_ctx.expanded.has(g.id)))
                            return;
                        __VLS_ctx.open(item);
                        // @ts-ignore
                        [open,];
                    } },
                key: (item.id),
                ...{ class: ({ active: __VLS_ctx.active === item.id }) },
            });
            // @ts-ignore
            [active,];
            (item.label);
            if (item.id === 'accounts') {
                __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
            }
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
for (const [tab] of __VLS_getVForSourceType((__VLS_ctx.tabs))) {
    // @ts-ignore
    [tabs,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.open(tab);
                // @ts-ignore
                [open,];
            } },
        key: (tab.id),
        ...{ class: ({ active: __VLS_ctx.active === tab.id }) },
    });
    // @ts-ignore
    [active,];
    (tab.label);
    if (tab.id !== 'home') {
        __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
            ...{ onClick: (...[$event]) => {
                    if (!(tab.id !== 'home'))
                        return;
                    __VLS_ctx.close(tab.id);
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
__VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
__VLS_asFunctionalElement(__VLS_elements.h1, __VLS_elements.h1)({});
(__VLS_ctx.title);
// @ts-ignore
[title,];
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "toolbar" },
});
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
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (__VLS_ctx.download) },
});
// @ts-ignore
[download,];
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (__VLS_ctx.save) },
    disabled: (__VLS_ctx.busy),
});
// @ts-ignore
[save, busy,];
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (__VLS_ctx.publish) },
    ...{ class: "primary" },
    disabled: (__VLS_ctx.busy || !__VLS_ctx.draft),
});
// @ts-ignore
[busy, publish, draft,];
if (__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness') {
    // @ts-ignore
    [active, active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "grid" },
    });
    __VLS_asFunctionalElement(__VLS_elements.article, __VLS_elements.article)({});
    __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
    __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
    (__VLS_ctx.ready.ready ? '已就绪' : '未就绪');
    // @ts-ignore
    [ready,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.article, __VLS_elements.article)({});
    __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
    __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
    (__VLS_ctx.config.roles?.length || 0);
    // @ts-ignore
    [config,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.article, __VLS_elements.article)({});
    __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
    __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
    (__VLS_ctx.config.scenarios?.length || 0);
    // @ts-ignore
    [config,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "panel wide" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
        ...{ class: ({ ok: __VLS_ctx.config.roles?.length === 3 }) },
    });
    // @ts-ignore
    [config,];
    (__VLS_ctx.config.roles?.length || 0);
    // @ts-ignore
    [config,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
        ...{ class: ({ ok: __VLS_ctx.config.scenarios?.length === 8 }) },
    });
    // @ts-ignore
    [config,];
    (__VLS_ctx.config.scenarios?.length || 0);
    // @ts-ignore
    [config,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
}
else if (['roles', 'permissions'].includes(__VLS_ctx.active)) {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    for (const [role] of __VLS_getVForSourceType((__VLS_ctx.config.roles))) {
        // @ts-ignore
        [config,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            key: (role.id),
            ...{ class: "role-card" },
        });
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
        __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
            ...{ onInput: (__VLS_ctx.changed) },
        });
        (role.name);
        // @ts-ignore
        [changed,];
        __VLS_asFunctionalElement(__VLS_elements.code, __VLS_elements.code)({});
        (role.id);
        __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
        __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
            ...{ onChange: (__VLS_ctx.changed) },
            type: "checkbox",
        });
        (role.enabled);
        // @ts-ignore
        [changed,];
        __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
        __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
            ...{ onChange: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                        return;
                    if (!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                        return;
                    __VLS_ctx.updateList(role, 'orgs', $event);
                    // @ts-ignore
                    [updateList,];
                } },
            value: (role.orgs.join(', ')),
        });
        __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
        __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
            ...{ onChange: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                        return;
                    if (!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                        return;
                    __VLS_ctx.updateList(role, 'metrics', $event);
                    // @ts-ignore
                    [updateList,];
                } },
            value: (role.metrics.join(', ')),
        });
        __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
        __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
            ...{ onChange: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                        return;
                    if (!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                        return;
                    __VLS_ctx.updateList(role, 'features', $event);
                    // @ts-ignore
                    [updateList,];
                } },
            value: (role.features.join(', ')),
        });
    }
}
else if (__VLS_ctx.active === 'accounts') {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel empty" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
}
else if (['metrics', 'dimensions'].includes(__VLS_ctx.active)) {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    (__VLS_ctx.title);
    // @ts-ignore
    [title,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "dictionary" },
    });
    for (const [value, i] of __VLS_getVForSourceType((__VLS_ctx.config.assets[__VLS_ctx.active]))) {
        // @ts-ignore
        [active, config,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            key: (i),
        });
        __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
            ...{ onInput: (__VLS_ctx.changed) },
        });
        (__VLS_ctx.config.assets[__VLS_ctx.active][i]);
        // @ts-ignore
        [active, config, changed,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                        return;
                    if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(__VLS_ctx.active === 'accounts'))
                        return;
                    if (!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                        return;
                    __VLS_ctx.removeValue(__VLS_ctx.config.assets[__VLS_ctx.active], i);
                    // @ts-ignore
                    [active, config, removeValue,];
                } },
            ...{ class: "danger" },
        });
    }
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                    return;
                if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'accounts'))
                    return;
                if (!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                    return;
                __VLS_ctx.addValue(__VLS_ctx.config.assets[__VLS_ctx.active]);
                // @ts-ignore
                [active, config, addValue,];
            } },
    });
    (__VLS_ctx.title);
    // @ts-ignore
    [title,];
}
else if (__VLS_ctx.active === 'recommendations') {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    for (const [role] of __VLS_getVForSourceType((__VLS_ctx.config.roles))) {
        // @ts-ignore
        [config,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            key: (role.id),
            ...{ class: "role-card" },
        });
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
        (role.name);
        __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
        __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
            ...{ onChange: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                        return;
                    if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(__VLS_ctx.active === 'accounts'))
                        return;
                    if (!!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                        return;
                    if (!(__VLS_ctx.active === 'recommendations'))
                        return;
                    __VLS_ctx.updateList(__VLS_ctx.config.assets.recommendations, role.id, $event);
                    // @ts-ignore
                    [config, updateList,];
                } },
            value: (__VLS_ctx.config.assets.recommendations[role.id].join(', ')),
        });
        // @ts-ignore
        [config,];
    }
}
else if (['mappings', 'sql-templates', 'intent', 'conversation', 'parameters', 'layers'].includes(__VLS_ctx.active)) {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    (__VLS_ctx.title);
    // @ts-ignore
    [title,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        disabled: true,
    });
    (__VLS_ctx.config.assets.table);
    // @ts-ignore
    [config,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.textarea, __VLS_elements.textarea)({
        ...{ onInput: (__VLS_ctx.changed) },
        ...{ class: "field-area" },
        value: (__VLS_ctx.config.assets.sql_template),
    });
    // @ts-ignore
    [config, changed,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
}
else if (['sensitive', 'limits', 'masking', 'intercepts'].includes(__VLS_ctx.active)) {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    (__VLS_ctx.title);
    // @ts-ignore
    [title,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        ...{ onChange: (...[$event]) => {
                if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                    return;
                if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'accounts'))
                    return;
                if (!!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'recommendations'))
                    return;
                if (!!(['mappings', 'sql-templates', 'intent', 'conversation', 'parameters', 'layers'].includes(__VLS_ctx.active)))
                    return;
                if (!(['sensitive', 'limits', 'masking', 'intercepts'].includes(__VLS_ctx.active)))
                    return;
                __VLS_ctx.updateList(__VLS_ctx.config.compliance, 'sensitive_words', $event);
                // @ts-ignore
                [config, updateList,];
            } },
        value: (__VLS_ctx.config.compliance.sensitive_words.join(', ')),
    });
    // @ts-ignore
    [config,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        ...{ onInput: (__VLS_ctx.changed) },
        type: "number",
    });
    (__VLS_ctx.config.compliance.max_rows);
    // @ts-ignore
    [config, changed,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        ...{ onChange: (__VLS_ctx.changed) },
        type: "checkbox",
    });
    (__VLS_ctx.config.compliance.masking);
    // @ts-ignore
    [config, changed,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.textarea, __VLS_elements.textarea)({
        ...{ onInput: (__VLS_ctx.changed) },
        ...{ class: "field-area" },
        value: (__VLS_ctx.config.compliance.intercept_message),
    });
    // @ts-ignore
    [config, changed,];
}
else if (['interface', 'system', 'demo-switch', 'wording'].includes(__VLS_ctx.active)) {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    (__VLS_ctx.title);
    // @ts-ignore
    [title,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        ...{ onInput: (__VLS_ctx.changed) },
    });
    (__VLS_ctx.config.system.title);
    // @ts-ignore
    [config, changed,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        ...{ onInput: (__VLS_ctx.changed) },
    });
    (__VLS_ctx.config.system.welcome);
    // @ts-ignore
    [config, changed,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
        ...{ onChange: (__VLS_ctx.changed) },
        value: (__VLS_ctx.config.system.default_role),
    });
    // @ts-ignore
    [config, changed,];
    for (const [role] of __VLS_getVForSourceType((__VLS_ctx.config.roles))) {
        // @ts-ignore
        [config,];
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: (role.id),
        });
        (role.name);
    }
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        ...{ onInput: (__VLS_ctx.changed) },
        type: "number",
        min: "0",
        max: "3000",
    });
    (__VLS_ctx.config.system.simulation_speed);
    // @ts-ignore
    [config, changed,];
    __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
    __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
        ...{ onChange: (__VLS_ctx.changed) },
        type: "checkbox",
    });
    (__VLS_ctx.config.system.show_trace);
    // @ts-ignore
    [config, changed,];
}
else if (__VLS_ctx.active === 'scenarios' || ['shortcuts', 'dashboards', 'fixtures'].includes(__VLS_ctx.active)) {
    // @ts-ignore
    [active, active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    for (const [scene] of __VLS_getVForSourceType((__VLS_ctx.config.scenarios))) {
        // @ts-ignore
        [config,];
        __VLS_asFunctionalElement(__VLS_elements.details, __VLS_elements.details)({
            key: (scene.id),
        });
        __VLS_asFunctionalElement(__VLS_elements.summary, __VLS_elements.summary)({});
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
        (scene.number);
        (scene.name);
        __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
        (scene.cases.length);
        for (const [c] of __VLS_getVForSourceType((scene.cases))) {
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                key: (c.id),
                ...{ class: "case" },
            });
            __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
            (c.role_id);
            for (const [turn] of __VLS_getVForSourceType((c.turns))) {
                __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                    key: (turn.turn),
                });
                __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
                    ...{ onInput: (__VLS_ctx.changed) },
                });
                (turn.question);
                // @ts-ignore
                [changed,];
                __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
                    ...{ onChange: (__VLS_ctx.changed) },
                    value: (turn.expected_status),
                });
                // @ts-ignore
                [changed,];
                __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
                __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
                __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
                __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
                __VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
                    ...{ onInput: (__VLS_ctx.changed) },
                });
                (turn.expected_last_layer);
                // @ts-ignore
                [changed,];
            }
        }
    }
}
else if (['sessions', 'requests', 'sql', 'audit'].includes(__VLS_ctx.active)) {
    // @ts-ignore
    [active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "log-tools" },
    });
    __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
        value: (__VLS_ctx.filter),
    });
    // @ts-ignore
    [filter,];
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "",
    });
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.loadLogs) },
    });
    // @ts-ignore
    [loadLogs,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.exportRows) },
    });
    // @ts-ignore
    [exportRows,];
    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
    (__VLS_ctx.rows.length);
    // @ts-ignore
    [rows,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "table-wrap" },
    });
    __VLS_asFunctionalElement(__VLS_elements.table, __VLS_elements.table)({});
    __VLS_asFunctionalElement(__VLS_elements.thead, __VLS_elements.thead)({});
    __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
    for (const [k] of __VLS_getVForSourceType((Object.keys(__VLS_ctx.rows[0] || {})))) {
        // @ts-ignore
        [rows,];
        __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({
            key: (k),
        });
        (k);
    }
    __VLS_asFunctionalElement(__VLS_elements.tbody, __VLS_elements.tbody)({});
    for (const [row, i] of __VLS_getVForSourceType((__VLS_ctx.rows))) {
        // @ts-ignore
        [rows,];
        __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                        return;
                    if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(__VLS_ctx.active === 'accounts'))
                        return;
                    if (!!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(__VLS_ctx.active === 'recommendations'))
                        return;
                    if (!!(['mappings', 'sql-templates', 'intent', 'conversation', 'parameters', 'layers'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(['sensitive', 'limits', 'masking', 'intercepts'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(['interface', 'system', 'demo-switch', 'wording'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(__VLS_ctx.active === 'scenarios' || ['shortcuts', 'dashboards', 'fixtures'].includes(__VLS_ctx.active)))
                        return;
                    if (!(['sessions', 'requests', 'sql', 'audit'].includes(__VLS_ctx.active)))
                        return;
                    __VLS_ctx.inspect(row);
                    // @ts-ignore
                    [inspect,];
                } },
            key: (i),
        });
        for (const [value, k] of __VLS_getVForSourceType((row))) {
            __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({
                key: (k),
            });
            __VLS_asFunctionalElement(__VLS_elements.code, __VLS_elements.code)({});
            (typeof value === 'string' && value.length > 100 ? value.slice(0, 100) + '…' : value);
        }
    }
    if (!__VLS_ctx.rows.length) {
        // @ts-ignore
        [rows,];
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
            ...{ class: "empty" },
        });
    }
    if (__VLS_ctx.selected) {
        // @ts-ignore
        [selected,];
        __VLS_asFunctionalElement(__VLS_elements.pre, __VLS_elements.pre)({
            ...{ class: "log-detail" },
        });
        (JSON.stringify(__VLS_ctx.selected, null, 2));
        // @ts-ignore
        [selected,];
    }
}
else if (__VLS_ctx.active === 'models' || __VLS_ctx.active === 'datasources') {
    // @ts-ignore
    [active, active,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    for (const [p] of __VLS_getVForSourceType((__VLS_ctx.active === 'models' ? ['mock', 'openai-compatible'] : ['sqlite', 'clickhouse', 'mysql']))) {
        // @ts-ignore
        [active,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            key: (p),
            ...{ class: "provider" },
        });
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
        (p);
        __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({
            ...{ class: ({ ok: ['mock', 'sqlite'].includes(p) }) },
        });
        (['mock', 'sqlite'].includes(p) ? 'READY' : (__VLS_ctx.isOffline ? 'POC 中配置' : 'PHASE 2'));
        // @ts-ignore
        [isOffline,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                        return;
                    if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(__VLS_ctx.active === 'accounts'))
                        return;
                    if (!!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(__VLS_ctx.active === 'recommendations'))
                        return;
                    if (!!(['mappings', 'sql-templates', 'intent', 'conversation', 'parameters', 'layers'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(['sensitive', 'limits', 'masking', 'intercepts'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(['interface', 'system', 'demo-switch', 'wording'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(__VLS_ctx.active === 'scenarios' || ['shortcuts', 'dashboards', 'fixtures'].includes(__VLS_ctx.active)))
                        return;
                    if (!!(['sessions', 'requests', 'sql', 'audit'].includes(__VLS_ctx.active)))
                        return;
                    if (!(__VLS_ctx.active === 'models' || __VLS_ctx.active === 'datasources'))
                        return;
                    __VLS_ctx.provider(p);
                    // @ts-ignore
                    [provider,];
                } },
        });
        (['mock', 'sqlite'].includes(p) ? '健康检查' : '查看能力');
    }
    if (!__VLS_ctx.isOffline) {
        // @ts-ignore
        [isOffline,];
        __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
        __VLS_asFunctionalElement(__VLS_elements.textarea, __VLS_elements.textarea)({
            ...{ class: "field-area" },
            value: (__VLS_ctx.phase2Json),
            'aria-label': "Phase 2 Provider JSON",
        });
        // @ts-ignore
        [phase2Json,];
        __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
            ...{ onClick: (__VLS_ctx.createPhase2) },
            ...{ class: "primary" },
            disabled: (__VLS_ctx.busy),
        });
        // @ts-ignore
        [busy, createPhase2,];
        for (const [profile] of __VLS_getVForSourceType((__VLS_ctx.phase2Profiles))) {
            // @ts-ignore
            [phase2Profiles,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                key: (profile.id),
                ...{ class: "provider" },
            });
            __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
            (profile.name);
            __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({
                ...{ class: ({ ok: profile.status === 'ENABLED' }) },
            });
            (profile.status);
            __VLS_asFunctionalElement(__VLS_elements.code, __VLS_elements.code)({});
            (profile.datasource_type);
        }
    }
    else {
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
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
        ...{ class: "actions" },
    });
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                    return;
                if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'accounts'))
                    return;
                if (!!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'recommendations'))
                    return;
                if (!!(['mappings', 'sql-templates', 'intent', 'conversation', 'parameters', 'layers'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['sensitive', 'limits', 'masking', 'intercepts'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['interface', 'system', 'demo-switch', 'wording'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'scenarios' || ['shortcuts', 'dashboards', 'fixtures'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['sessions', 'requests', 'sql', 'audit'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'models' || __VLS_ctx.active === 'datasources'))
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
                if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                    return;
                if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'accounts'))
                    return;
                if (!!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'recommendations'))
                    return;
                if (!!(['mappings', 'sql-templates', 'intent', 'conversation', 'parameters', 'layers'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['sensitive', 'limits', 'masking', 'intercepts'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['interface', 'system', 'demo-switch', 'wording'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'scenarios' || ['shortcuts', 'dashboards', 'fixtures'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['sessions', 'requests', 'sql', 'audit'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'models' || __VLS_ctx.active === 'datasources'))
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
                if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                    return;
                if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'accounts'))
                    return;
                if (!!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'recommendations'))
                    return;
                if (!!(['mappings', 'sql-templates', 'intent', 'conversation', 'parameters', 'layers'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['sensitive', 'limits', 'masking', 'intercepts'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['interface', 'system', 'demo-switch', 'wording'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'scenarios' || ['shortcuts', 'dashboards', 'fixtures'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['sessions', 'requests', 'sql', 'audit'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'models' || __VLS_ctx.active === 'datasources'))
                    return;
                if (!(__VLS_ctx.active === 'recovery'))
                    return;
                __VLS_ctx.recovery('mock-data');
                // @ts-ignore
                [recovery,];
            } },
        ...{ class: "danger" },
    });
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
}
else {
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "panel editor" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
    (__VLS_ctx.title);
    // @ts-ignore
    [title,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.textarea, __VLS_elements.textarea)({
        ...{ onChange: (...[$event]) => {
                if (!!(__VLS_ctx.active === 'home' || __VLS_ctx.active === 'readiness'))
                    return;
                if (!!(['roles', 'permissions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'accounts'))
                    return;
                if (!!(['metrics', 'dimensions'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'recommendations'))
                    return;
                if (!!(['mappings', 'sql-templates', 'intent', 'conversation', 'parameters', 'layers'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['sensitive', 'limits', 'masking', 'intercepts'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['interface', 'system', 'demo-switch', 'wording'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'scenarios' || ['shortcuts', 'dashboards', 'fixtures'].includes(__VLS_ctx.active)))
                    return;
                if (!!(['sessions', 'requests', 'sql', 'audit'].includes(__VLS_ctx.active)))
                    return;
                if (!!(__VLS_ctx.active === 'models' || __VLS_ctx.active === 'datasources'))
                    return;
                if (!!(__VLS_ctx.active === 'recovery'))
                    return;
                __VLS_ctx.config = JSON.parse($event.target.value);
                __VLS_ctx.changed();
                // @ts-ignore
                [config, changed,];
            } },
        value: (JSON.stringify(__VLS_ctx.config, null, 2)),
    });
    // @ts-ignore
    [config,];
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
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['wide']} */ ;
/** @type {__VLS_StyleScopedClasses['ok']} */ ;
/** @type {__VLS_StyleScopedClasses['ok']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['role-card']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['dictionary']} */ ;
/** @type {__VLS_StyleScopedClasses['danger']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['role-card']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['field-area']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['field-area']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['case']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['log-tools']} */ ;
/** @type {__VLS_StyleScopedClasses['table-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['log-detail']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['provider']} */ ;
/** @type {__VLS_StyleScopedClasses['ok']} */ ;
/** @type {__VLS_StyleScopedClasses['field-area']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['provider']} */ ;
/** @type {__VLS_StyleScopedClasses['ok']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['danger']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['editor']} */ ;
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
            config: config,
            ready: ready,
            rows: rows,
            busy: busy,
            message: message,
            draft: draft,
            filter: filter,
            selected: selected,
            phase2Profiles: phase2Profiles,
            phase2Json: phase2Json,
            title: title,
            toggle: toggle,
            open: open,
            close: close,
            changed: changed,
            updateList: updateList,
            addValue: addValue,
            removeValue: removeValue,
            inspect: inspect,
            exportRows: exportRows,
            loadLogs: loadLogs,
            save: save,
            publish: publish,
            provider: provider,
            createPhase2: createPhase2,
            recovery: recovery,
            download: download,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
    },
});
; /* PartiallyEnd: #4569/main.vue */

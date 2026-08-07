import { computed, nextTick, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { PocApiAdapter } from './adapters/poc';
import { OfflineAdapter } from './adapters/offline';
const router = useRouter(), offline = location.protocol === 'file:' || new URLSearchParams(location.search).has('offline'), adapter = offline ? new OfflineAdapter() : new PocApiAdapter();
const roles = [['admin', '张总｜总行行长（全机构+全指标权限）'], ['beijing', '李总｜分行行长（北京分行权限）'], ['retail', '王总｜业务负责人（零售信贷业务权限）']];
const scenes = ['基础查数（机构/指标权限）', 'BI驾驶舱跳转', '模糊问句兜底推荐', '同比归因分析', '越权权限拦截', '多轮上下文追问', '缺失参数交互式补全', '纯取数+二次归因连贯会话'];
const defaults = { admin: ['2026年3月上海分行对公贷款投放金额', '查看全行经营指标分析大盘', '查一下2026年3月银行贷款相关数据', '2026年3月北京分行贷款投放同比去年变化', '查询客户身份证号和贷款明细', '2026年3月北京分行零售贷款投放金额', '查询贷款投放同比数据', '2026年3月全行对公贷款投放金额'], beijing: ['2026年3月北京分行对公贷款投放金额', '查看北京分行经营指标分析大盘', '查一下2026年3月北京分行贷款相关数据', '2026年3月北京分行贷款投放同比去年变化', '查询上海分行2026年3月对公贷款数据', '2026年3月北京分行零售贷款投放金额', '查询贷款投放同比数据', '2026年3月北京分行对公贷款投放金额'], retail: ['2026年3月全行零售贷款投放金额', '查看零售信贷专项经营驾驶舱', '查一下2026年3月零售贷款相关数据', '2026年3月全行零售贷款同比去年变化', '查询2026年3月对公贷款投放', '2026年3月全行零售贷款投放金额', '查询零售贷款同比数据', '2026年3月全行零售贷款投放金额'] };
const layerNames = { L1: '交互层', L2: '对话理解层', L3: '语义层', L4: '数据资产层', L5: '查询生成层', L6: '执行层', L7: '问数解读层' };
const role = ref('admin'), session = ref(), question = ref(''), active = ref(0), turns = ref([]), parent = ref(), executionMode = ref('PHASE1_DEMO'), providerProfiles = ref([]), providerProfileId = ref(''), sessionError = ref(''), chat = ref();
const currentRole = computed(() => roles.find(x => x[0] === role.value)?.[1]), running = computed(() => turns.value.some(x => x.running));
async function scroll() { await nextTick(); if (chat.value)
    chat.value.scrollTop = chat.value.scrollHeight; }
async function loadProfiles() { if (!offline) {
    providerProfiles.value = (await adapter.admin('/phase2/providers')).items;
    const available = providerProfiles.value.filter(x => x.selectable);
    if (!available.some(x => x.id === providerProfileId.value))
        providerProfileId.value = available[0]?.id || '';
} }
async function newSession() { sessionError.value = ''; session.value = undefined; try {
    if (executionMode.value.startsWith('PHASE2') && !providerProfileId.value)
        throw new Error('没有可用的二期Provider Profile。请在后台新增真实模型与数据源连接，执行诊断并启用。');
    session.value = await adapter.createSession(role.value, offline ? {} : { execution_mode: executionMode.value, provider_profile_id: executionMode.value.startsWith('PHASE2') ? providerProfileId.value : undefined });
    parent.value = undefined;
}
catch (e) {
    sessionError.value = String(e);
} }
async function roleChanged() { turns.value = []; await newSession(); turns.value.push({ id: 'notice-' + Date.now(), question: '', scene: 0, sceneName: '系统提示', role: role.value, events: [{ type: 'notice', output: { message: '已切换演示角色，聊天界面与权限缓存已清空，旧会话记录仍保留。' } }], running: false, displayText: '已切换演示角色，聊天界面与权限缓存已清空，旧会话记录仍保留。', outputQueue: [], typing: false, waiting: false }); }
function sceneClick(i) { active.value = i; question.value = defaults[role.value][i]; run(question.value, i); }
const terminalStates = new Set(['SUCCEEDED', 'FAILED', 'BLOCKED', 'SHORT_CIRCUITED', 'WAITING_INPUT', 'PARTIAL_SUCCESS', 'CANCELLED']);
async function watchTerminal(id, turn) { for (let i = 0; i < 120 && turn.running; i++) {
    await new Promise(r => setTimeout(r, 500));
    try {
        const detail = await adapter.detail(id);
        if (terminalStates.has(String(detail.request.status))) {
            turn.detail = detail;
            turn.running = false;
            await scroll();
            return;
        }
    }
    catch { }
} }
function clearLayerWait(t) { if (t.waitTimer)
    window.clearTimeout(t.waitTimer); t.waitTimer = undefined; t.waiting = false; }
function armLayerWait(t) { clearLayerWait(t); t.waitTimer = window.setTimeout(() => { if (t.running)
    t.waiting = true; scroll(); }, 3000); }
async function drainOutput(t) { if (t.typing)
    return; t.typing = true; while (t.outputQueue.length) {
    const chunk = t.outputQueue.shift() || '';
    for (const char of chunk) {
        t.displayText += char;
        await new Promise(r => setTimeout(r, 12));
        if (t.displayText.length % 8 === 0)
            scroll();
    }
} t.typing = false; await scroll(); }
function enqueueOutput(t, text) { if (!text)
    return; t.outputQueue.push(text); void drainOutput(t); }
function layerTranscript(t, e) { const completed = t.events.filter(x => x.type === 'layer.completed').length; const prefix = completed > 1 ? '\n\n' : ''; const result = e.layer_code === 'L7' ? '解读已完成，正在流式生成最终答复…' : outputText(e); return `${prefix}✓ ${e.layer_code} ${layerNames[e.layer_code]}  ·  ${e.status}\n${result}`; }
async function run(text = question.value, scene = active.value) { if (!session.value || !text.trim() || running.value)
    return; active.value = scene; question.value = ''; turns.value.push({ id: 'pending-' + Date.now(), question: text, scene: scene + 1, sceneName: scenes[scene], role: role.value, events: [], running: true, streamedAnswer: '', displayText: '', outputQueue: [], typing: false, waiting: false }); const turn = turns.value[turns.value.length - 1]; await scroll(); try {
    const id = await adapter.query(session.value.id, text, 'scenario-' + (scene + 1), parent.value);
    turn.id = id;
    parent.value = id;
    void watchTerminal(id, turn);
    await adapter.events(id, e => { turn.events.push(e); if (e.type === 'layer.started')
        armLayerWait(turn); if (e.type === 'layer.completed') {
        clearLayerWait(turn);
        enqueueOutput(turn, layerTranscript(turn, e));
    } if (e.type === 'answer.delta') {
        const delta = String(e.delta || '');
        turn.streamedAnswer = (turn.streamedAnswer || '') + delta;
        enqueueOutput(turn, delta);
    } if (e.type === 'request.completed' || e.type === 'request.cancelled') {
        clearLayerWait(turn);
        turn.running = false;
    } scroll(); });
    turn.detail = await adapter.detail(id);
}
catch (e) {
    clearLayerWait(turn);
    turn.error = String(e);
}
finally {
    clearLayerWait(turn);
    turn.running = false;
    await scroll();
} }
async function stop() { const t = turns.value.find(x => x.running); if (t && !t.id.startsWith('pending-'))
    await adapter.cancel(t.id); }
function outputText(e) { const o = e.output || {}; if (o.message)
    return o.message; if (o.answer)
    return o.answer; if (o.normalized_question)
    return '标准化问句：' + o.normalized_question; if (o.parameters)
    return '识别参数：' + JSON.stringify(o.parameters); if (o.dashboard)
    return '匹配驾驶舱：' + o.dashboard; if (o.table || o.metric)
    return '选定资产：' + [o.provider, o.table, o.metric].filter(Boolean).join(' / '); if (o.queries)
    return '生成 ' + o.queries.length + ' 条参数化SQL'; if (o.row_count !== undefined)
    return '返回 ' + o.row_count + ' 行，来源：' + (o.sources || []).join(','); return JSON.stringify(o); }
function terminalOutput(t) { return (t.detail?.layers.at(-1)?.output || {}); }
function dashboardItems(t) { const configured = terminalOutput(t).dashboards; if (configured?.length)
    return configured; return t.role === 'admin' ? [{ name: '总行行长经营驾驶舱', url: '/dashboards/head-office.html' }] : t.role === 'beijing' ? [{ name: '分行行长经营驾驶舱', url: '/dashboards/branch-president.html' }] : [{ name: '业务负责人专项驾驶舱', url: '/dashboards/business-owner.html' }]; }
function resultText(t) { const o = terminalOutput(t); if (t.scene === 2)
    return '根据当前角色权限，为您匹配可访问的经营大盘：'; return t.streamedAnswer || o.answer || o.message || t.detail?.request.status || ''; }
function chartSpec(t) { return terminalOutput(t).chart || null; }
function chartRows(t) { const spec = chartSpec(t), rows = t.detail?.result || []; if (!spec || !rows.length)
    return []; const series = (spec.series || []).filter((key) => rows.some((r) => Number(r[key]))); return rows.flatMap((row) => series.map((key) => ({ label: `${row[spec.category_field] || row.org_name || '结果'}·${key === 'previous_value' ? '同期' : '本期'}`, value: Number(row[key] || 0) }))); }
function chartWidth(t, value) { const max = Math.max(1, ...chartRows(t).map(x => Math.abs(x.value))); return Math.max(5, Math.abs(value) / max * 100) + '%'; }
function optionQuery(t, value) { const base = terminalOutput(t).options || []; const chosen = value.includes('2026') ? '2026年3月' : value; const org = chosen.includes('分行') || chosen === '全行' ? chosen : (base.find((x) => x.includes('分行') || x === '全行') || '全行'); const metric = chosen.includes('贷款') ? chosen : '贷款投放'; return [chosen.includes('2026') ? chosen : '2026年3月', org, metric].join('，'); }
function guideScene(text, current) { if (text.includes('驾驶舱'))
    return 1; if (text.includes('同比'))
    return 3; return current - 1; }
function layerInput(t, e) { if (e.layer_code === 'L1')
    return '原始问句：' + t.question; if (e.layer_code === 'L2')
    return '标准化问句 + 当前角色权限快照：' + currentRole.value; if (e.layer_code === 'L3')
    return '已识别业务参数与意图'; if (e.layer_code === 'L4')
    return '语义计划与已发布资产配置'; if (e.layer_code === 'L5')
    return '受控资产映射与SQL模板'; if (e.layer_code === 'L6')
    return '参数化SQL计划'; return 'L6实际执行结果'; }
onMounted(async () => { await loadProfiles(); await newSession(); });
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_elements;
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "ask-page" },
});
__VLS_asFunctionalElement(__VLS_elements.header, __VLS_elements.header)({
    ...{ class: "ask-header" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "ask-title" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "header-controls" },
});
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.router.push('/admin');
            // @ts-ignore
            [router,];
        } },
});
if (!__VLS_ctx.offline) {
    // @ts-ignore
    [offline,];
    __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
        ...{ onChange: (__VLS_ctx.newSession) },
        value: (__VLS_ctx.executionMode),
    });
    // @ts-ignore
    [newSession, executionMode,];
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({});
}
if (!__VLS_ctx.offline && __VLS_ctx.executionMode.startsWith('PHASE2')) {
    // @ts-ignore
    [offline, executionMode,];
    __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
        ...{ onChange: (__VLS_ctx.newSession) },
        value: (__VLS_ctx.providerProfileId),
    });
    // @ts-ignore
    [newSession, providerProfileId,];
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "",
        disabled: true,
    });
    for (const [p] of __VLS_getVForSourceType((__VLS_ctx.providerProfiles.filter(x => x.selectable)))) {
        // @ts-ignore
        [providerProfiles,];
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: (p.id),
        });
        (p.name);
        (p.diagnostic_status);
    }
}
__VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
__VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
    ...{ onChange: (__VLS_ctx.roleChanged) },
    value: (__VLS_ctx.role),
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
if (__VLS_ctx.sessionError) {
    // @ts-ignore
    [sessionError,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "session-error" },
    });
    (__VLS_ctx.sessionError);
    // @ts-ignore
    [sessionError,];
}
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ref: "chat",
    ...{ class: "chat-wrap" },
});
/** @type {typeof __VLS_ctx.chat} */ ;
// @ts-ignore
[chat,];
if (!__VLS_ctx.turns.length) {
    // @ts-ignore
    [turns,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "welcome-bubble" },
    });
    __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
    (__VLS_ctx.currentRole);
    // @ts-ignore
    [currentRole,];
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
    (__VLS_ctx.offline ? 'Offline Demo 本地模拟' : 'POC 七层真实执行');
    // @ts-ignore
    [offline,];
}
for (const [t] of __VLS_getVForSourceType((__VLS_ctx.turns))) {
    // @ts-ignore
    [turns,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        key: (t.id),
        ...{ class: "conversation-turn" },
    });
    if (t.question) {
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "msg-item user-msg" },
        });
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "user-bubble" },
        });
        (t.question);
    }
    if (t.displayText || t.running || t.waiting) {
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "msg-item ai-msg" },
        });
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "ai-bubble unified-trace-bubble" },
        });
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "unified-trace-head" },
        });
        __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "stream-transcript" },
        });
        (t.displayText);
        if (t.typing) {
            __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
                ...{ class: "typing-cursor" },
            });
        }
        if (t.waiting) {
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "layer-wait" },
            });
            __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({});
            __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
        }
    }
    if (t.detail) {
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "msg-item ai-msg" },
        });
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "ai-bubble result-bubble" },
        });
        __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({
            ...{ class: "scene-tag" },
        });
        (t.scene);
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({
            ...{ class: "stream-answer" },
        });
        (__VLS_ctx.resultText(t));
        if (t.running) {
            // @ts-ignore
            [resultText,];
            __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
                ...{ class: "typing-cursor" },
            });
        }
        if (t.scene === 2) {
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "dashboard-result" },
            });
            __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
            for (const [x] of __VLS_getVForSourceType((__VLS_ctx.dashboardItems(t)))) {
                // @ts-ignore
                [dashboardItems,];
                __VLS_asFunctionalElement(__VLS_elements.a, __VLS_elements.a)({
                    href: (x.url),
                    target: "_blank",
                    rel: "noopener",
                    ...{ class: "dashboard-link" },
                });
                (x.name);
            }
            if (t.role === 'beijing') {
                __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
                    ...{ class: "role-filter" },
                });
            }
            if (t.role === 'retail') {
                __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
                    ...{ class: "role-filter" },
                });
            }
        }
        if (__VLS_ctx.chartRows(t).length) {
            // @ts-ignore
            [chartRows,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "result-chart" },
            });
            __VLS_asFunctionalElement(__VLS_elements.h4, __VLS_elements.h4)({});
            (__VLS_ctx.chartSpec(t)?.title);
            // @ts-ignore
            [chartSpec,];
            for (const [bar] of __VLS_getVForSourceType((__VLS_ctx.chartRows(t)))) {
                // @ts-ignore
                [chartRows,];
                __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                    ...{ class: "result-chart-row" },
                });
                __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
                (bar.label);
                __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({});
                __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({
                    ...{ style: ({ width: __VLS_ctx.chartWidth(t, bar.value) }) },
                });
                // @ts-ignore
                [chartWidth,];
                __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
                (bar.value.toLocaleString());
            }
        }
        if (t.detail.result.length) {
            __VLS_asFunctionalElement(__VLS_elements.table, __VLS_elements.table)({});
            __VLS_asFunctionalElement(__VLS_elements.thead, __VLS_elements.thead)({});
            __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
            for (const [_, k] of __VLS_getVForSourceType((t.detail.result[0]))) {
                __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
                (k);
            }
            __VLS_asFunctionalElement(__VLS_elements.tbody, __VLS_elements.tbody)({});
            for (const [r] of __VLS_getVForSourceType((t.detail.result))) {
                __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
                for (const [v] of __VLS_getVForSourceType((r))) {
                    __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
                    (v);
                }
            }
        }
        if (!t.detail.sql_executions?.length) {
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "no-sql" },
            });
            (t.detail.request.last_layer || '前置层');
        }
        if (t.detail.sql_executions?.length) {
            __VLS_asFunctionalElement(__VLS_elements.details, __VLS_elements.details)({});
            __VLS_asFunctionalElement(__VLS_elements.summary, __VLS_elements.summary)({});
            (t.detail.sql_executions.length);
            __VLS_asFunctionalElement(__VLS_elements.pre, __VLS_elements.pre)({});
            (JSON.stringify(t.detail.sql_executions, null, 2));
        }
        if (__VLS_ctx.terminalOutput(t).guides?.length) {
            // @ts-ignore
            [terminalOutput,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "guide-box" },
            });
            __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
            for (const [x] of __VLS_getVForSourceType((__VLS_ctx.terminalOutput(t).guides))) {
                // @ts-ignore
                [terminalOutput,];
                __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!(t.detail))
                                return;
                            if (!(__VLS_ctx.terminalOutput(t).guides?.length))
                                return;
                            __VLS_ctx.run(x, __VLS_ctx.guideScene(x, t.scene));
                            // @ts-ignore
                            [run, guideScene,];
                        } },
                });
                (x);
            }
        }
        if (__VLS_ctx.terminalOutput(t).recommendations?.length) {
            // @ts-ignore
            [terminalOutput,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "option-row" },
            });
            for (const [x] of __VLS_getVForSourceType((__VLS_ctx.terminalOutput(t).recommendations))) {
                // @ts-ignore
                [terminalOutput,];
                __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!(t.detail))
                                return;
                            if (!(__VLS_ctx.terminalOutput(t).recommendations?.length))
                                return;
                            __VLS_ctx.run(x, t.scene - 1);
                            // @ts-ignore
                            [run,];
                        } },
                });
                (x);
            }
        }
        if (__VLS_ctx.terminalOutput(t).options?.length) {
            // @ts-ignore
            [terminalOutput,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "option-row" },
            });
            for (const [x] of __VLS_getVForSourceType((__VLS_ctx.terminalOutput(t).options))) {
                // @ts-ignore
                [terminalOutput,];
                __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!(t.detail))
                                return;
                            if (!(__VLS_ctx.terminalOutput(t).options?.length))
                                return;
                            __VLS_ctx.run(__VLS_ctx.optionQuery(t, x), t.scene - 1);
                            // @ts-ignore
                            [run, optionQuery,];
                        } },
                });
                (x);
            }
        }
    }
    if (t.error) {
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "msg-item ai-msg" },
        });
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "ai-bubble error" },
        });
        (t.error);
    }
}
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "quick-chat-bar" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "quick-chat-title" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "quick-chat-buttons" },
});
for (const [s, i] of __VLS_getVForSourceType((__VLS_ctx.scenes))) {
    // @ts-ignore
    [scenes,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.sceneClick(i);
                // @ts-ignore
                [sceneClick,];
            } },
        ...{ class: ({ selected: __VLS_ctx.active === i }) },
    });
    // @ts-ignore
    [active,];
    (i + 1);
    (s);
}
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "input-footer" },
});
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.question = '2026年3月各分行零售贷款同比变化';
            // @ts-ignore
            [question,];
        } },
    ...{ class: "voice-btn" },
});
__VLS_asFunctionalElement(__VLS_elements.input, __VLS_elements.input)({
    ...{ onKeydown: (...[$event]) => {
            __VLS_ctx.run();
            // @ts-ignore
            [run,];
        } },
    disabled: (!__VLS_ctx.session),
    placeholder: "输入自然语言提问，支持8大场景、多轮追问、权限校验",
});
(__VLS_ctx.question);
// @ts-ignore
[question, session,];
if (__VLS_ctx.running) {
    // @ts-ignore
    [running,];
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
                if (!!(__VLS_ctx.running))
                    return;
                __VLS_ctx.run();
                // @ts-ignore
                [run,];
            } },
        disabled: (!__VLS_ctx.session),
    });
    // @ts-ignore
    [session,];
}
/** @type {__VLS_StyleScopedClasses['ask-page']} */ ;
/** @type {__VLS_StyleScopedClasses['ask-header']} */ ;
/** @type {__VLS_StyleScopedClasses['ask-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['session-error']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['welcome-bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['conversation-turn']} */ ;
/** @type {__VLS_StyleScopedClasses['msg-item']} */ ;
/** @type {__VLS_StyleScopedClasses['user-msg']} */ ;
/** @type {__VLS_StyleScopedClasses['user-bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['msg-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-msg']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['unified-trace-bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['unified-trace-head']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-transcript']} */ ;
/** @type {__VLS_StyleScopedClasses['typing-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['layer-wait']} */ ;
/** @type {__VLS_StyleScopedClasses['msg-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-msg']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['result-bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['scene-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-answer']} */ ;
/** @type {__VLS_StyleScopedClasses['typing-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-result']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-link']} */ ;
/** @type {__VLS_StyleScopedClasses['role-filter']} */ ;
/** @type {__VLS_StyleScopedClasses['role-filter']} */ ;
/** @type {__VLS_StyleScopedClasses['result-chart']} */ ;
/** @type {__VLS_StyleScopedClasses['result-chart-row']} */ ;
/** @type {__VLS_StyleScopedClasses['no-sql']} */ ;
/** @type {__VLS_StyleScopedClasses['guide-box']} */ ;
/** @type {__VLS_StyleScopedClasses['option-row']} */ ;
/** @type {__VLS_StyleScopedClasses['option-row']} */ ;
/** @type {__VLS_StyleScopedClasses['msg-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-msg']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-chat-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-chat-title']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-chat-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['selected']} */ ;
/** @type {__VLS_StyleScopedClasses['input-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['voice-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['stop']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            router: router,
            offline: offline,
            roles: roles,
            scenes: scenes,
            role: role,
            session: session,
            question: question,
            active: active,
            turns: turns,
            executionMode: executionMode,
            providerProfiles: providerProfiles,
            providerProfileId: providerProfileId,
            sessionError: sessionError,
            chat: chat,
            currentRole: currentRole,
            running: running,
            newSession: newSession,
            roleChanged: roleChanged,
            sceneClick: sceneClick,
            run: run,
            stop: stop,
            terminalOutput: terminalOutput,
            dashboardItems: dashboardItems,
            resultText: resultText,
            chartSpec: chartSpec,
            chartRows: chartRows,
            chartWidth: chartWidth,
            optionQuery: optionQuery,
            guideScene: guideScene,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
    },
});
; /* PartiallyEnd: #4569/main.vue */

import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { PocApiAdapter } from "./adapters/poc";
import { OfflineAdapter } from "./adapters/offline";
import { isOffline } from "./runtime";
const router = useRouter(), adapter = isOffline ? new OfflineAdapter() : new PocApiAdapter(), scrollBox = ref(), bottomAnchor = ref();
const roles = [
    ["admin", "张总"],
    ["beijing", "李总"],
    ["retail", "王总"],
];
const role = ref("admin"), mode = ref("DEMO"), scenario = ref("MT01"), session = ref(), providerProfiles = ref([]), providerProfileId = ref(""), question = ref("同时查询2026年一季度贷款投放、存款余额、不良率和中收，并统一汇总同比变化"), submittedQuestion = ref(""), requestId = ref(""), detail = ref(), events = ref([]), running = ref(false), presenting = ref(false), confirming = ref(false), cancelledPresentation = ref(false), error = ref(""), startedAt = ref(0), elapsed = ref(0), displayedIntro = ref(""), displayedAnswer = ref(""), answerTyping = ref(false), processOpen = ref(true), planPresented = ref(false), taskLabels = ref({}), taskPresentationState = ref({}), layerLabels = ref({}), planLabel = ref(""), summaryLabel = ref("");
const intro = computed(() => {
    const copy = {
        MT01: "我来帮你查询并汇总这些指标。我会先拆解查询目标，再并行核对每项指标，最后只使用执行成功的事实生成结论。",
        MT02: "我先核实贷款投放同比变化，再按照依赖关系检查关联指标和可用下钻维度，最后说明能够得到的结论及数据边界。",
        MT03: "我会先生成本次问数的任务计划，展示计划版本和关键节点，确认完成后再执行查询。",
        MT04: "我会把趋势和排名查询拆成长任务节点，持续展示执行状态；执行期间可以随时停止。",
        MT05: "我会查询核心经营指标，并保留每个节点的独立执行记录；临时失败只影响对应节点。",
        MT06: "我会分别查询核心经营指标和补充指标，并按照节点关键性裁决整体结果，只汇总已经核实的事实。",
        MT07: "我会先核实形成总体判断所必需的核心事实；如果关键事实不完整，将不会生成不可靠的总体结论。",
        MT08: "我会读取当前会话中可验证的上一轮事实，比较本轮扩展目标，只复用仍然有效且权限一致的结果。",
    };
    return copy[scenario.value] || copy.MT01;
});
const shortcuts = [
    ["MT01", "多指标并行汇总"],
    ["MT02", "下降指标归因"],
    ["MT03", "计划预览调整"],
    ["MT04", "趋势与机构排名"],
    ["MT05", "核心指标查询"],
    ["MT06", "经营指标汇总"],
    ["MT07", "整体经营判断"],
    ["MT08", "多轮计划扩展"],
];
const scenarioName = computed(() => shortcuts.find((item) => item[0] === scenario.value)?.[1] || "多任务问数");
const demoQuestions = {
    MT01: "同时查询2026年一季度贷款投放、存款余额、不良率和中收，并统一汇总同比变化",
    MT02: "贷款投放同比下降了吗？请按客户类型和机构进一步分析原因",
    MT03: "请查询一季度核心经营指标，执行前先展示任务计划供我确认",
    MT04: "请查询近12个月贷款投放趋势和各机构排名",
    MT05: "请同时查询一季度贷款投放、存款余额和不良率",
    MT06: "请汇总一季度贷款投放、存款余额、不良率和中收表现",
    MT07: "请综合判断一季度核心经营指标的整体表现",
    MT08: "在上一轮贷款投放结果基础上，补充查询相关指标并更新结论",
};
const pocQuestions = {
    MT01: "同时查询全行2026年3月贷款投放、零售贷款和对公贷款，并统一汇总同比变化",
    MT02: "全行2026年3月贷款投放同比下降了吗？请继续核对零售贷款和对公贷款",
    MT03: "请查询全行2026年3月核心贷款指标，执行前先展示任务计划供我确认",
    MT04: "请查询全行2026年3月贷款投放、零售贷款和对公贷款，这是一个长任务",
    MT05: "请同时查询全行2026年3月贷款投放、零售贷款和对公贷款",
    MT06: "请汇总全行2026年3月贷款投放、零售贷款和对公贷款表现",
    MT07: "请综合判断全行2026年3月核心贷款指标的整体表现",
    MT08: "在上一轮贷款投放结果基础上，补充查询零售贷款并更新结论",
};
const activeQuestions = computed(() => mode.value === "POC" ? pocQuestions : demoQuestions);
const tasks = computed(() => detail.value?.tasks || []), plan = computed(() => detail.value?.plan?.plan), finalOutput = computed(() => detail.value?.layers?.at(-1)?.output || {}), scenarioPresentation = computed(() => finalOutput.value.presentation || {}), answer = computed(() => finalOutput.value.answer || ""), evidence = computed(() => finalOutput.value.evidence || []), queryTasks = computed(() => tasks.value.filter((x) => x.type === "SQL")), allTasksPresented = computed(() => queryTasks.value.length > 0 &&
    queryTasks.value.every((task) => ["SUCCEEDED", "FAILED", "CANCELLED"].includes(taskPresentationState.value[task.code]))), summaryTask = computed(() => tasks.value.find((x) => x.type === "SUMMARY"));
const globalLayers = computed(() => [1, 2, 3]
    .map((number) => detail.value?.layers?.find((x) => x.layer_code === `L${number}`))
    .filter(Boolean)), interpretationLayer = computed(() => detail.value?.layers?.find((x) => x.layer_code === "L7"));
const waitingConfirmation = computed(() => events.value.some((event) => event.type === "plan.waiting_confirmation") &&
    !events.value.some((event) => event.type === "plan.confirmed"));
const failureMessage = computed(() => {
    if (detail.value?.request?.status !== "FAILED")
        return "";
    return `正式 POC 执行失败：${detail.value.request.termination_reason || "UNKNOWN"}。本次未使用演示数据或降级结果。`;
});
async function scroll() {
    await nextTick();
    const box = scrollBox.value;
    if (!box)
        return;
    box.scrollTop = box.scrollHeight;
    await new Promise((resolve) => requestAnimationFrame(() => resolve()));
    box.scrollTop = box.scrollHeight;
}
async function createSession() {
    error.value = "";
    detail.value = undefined;
    events.value = [];
    submittedQuestion.value = "";
    try {
        if (mode.value === "POC" && !providerProfileId.value)
            throw new Error("正式 POC 需要已启用且诊断通过的二期 Provider Profile。");
        session.value = await adapter.createSession(role.value, isOffline
            ? {}
            : {
                execution_mode: mode.value === "POC" ? "PHASE2_POC" : "PHASE1_DEMO",
                provider_profile_id: mode.value === "POC" ? providerProfileId.value : undefined,
            });
    }
    catch (e) {
        error.value = String(e);
        presenting.value = false;
    }
}
async function loadProfiles() {
    if (isOffline)
        return;
    try {
        providerProfiles.value = (await adapter.admin("/phase2/providers")).items;
        const available = providerProfiles.value.filter((item) => item.selectable && item.diagnostic_status === "READY");
        if (!available.some((item) => item.id === providerProfileId.value))
            providerProfileId.value = available[0]?.id || "";
    }
    catch (e) {
        error.value = String(e);
    }
}
async function setMode(value) {
    if (running.value || presenting.value)
        return;
    mode.value = value;
    question.value = activeQuestions.value[scenario.value];
    if (value === "POC")
        await loadProfiles();
    await createSession();
}
async function typeInto(target, key, value, speed = 28) {
    if (target[key] !== undefined)
        return;
    target[key] = "";
    for (const char of value) {
        if (cancelledPresentation.value &&
            scenario.value === "MT04" &&
            key !== "L7")
            break;
        target[key] += char;
        await new Promise((r) => setTimeout(r, "。；！？".includes(char) ? 75 : "，：".includes(char) ? 45 : speed));
        await scroll();
    }
}
let presentation = Promise.resolve(), queued = new Set(), taskPresentationPromises = [], taskPresentationByCode = new Map(), firstTaskStartedAt = 0;
function enqueue(key, work) {
    if (queued.has(key))
        return;
    queued.add(key);
    presentation = presentation.then(work);
}
function queueGlobalLayers() {
    for (const layer of globalLayers.value)
        enqueue(layer.layer_code, () => typeInto(layerLabels.value, layer.layer_code, `${layer.layer_code} ${layerName(layer.layer_code)}：${layerText(layer)}`));
}
let typingSummary = false;
async function typeSummary() {
    if (typingSummary || summaryLabel.value)
        return;
    typingSummary = true;
    const text = `正在汇总 ${queryTasks.value.length} 个查询任务的成功事实`;
    for (const char of text) {
        if (cancelledPresentation.value && scenario.value === "MT04")
            break;
        summaryLabel.value += char;
        await new Promise((r) => setTimeout(r, 28));
        await scroll();
    }
    typingSummary = false;
}
let typingPlan = false;
async function typePlan() {
    if (typingPlan || planLabel.value)
        return;
    typingPlan = true;
    const text = `已加载 ${scenario.value} ${scenarioName.value}任务计划；${queryTasks.value.length} 个查询任务，最大并行 ${plan.value?.maxConcurrency || 3}`;
    for (const char of text) {
        planLabel.value += char;
        await new Promise((r) => setTimeout(r, 28));
        await scroll();
    }
    planPresented.value = true;
    typingPlan = false;
    await scroll();
}
async function refresh() {
    if (requestId.value) {
        detail.value = await adapter.detail(requestId.value);
        queueGlobalLayers();
        if (plan.value)
            enqueue("PLAN", typePlan);
        for (const task of queryTasks.value)
            if (task.started_at)
                queueParallelTask(String(task.code), taskName(task), Date.parse(task.started_at));
        if (summaryTask.value &&
            ["RUNNING", "SUCCEEDED", "SKIPPED"].includes(summaryTask.value.status) &&
            taskPresentationPromises.length >= queryTasks.value.length)
            enqueue("SUMMARY", async () => {
                await Promise.all(taskPresentationPromises);
                await typeSummary();
            });
        if (interpretationLayer.value)
            enqueue("L7", () => typeInto(layerLabels.value, "L7", `L7 ${layerName("L7")}：${layerText(interpretationLayer.value)}`));
        await scroll();
    }
}
async function typeTask(code, name) {
    if (taskLabels.value[code] !== undefined)
        return;
    taskPresentationState.value[code] = "RUNNING";
    taskLabels.value[code] = "";
    const text = `正在执行${name}指标的查询任务：L4 绑定指标资产与权限；L5 生成参数化查询；L6 执行查询并校验结果`;
    for (const char of text) {
        if (cancelledPresentation.value && scenario.value === "MT04") {
            taskLabels.value[code] += "……已停止";
            taskPresentationState.value[code] = "CANCELLED";
            await scroll();
            return;
        }
        taskLabels.value[code] += char;
        await new Promise((r) => setTimeout(r, "；：".includes(char) ? 55 : 28));
        await scroll();
    }
    const task = queryTasks.value.find((item) => item.code === code);
    taskPresentationState.value[code] = task?.status || "SUCCEEDED";
    await scroll();
}
function queueParallelTask(code, name, startedAt = Date.now()) {
    const key = `TASK-${code}`;
    if (queued.has(key))
        return;
    queued.add(key);
    const eventTime = startedAt;
    if (!firstTaskStartedAt)
        firstTaskStartedAt = eventTime;
    const relativeDelay = eventTime - firstTaskStartedAt;
    const gate = presentation;
    const taskPromise = gate.then(async () => {
        const task = queryTasks.value.find((item) => item.code === code);
        const dependencies = (task?.depends_on || [])
            .map((dependency) => taskPresentationByCode.get(dependency))
            .filter(Boolean);
        if (dependencies.length)
            await Promise.all(dependencies);
        else if (relativeDelay)
            await new Promise((resolve) => setTimeout(resolve, relativeDelay));
        await typeTask(code, name);
    });
    taskPresentationPromises.push(taskPromise);
    taskPresentationByCode.set(code, taskPromise);
}
async function execute() {
    if (!session.value || !question.value.trim() || running.value)
        return;
    running.value = true;
    presenting.value = true;
    cancelledPresentation.value = false;
    error.value = "";
    detail.value = undefined;
    events.value = [];
    taskLabels.value = {};
    taskPresentationState.value = {};
    layerLabels.value = {};
    planLabel.value = "";
    summaryLabel.value = "";
    displayedIntro.value = "";
    planPresented.value = false;
    presentation = Promise.resolve();
    queued = new Set();
    taskPresentationPromises = [];
    taskPresentationByCode = new Map();
    firstTaskStartedAt = 0;
    submittedQuestion.value = question.value;
    startedAt.value = Date.now();
    elapsed.value = 0;
    await scroll();
    const timer = window.setInterval(() => (elapsed.value = Math.max(1, Math.round((Date.now() - startedAt.value) / 1000))), 1000);
    try {
        for (const char of intro.value) {
            displayedIntro.value += char;
            await new Promise((r) => setTimeout(r, "。；！？".includes(char) ? 75 : "，：".includes(char) ? 45 : 28));
            await scroll();
        }
        requestId.value = await adapter.query(session.value.id, question.value, scenario.value, undefined, mode.value);
        await refresh();
        const poll = window.setInterval(() => void refresh(), 100);
        try {
            await adapter.events(requestId.value, (e) => {
                events.value.push(e);
                if (e.type === "task.started") {
                    const code = String(e.code), name = String(e.name || e.code);
                    queueParallelTask(code, name);
                }
                void refresh();
            });
        }
        finally {
            window.clearInterval(poll);
        }
        await refresh();
    }
    catch (e) {
        error.value = String(e);
        presenting.value = false;
    }
    finally {
        window.clearInterval(timer);
        elapsed.value = Math.max(1, Math.round((Date.now() - startedAt.value) / 1000));
        running.value = false;
        await scroll();
    }
}
async function cancel() {
    if (requestId.value) {
        cancelledPresentation.value = true;
        await adapter.cancel(requestId.value);
        await refresh();
    }
}
async function confirmPlan() {
    if (!requestId.value || confirming.value)
        return;
    confirming.value = true;
    try {
        await adapter.confirm(requestId.value);
        await refresh();
    }
    catch (e) {
        error.value = String(e);
    }
    finally {
        confirming.value = false;
    }
}
function node(task) {
    return plan.value?.nodes?.find((x) => x.code === task.code) || {};
}
function taskName(task) {
    return node(task).name || task.code;
}
function taskDescription(task) {
    if (task.type === "SUMMARY")
        return scenario.value === "MT07"
            ? "关键事实失败，跳过总体汇总"
            : "汇总全部已验证指标事实并生成证据化回答";
    const purpose = {
        MT02: "按前置依赖执行关联指标验证",
        MT03: "执行已确认计划中的受控查询节点",
        MT04: "执行可跟踪、可取消的长查询节点",
        MT05: "执行可定点重试且保留成功事实的查询节点",
        MT06: "执行带关键性标记的查询节点",
        MT07: "执行关键事实安全门禁查询",
        MT08: "执行扩展计划并检查可复用事实",
    };
    return `${purpose[scenario.value] || "执行多指标并行查询"}：${taskName(task)}`;
}
function params(task) {
    return {
        organization: task.input?.org,
        metric: task.input?.metric,
        period: task.input?.date || "2026Q1",
        intent: { action: "metric:query", is_write: false, kind: "askdata-v2.1" },
    };
}
function result(task) {
    if (task.status === "RUNNING")
        return "正在查询并校验结果…";
    if (task.status === "WAITING" || task.status === "READY")
        return task.depends_on?.length ? "等待上游任务完成" : "等待执行槽";
    if (task.status === "FAILED")
        return `执行失败：${task.error_code || "TASK_FAILED"}`;
    if (task.type === "SUMMARY")
        return task.output || [];
    return task.output || {};
}
function metricLabel(code) {
    return ({
        loan_issue_amt: "贷款投放",
        deposit_balance: "存款余额",
        npl_ratio: "不良率",
        fee_income: "中收",
        retail_loan_issue_amt: "零售贷款投放",
        active_customer_count: "活跃客户数",
        loan_cur: "贷款投放",
        retail_cur: "零售贷款",
        corporate_cur: "对公贷款",
    }[code] || code);
}
function format(value) {
    return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}
function taskDuration(task) {
    const state = taskPresentationState.value[task.code];
    if (!state || state === "RUNNING")
        return "";
    if (!task.started_at)
        return "";
    const end = task.completed_at ? Date.parse(task.completed_at) : Date.now();
    return (Math.max(0.1, (end - Date.parse(task.started_at)) / 1000).toFixed(1) + "s");
}
function chartWidth(row) {
    const values = (detail.value?.result || []).map((x) => Math.abs(Number(x.changeRate) || 0));
    return (Math.max(8, (Math.abs(Number(row.changeRate) || 0) / Math.max(1, ...values)) * 100) + "%");
}
function layerText(layer) {
    const focus = {
        MT02: {
            L2: "识别下降指标、关联指标与下钻目标",
            L3: "生成前置事实→关联验证的串行依赖计划",
            L7: "汇总已验证关联事实并披露归因数据边界",
        },
        MT03: {
            L2: "识别计划预览与确认要求",
            L3: "生成计划 v1，等待确认后以计划 v2 执行",
            L7: "输出计划确认状态、执行事实与证据",
        },
        MT04: {
            L2: "识别长任务、实时进度与取消意图",
            L3: "生成支持状态跟踪和取消传播的任务计划",
            L7: "输出完成或取消状态及已验证事实",
        },
        MT05: {
            L2: "识别当前已发布配置中的三个核心查询目标",
            L3: "生成三个独立查询节点并绑定节点级超时重试策略",
            L7: "输出重试结果、attempt 状态与成功事实",
        },
        MT06: {
            L2: "识别当前已发布配置中的核心指标和补充指标",
            L3: "按发布配置标记核心事实与补充事实并生成完整性规则",
            L7: "仅基于成功事实输出部分结果和未核实项",
        },
        MT07: {
            L2: "识别整体经营判断所需的全部核心事实",
            L3: "将总体判断绑定到三个核心事实的完整性约束",
            L7: "禁止不完整总体判断并披露终止原因",
        },
        MT08: {
            L2: "解析上一轮上下文和本轮扩展目标",
            L3: "比较计划差异并检查可复用事实",
            L7: "说明复用检查结果和本轮新增事实",
        },
    };
    return (focus[scenario.value]?.[layer.layer_code] ||
        {
            L1: "接收问题并绑定当前用户、会话与配置",
            L2: `识别${queryTasks.value.length || 4}个查询目标、机构和统计周期`,
            L3: `生成${tasks.value.length || 5}个任务及依赖关系`,
            L7: "基于成功事实生成文字、表格、图表与证据说明",
        }[layer.layer_code] ||
        layer.layer_name);
}
function layerName(code) {
    return ({ L1: "交互层", L2: "理解层", L3: "规划层", L7: "问数解读层" }[code] || code);
}
function taskState(task) {
    const state = taskPresentationState.value[task.code] || "WAITING";
    return state === "SUCCEEDED"
        ? "完成"
        : state === "RUNNING"
            ? "执行中"
            : state === "FAILED"
                ? "失败"
                : state === "CANCELLED"
                    ? "已取消"
                    : task.depends_on?.length
                        ? "等待 " + task.depends_on.join("、")
                        : "等待执行槽";
}
function chooseShortcut(item) {
    scenario.value = item[0];
    question.value = activeQuestions.value[item[0]];
}
const guideQuestions = computed(() => ({
    MT01: [
        "哪个指标同比变化最明显？",
        "请展开说明各指标的数据口径",
        "基于本次结果继续下钻分析",
    ],
    MT02: [
        "请说明当前归因结论的数据边界",
        "继续查询客户类型贡献度",
        "继续查询机构贡献度",
    ],
    MT03: [
        "查看计划 v1 与 v2 的差异",
        "哪些节点不允许删除？",
        "按当前计划重新执行",
    ],
    MT04: [
        "重新发起长任务并演示取消",
        "查看取消传播时间线",
        "只查询贷款投放趋势",
    ],
    MT05: [
        "查看失败节点的两次 attempt",
        "哪些成功事实被保留？",
        "重新执行失败节点",
    ],
    MT06: [
        "查看未核实的非关键任务",
        "仅展示已验证事实",
        "补查失败的非关键节点",
    ],
    MT07: [
        "查看关键节点失败原因",
        "重新执行关键节点",
        "为什么禁止总体判断？",
    ],
    MT08: [
        "查看本轮计划新增节点",
        "哪些事实可以复用？",
        "基于本轮结果继续追问",
    ],
})[scenario.value] || []);
const scenarioEventLines = computed(() => {
    const types = new Set(events.value.map((event) => event.type));
    const lines = [];
    if (scenario.value === "MT03") {
        if (types.has("plan.waiting_confirmation"))
            lines.push("计划 v1 已生成，执行前进入等待确认状态");
        if (types.has("plan.confirmed"))
            lines.push("用户确认完成，计划 v2 已获准执行");
    }
    if (scenario.value === "MT05" && types.has("task.retrying"))
        lines.push("失败节点 attempt 1 超时，仅对该节点发起 attempt 2");
    if (scenario.value === "MT06")
        lines.push("补充指标为非关键节点；失败后整体状态裁决为部分成功");
    if (scenario.value === "MT07")
        lines.push("贷款投放关键节点失败；汇总节点跳过并触发安全终止");
    if (scenario.value === "MT08" && types.has("plan.expanded")) {
        const expanded = events.value.find((event) => event.type === "plan.expanded");
        lines.push(Number(expanded?.reusedFactCount) > 0
            ? `已复用 ${expanded?.reusedFactCount} 项同会话有效事实，新查询 ${expanded?.newTaskCount} 项`
            : "未发现可验证的上一轮事实，本轮扩展计划不执行事实复用");
    }
    return lines;
});
let answerGeneration = 0;
watch(answer, (value) => {
    const generation = ++answerGeneration;
    displayedAnswer.value = "";
    if (!value)
        return;
    enqueue("ANSWER", async () => {
        answerTyping.value = true;
        for (const char of String(value)) {
            if (generation !== answerGeneration)
                return;
            displayedAnswer.value += char;
            const pause = "。；！？".includes(char)
                ? 80
                : "，：".includes(char)
                    ? 40
                    : 18;
            await new Promise((r) => setTimeout(r, pause));
            await scroll();
        }
        if (generation === answerGeneration) {
            answerTyping.value = false;
            presenting.value = false;
            await scroll();
        }
    });
});
watch(running, (value) => {
    if (value)
        processOpen.value = true;
});
onMounted(async () => {
    await loadProfiles();
    await createSession();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_elements;
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "ref-chat-page" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "ref-top-tools" },
});
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.router.push('/');
            // @ts-ignore
            [router,];
        } },
});
__VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "ref-mode" },
});
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.setMode('DEMO');
            // @ts-ignore
            [setMode,];
        } },
    ...{ class: ({ active: __VLS_ctx.mode === 'DEMO' }) },
});
// @ts-ignore
[mode,];
__VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.setMode('POC');
            // @ts-ignore
            [setMode,];
        } },
    ...{ class: ({ active: __VLS_ctx.mode === 'POC' }) },
});
// @ts-ignore
[mode,];
if (__VLS_ctx.mode === 'POC') {
    // @ts-ignore
    [mode,];
    __VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
        ...{ onChange: (__VLS_ctx.createSession) },
        value: (__VLS_ctx.providerProfileId),
        title: "模型与数据源 Provider Profile",
    });
    // @ts-ignore
    [createSession, providerProfileId,];
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: "",
        disabled: true,
    });
    for (const [profile] of __VLS_getVForSourceType((__VLS_ctx.providerProfiles.filter((item) => item.selectable && item.diagnostic_status === 'READY')))) {
        // @ts-ignore
        [providerProfiles,];
        __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
            value: (profile.id),
        });
        (profile.name);
    }
}
__VLS_asFunctionalElement(__VLS_elements.select, __VLS_elements.select)({
    ...{ onChange: (__VLS_ctx.createSession) },
    value: (__VLS_ctx.role),
});
// @ts-ignore
[createSession, role,];
for (const [r] of __VLS_getVForSourceType((__VLS_ctx.roles))) {
    // @ts-ignore
    [roles,];
    __VLS_asFunctionalElement(__VLS_elements.option, __VLS_elements.option)({
        value: (r[0]),
    });
    (r[1]);
}
if (__VLS_ctx.error && !__VLS_ctx.submittedQuestion) {
    // @ts-ignore
    [error, submittedQuestion,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "ref-session-error" },
    });
    (__VLS_ctx.error);
    // @ts-ignore
    [error,];
}
__VLS_asFunctionalElement(__VLS_elements.main, __VLS_elements.main)({
    ref: "scrollBox",
    ...{ class: "ref-chat-scroll" },
    ...{ style: {} },
});
/** @type {typeof __VLS_ctx.scrollBox} */ ;
// @ts-ignore
[scrollBox,];
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "ref-chat-column" },
    ...{ style: {} },
});
if (!__VLS_ctx.submittedQuestion) {
    // @ts-ignore
    [submittedQuestion,];
    __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
        ...{ class: "ref-empty" },
    });
    __VLS_asFunctionalElement(__VLS_elements.h1, __VLS_elements.h1)({});
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.execute) },
    });
    // @ts-ignore
    [execute,];
}
else {
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "ref-user-row" },
    });
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "ref-user-bubble" },
    });
    (__VLS_ctx.submittedQuestion);
    // @ts-ignore
    [submittedQuestion,];
    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
        ...{ class: "ref-duration" },
    });
    (__VLS_ctx.elapsed);
    // @ts-ignore
    [elapsed,];
    __VLS_asFunctionalElement(__VLS_elements.article, __VLS_elements.article)({
        ...{ class: "ref-assistant" },
    });
    __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
        ...{ class: "ref-intro" },
    });
    (__VLS_ctx.displayedIntro);
    if (__VLS_ctx.running && __VLS_ctx.displayedIntro.length < __VLS_ctx.intro.length) {
        // @ts-ignore
        [displayedIntro, displayedIntro, running, intro,];
        __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
            ...{ class: "ref-cursor" },
        });
    }
    if (__VLS_ctx.plan) {
        // @ts-ignore
        [plan,];
        __VLS_asFunctionalElement(__VLS_elements.details, __VLS_elements.details)({
            ...{ onToggle: (...[$event]) => {
                    if (!!(!__VLS_ctx.submittedQuestion))
                        return;
                    if (!(__VLS_ctx.plan))
                        return;
                    __VLS_ctx.processOpen = $event.target.open;
                    // @ts-ignore
                    [processOpen,];
                } },
            ...{ class: "ref-process" },
            open: (__VLS_ctx.processOpen),
        });
        // @ts-ignore
        [processOpen,];
        __VLS_asFunctionalElement(__VLS_elements.summary, __VLS_elements.summary)({});
        __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
        __VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
        (__VLS_ctx.running || __VLS_ctx.presenting ? "处理中" : "已完成");
        // @ts-ignore
        [running, presenting,];
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "ref-process-body" },
        });
        for (const [layer] of __VLS_getVForSourceType((__VLS_ctx.globalLayers))) {
            // @ts-ignore
            [globalLayers,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                key: (layer.layer_code),
                ...{ class: "ref-process-line" },
            });
            __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
            (__VLS_ctx.layerLabels[layer.layer_code] || "");
            if (__VLS_ctx.layerLabels[layer.layer_code] !== undefined &&
                __VLS_ctx.layerLabels[layer.layer_code].length <
                    `${layer.layer_code} ${__VLS_ctx.layerName(layer.layer_code)}：${__VLS_ctx.layerText(layer)}`
                        .length) {
                // @ts-ignore
                [layerLabels, layerLabels, layerLabels, layerName, layerText,];
                __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
                    ...{ class: "ref-cursor" },
                });
            }
            if (__VLS_ctx.layerLabels[layer.layer_code]?.length ===
                `${layer.layer_code} ${__VLS_ctx.layerName(layer.layer_code)}：${__VLS_ctx.layerText(layer)}`
                    .length) {
                // @ts-ignore
                [layerLabels, layerName, layerText,];
                __VLS_asFunctionalElement(__VLS_elements.em, __VLS_elements.em)({});
            }
        }
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
            ...{ class: "ref-plan-line" },
        });
        __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
        __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
        (__VLS_ctx.planLabel);
        // @ts-ignore
        [planLabel,];
        if (__VLS_ctx.planLabel.length <
            `已加载 ${__VLS_ctx.scenario} ${__VLS_ctx.scenarioName}任务计划；${__VLS_ctx.queryTasks.length} 个查询任务，最大并行 ${__VLS_ctx.plan.maxConcurrency || 3}`
                .length) {
            // @ts-ignore
            [plan, planLabel, scenario, scenarioName, queryTasks,];
            __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
                ...{ class: "ref-cursor" },
            });
        }
        if (__VLS_ctx.scenario === 'MT03' && __VLS_ctx.waitingConfirmation && __VLS_ctx.planPresented) {
            // @ts-ignore
            [scenario, waitingConfirmation, planPresented,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "ref-confirm-plan" },
            });
            __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
            __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                ...{ onClick: (__VLS_ctx.confirmPlan) },
                disabled: (__VLS_ctx.confirming),
            });
            // @ts-ignore
            [confirmPlan, confirming,];
            (__VLS_ctx.confirming ? "确认中…" : "确认并执行");
            // @ts-ignore
            [confirming,];
        }
        if (__VLS_ctx.planPresented) {
            // @ts-ignore
            [planPresented,];
            for (const [line] of __VLS_getVForSourceType((__VLS_ctx.scenarioEventLines))) {
                // @ts-ignore
                [scenarioEventLines,];
                __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                    key: (line),
                    ...{ class: "ref-scenario-event" },
                });
                (line);
            }
        }
        if (__VLS_ctx.planPresented) {
            // @ts-ignore
            [planPresented,];
            for (const [task] of __VLS_getVForSourceType((__VLS_ctx.queryTasks))) {
                // @ts-ignore
                [queryTasks,];
                __VLS_asFunctionalElement(__VLS_elements.details, __VLS_elements.details)({
                    key: (task.id),
                    ...{ class: "ref-command ref-task-row" },
                });
                __VLS_asFunctionalElement(__VLS_elements.summary, __VLS_elements.summary)({});
                __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
                (__VLS_ctx.taskLabels[task.code] !== undefined
                    ? __VLS_ctx.taskLabels[task.code]
                    : `等待执行${__VLS_ctx.taskName(task)}指标的查询任务`);
                if (__VLS_ctx.taskPresentationState[task.code] === 'RUNNING') {
                    // @ts-ignore
                    [taskLabels, taskLabels, taskName, taskPresentationState,];
                    __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
                        ...{ class: "ref-cursor" },
                    });
                }
                __VLS_asFunctionalElement(__VLS_elements.em, __VLS_elements.em)({});
                (__VLS_ctx.taskState(task));
                (__VLS_ctx.taskDuration(task));
                // @ts-ignore
                [taskState, taskDuration,];
                __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
                __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                    ...{ class: "ref-command-detail" },
                });
                __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
                __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
                    ...{ class: "ref-layer-detail" },
                });
                __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
                (__VLS_ctx.taskName(task));
                // @ts-ignore
                [taskName,];
                __VLS_asFunctionalElement(__VLS_elements.br)({});
                __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
                __VLS_asFunctionalElement(__VLS_elements.br)({});
                __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
                __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
                __VLS_asFunctionalElement(__VLS_elements.pre, __VLS_elements.pre)({});
                (JSON.stringify({
                    command: `query_metric --org ${task.input?.org} --metric ${task.input?.metric} --period 2026Q1`,
                    description: __VLS_ctx.taskDescription(task),
                    depends_on: task.depends_on,
                    intent: __VLS_ctx.params(task).intent,
                }, null, 2));
                // @ts-ignore
                [taskDescription, params,];
                __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
                __VLS_asFunctionalElement(__VLS_elements.pre, __VLS_elements.pre)({
                    ...{ class: ({ 'result-running': task.status === 'RUNNING' }) },
                });
                (typeof __VLS_ctx.result(task) === "string"
                    ? __VLS_ctx.result(task)
                    : JSON.stringify(__VLS_ctx.result(task), null, 2));
                // @ts-ignore
                [result, result, result,];
            }
            if (__VLS_ctx.summaryTask && __VLS_ctx.allTasksPresented) {
                // @ts-ignore
                [summaryTask, allTasksPresented,];
                __VLS_asFunctionalElement(__VLS_elements.details, __VLS_elements.details)({
                    ...{ class: "ref-command ref-task-row ref-summary-row" },
                });
                __VLS_asFunctionalElement(__VLS_elements.summary, __VLS_elements.summary)({});
                __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
                (__VLS_ctx.summaryLabel);
                if (__VLS_ctx.summaryLabel.length <
                    `正在汇总 ${__VLS_ctx.queryTasks.length} 个查询任务的成功事实`
                        .length) {
                    // @ts-ignore
                    [queryTasks, summaryLabel, summaryLabel,];
                    __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
                        ...{ class: "ref-cursor" },
                    });
                }
                __VLS_asFunctionalElement(__VLS_elements.em, __VLS_elements.em)({});
                (__VLS_ctx.summaryLabel.length <
                    `正在汇总 ${__VLS_ctx.queryTasks.length} 个查询任务的成功事实`
                        .length
                    ? "汇总中"
                    : __VLS_ctx.summaryTask.status === "SUCCEEDED"
                        ? "完成"
                        : __VLS_ctx.summaryTask.status === "SKIPPED"
                            ? "已跳过"
                            : "等待查询任务完成");
                // @ts-ignore
                [queryTasks, summaryTask, summaryTask, summaryLabel,];
                __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
                __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                    ...{ class: "ref-command-detail" },
                });
                __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
                __VLS_asFunctionalElement(__VLS_elements.pre, __VLS_elements.pre)({});
                (JSON.stringify({
                    command: "summarize_verified_facts",
                    description: __VLS_ctx.taskDescription(__VLS_ctx.summaryTask),
                    depends_on: __VLS_ctx.summaryTask.depends_on,
                }, null, 2));
                // @ts-ignore
                [taskDescription, summaryTask, summaryTask,];
                __VLS_asFunctionalElement(__VLS_elements.label, __VLS_elements.label)({});
                __VLS_asFunctionalElement(__VLS_elements.pre, __VLS_elements.pre)({});
                (__VLS_ctx.summaryTask.status === "SUCCEEDED"
                    ? "已完成统一口径汇总，证据 " +
                        __VLS_ctx.evidence.length +
                        " 项。"
                    : __VLS_ctx.summaryTask.status === "SKIPPED"
                        ? "关键事实失败，已跳过汇总，禁止生成不完整总体判断。"
                        : "等待全部查询任务结束。");
                // @ts-ignore
                [summaryTask, summaryTask, evidence,];
            }
            if (__VLS_ctx.interpretationLayer && __VLS_ctx.layerLabels.L7 !== undefined) {
                // @ts-ignore
                [layerLabels, interpretationLayer,];
                __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                    ...{ class: "ref-process-line ref-l7-line" },
                });
                __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
                (__VLS_ctx.layerLabels.L7);
                // @ts-ignore
                [layerLabels,];
                if (__VLS_ctx.layerLabels.L7.length ===
                    `L7 ${__VLS_ctx.layerName('L7')}：${__VLS_ctx.layerText(__VLS_ctx.interpretationLayer)}`
                        .length) {
                    // @ts-ignore
                    [layerLabels, layerName, layerText, interpretationLayer,];
                    __VLS_asFunctionalElement(__VLS_elements.em, __VLS_elements.em)({});
                    (__VLS_ctx.interpretationLayer.status === "SUCCEEDED"
                        ? "完成"
                        : __VLS_ctx.interpretationLayer.status);
                    // @ts-ignore
                    [interpretationLayer, interpretationLayer,];
                }
            }
        }
    }
    if (__VLS_ctx.displayedAnswer) {
        // @ts-ignore
        [displayedAnswer,];
        __VLS_asFunctionalElement(__VLS_elements.section, __VLS_elements.section)({
            ...{ class: "ref-answer" },
        });
        __VLS_asFunctionalElement(__VLS_elements.h2, __VLS_elements.h2)({});
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({});
        (__VLS_ctx.displayedAnswer);
        if (__VLS_ctx.answerTyping) {
            // @ts-ignore
            [displayedAnswer, answerTyping,];
            __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({
                ...{ class: "ref-cursor" },
            });
        }
        if (!__VLS_ctx.answerTyping) {
            // @ts-ignore
            [answerTyping,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "ref-scenario-result" },
            });
            __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
            (__VLS_ctx.scenarioPresentation.title || "多任务执行结果");
            // @ts-ignore
            [scenarioPresentation,];
            __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
            (__VLS_ctx.scenarioPresentation.capability);
            // @ts-ignore
            [scenarioPresentation,];
            __VLS_asFunctionalElement(__VLS_elements.em, __VLS_elements.em)({
                ...{ class: (String(__VLS_ctx.detail?.request.status).toLowerCase()) },
            });
            // @ts-ignore
            [detail,];
            (__VLS_ctx.detail?.request.status);
            // @ts-ignore
            [detail,];
            __VLS_asFunctionalElement(__VLS_elements.h2, __VLS_elements.h2)({});
            (__VLS_ctx.scenarioPresentation.title || "执行结果");
            // @ts-ignore
            [scenarioPresentation,];
            if (__VLS_ctx.scenario !== 'MT07' &&
                __VLS_ctx.detail?.request.status !== 'CANCELLED') {
                // @ts-ignore
                [scenario, detail,];
                __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                    ...{ class: "ref-table-wrap" },
                });
                __VLS_asFunctionalElement(__VLS_elements.table, __VLS_elements.table)({});
                __VLS_asFunctionalElement(__VLS_elements.thead, __VLS_elements.thead)({});
                __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
                __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
                __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
                __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
                __VLS_asFunctionalElement(__VLS_elements.th, __VLS_elements.th)({});
                __VLS_asFunctionalElement(__VLS_elements.tbody, __VLS_elements.tbody)({});
                for (const [row] of __VLS_getVForSourceType((__VLS_ctx.detail?.result))) {
                    // @ts-ignore
                    [detail,];
                    __VLS_asFunctionalElement(__VLS_elements.tr, __VLS_elements.tr)({});
                    __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
                    (__VLS_ctx.metricLabel(String(row.metric)));
                    // @ts-ignore
                    [metricLabel,];
                    __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
                    (__VLS_ctx.format(row.current_value ?? row.current));
                    // @ts-ignore
                    [format,];
                    __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({});
                    (__VLS_ctx.format(row.previous_value ?? row.previous));
                    // @ts-ignore
                    [format,];
                    __VLS_asFunctionalElement(__VLS_elements.td, __VLS_elements.td)({
                        ...{ class: (Number(row.changeRate) >= 0
                                ? 'positive'
                                : 'negative') },
                    });
                    (Number(row.changeRate) >= 0 ? "+" : "");
                    (__VLS_ctx.format(row.changeRate));
                    // @ts-ignore
                    [format,];
                }
            }
            if (__VLS_ctx.scenario !== 'MT07' &&
                __VLS_ctx.detail?.request.status !== 'CANCELLED') {
                // @ts-ignore
                [scenario, detail,];
                __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                    ...{ class: "ref-chart" },
                });
                __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
                for (const [row] of __VLS_getVForSourceType((__VLS_ctx.detail?.result))) {
                    // @ts-ignore
                    [detail,];
                    __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
                    __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
                    (__VLS_ctx.metricLabel(String(row.metric)));
                    // @ts-ignore
                    [metricLabel,];
                    __VLS_asFunctionalElement(__VLS_elements.i, __VLS_elements.i)({});
                    __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({
                        ...{ class: (Number(row.changeRate) >= 0 ? 'up' : 'down') },
                        ...{ style: ({ width: __VLS_ctx.chartWidth(row) }) },
                    });
                    // @ts-ignore
                    [chartWidth,];
                    __VLS_asFunctionalElement(__VLS_elements.strong, __VLS_elements.strong)({});
                    (Number(row.changeRate) >= 0 ? "+" : "");
                    (__VLS_ctx.format(row.changeRate));
                    // @ts-ignore
                    [format,];
                }
            }
            __VLS_asFunctionalElement(__VLS_elements.h3, __VLS_elements.h3)({});
            __VLS_asFunctionalElement(__VLS_elements.ul, __VLS_elements.ul)({});
            __VLS_asFunctionalElement(__VLS_elements.li, __VLS_elements.li)({});
            __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
            (__VLS_ctx.detail?.request.status);
            (__VLS_ctx.queryTasks.filter((x) => x.status === "SUCCEEDED").length);
            (__VLS_ctx.queryTasks.length);
            // @ts-ignore
            [queryTasks, queryTasks, detail,];
            __VLS_asFunctionalElement(__VLS_elements.li, __VLS_elements.li)({});
            __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
            (__VLS_ctx.evidence.length);
            // @ts-ignore
            [evidence,];
            __VLS_asFunctionalElement(__VLS_elements.li, __VLS_elements.li)({});
            __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
            (__VLS_ctx.isOffline
                ? "离线合成 Fixture 演示"
                : "SQLite 测试数仓参数化查询");
            (__VLS_ctx.scenario);
            // @ts-ignore
            [scenario, isOffline,];
            __VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
                ...{ class: "ref-guides" },
            });
            __VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
            for (const [guide] of __VLS_getVForSourceType((__VLS_ctx.guideQuestions))) {
                // @ts-ignore
                [guideQuestions,];
                __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.submittedQuestion))
                                return;
                            if (!(__VLS_ctx.displayedAnswer))
                                return;
                            if (!(!__VLS_ctx.answerTyping))
                                return;
                            __VLS_ctx.question = guide;
                            // @ts-ignore
                            [question,];
                        } },
                });
                (guide);
            }
        }
    }
    if (__VLS_ctx.error || __VLS_ctx.failureMessage) {
        // @ts-ignore
        [error, failureMessage,];
        __VLS_asFunctionalElement(__VLS_elements.p, __VLS_elements.p)({
            ...{ class: "ref-error" },
        });
        (__VLS_ctx.error || __VLS_ctx.failureMessage);
        // @ts-ignore
        [error, failureMessage,];
    }
}
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ref: "bottomAnchor",
    ...{ style: {} },
});
/** @type {typeof __VLS_ctx.bottomAnchor} */ ;
// @ts-ignore
[bottomAnchor,];
__VLS_asFunctionalElement(__VLS_elements.footer, __VLS_elements.footer)({
    ...{ class: "ref-input-shell" },
});
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "ref-shortcuts" },
});
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.shortcuts))) {
    // @ts-ignore
    [shortcuts,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.chooseShortcut(item);
                // @ts-ignore
                [chooseShortcut,];
            } },
        ...{ class: ({ active: __VLS_ctx.scenario === item[0] }) },
    });
    // @ts-ignore
    [scenario,];
    __VLS_asFunctionalElement(__VLS_elements.b, __VLS_elements.b)({});
    (item[0]);
    (item[1]);
}
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({
    ...{ class: "ref-input" },
});
__VLS_asFunctionalElement(__VLS_elements.textarea, __VLS_elements.textarea)({
    ...{ onKeydown: (__VLS_ctx.execute) },
    value: (__VLS_ctx.question),
    disabled: (__VLS_ctx.running || __VLS_ctx.presenting),
    placeholder: "您可以使用自然语言描述综合问数需求～",
});
// @ts-ignore
[execute, running, presenting, question,];
__VLS_asFunctionalElement(__VLS_elements.div, __VLS_elements.div)({});
__VLS_asFunctionalElement(__VLS_elements.span, __VLS_elements.span)({});
__VLS_asFunctionalElement(__VLS_elements.small, __VLS_elements.small)({});
(__VLS_ctx.isOffline ? "离线演示" : __VLS_ctx.mode);
// @ts-ignore
[mode, isOffline,];
if (__VLS_ctx.running) {
    // @ts-ignore
    [running,];
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.cancel) },
        ...{ class: "cancel text-action" },
    });
    // @ts-ignore
    [cancel,];
}
else {
    __VLS_asFunctionalElement(__VLS_elements.button, __VLS_elements.button)({
        ...{ onClick: (__VLS_ctx.execute) },
        ...{ class: "text-action" },
        disabled: (!__VLS_ctx.session || __VLS_ctx.presenting),
    });
    // @ts-ignore
    [execute, presenting, session,];
    (__VLS_ctx.presenting ? "输出中" : "发送");
    // @ts-ignore
    [presenting,];
}
/** @type {__VLS_StyleScopedClasses['ref-chat-page']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-top-tools']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-mode']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-session-error']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-chat-scroll']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-chat-column']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-user-row']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-user-bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-duration']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-assistant']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-intro']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-process']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-process-body']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-process-line']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-plan-line']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-confirm-plan']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-scenario-event']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-command']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-task-row']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-command-detail']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-layer-detail']} */ ;
/** @type {__VLS_StyleScopedClasses['result-running']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-command']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-task-row']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-summary-row']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-command-detail']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-process-line']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-l7-line']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-answer']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-cursor']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-scenario-result']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-table-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-chart']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-guides']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-error']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-input-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-shortcuts']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-input']} */ ;
/** @type {__VLS_StyleScopedClasses['cancel']} */ ;
/** @type {__VLS_StyleScopedClasses['text-action']} */ ;
/** @type {__VLS_StyleScopedClasses['text-action']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            isOffline: isOffline,
            router: router,
            scrollBox: scrollBox,
            bottomAnchor: bottomAnchor,
            roles: roles,
            role: role,
            mode: mode,
            scenario: scenario,
            session: session,
            providerProfiles: providerProfiles,
            providerProfileId: providerProfileId,
            question: question,
            submittedQuestion: submittedQuestion,
            detail: detail,
            running: running,
            presenting: presenting,
            confirming: confirming,
            error: error,
            elapsed: elapsed,
            displayedIntro: displayedIntro,
            displayedAnswer: displayedAnswer,
            answerTyping: answerTyping,
            processOpen: processOpen,
            planPresented: planPresented,
            taskLabels: taskLabels,
            taskPresentationState: taskPresentationState,
            layerLabels: layerLabels,
            planLabel: planLabel,
            summaryLabel: summaryLabel,
            intro: intro,
            shortcuts: shortcuts,
            scenarioName: scenarioName,
            plan: plan,
            scenarioPresentation: scenarioPresentation,
            evidence: evidence,
            queryTasks: queryTasks,
            allTasksPresented: allTasksPresented,
            summaryTask: summaryTask,
            globalLayers: globalLayers,
            interpretationLayer: interpretationLayer,
            waitingConfirmation: waitingConfirmation,
            failureMessage: failureMessage,
            createSession: createSession,
            setMode: setMode,
            execute: execute,
            cancel: cancel,
            confirmPlan: confirmPlan,
            taskName: taskName,
            taskDescription: taskDescription,
            params: params,
            result: result,
            metricLabel: metricLabel,
            format: format,
            taskDuration: taskDuration,
            chartWidth: chartWidth,
            layerText: layerText,
            layerName: layerName,
            taskState: taskState,
            chooseShortcut: chooseShortcut,
            guideQuestions: guideQuestions,
            scenarioEventLines: scenarioEventLines,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
    },
});
; /* PartiallyEnd: #4569/main.vue */

import baseline from "../../../fixtures/official_baseline_v1.json";
import v21 from "../../../fixtures/demo/v2.1/baseline.json";
import type { Adapter, RoleId, Session, QueryDetail } from "../types";
const layers = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
  names = [
    "交互层",
    "对话理解层",
    "语义层",
    "数据资产层",
    "查询生成层",
    "执行层",
    "问数解读层",
  ];
const db = () =>
  new Promise<IDBDatabase>((ok, no) => {
    const r = indexedDB.open("askdata-phase1", 2);
    r.onupgradeneeded = () => {
      ["sessions", "requests", "audit", "config"].forEach((x) => {
        if (!r.result.objectStoreNames.contains(x))
          r.result.createObjectStore(x, { keyPath: "id" });
      });
    };
    r.onsuccess = () => ok(r.result);
    r.onerror = () => no(r.error);
  });
async function put(store: string, value: unknown) {
  const d = await db();
  await new Promise<void>((ok, no) => {
    const t = d.transaction(store, "readwrite");
    t.objectStore(store).put(value);
    t.oncomplete = () => ok();
    t.onerror = () => no(t.error);
  });
  d.close();
}
async function get<T>(store: string, id: string) {
  const d = await db();
  return new Promise<T | undefined>((ok, no) => {
    const r = d.transaction(store).objectStore(store).get(id);
    r.onsuccess = () => {
      d.close();
      ok(r.result as T | undefined);
    };
    r.onerror = () => {
      d.close();
      no(r.error);
    };
  });
}
export class OfflineAdapter implements Adapter {
  mode = "OFFLINE" as const;
  private details = new Map<string, QueryDetail>();
  private stopped = new Set<string>();
  async createSession(role_id: RoleId) {
    const s = {
      id: crypto.randomUUID(),
      role_id,
      config_version_id: "official-v1",
    };
    await put("sessions", s);
    return s;
  }
  async session(id: string): Promise<Session> {
    const value = await get<Session>("sessions", id);
    if (!value) throw new Error("离线Session不存在");
    return value;
  }
  async query(
    session_id: string,
    question: string,
    scenario: string,
    parent_request_id?: string,
    _variant: "DEMO" | "POC" = "DEMO",
  ) {
    const id = crypto.randomUUID(),
      role = (await this.session(session_id)).role_id;
    if (scenario.startsWith("MT"))
      return this.v21(
        id,
        session_id,
        question,
        scenario,
        role,
        parent_request_id,
      );
    const num = Number(scenario.split("-")[1]),
      sc = baseline.scenarios.find((x) => x.number === num)!,
      turn = sc.cases
        .find((x) => x.role_id === role)!
        .turns.find((x) =>
          question.includes("去年同期") || question.includes("为什么")
            ? x.turn === 2
            : x.turn === 1,
        )!;
    const last = Number(turn.expected_last_layer.slice(1)),
      blocked = num === 5,
      waiting = num === 7 && !parent_request_id,
      status = blocked
        ? "BLOCKED"
        : waiting
          ? "WAITING_INPUT"
          : num === 2 || num === 3
            ? "SHORT_CIRCUITED"
            : "SUCCEEDED";
    const result =
      status === "SUCCEEDED"
        ? [
            {
              机构: role === "beijing" ? "北京分行" : "全行",
              统计日期: "2026-03-31",
              查询结果: role === "retail" ? 260.45 : 980.5,
            },
          ]
        : [];
    const detail = {
      request: {
        id,
        session_id,
        parent_request_id,
        status,
        question,
        scenario_id: scenario,
        mode: "OFFLINE",
      },
      layers: layers.slice(0, last).map((x, i) => ({
        layer_code: x,
        layer_name: names[i],
        status: i === last - 1 && status !== "SUCCEEDED" ? status : "SUCCEEDED",
        output: {},
      })),
      sql_executions:
        status === "SUCCEEDED"
          ? [
              {
                sequence: 1,
                business_sql: "SELECT 指标 FROM 模拟宽表 WHERE 机构=:org",
                source: "OFFLINE_SIMULATION",
              },
            ]
          : [],
      result,
    };
    this.details.set(id, detail);
    await put("requests", { id, ...detail });
    return id;
  }
  async v21(
    id: string,
    session_id: string,
    question: string,
    scenario: string,
    role: RoleId,
    parent_request_id?: string,
  ) {
    const org = role === "beijing" ? "BJ" : "HQ",
      allowed =
        role === "retail"
          ? ["retail_loan_issue_amt", "active_customer_count"]
          : ["loan_issue_amt", "deposit_balance", "npl_ratio", "fee_income"];
    let facts = v21.quarterlyFacts.filter(
      (x) => x.org === org && allowed.includes(x.metric),
    );
    if (["MT02", "MT05", "MT07"].includes(scenario)) facts = facts.slice(0, 3);
    if (scenario === "MT08") facts = facts.slice(0, 2);
    const failedMetric =
        scenario === "MT06"
          ? "fee_income"
          : scenario === "MT07"
            ? "loan_issue_amt"
            : "",
      queryTasks = facts.map((x, i) => ({
        id: crypto.randomUUID(),
        code: `Q${i + 1}`,
        type: "SQL",
        critical:
          x.metric !== "fee_income" && x.metric !== "active_customer_count",
        status: x.metric === failedMetric ? "FAILED" : "SUCCEEDED",
        depends_on: scenario === "MT02" && i > 0 ? ["Q1"] : [],
        output: x.metric === failedMetric ? null : x,
        error_code: x.metric === failedMetric ? "DEMO_INJECTED_FAILURE" : null,
        attempts: scenario === "MT05" && x.metric === "deposit_balance" ? 2 : 1,
      }));
    const successful = queryTasks.filter((x) => x.status === "SUCCEEDED"),
      status =
        scenario === "MT07"
          ? "FAILED"
          : scenario === "MT06"
            ? "PARTIAL_SUCCESS"
            : "SUCCEEDED",
      tasks = [
        ...queryTasks,
        {
          id: crypto.randomUUID(),
          code: "S1",
          type: "SUMMARY",
          critical: true,
          status: status === "FAILED" ? "SKIPPED" : "SUCCEEDED",
          depends_on: queryTasks.map((x) => x.code),
          output: successful.map((x) => x.output),
        },
      ],
      answer =
        (scenario === "MT05"
          ? "失败节点重试成功："
          : scenario === "MT08"
            ? "已复用有效事实："
            : "") +
        successful
          .map((x) => `${x.output!.metric} ${x.output!.current}`)
          .join("；") +
        (status !== "SUCCEEDED" ? "。存在未核实任务。" : "");
    const detail: QueryDetail = {
      request: {
        id,
        session_id,
        parent_request_id,
        status,
        question,
        scenario_id: scenario,
        mode: "V21_DEMO",
      },
      layers: layers.map((x, i) => ({
        layer_code: x,
        layer_name: names[i],
        status: i >= 5 ? status : "SUCCEEDED",
        output:
          i === 6
            ? {
                answer,
                evidence: successful.map((x) => ({
                  taskId: x.id,
                  taskCode: x.code,
                })),
                unverified: queryTasks
                  .filter((x) => x.status === "FAILED")
                  .map((x) => x.code),
                completion: `${successful.length}/${queryTasks.length}`,
              }
            : {},
      })),
      sql_executions: successful.map((x, i) => ({
        sequence: i + 1,
        business_sql: `${scenario} Demo Fixture 查询`,
        source: "DEMO_FIXTURE",
        status: "SUCCEEDED",
      })),
      result: successful.map((x) => x.output!),
      plan: {
        scenario_id: scenario,
        plan: {
          scenarioId: scenario,
          version: scenario === "MT03" ? 2 : 1,
          maxConcurrency: 3,
          nodes: tasks,
        },
      },
      tasks,
    };
    this.details.set(id, detail);
    await put("requests", { id, ...detail });
    return id;
  }
  async events(id: string, onEvent: (e: Record<string, unknown>) => void) {
    const d = this.details.get(id)!;
    for (const l of d.layers) {
      if (this.stopped.has(id)) break;
      onEvent({
        type: "layer.started",
        layer_code: l.layer_code,
        layer_name: l.layer_name,
      });
      await new Promise((r) => setTimeout(r, 100));
      onEvent({
        type: "layer.completed",
        layer_code: l.layer_code,
        status: l.status,
        output: l.output,
      });
      if (l.layer_code === "L5" && d.tasks)
        for (const task of d.tasks.filter((x) => x.type === "SQL")) {
          onEvent({ type: "task.started", taskId: task.id, code: task.code });
          await new Promise((r) => setTimeout(r, 70));
          if (task.attempts === 2)
            onEvent({
              type: "task.retrying",
              taskId: task.id,
              code: task.code,
              attempt: 2,
            });
          onEvent({
            type: "task.completed",
            taskId: task.id,
            code: task.code,
            status: task.status,
          });
        }
    }
    onEvent({
      type: "request.completed",
      status: this.stopped.has(id) ? "CANCELLED" : d.request.status,
    });
  }
  async detail(id: string) {
    const memory = this.details.get(id);
    if (memory) return memory;
    const saved = await get<Record<string, unknown>>("requests", id);
    if (!saved) throw new Error("离线请求不存在");
    const { id: _, ...detail } = saved;
    return detail as unknown as QueryDetail;
  }
  async confirm(_id: string) {
    return;
  }
  async cancel(id: string) {
    this.stopped.add(id);
  }
  async readiness() {
    return {
      ready: true,
      mode: "OFFLINE",
      roles: 3,
      scenarios: 16,
      simulation: true,
    };
  }
  async admin(path: string, init?: RequestInit) {
    if (path === "/baseline" || path === "/config/export") return baseline;
    if (path.startsWith("/reset/")) {
      await put("config", {
        id: "official-v1",
        payload: baseline,
        updated_at: new Date().toISOString(),
      });
      return { status: "ok", scope: path.split("/").at(-1) };
    }
    if (path === "/config/drafts") {
      const body = JSON.parse(String(init?.body || "{}"));
      const value = { id: crypto.randomUUID(), status: "DRAFT", ...body };
      await put("config", value);
      return value;
    }
    if (path.startsWith("/resources/")) {
      const parts = path.split("/"),
        kind = parts[2],
        id = parts[3];
      if (init?.method === "PUT") {
        const body = JSON.parse(String(init.body));
        await put("config", { id: `${kind}:${id}`, ...body });
        await put("audit", {
          id: crypto.randomUUID(),
          action: "SAVE_RESOURCE",
          kind,
          resource_id: id,
          created_at: new Date().toISOString(),
        });
        return { kind, id, saved_as: "DRAFT_RESOURCE" };
      }
      return { items: [] };
    }
    throw new Error("离线管理操作不支持该路径");
  }
}

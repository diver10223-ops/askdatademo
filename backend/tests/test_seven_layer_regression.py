import asyncio
import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import PLATFORM_DB
from app.db import connect, restore_baseline
from app.engine import Engine
from app.main import app
from app.models import PipelineContext
from app.providers.phase2 import AsyncGate, RetryPolicy
from app.runtime import resolve_runtime


ROOT = Path(__file__).resolve().parents[2]


class FailingOptionalModel:
    async def structured_generate(self, *_):
        raise TimeoutError("model detail must not escape")


class SuccessfulDataSource:
    async def execute(self, sql, parameters, permissions=None):
        return [{"org_name": "全行", "stat_dt": "2026-03-31", "current_value": 100.0}]
    async def cancel(self, _): return True
    def set_request_id(self, _): pass


class Fixture:
    async def execute(self, *_): return [{"factor": "fixture"}]


class Registry:
    phase = 2
    profile_id = "p353"
    def __init__(self, datasource=None):
        self.model = FailingOptionalModel()
        self.datasource = datasource or SuccessfulDataSource()
        self.fixture = Fixture()


def seed_context(request_id, registry, scenario="scenario-1"):
    config = json.loads((ROOT / "fixtures" / "official_baseline_v1.json").read_text())
    config["runtime"] = json.loads((ROOT / "fixtures" / "demo_runtime_defaults.json").read_text())
    session_id = f"session-{request_id}"
    permissions = {"orgs": ["全行"], "metrics": ["贷款投放", "零售贷款", "对公贷款"]}
    with connect(PLATFORM_DB) as db:
        db.execute("INSERT INTO sessions(id,role_id,permission_snapshot_id,permission_snapshot,config_version_id,created_at) VALUES(?,?,?,?,?,?)", (session_id, "admin", "p353", json.dumps(permissions, ensure_ascii=False), "official-v1", "now"))
        db.execute("INSERT INTO requests(id,session_id,trace_id,scenario_id,question,mode,status,config_version_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (request_id, session_id, f"trace-{request_id}", scenario, "2026年3月全行贷款投放是多少？", "PHASE2_POC", "PENDING", "official-v1", "now"))
    runtime = resolve_runtime(config, "PHASE2_POC", ["dws_loan_aggr_wide"])
    return PipelineContext(session_id, request_id, "admin", "official-v1", "2026年3月全行贷款投放是多少？", scenario_id=scenario, mode="PHASE2_POC", permissions=permissions, config=config, runtime=runtime)


def test_optional_model_failure_falls_back_and_seven_layers_still_succeed():
    restore_baseline(); registry = Registry(); context = seed_context("p353-model-failure", registry)
    asyncio.run(Engine(registry).run(context))
    with connect(PLATFORM_DB) as db:
        request = db.execute("SELECT status,last_layer FROM requests WHERE id=?", (context.request_id,)).fetchone()
        layers = db.execute("SELECT layer_code,status,output_json FROM layer_executions WHERE request_id=? ORDER BY id", (context.request_id,)).fetchall()
    assert (request["status"], request["last_layer"]) == ("SUCCEEDED", "L7")
    assert [row["layer_code"] for row in layers] == [f"L{i}" for i in range(1, 8)]
    assert json.loads(layers[1]["output_json"])["model_status"] == "ERROR_FALLBACK"
    assert json.loads(layers[-1]["output_json"])["model_validation"] == "PROVIDER_ERROR_FALLBACK"


def test_retry_gate_retries_transient_failure_only_to_configured_limit():
    attempts = 0
    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3: raise TimeoutError("transient")
        return "ok"
    assert asyncio.run(AsyncGate(RetryPolicy(timeout=1, retries=2, backoff=0)).run(operation)) == "ok"
    assert attempts == 3


def test_running_request_reaches_cancelled_final_state_before_l7():
    class BlockingDataSource(SuccessfulDataSource):
        def __init__(self): self.started = asyncio.Event(); self.release = asyncio.Event(); self.cancelled = False
        async def execute(self, sql, parameters, permissions=None):
            self.started.set(); await self.release.wait()
            return await super().execute(sql, parameters, permissions)
        async def cancel(self, _): self.cancelled = True; self.release.set(); return True
    async def run_case():
        restore_baseline(); datasource = BlockingDataSource(); registry = Registry(datasource); context = seed_context("p353-cancel", registry)
        task = asyncio.create_task(Engine(registry).run(context)); await datasource.started.wait()
        with connect(PLATFORM_DB) as db: db.execute("UPDATE requests SET cancel_requested=1 WHERE id=?", (context.request_id,))
        datasource.release.set(); await task
        with connect(PLATFORM_DB) as db:
            request = db.execute("SELECT status,last_layer,termination_reason FROM requests WHERE id=?", (context.request_id,)).fetchone()
            layers = [row[0] for row in db.execute("SELECT layer_code FROM layer_executions WHERE request_id=? ORDER BY id", (context.request_id,))]
        return request, layers, datasource.cancelled
    request, layers, cancelled = asyncio.run(run_case())
    assert (request["status"], request["last_layer"], request["termination_reason"]) == ("CANCELLED", "L7", "CANCELLED")
    assert layers == [f"L{i}" for i in range(1, 7)] and cancelled


def test_internal_session_identity_and_idempotency_reject_context_contamination():
    restore_baseline(); request_id = str(uuid.uuid4()); session_id = str(uuid.uuid4()); key = f"p353-{uuid.uuid4()}"
    payload = {"requestId": request_id, "sessionId": session_id, "parentRequestId": None, "subjectId": "p353-user", "roleIds": ["admin"], "question": "2026年3月全行贷款投放是多少？", "scenarioId": "scenario-1", "executionMode": "DEMO", "permissionSnapshot": {"orgs": ["全行"], "metrics": ["贷款投放"]}, "configVersionId": "official-v1", "providerProfileId": None, "timeoutMs": 30000}
    headers = {"X-Service-Token": "askdata-local-service-token", "X-Trace-Id": "trace-p353", "Idempotency-Key": key}
    with TestClient(app) as client:
        assert client.post("/internal/v1/executions", json=payload, headers=headers).status_code == 202
        changed = {**payload, "requestId": str(uuid.uuid4()), "permissionSnapshot": {"orgs": ["上海分行"], "metrics": ["贷款投放"]}}
        changed_headers = {**headers, "Idempotency-Key": f"p353-{uuid.uuid4()}"}
        response = client.post("/internal/v1/executions", json=changed, headers=changed_headers)
        assert response.status_code == 409 and response.json()["detail"]["code"] == "FORBIDDEN"
        conflict = client.post("/internal/v1/executions", json={**payload, "question": "不同问题"}, headers=headers)
        assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"

import hmac
import hashlib
import json
import os
import asyncio
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from .config import PLATFORM_DB
from .db import connect
from .engine import Engine
from .models import PipelineContext
from .phase2_service import build_registry
from .runtime import resolve_runtime, RuntimeConfigError

router = APIRouter(prefix="/internal/v1", tags=["internal-execution"])
_lock = RLock()
_executions: dict[str, dict[str, Any]] = {}
_idempotency: dict[str, tuple[str, str]] = {}
_active_engines: dict[str, Engine] = {}


class ExecutionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requestId: UUID
    sessionId: UUID
    parentRequestId: UUID | None = None
    subjectId: str = Field(min_length=1)
    roleIds: list[str] = Field(min_length=1)
    question: str = Field(min_length=1, max_length=4000)
    scenarioId: str | None = None
    executionMode: Literal["DEMO", "POC", "PRODUCTION"]
    permissionSnapshot: dict[str, Any]
    configVersionId: str = Field(min_length=1)
    configSnapshot: dict[str, Any] | None = None
    providerProfileId: str | None = None
    timeoutMs: int = Field(ge=1000, le=300000)


def require_service_token(x_service_token: str | None = Header(default=None)) -> None:
    configured = os.getenv("ASKDATA_INTERNAL_SERVICE_TOKEN", "askdata-local-service-token")
    if not x_service_token or not hmac.compare_digest(x_service_token, configured):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "内部服务鉴权失败"})


@router.get("/health", dependencies=[])
def internal_health(x_service_token: str | None = Header(default=None)):
    require_service_token(x_service_token)
    return {"status": "ok", "version": "1.0.0"}


def _authenticate(token: str | None) -> None:
    require_service_token(token)


@router.post("/executions", status_code=202)
async def create_execution(
    command: ExecutionCommand,
    x_service_token: str | None = Header(default=None),
    x_trace_id: str = Header(min_length=1, max_length=128),
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    _authenticate(x_service_token)
    canonical = json.dumps(command.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    request_id = str(command.requestId)
    with _lock:
        previous = _idempotency.get(idempotency_key)
        if previous:
            if previous != (request_id, digest):
                raise HTTPException(409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": "幂等键已用于其他请求"})
            state = _executions[request_id]
            return {"requestId": request_id, "status": "PENDING", "traceId": state["traceId"], "idempotentReplay": True}
        with connect(PLATFORM_DB) as db:
            persisted = db.execute("SELECT request_id,command_digest FROM internal_execution_idempotency WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if persisted:
                if persisted["request_id"] != request_id or persisted["command_digest"] != digest:
                    raise HTTPException(409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": "幂等键已用于其他请求"})
                state = _state_from_database(request_id, x_trace_id)
                _idempotency[idempotency_key] = (request_id, digest)
                _executions[request_id] = state
                return {"requestId": request_id, "status": "PENDING", "traceId": state["traceId"], "idempotentReplay": True}
            existing_request = db.execute("SELECT session_id,question,scenario_id,mode,config_version_id FROM requests WHERE id=?", (request_id,)).fetchone()
            if existing_request:
                expected = (str(command.sessionId), command.question, command.scenarioId, _engine_mode(command.executionMode), command.configVersionId)
                actual = (existing_request["session_id"], existing_request["question"], existing_request["scenario_id"], existing_request["mode"], existing_request["config_version_id"])
                if actual != expected:
                    raise HTTPException(409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": "请求ID已用于不同命令"})
                db.execute("INSERT INTO internal_execution_idempotency VALUES(?,?,?,?)", (idempotency_key, request_id, digest, datetime.now(timezone.utc).isoformat()))
                state = _state_from_database(request_id, x_trace_id)
                _idempotency[idempotency_key] = (request_id, digest)
                _executions[request_id] = state
                return {"requestId": request_id, "status": "PENDING", "traceId": state["traceId"], "idempotentReplay": True}
            version = db.execute("SELECT payload FROM config_versions WHERE id=?", (command.configVersionId,)).fetchone()
            if not version and command.configSnapshot is None:
                raise HTTPException(409, detail={"code": "CONFIG_VERSION_UNAVAILABLE", "message": "配置版本不存在或未发布"})
            if version and command.configSnapshot is not None and json.loads(version[0]) != command.configSnapshot:
                raise HTTPException(409, detail={"code": "CONFIG_VERSION_UNAVAILABLE", "message": "配置版本ID与既有快照不一致"})
            if not version:
                next_version = db.execute("SELECT COALESCE(MAX(version),0)+1 FROM config_versions").fetchone()[0]
                db.execute("INSERT INTO config_versions(id,name,status,version,payload,official,created_at) VALUES(?,?,'ARCHIVED',?,?,0,?)",
                           (command.configVersionId, f"Java snapshot {command.configVersionId}", next_version, json.dumps(command.configSnapshot, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
            if command.parentRequestId and not db.execute("SELECT 1 FROM requests WHERE id=? AND session_id=?", (str(command.parentRequestId), str(command.sessionId))).fetchone():
                raise HTTPException(422, detail={"code": "INVALID_INPUT", "message": "父请求不属于当前会话"})
            role_id = command.roleIds[0]
            role = db.execute("SELECT 1 FROM roles WHERE id=? AND enabled=1", (role_id,)).fetchone()
            if not role:
                db.execute("INSERT INTO roles(id,name,enabled,permissions) VALUES(?,?,1,?)", (role_id, role_id, json.dumps(command.permissionSnapshot, ensure_ascii=False)))
            db.execute("INSERT OR IGNORE INTO sessions(id,role_id,permission_snapshot_id,permission_snapshot,config_version_id,created_at) VALUES(?,?,?,?,?,?)",
                       (str(command.sessionId), role_id, f"java:{command.sessionId}", json.dumps(command.permissionSnapshot, ensure_ascii=False), command.configVersionId, datetime.now(timezone.utc).isoformat()))
            role_snapshot = json.dumps(command.roleIds, sort_keys=True, ensure_ascii=False)
            permission_digest = hashlib.sha256(json.dumps(command.permissionSnapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            identity = db.execute("SELECT subject_id,role_snapshot,permission_digest,config_version_id FROM internal_session_identity WHERE session_id=?", (str(command.sessionId),)).fetchone()
            expected_identity = (command.subjectId, role_snapshot, permission_digest, command.configVersionId)
            if identity and tuple(identity) != expected_identity:
                raise HTTPException(409, detail={"code": "FORBIDDEN", "message": "Session身份、权限或配置快照不可变"})
            if not identity:
                db.execute("INSERT INTO internal_session_identity VALUES(?,?,?,?,?)", (str(command.sessionId), *expected_identity))
            db.execute("INSERT INTO requests(id,session_id,parent_request_id,trace_id,scenario_id,question,mode,status,config_version_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (request_id, str(command.sessionId), str(command.parentRequestId) if command.parentRequestId else None, x_trace_id, command.scenarioId, command.question, _engine_mode(command.executionMode), "PENDING", command.configVersionId, datetime.now(timezone.utc).isoformat()))
            db.execute("INSERT INTO internal_execution_idempotency VALUES(?,?,?,?)", (idempotency_key, request_id, digest, datetime.now(timezone.utc).isoformat()))
        state = {
            "requestId": request_id,
            "status": "PENDING",
            "traceId": x_trace_id,
            "lastEventId": 0,
            "lastLayer": None,
            "terminationReason": None,
            "result": None,
            "occurredAt": datetime.now(timezone.utc).isoformat(),
        }
        _executions[request_id] = state
        _idempotency[idempotency_key] = (request_id, digest)
    asyncio.create_task(_execute(command, x_trace_id))
    return {"requestId": request_id, "status": "PENDING", "traceId": x_trace_id, "idempotentReplay": False}


def _engine_mode(mode: str) -> str:
    return "PHASE1_DEMO" if mode == "DEMO" else "PHASE2_POC"


async def _execute(command: ExecutionCommand, trace_id: str) -> None:
    request_id = str(command.requestId)
    try:
        with connect(PLATFORM_DB) as db:
            session = db.execute("SELECT context FROM sessions WHERE id=?", (str(command.sessionId),)).fetchone()
            version = db.execute("SELECT payload FROM config_versions WHERE id=?", (command.configVersionId,)).fetchone()
        config = command.configSnapshot if command.configSnapshot is not None else json.loads(version[0])
        mode = _engine_mode(command.executionMode)
        registry = build_registry(command.providerProfileId) if command.providerProfileId else None
        if command.executionMode != "DEMO" and registry is None:
            raise RuntimeConfigError(["providerProfileId"])
        engine = Engine(registry) if registry else Engine()
        allowed_tables = None
        if command.providerProfileId:
            with connect(PLATFORM_DB) as db:
                profile = db.execute("SELECT public_config FROM phase2_provider_profiles WHERE id=? AND status='ENABLED'", (command.providerProfileId,)).fetchone()
            if not profile:
                raise RuntimeConfigError(["providerProfileId.enabled"])
            allowed_tables = json.loads(profile[0]).get("allowed_tables")
        runtime = resolve_runtime(config, mode, allowed_tables)
        context = PipelineContext(str(command.sessionId), request_id, command.roleIds[0], command.configVersionId,
                                  command.question, str(command.parentRequestId) if command.parentRequestId else None,
                                  command.scenarioId, mode=mode, parameters=json.loads(session[0]),
                                  permissions=command.permissionSnapshot, config=config, runtime=runtime)
        _active_engines[request_id] = engine
        await asyncio.wait_for(engine.run(context), timeout=command.timeoutMs / 1000)
    except asyncio.TimeoutError:
        with connect(PLATFORM_DB) as db:
            db.execute("UPDATE requests SET status='TIMED_OUT',termination_reason='EXECUTION_TIMEOUT',completed_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), request_id))
    except Exception as exc:
        reason = "PROVIDER_UNAVAILABLE" if isinstance(exc, RuntimeConfigError) else "EXECUTION_FAILED"
        with connect(PLATFORM_DB) as db:
            db.execute("UPDATE requests SET status='FAILED',termination_reason=?,completed_at=? WHERE id=?", (reason, datetime.now(timezone.utc).isoformat(), request_id))
    finally:
        _active_engines.pop(request_id, None)
        with _lock:
            _executions[request_id] = _state_from_database(request_id, trace_id)


def _state_from_database(request_id: str, trace_id: str | None = None) -> dict[str, Any]:
    with connect(PLATFORM_DB) as db:
        request = db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        if not request:
            raise KeyError(request_id)
        layers = [{**dict(row), "input": json.loads(row["input_json"]), "output": json.loads(row["output_json"] or "{}")} for row in db.execute("SELECT * FROM layer_executions WHERE request_id=? ORDER BY id", (request_id,))]
        sql = [{**dict(row), "parameters": json.loads(row["parameters"])} for row in db.execute("SELECT * FROM sql_executions WHERE request_id=? ORDER BY sequence", (request_id,))]
        snapshot = db.execute("SELECT payload,masked,size_bytes FROM result_snapshots WHERE request_id=?", (request_id,)).fetchone()
        last_event = db.execute("SELECT COALESCE(MAX(event_id),0) FROM sse_events WHERE request_id=?", (request_id,)).fetchone()[0]
    return {"requestId": request_id, "status": request["status"], "traceId": request["trace_id"] if request else trace_id,
            "lastEventId": last_event, "lastLayer": request["last_layer"], "terminationReason": request["termination_reason"],
            "result": {"layers": layers, "sqlExecutions": sql, "resultSnapshot": json.loads(snapshot["payload"]) if snapshot else [],
                       "masked": bool(snapshot["masked"]) if snapshot else True}}


@router.get("/executions/{request_id}")
def get_execution(request_id: UUID, x_service_token: str | None = Header(default=None), x_trace_id: str = Header(min_length=1)):
    _authenticate(x_service_token)
    with _lock:
        state = _executions.get(str(request_id))
    try:
        state = _state_from_database(str(request_id), state["traceId"] if state else x_trace_id)
    except KeyError:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "执行请求不存在"})
    return state


@router.post("/executions/{request_id}/cancel", status_code=202)
async def cancel_execution(request_id: UUID, x_service_token: str | None = Header(default=None), x_trace_id: str = Header(min_length=1), idempotency_key: str = Header(min_length=8)):
    _authenticate(x_service_token)
    try:
        state = _state_from_database(str(request_id), x_trace_id)
    except KeyError:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "执行请求不存在"})
    if state["status"] not in {"SUCCEEDED","FAILED","BLOCKED","SHORT_CIRCUITED","WAITING_INPUT","CANCELLED"}:
        with connect(PLATFORM_DB) as db:
            db.execute("UPDATE requests SET cancel_requested=1,cancelled_by='java-platform',cancelled_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), str(request_id)))
        running = _active_engines.get(str(request_id))
        if running:
            awaitable = running.registry.datasource.cancel(str(request_id))
            if asyncio.iscoroutine(awaitable): asyncio.create_task(awaitable)
        status = "CANCELLATION_REQUESTED"
    else: status = "CANCELLED" if state["status"] == "CANCELLED" else "PENDING"
    return {"requestId": str(request_id), "status": status, "traceId": state["traceId"], "idempotentReplay": True}


@router.get("/executions/{request_id}/events")
def execution_events(request_id: UUID, x_service_token: str | None = Header(default=None), x_trace_id: str = Header(min_length=1), last_event_id: int = Header(default=0, alias="Last-Event-ID")):
    _authenticate(x_service_token)
    try: state = _state_from_database(str(request_id), x_trace_id)
    except KeyError: raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "执行请求不存在"})
    with connect(PLATFORM_DB) as db:
        events = [(row["event_id"], row["event_type"], json.loads(row["payload"]), row["created_at"]) for row in db.execute("SELECT * FROM sse_events WHERE request_id=? ORDER BY event_id", (str(request_id),))]
    def stream():
        for event_id, event_type, payload, occurred_at in events:
            if event_id <= last_event_id:
                continue
            data = {"eventId": event_id, "eventType": event_type, "requestId": str(request_id), "traceId": state["traceId"], "occurredAt": occurred_at, "payload": payload}
            yield f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

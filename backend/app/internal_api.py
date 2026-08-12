import hmac
import hashlib
import json
import os
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/internal/v1", tags=["internal-execution"])
_lock = RLock()
_executions: dict[str, dict[str, Any]] = {}
_idempotency: dict[str, tuple[str, str]] = {}


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
def create_execution(
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
            return {"requestId": request_id, "status": state["status"], "traceId": state["traceId"], "idempotentReplay": True}
        state = {
            "requestId": request_id,
            "status": "SUCCEEDED",
            "traceId": x_trace_id,
            "lastEventId": 2,
            "lastLayer": "L1",
            "terminationReason": "P313_SIMULATED_EXECUTION",
            "result": {"mode": "SIMULATED", "normalizedQuestion": command.question.strip()},
            "occurredAt": datetime.now(timezone.utc).isoformat(),
        }
        _executions[request_id] = state
        _idempotency[idempotency_key] = (request_id, digest)
    return {"requestId": request_id, "status": "PENDING", "traceId": x_trace_id, "idempotentReplay": False}


@router.get("/executions/{request_id}")
def get_execution(request_id: UUID, x_service_token: str | None = Header(default=None), x_trace_id: str = Header(min_length=1)):
    _authenticate(x_service_token)
    with _lock:
        state = _executions.get(str(request_id))
    if not state:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "执行请求不存在"})
    return state


@router.post("/executions/{request_id}/cancel", status_code=202)
def cancel_execution(request_id: UUID, x_service_token: str | None = Header(default=None), x_trace_id: str = Header(min_length=1), idempotency_key: str = Header(min_length=8)):
    _authenticate(x_service_token)
    with _lock:
        state = _executions.get(str(request_id))
    if not state:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "执行请求不存在"})
    return {"requestId": str(request_id), "status": state["status"], "traceId": state["traceId"], "idempotentReplay": True}


@router.get("/executions/{request_id}/events")
def execution_events(request_id: UUID, x_service_token: str | None = Header(default=None), x_trace_id: str = Header(min_length=1), last_event_id: int = Header(default=0, alias="Last-Event-ID")):
    _authenticate(x_service_token)
    with _lock:
        state = _executions.get(str(request_id))
    if not state:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "执行请求不存在"})
    events = [
        (1, "request.created", {"status": "PENDING"}),
        (2, "request.completed", {"status": state["status"], "lastLayer": state["lastLayer"]}),
    ]
    def stream():
        for event_id, event_type, payload in events:
            if event_id <= last_event_id:
                continue
            data = {"eventId": event_id, "eventType": event_type, "requestId": str(request_id), "traceId": state["traceId"], "occurredAt": state["occurredAt"], "payload": payload}
            yield f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

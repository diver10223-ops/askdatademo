import hmac
import os
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/internal/v1", tags=["internal-execution"])


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

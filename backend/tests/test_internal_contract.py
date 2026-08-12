import json
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.internal_api import ExecutionCommand
from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def command_payload():
    return {
        "requestId": "c0a80101-0000-4000-8000-000000000001",
        "sessionId": "c0a80101-0000-4000-8000-000000000002",
        "parentRequestId": None,
        "subjectId": "user-1",
        "roleIds": ["analyst"],
        "question": "2026年3月贷款余额是多少？",
        "scenarioId": "scenario-1",
        "executionMode": "POC",
        "permissionSnapshot": {"orgIds": ["head-office"], "masking": "standard"},
        "configVersionId": "official-v1",
        "providerProfileId": None,
        "timeoutMs": 30000,
    }


def test_python_provider_model_matches_frozen_required_fields():
    contract = json.loads((ROOT / "contracts/internal-execution-v1.openapi.json").read_text())
    required = set(contract["components"]["schemas"]["ExecutionCommand"]["required"])
    assert required <= set(ExecutionCommand.model_fields)
    assert ExecutionCommand.model_validate(command_payload()).executionMode == "POC"
    payload = command_payload()
    payload["unknown"] = True
    try:
        ExecutionCommand.model_validate(payload)
    except ValidationError:
        pass
    else:
        raise AssertionError("unknown fields must be rejected")


def test_internal_health_requires_service_authentication():
    with TestClient(app) as client:
        assert client.get("/internal/v1/health").status_code == 401
        response = client.get(
            "/internal/v1/health",
            headers={"X-Service-Token": "askdata-local-service-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "1.0.0"}

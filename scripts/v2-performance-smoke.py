#!/usr/bin/env python3
"""Bounded DEMO execution smoke test; this is not a capacity benchmark."""

from __future__ import annotations

import argparse
import math
import os
import statistics
import time
import uuid

from fastapi.testclient import TestClient

from app.main import app


SERVICE_TOKEN = "askdata-local-service-token"


def payload(sequence: int) -> dict:
    suffix = uuid.uuid5(uuid.NAMESPACE_URL, f"askdata-v2-performance-smoke-{sequence}")
    session = uuid.uuid5(uuid.NAMESPACE_URL, f"askdata-v2-performance-session-{sequence}")
    return {
        "requestId": str(suffix),
        "sessionId": str(session),
        "parentRequestId": None,
        "subjectId": "v2-performance-smoke",
        "roleIds": ["admin"],
        "question": "2026年3月全行贷款投放是多少？",
        "scenarioId": "scenario-1",
        "executionMode": "DEMO",
        "permissionSnapshot": {
            "orgs": ["全行", "北京分行", "上海分行"],
            "metrics": ["贷款投放", "零售贷款", "对公贷款"],
        },
        "configVersionId": "official-v1",
        "providerProfileId": None,
        "timeoutMs": 30_000,
    }


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=12)
    parser.add_argument("--max-p95-seconds", type=float, default=3.0)
    parser.add_argument("--max-total-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if not 1 <= args.requests <= 100:
        parser.error("--requests must be between 1 and 100")
    if os.getenv("ASKDATA_CREDENTIAL_KEY"):
        raise SystemExit("refusing performance smoke with ASKDATA_CREDENTIAL_KEY set")

    durations: list[float] = []
    started = time.perf_counter()
    with TestClient(app) as client:
        for sequence in range(args.requests):
            command = payload(sequence)
            headers = {
                "X-Service-Token": SERVICE_TOKEN,
                "X-Trace-Id": f"v2-perf-{sequence}",
                "Idempotency-Key": f"v2-perf-{sequence}",
            }
            request_started = time.perf_counter()
            accepted = client.post("/internal/v1/executions", json=command, headers=headers)
            assert accepted.status_code == 202, accepted.text
            for _ in range(300):
                state = client.get(f"/internal/v1/executions/{command['requestId']}", headers=headers)
                assert state.status_code == 200, state.text
                detail = state.json()
                if detail["status"] not in {"PENDING", "RUNNING"}:
                    break
                time.sleep(0.01)
            else:
                raise AssertionError(f"request {sequence} did not reach a terminal state")
            assert detail["status"] == "SUCCEEDED", detail
            assert [row["layer_code"] for row in detail["result"]["layers"]] == [f"L{i}" for i in range(1, 8)]
            assert len(detail["result"]["sqlExecutions"]) == 1
            durations.append(time.perf_counter() - request_started)

    total = time.perf_counter() - started
    p95 = percentile(durations, 0.95)
    mean = statistics.fmean(durations)
    assert p95 <= args.max_p95_seconds, f"p95 {p95:.3f}s exceeds {args.max_p95_seconds:.3f}s"
    assert total <= args.max_total_seconds, f"total {total:.3f}s exceeds {args.max_total_seconds:.3f}s"
    print(
        "PERFORMANCE_SMOKE_PASS "
        f"mode=DEMO provider=fixture requests={args.requests} "
        f"mean_seconds={mean:.3f} p95_seconds={p95:.3f} total_seconds={total:.3f}"
    )


if __name__ == "__main__":
    main()

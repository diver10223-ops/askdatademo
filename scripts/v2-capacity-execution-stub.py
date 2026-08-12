#!/usr/bin/env python3
"""Credential-free async execution-plane stub for product capacity tests only."""

from __future__ import annotations

import argparse
import time

import uvicorn
from fastapi import FastAPI, Header, Request


def build_app(hold: bool, latency_ms: int) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    requests: dict[str, tuple[float, str]] = {}
    latency = latency_ms / 1000

    @app.get("/internal/v1/health")
    async def health():
        return {"status": "ok", "version": "capacity-stub"}

    @app.post("/internal/v1/executions", status_code=202)
    async def submit(request: Request, x_trace_id: str = Header(default="capacity")):
        value = await request.json(); request_id = value["requestId"]
        replay = request_id in requests
        requests.setdefault(request_id, (time.monotonic(), x_trace_id))
        return {"requestId": request_id, "status": "PENDING", "traceId": x_trace_id, "idempotentReplay": replay}

    @app.get("/internal/v1/executions/{request_id}")
    async def state(request_id: str):
        item = requests.get(request_id)
        if item is None:
            return {"requestId": request_id, "status": "FAILED", "lastLayer": None,
                    "terminationReason": "NOT_FOUND", "result": empty_result()}
        terminal = not hold and time.monotonic() - item[0] >= latency
        return {"requestId": request_id, "status": "SUCCEEDED" if terminal else "RUNNING",
                "lastLayer": "L7" if terminal else "L1", "terminationReason": "SUCCEEDED" if terminal else None,
                "result": empty_result()}

    @app.post("/internal/v1/executions/{request_id}/cancel", status_code=202)
    async def cancel(request_id: str):
        return {"requestId": request_id, "status": "CANCELLATION_REQUESTED"}

    return app


def empty_result() -> dict:
    return {"layers": [], "sqlExecutions": [], "events": [], "resultSnapshot": [], "masked": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--hold", action="store_true")
    parser.add_argument("--latency-ms", type=int, default=100)
    args = parser.parse_args()
    uvicorn.run(build_app(args.hold, args.latency_ms), host="127.0.0.1", port=args.port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()

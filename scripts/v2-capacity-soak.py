#!/usr/bin/env python3
"""Sustained, credential-free V2 query lifecycle and resource verification."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from pathlib import Path


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


async def http_json(host: str, port: int, method: str, path: str, payload: dict | None,
                    headers: dict[str, str]) -> tuple[int, dict, float]:
    reader, writer = await asyncio.open_connection(host, port)
    body = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    values = {"Host": f"{host}:{port}", "Connection": "close", **headers}
    if payload is not None:
        values.update({"Content-Type": "application/json", "Content-Length": str(len(body))})
    request = f"{method} {path} HTTP/1.1\r\n" + "".join(f"{key}: {value}\r\n" for key, value in values.items())
    began = time.perf_counter()
    writer.write(request.encode() + b"\r\n" + body)
    await writer.drain()
    status_line = await asyncio.wait_for(reader.readline(), 5)
    status = int(status_line.split()[1])
    response_headers: dict[str, str] = {}
    while (line := await asyncio.wait_for(reader.readline(), 5)) not in {b"\r\n", b"\n", b""}:
        key, value = line.decode().split(":", 1)
        response_headers[key.lower()] = value.strip()
    length = int(response_headers.get("content-length", "0"))
    result = await asyncio.wait_for(reader.readexactly(length), 5) if length else b"{}"
    writer.close()
    await writer.wait_closed()
    return status, json.loads(result), time.perf_counter() - began


async def lifecycle(args, session: str, sequence: int) -> tuple[str, float, float]:
    trace = f"soak-{sequence:09d}"
    payload = {
        "sessionId": session, "parentRequestId": None,
        "question": "2026年3月全行贷款投放是多少？", "scenarioId": "scenario-1", "timeoutMs": 30000,
    }
    status, result, submit_seconds = await http_json(
        args.host, args.port, "POST", "/api/v2/execution/queries", payload,
        {"Idempotency-Key": trace, "X-Trace-Id": trace, "Authorization": f"Bearer {args.api_token}"},
    )
    if status != 202:
        return f"HTTP_{status}", submit_seconds, submit_seconds
    request_id = result["requestId"]
    began = time.perf_counter()
    while time.perf_counter() - began < args.terminal_timeout:
        await asyncio.sleep(args.poll_interval)
        detail_status, detail, _ = await http_json(
            args.host, args.port, "GET", f"/api/v2/execution/queries/{request_id}", None,
            {"X-Trace-Id": trace, "Authorization": f"Bearer {args.api_token}"},
        )
        if detail_status != 200:
            return f"DETAIL_HTTP_{detail_status}", submit_seconds, time.perf_counter() - began
        if detail["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return detail["status"], submit_seconds, time.perf_counter() - began
    return "TERMINAL_TIMEOUT", submit_seconds, time.perf_counter() - began


def resources(pid: int) -> tuple[int, int, int]:
    status = Path(f"/proc/{pid}/status").read_text()
    fields = {line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in status.splitlines() if ":" in line}
    return int(fields["VmRSS"].split()[0]), len(list(Path(f"/proc/{pid}/fd").iterdir())), int(fields["Threads"])


async def run(args) -> None:
    sessions = Path(args.sessions).read_text().splitlines()
    if not sessions:
        raise SystemExit("capacity session file is empty")
    interval = 1 / args.rps
    began = time.monotonic()
    next_launch = began
    tasks: set[asyncio.Task] = set()
    all_tasks: list[asyncio.Task] = []
    maxima = {"rss_kb": 0, "fds": 0, "threads": 0, "inflight": 0}
    initial = resources(args.server_pid) if args.server_pid else (0, 0, 0)
    final = initial
    sequence = 0
    next_report = began + args.report_interval
    while time.monotonic() - began < args.duration:
        now = time.monotonic()
        while next_launch <= now and time.monotonic() - began < args.duration:
            task = asyncio.create_task(lifecycle(args, sessions[sequence % len(sessions)], sequence))
            tasks.add(task)
            all_tasks.append(task)
            task.add_done_callback(tasks.discard)
            sequence += 1
            next_launch += interval
        maxima["inflight"] = max(maxima["inflight"], len(tasks))
        if args.server_pid:
            rss, fds, threads = resources(args.server_pid)
            final = (rss, fds, threads)
            maxima["rss_kb"] = max(maxima["rss_kb"], rss)
            maxima["fds"] = max(maxima["fds"], fds)
            maxima["threads"] = max(maxima["threads"], threads)
        if now >= next_report:
            print(f"SOAK_PROGRESS elapsed_seconds={now-began:.1f} launched={sequence} completed={len(all_tasks)-len(tasks)} inflight={len(tasks)}", flush=True)
            next_report += args.report_interval
        await asyncio.sleep(min(.05, max(.001, next_launch - time.monotonic())))
    outcomes = await asyncio.gather(*all_tasks)
    elapsed = time.monotonic() - began
    states: dict[str, int] = {}
    for state, _, _ in outcomes:
        states[state] = states.get(state, 0) + 1
    submit = [item[1] for item in outcomes]
    terminal = [item[2] for item in outcomes]
    success = states.get("SUCCEEDED", 0)
    failure_rate = 1 - success / max(1, len(outcomes))
    print("CAPACITY_SOAK_RESULT " + " ".join([
        f"label={args.label}", f"required_seconds={args.duration:.3f}", f"elapsed_seconds={elapsed:.3f}",
        f"launched={sequence}", f"completed={len(outcomes)}", f"states={json.dumps(states,sort_keys=True,separators=(',',':'))}",
        f"failure_rate={failure_rate:.6f}", f"submit_p95_seconds={percentile(submit,.95):.3f}",
        f"submit_p99_seconds={percentile(submit,.99):.3f}", f"terminal_p95_seconds={percentile(terminal,.95):.3f}",
        f"terminal_p99_seconds={percentile(terminal,.99):.3f}", f"max_inflight={maxima['inflight']}",
        f"initial_rss_kb={initial[0]}", f"final_rss_kb={final[0]}", f"rss_growth_kb={final[0]-initial[0]}",
        f"max_rss_kb={maxima['rss_kb']}", f"max_fds={maxima['fds']}", f"max_platform_threads={maxima['threads']}",
    ]), flush=True)
    assert elapsed >= args.duration, (elapsed, args.duration)
    assert sequence == len(outcomes) and sequence > 0
    assert failure_rate <= args.max_failure_rate, (failure_rate, args.max_failure_rate)
    assert percentile(submit, .99) <= args.max_submit_p99, percentile(submit, .99)
    assert percentile(terminal, .95) <= args.max_terminal_p95, percentile(terminal, .95)
    assert percentile(terminal, .99) <= args.max_terminal_p99, percentile(terminal, .99)
    assert final[0] - initial[0] <= args.max_rss_growth_kb, (initial[0], final[0], args.max_rss_growth_kb)
    print(f"CAPACITY_SOAK_PASS label={args.label}", flush=True)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--label", required=True)
    value.add_argument("--host", default="127.0.0.1")
    value.add_argument("--port", type=int, required=True)
    value.add_argument("--sessions", required=True)
    value.add_argument("--duration", type=float, required=True)
    value.add_argument("--rps", type=float, required=True)
    value.add_argument("--server-pid", type=int)
    value.add_argument("--api-token", default="askdata-capacity-platform-api-token-32-bytes-minimum")
    value.add_argument("--poll-interval", type=float, default=.25)
    value.add_argument("--terminal-timeout", type=float, default=30)
    value.add_argument("--report-interval", type=float, default=60)
    value.add_argument("--max-failure-rate", type=float, default=.01)
    value.add_argument("--max-submit-p99", type=float, default=1)
    value.add_argument("--max-terminal-p95", type=float, default=15)
    value.add_argument("--max-terminal-p99", type=float, default=30)
    value.add_argument("--max-rss-growth-kb", type=int, default=524288)
    return value


if __name__ == "__main__":
    asyncio.run(run(parser().parse_args()))

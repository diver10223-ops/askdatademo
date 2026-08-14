#!/usr/bin/env python3
"""Raw-HTTP load client for bounded AskData V2 product-capacity evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
from collections import Counter
import time
from pathlib import Path


async def response(reader: asyncio.StreamReader) -> tuple[int, dict[str, str], bytes]:
    status_line = await asyncio.wait_for(reader.readline(), 10)
    if not status_line:
        raise RuntimeError("connection closed before status")
    status = int(status_line.split()[1])
    headers: dict[str, str] = {}
    while True:
        line = await asyncio.wait_for(reader.readline(), 10)
        if line in {b"\r\n", b"\n", b""}:
            break
        key, value = line.decode().split(":", 1)
        headers[key.lower()] = value.strip()
    if headers.get("transfer-encoding", "").lower() == "chunked":
        chunks: list[bytes] = []
        while True:
            size_line = await asyncio.wait_for(reader.readline(), 10)
            size = int(size_line.split(b";", 1)[0], 16)
            if size == 0:
                await asyncio.wait_for(reader.readline(), 10)
                break
            chunks.append(await asyncio.wait_for(reader.readexactly(size), 10))
            await asyncio.wait_for(reader.readexactly(2), 10)
        body = b"".join(chunks)
    else:
        body = await asyncio.wait_for(reader.readexactly(int(headers.get("content-length", "0"))), 10)
    return status, headers, body


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


async def submit(args, session: str, sequence: int, start: asyncio.Event, ready: asyncio.Queue):
    host, port = args.host, args.port
    reader, writer = await asyncio.open_connection(host, port)
    await ready.put(sequence)
    await start.wait()
    began = time.perf_counter()
    payload = json.dumps({
        "sessionId": session, "parentRequestId": None,
        "question": "2026年3月全行贷款投放是多少？", "scenarioId": "scenario-1", "timeoutMs": 30000,
    }, separators=(",", ":")).encode()
    request = (
        f"POST /api/v2/execution/queries HTTP/1.1\r\nHost: {host}:{port}\r\n"
        f"Content-Type: application/json\r\nContent-Length: {len(payload)}\r\n"
        f"Authorization: Bearer {args.api_token}\r\n"
        f"Idempotency-Key: capacity-{sequence:06d}\r\nX-Trace-Id: capacity-{sequence:06d}\r\n"
        "Connection: close\r\n\r\n"
    ).encode() + payload
    writer.write(request); await writer.drain()
    status, headers, body = await response(reader)
    writer.close(); await writer.wait_closed()
    elapsed = time.perf_counter() - began
    value = json.loads(body)
    return status, headers, value, elapsed, began


async def burst(args) -> None:
    sessions = Path(args.sessions).read_text().splitlines()
    if len(sessions) < args.requests:
        raise SystemExit("not enough capacity sessions")
    start = asyncio.Event()
    ready: asyncio.Queue = asyncio.Queue()
    tasks = [asyncio.create_task(submit(args, sessions[i], i, start, ready)) for i in range(args.requests)]
    for _ in range(args.requests): await asyncio.wait_for(ready.get(), 30)
    began = time.perf_counter(); start.set(); results = await asyncio.gather(*tasks); total = time.perf_counter() - began
    statuses = [item[0] for item in results]
    durations = [item[3] for item in results]
    accepted = [item[2]["requestId"] for item in results if item[0] == 202]
    overload = [item for item in results if item[0] in {429, 503}]
    unexpected = [status for status in statuses if status not in {202, 429, 503}]
    assert not unexpected, unexpected
    assert len(accepted) == args.expected_accepted, (len(accepted), args.expected_accepted)
    assert all(item[1].get("retry-after") == "1" for item in overload)
    p99 = percentile(durations, .99)
    dispatch_span = max(item[4] for item in results) - min(item[4] for item in results)
    offered_qps = args.requests / max(dispatch_span, .000001)
    completion_qps = args.requests / total
    print("CAPACITY_BURST_RESULT " + " ".join([
        f"requests={args.requests}", f"accepted={len(accepted)}", f"overloaded={len(overload)}",
        f"offered_qps={offered_qps:.2f}", f"completion_qps={completion_qps:.2f}",
        f"mean_seconds={statistics.fmean(durations):.3f}", f"p99_seconds={p99:.3f}",
    ]))
    assert p99 <= args.max_p99_seconds, (p99, args.max_p99_seconds)
    assert offered_qps >= args.min_qps, (offered_qps, args.min_qps)
    if args.accepted_output:
        Path(args.accepted_output).write_text("\n".join(accepted) + "\n")
    print("CAPACITY_BURST_PASS")


async def sse_connection(args, sequence: int, start: asyncio.Event, ready: asyncio.Queue, all_connected: asyncio.Event):
    await start.wait()
    await asyncio.sleep(args.ramp_seconds * sequence / max(1, args.connections - 1))
    reader, writer = await asyncio.open_connection(args.host, args.port)
    request = (
        f"GET /api/v2/execution/queries/{args.request_id}/events HTTP/1.1\r\n"
        f"Host: {args.host}:{args.port}\r\nAccept: text/event-stream\r\n"
        f"Authorization: Bearer {args.api_token}\r\nConnection: close\r\n\r\n"
    ).encode()
    writer.write(request); await writer.drain()
    status_line = await asyncio.wait_for(reader.readline(), args.connect_timeout)
    assert int(status_line.split()[1]) == 200
    headers: dict[str, str] = {}
    while (line := await asyncio.wait_for(reader.readline(), args.connect_timeout)) not in {b"\r\n", b"\n", b""}:
        key, value = line.decode().split(":", 1); headers[key.lower()] = value.strip()
    await ready.put(sequence)
    await all_connected.wait()
    deadline = time.monotonic() + args.duration
    event_ids: list[int] = []
    heartbeat = False
    retry = False
    buffer = b""
    while time.monotonic() < deadline:
        try:
            timeout = min(2, max(.1, deadline - time.monotonic()))
            if headers.get("transfer-encoding", "").lower() == "chunked":
                size_line = await asyncio.wait_for(reader.readline(), timeout)
                size = int(size_line.split(b";", 1)[0], 16)
                if size == 0: break
                chunk = await asyncio.wait_for(reader.readexactly(size), timeout)
                await asyncio.wait_for(reader.readexactly(2), timeout)
            else:
                chunk = await asyncio.wait_for(reader.read(4096), timeout)
        except asyncio.TimeoutError:
            continue
        if not chunk:
            break
        if args.debug and sequence == 0:
            print(f"SSE_DEBUG headers={headers} chunk={chunk[:300]!r}")
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            text = line.decode().strip()
            if text.startswith("id:"):
                event_ids.append(int(text[3:].strip()))
            elif text in {": heartbeat", ":heartbeat"}:
                heartbeat = True
            elif text in {"retry: 1000", "retry:1000"}:
                retry = True
    writer.close(); await writer.wait_closed()
    return event_ids, heartbeat, retry


async def sse(args) -> None:
    stop_sample = asyncio.Event()
    async def sample_resources():
        maximum = {"rss_kb": 0, "fds": 0, "threads": 0}
        if not args.server_pid:
            return maximum
        status_path = Path(f"/proc/{args.server_pid}/status")
        fd_path = Path(f"/proc/{args.server_pid}/fd")
        while not stop_sample.is_set():
            fields = {line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in status_path.read_text().splitlines() if ":" in line}
            maximum["rss_kb"] = max(maximum["rss_kb"], int(fields["VmRSS"].split()[0]))
            maximum["threads"] = max(maximum["threads"], int(fields["Threads"]))
            maximum["fds"] = max(maximum["fds"], len(list(fd_path.iterdir())))
            try: await asyncio.wait_for(stop_sample.wait(), .2)
            except asyncio.TimeoutError: pass
        return maximum
    sampler = asyncio.create_task(sample_resources())
    start = asyncio.Event(); all_connected = asyncio.Event(); ready: asyncio.Queue = asyncio.Queue()
    tasks = [asyncio.create_task(sse_connection(args, i, start, ready, all_connected)) for i in range(args.connections)]
    began = time.perf_counter(); start.set()
    for _ in range(args.connections):
        await asyncio.wait_for(ready.get(), args.connect_timeout + args.ramp_seconds)
    established = time.perf_counter() - began
    all_connected.set(); results = await asyncio.gather(*tasks); elapsed = time.perf_counter() - began
    stop_sample.set(); resources = await sampler
    expected = list(range(1, args.events + 1))
    distributions = Counter(tuple(ids) for ids, _, _ in results)
    print(f"CAPACITY_SSE_RESULT distributions={dict(distributions)} heartbeats={sum(heartbeat for _, heartbeat, _ in results)} retries={sum(retry for _, _, retry in results)}")
    assert all(ids == expected for ids, _, _ in results), "SSE event order/loss/duplication detected"
    assert all(heartbeat for _, heartbeat, _ in results), "not every SSE connection received heartbeat"
    assert all(retry for _, _, retry in results), "not every SSE connection received retry guidance"
    print(f"CAPACITY_SSE_PASS connections={args.connections} events_per_connection={args.events} establish_seconds={established:.3f} simultaneous_hold_seconds={args.duration:.3f} total_seconds={elapsed:.3f} ordered=true duplicated=false lost=false max_rss_kb={resources['rss_kb']} max_fds={resources['fds']} max_platform_threads={resources['threads']}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="mode", required=True)
    burst_parser = sub.add_parser("burst")
    burst_parser.add_argument("--host", default="127.0.0.1"); burst_parser.add_argument("--port", type=int, required=True)
    burst_parser.add_argument("--sessions", required=True); burst_parser.add_argument("--requests", type=int, required=True)
    burst_parser.add_argument("--expected-accepted", type=int, required=True); burst_parser.add_argument("--accepted-output")
    burst_parser.add_argument("--max-p99-seconds", type=float, default=1); burst_parser.add_argument("--min-qps", type=float, default=0)
    burst_parser.add_argument("--api-token", default="askdata-capacity-platform-api-token-32-bytes-minimum")
    sse_parser = sub.add_parser("sse")
    sse_parser.add_argument("--host", default="127.0.0.1"); sse_parser.add_argument("--port", type=int, required=True)
    sse_parser.add_argument("--request-id", required=True); sse_parser.add_argument("--connections", type=int, default=1300)
    sse_parser.add_argument("--events", type=int, default=3); sse_parser.add_argument("--duration", type=float, default=12)
    sse_parser.add_argument("--connect-timeout", type=float, default=30)
    sse_parser.add_argument("--ramp-seconds", type=float, default=20)
    sse_parser.add_argument("--server-pid", type=int)
    sse_parser.add_argument("--debug", action="store_true")
    sse_parser.add_argument("--api-token", default="askdata-capacity-platform-api-token-32-bytes-minimum")
    return root


if __name__ == "__main__":
    arguments = parser().parse_args()
    asyncio.run(burst(arguments) if arguments.mode == "burst" else sse(arguments))

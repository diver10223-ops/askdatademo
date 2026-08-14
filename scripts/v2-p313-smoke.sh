#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_port="${ASKDATA_P313_PYTHON_PORT:-18000}"
java_port="${ASKDATA_P313_JAVA_PORT:-18080}"
log_dir="$(mktemp -d /tmp/askdata-p313-smoke.XXXXXX)"
service_token="askdata-p313-isolated-test-token"

if ! command -v java >/dev/null 2>&1; then
  echo "Java 21 is required (set JAVA_HOME and prepend JAVA_HOME/bin to PATH)." >&2
  exit 2
fi

cleanup() {
  kill "${java_pid:-}" "${python_pid:-}" 2>/dev/null || true
}
trap cleanup EXIT

cd "$root_dir"
./platform-service/mvnw -f platform-service/pom.xml -q -DskipTests package
ASKDATA_INTERNAL_SERVICE_TOKEN="$service_token" ASKDATA_DATA_DIR="$log_dir/data" PYTHONPATH=backend .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$python_port" >"$log_dir/python.log" 2>&1 &
python_pid=$!
ASKDATA_PLATFORM_PORT="$java_port" \
ASKDATA_EXECUTION_BASE_URL="http://127.0.0.1:$python_port" \
ASKDATA_INTERNAL_SERVICE_TOKEN="$service_token" \
ASKDATA_PLATFORM_API_TOKEN=askdata-p313-platform-api-token-32-bytes-minimum \
ASKDATA_PLATFORM_DB_URL='jdbc:h2:mem:p313;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1' \
ASKDATA_PLATFORM_DB_USERNAME=sa ASKDATA_PLATFORM_DB_PASSWORD=p313-isolated \
ASKDATA_MIGRATION_DB_USERNAME=sa ASKDATA_MIGRATION_DB_PASSWORD=p313-isolated \
java -jar platform-service/target/platform-service-2.0.0.jar >"$log_dir/java.log" 2>&1 &
java_pid=$!

ready=false
for _attempt in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$java_port/api/v2/health" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 0.25
done
if [[ "$ready" != true ]]; then
  echo "P313 smoke failed to start; logs: $log_dir" >&2
  exit 1
fi

health="$(curl -fsS "http://127.0.0.1:$java_port/api/v2/execution/health" -H 'Authorization: Bearer askdata-p313-platform-api-token-32-bytes-minimum')"
response="$(curl -fsS -X POST "http://127.0.0.1:$python_port/internal/v1/executions" \
  -H 'Content-Type: application/json' \
  -H "X-Service-Token: $service_token" \
  -H 'Idempotency-Key: p313-e2e-idempotency' \
  -H 'X-Trace-Id: p313-e2e-trace' \
  --data '{"requestId":"c0a80101-0000-4000-8000-000000000011","sessionId":"c0a80101-0000-4000-8000-000000000012","parentRequestId":null,"subjectId":"p313-user","roleIds":["admin"],"question":"2026年3月全行贷款投放是多少？","scenarioId":"scenario-1","executionMode":"DEMO","permissionSnapshot":{"orgs":["全行","北京分行","上海分行"],"metrics":["贷款投放","零售贷款","对公贷款"]},"configVersionId":"official-v1","providerProfileId":null,"timeoutMs":30000}')"

state=''
for _attempt in $(seq 1 100); do
  state="$(curl -fsS "http://127.0.0.1:$python_port/internal/v1/executions/c0a80101-0000-4000-8000-000000000011" -H "X-Service-Token: $service_token" -H 'X-Trace-Id: p313-e2e-trace')"
  current_status="$(python -c 'import json,sys; print(json.loads(sys.argv[1])["status"])' "$state")"
  [[ "$current_status" != PENDING && "$current_status" != RUNNING ]] && break
  sleep 0.05
done

python - "$health" "$response" "$state" <<'PY'
import json
import sys
health, response, state = map(json.loads, sys.argv[1:])
assert health == {"status": "ok", "version": "1.0.0"}, health
assert response["requestId"] == "c0a80101-0000-4000-8000-000000000011", response
assert response["status"] == "PENDING", response
assert response["traceId"] == "p313-e2e-trace", response
assert state["status"] == "SUCCEEDED", state
assert [item["layer_code"] for item in state["result"]["layers"]] == [f"L{i}" for i in range(1, 8)], state
assert len(state["result"]["sqlExecutions"]) == 1, state
assert state["result"]["resultSnapshot"], state
assert state["terminationReason"] != "P313_SIMULATED_EXECUTION", state
print("P350 READY: Java control-plane connectivity + real Python L1-L7 execution")
PY

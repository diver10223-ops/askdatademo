#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_port="${ASKDATA_P313_PYTHON_PORT:-18000}"
java_port="${ASKDATA_P313_JAVA_PORT:-18080}"
log_dir="$(mktemp -d /tmp/askdata-p313-smoke.XXXXXX)"

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
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$python_port" >"$log_dir/python.log" 2>&1 &
python_pid=$!
ASKDATA_PLATFORM_PORT="$java_port" \
ASKDATA_EXECUTION_BASE_URL="http://127.0.0.1:$python_port" \
ASKDATA_PLATFORM_DB_URL='jdbc:h2:mem:p313;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1' \
java -jar platform-service/target/platform-service-2.0.0-SNAPSHOT.jar >"$log_dir/java.log" 2>&1 &
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

health="$(curl -fsS "http://127.0.0.1:$java_port/api/v2/execution/health")"
response="$(curl -fsS -X POST "http://127.0.0.1:$java_port/api/v2/execution/simulate" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: p313-e2e-idempotency' \
  -H 'X-Trace-Id: p313-e2e-trace' \
  --data '{"requestId":"c0a80101-0000-4000-8000-000000000011","sessionId":"c0a80101-0000-4000-8000-000000000012","parentRequestId":null,"subjectId":"p313-user","roleIds":["analyst"],"question":"联调贷款余额","scenarioId":"scenario-1","executionMode":"POC","permissionSnapshot":{"orgIds":["head-office"]},"configVersionId":"official-v1","providerProfileId":null,"timeoutMs":30000}')"

python - "$health" "$response" <<'PY'
import json
import sys
health, response = map(json.loads, sys.argv[1:])
assert health == {"status": "ok", "version": "1.0.0"}, health
assert response["requestId"] == "c0a80101-0000-4000-8000-000000000011", response
assert response["status"] == "PENDING", response
assert response["traceId"] == "p313-e2e-trace", response
print("P313 READY: Java control plane -> Python execution plane")
PY

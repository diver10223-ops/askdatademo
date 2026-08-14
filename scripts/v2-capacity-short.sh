#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
capacity_root="$(mktemp -d /tmp/askdata-v2-capacity-short.XXXXXX)"
[[ "$capacity_root" == /tmp/askdata-v2-capacity-short.* ]] || exit 2
stub_port="${ASKDATA_CAPACITY_STUB_PORT:-18100}"
stub_pid=""; app_pid=""
cleanup() {
  local status=$?
  [[ -z "$app_pid" ]] || kill "$app_pid" 2>/dev/null || true
  [[ -z "$stub_pid" ]] || kill "$stub_pid" 2>/dev/null || true
  if [[ $status -eq 0 ]]; then rm -rf -- "$capacity_root"; else echo "capacity artifacts retained: $capacity_root" >&2; fi
}
trap cleanup EXIT

command -v java >/dev/null 2>&1 || { echo "Java 21 is required" >&2; exit 2; }
python_bin="$repo_root/.venv/bin/python"
"$repo_root/platform-service/mvnw" -f "$repo_root/platform-service/pom.xml" -q -DskipTests package
jar_file="$repo_root/platform-service/target/platform-service-2.0.0.jar"
h2_jar="$(find "$HOME/.m2/repository/com/h2database/h2" -name 'h2-*.jar' -type f | sort -V | tail -1)"
classpath="$repo_root/platform-service/target/classes:$h2_jar"

"$python_bin" "$repo_root/scripts/v2-capacity-execution-stub.py" --port "$stub_port" --hold >"$capacity_root/stub.log" 2>&1 &
stub_pid=$!

stop_app() {
  kill "$app_pid"
  wait "$app_pid" || true
  app_pid=""
}

start_app() {
  local limit="$1" port="$2" database="$3" log="$4"
  ASKDATA_PLATFORM_DB_URL="jdbc:h2:file:$database;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE" \
  ASKDATA_MIGRATION_DB_URL="jdbc:h2:file:$database;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE" \
  ASKDATA_PLATFORM_DB_USERNAME=sa ASKDATA_PLATFORM_DB_PASSWORD=capacity \
  ASKDATA_MIGRATION_DB_USERNAME=sa ASKDATA_MIGRATION_DB_PASSWORD=capacity \
  ASKDATA_INTERNAL_SERVICE_TOKEN=askdata-capacity-isolated-test-token \
  ASKDATA_PLATFORM_API_TOKEN=askdata-capacity-platform-api-token-32-bytes-minimum \
  ASKDATA_PLATFORM_PORT="$port" ASKDATA_SEED_ENABLED=true ASKDATA_SEED_DIRECTORY="$repo_root/fixtures" \
  ASKDATA_EXECUTION_BASE_URL="http://127.0.0.1:$stub_port" ASKDATA_EXECUTION_MAX_CONCURRENCY="$limit" \
  ASKDATA_EXECUTION_PER_USER_CONCURRENCY=2 ASKDATA_EXECUTION_QUEUE_CAPACITY=50 ASKDATA_EXECUTION_MAX_QUEUE_WAIT_MS=50 \
  java -jar "$jar_file" >"$log" 2>&1 &
  app_pid=$!
  for _attempt in $(seq 1 120); do
    curl -fsS "http://127.0.0.1:$port/api/v2/health" >/dev/null 2>&1 && return 0
    kill -0 "$app_pid" 2>/dev/null || { echo "capacity application stopped; log=$log" >&2; return 1; }
    sleep .25
  done
  echo "capacity application startup timed out; log=$log" >&2; return 1
}

seed_sessions() {
  local database="$1" count="$2" output="$3"
  java -cp "$classpath" com.askdata.platform.capacity.CapacitySeedTool sessions \
    "jdbc:h2:file:$database;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE" sa capacity "$count" "$output"
}

# Verify the lower execution-concurrency product setting independently.
start_app 30 18130 "$capacity_root/limit30" "$capacity_root/limit30.log"
seed_sessions "$capacity_root/limit30" 40 "$capacity_root/sessions30.txt"
"$python_bin" "$repo_root/scripts/v2-capacity-load.py" burst --port 18130 --sessions "$capacity_root/sessions30.txt" \
  --requests 30 --expected-accepted 30 --max-p99-seconds 1 --min-qps 30
stop_app

# Verify 50 active executions, a 200-QPS short burst and explicit overload responses.
start_app 50 18150 "$capacity_root/limit50" "$capacity_root/limit50.log"
seed_sessions "$capacity_root/limit50" 260 "$capacity_root/sessions50.txt"
"$python_bin" "$repo_root/scripts/v2-capacity-load.py" burst --port 18150 --sessions "$capacity_root/sessions50.txt" \
  --requests 50 --expected-accepted 50 --accepted-output "$capacity_root/accepted.txt" --max-p99-seconds 1 --min-qps 50
tail -n +51 "$capacity_root/sessions50.txt" >"$capacity_root/sessions-burst.txt"
"$python_bin" "$repo_root/scripts/v2-capacity-load.py" burst --port 18150 --sessions "$capacity_root/sessions-burst.txt" \
  --requests 200 --expected-accepted 0 --max-p99-seconds 1 --min-qps 200
request_id="$(sed -n '1p' "$capacity_root/accepted.txt")"
java -cp "$classpath" com.askdata.platform.capacity.CapacitySeedTool events \
  "jdbc:h2:file:$capacity_root/limit50;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE" sa capacity "$request_id" 3
"$python_bin" "$repo_root/scripts/v2-capacity-load.py" sse --port 18150 --request-id "$request_id" \
  --connections "${ASKDATA_CAPACITY_SSE_CONNECTIONS:-1300}" --events 3 --duration "${ASKDATA_CAPACITY_SSE_DURATION:-12}" \
  --ramp-seconds "${ASKDATA_CAPACITY_SSE_RAMP_SECONDS:-20}" --connect-timeout 90 --server-pid "$app_pid" ${ASKDATA_CAPACITY_SSE_DEBUG:+--debug}
stop_app
echo "CAPACITY_SHORT_GATE_PASS limits=30,50 burst_qps=200 sse_connections=1300 artifacts=$capacity_root"

#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode="${1:-}"
case "$mode" in
  peak) duration="${ASKDATA_CAPACITY_DURATION_SECONDS:-1800}"; rps="${ASKDATA_CAPACITY_RPS:-20}" ;;
  steady) duration="${ASKDATA_CAPACITY_DURATION_SECONDS:-28800}"; rps="${ASKDATA_CAPACITY_RPS:-1}" ;;
  *) echo "usage: $0 <peak|steady>" >&2; exit 2 ;;
esac
test_root="$(mktemp -d "/tmp/askdata-v2-capacity-${mode}.XXXXXX")"
stub_port="${ASKDATA_CAPACITY_STUB_PORT:-18200}"
app_port="${ASKDATA_CAPACITY_APP_PORT:-18250}"
stub_pid=""; app_pid=""
cleanup() {
  status=$?
  [[ -z "$app_pid" ]] || kill "$app_pid" 2>/dev/null || true
  [[ -z "$stub_pid" ]] || kill "$stub_pid" 2>/dev/null || true
  if [[ $status -eq 0 ]]; then rm -rf -- "$test_root"; else echo "capacity artifacts retained: $test_root" >&2; fi
}
trap cleanup EXIT

command -v java >/dev/null 2>&1 || { echo "Java 21 is required" >&2; exit 2; }
python_bin="$repo_root/.venv/bin/python"
"$repo_root/platform-service/mvnw" -f "$repo_root/platform-service/pom.xml" -q -DskipTests package
jar_file="$repo_root/platform-service/target/platform-service-2.0.0-SNAPSHOT.jar"
h2_jar="$(find "$HOME/.m2/repository/com/h2database/h2" -name 'h2-*.jar' -type f | sort -V | tail -1)"
classpath="$repo_root/platform-service/target/classes:$h2_jar"

"$python_bin" "$repo_root/scripts/v2-capacity-execution-stub.py" --port "$stub_port" --latency-ms 100 >"$test_root/stub.log" 2>&1 &
stub_pid=$!
database="$test_root/platform"
ASKDATA_PLATFORM_DB_URL="jdbc:h2:file:$database;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE" \
ASKDATA_MIGRATION_DB_URL="jdbc:h2:file:$database;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE" \
ASKDATA_PLATFORM_DB_USERNAME=sa ASKDATA_PLATFORM_DB_PASSWORD=capacity \
ASKDATA_MIGRATION_DB_USERNAME=sa ASKDATA_MIGRATION_DB_PASSWORD=capacity \
ASKDATA_PLATFORM_PORT="$app_port" ASKDATA_SEED_ENABLED=true ASKDATA_SEED_DIRECTORY="$repo_root/fixtures" \
ASKDATA_EXECUTION_BASE_URL="http://127.0.0.1:$stub_port" ASKDATA_EXECUTION_MAX_CONCURRENCY=50 \
ASKDATA_EXECUTION_PER_USER_CONCURRENCY=2 ASKDATA_EXECUTION_QUEUE_CAPACITY=50 ASKDATA_EXECUTION_MAX_QUEUE_WAIT_MS=50 \
java -jar "$jar_file" >"$test_root/platform.log" 2>&1 &
app_pid=$!
for _attempt in $(seq 1 120); do
  curl -fsS "http://127.0.0.1:$app_port/api/v2/health" >/dev/null 2>&1 && break
  kill -0 "$app_pid" 2>/dev/null || { echo "capacity application stopped; artifacts=$test_root" >&2; exit 1; }
  sleep .25
done
curl -fsS "http://127.0.0.1:$app_port/api/v2/health" >/dev/null
java -cp "$classpath" com.askdata.platform.capacity.CapacitySeedTool sessions \
  "jdbc:h2:file:$database;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE" sa capacity 500 "$test_root/sessions.txt"
"$python_bin" "$repo_root/scripts/v2-capacity-soak.py" --label "$mode" --port "$app_port" \
  --sessions "$test_root/sessions.txt" --duration "$duration" --rps "$rps" --server-pid "$app_pid"
echo "CAPACITY_SOAK_GATE_PASS mode=$mode duration_seconds=$duration rps=$rps"

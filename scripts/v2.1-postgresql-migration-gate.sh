#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${ASKDATA_V21_POSTGRES_URL:?set ASKDATA_V21_POSTGRES_URL to an isolated empty PostgreSQL database}"
: "${ASKDATA_V21_POSTGRES_USERNAME:?set ASKDATA_V21_POSTGRES_USERNAME}"
: "${ASKDATA_V21_POSTGRES_PASSWORD:?set ASKDATA_V21_POSTGRES_PASSWORD}"

case "$ASKDATA_V21_POSTGRES_URL" in
  jdbc:postgresql://*) ;;
  *) echo "ASKDATA_V21_POSTGRES_URL must be a PostgreSQL JDBC URL" >&2; exit 2 ;;
esac

command -v java >/dev/null 2>&1 || { echo "Java 21 is required" >&2; exit 2; }
JAVA_HOME="${JAVA_HOME:?JAVA_HOME must point to Java 21}" "$repo_root/platform-service/mvnw" \
  -f "$repo_root/platform-service/pom.xml" -q -DskipTests package

ASKDATA_PLATFORM_DB_URL="$ASKDATA_V21_POSTGRES_URL" \
ASKDATA_MIGRATION_DB_URL="$ASKDATA_V21_POSTGRES_URL" \
ASKDATA_PLATFORM_DB_USERNAME="$ASKDATA_V21_POSTGRES_USERNAME" \
ASKDATA_PLATFORM_DB_PASSWORD="$ASKDATA_V21_POSTGRES_PASSWORD" \
ASKDATA_MIGRATION_DB_USERNAME="$ASKDATA_V21_POSTGRES_USERNAME" \
ASKDATA_MIGRATION_DB_PASSWORD="$ASKDATA_V21_POSTGRES_PASSWORD" \
ASKDATA_INTERNAL_SERVICE_TOKEN=askdata-v21-postgresql-gate-token \
ASKDATA_PLATFORM_API_TOKEN=askdata-v21-postgresql-api-token-32-bytes \
ASKDATA_SEED_ENABLED=false ASKDATA_PLATFORM_PORT=0 \
timeout 90 java -jar "$repo_root/platform-service/target/platform-service-2.0.0.jar" > /tmp/askdata-v21-postgresql-gate.log 2>&1 &
app_pid=$!
trap 'kill "$app_pid" 2>/dev/null || true' EXIT

for _attempt in $(seq 1 180); do
  if grep -q 'Started PlatformServiceApplication' /tmp/askdata-v21-postgresql-gate.log; then
    echo "POSTGRESQL_MIGRATION_GATE_PASS flyway=17"
    exit 0
  fi
  kill -0 "$app_pid" 2>/dev/null || { tail -80 /tmp/askdata-v21-postgresql-gate.log >&2; exit 1; }
  sleep .5
done
echo "PostgreSQL migration gate timed out" >&2
exit 1

#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
drill_root="$(mktemp -d /tmp/askdata-v2-migration.XXXXXX)"
[[ "$drill_root" == /tmp/askdata-v2-migration.* ]] || exit 2
cleanup() {
  local status=$?
  [[ -z "${app_pid:-}" ]] || kill "$app_pid" 2>/dev/null || true
  if [[ $status -eq 0 ]]; then
    rm -rf -- "$drill_root"
  else
    echo "migration drill artifacts retained: $drill_root" >&2
  fi
}
trap cleanup EXIT

command -v java >/dev/null 2>&1 || { echo "Java 21 is required" >&2; exit 2; }
"$repo_root/platform-service/mvnw" -f "$repo_root/platform-service/pom.xml" -q -DskipTests package
jar_file="$repo_root/platform-service/target/platform-service-2.0.0-SNAPSHOT.jar"
h2_jar="$(find "$HOME/.m2/repository/com/h2database/h2" -name 'h2-*.jar' -type f | sort -V | tail -1)"
classpath="$repo_root/platform-service/target/classes:$h2_jar"
pre_url="jdbc:h2:file:$drill_root/pre-upgrade;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE"
rollback_url="jdbc:h2:file:$drill_root/rollback;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE"

inventory() {
  java -cp "$classpath" com.askdata.platform.recovery.DatabaseRecoveryTool inventory "$1" sa migration "$2" h2
}

start_platform() {
  local url="$1" seed="$2" log="$3"
  # H2 AUTO_SERVER leaves a short lock hand-off window after an inventory client exits.
  sleep 2
  ASKDATA_PLATFORM_DB_URL="$url" ASKDATA_MIGRATION_DB_URL="$url" \
  ASKDATA_PLATFORM_DB_USERNAME=sa ASKDATA_PLATFORM_DB_PASSWORD=migration \
  ASKDATA_MIGRATION_DB_USERNAME=sa ASKDATA_MIGRATION_DB_PASSWORD=migration \
  ASKDATA_PLATFORM_PORT=0 ASKDATA_SEED_ENABLED="$seed" ASKDATA_SEED_DIRECTORY="$repo_root/fixtures" \
  java -jar "$jar_file" >"$log" 2>&1 &
  app_pid=$!
  # Do not let an external inventory connection race the application's first file open.
  for _attempt in $(seq 1 120); do
    grep -q 'Started PlatformServiceApplication' "$log" && return 0
    if ! kill -0 "$app_pid" 2>/dev/null; then
      echo "migration application stopped during startup; log=$log" >&2
      return 1
    fi
    sleep .25
  done
  echo "migration application startup timed out; log=$log" >&2
  return 1
}

wait_for_inventory() {
  local url="$1" output="$2" expected_seed_count="$3"
  for _attempt in $(seq 1 120); do
    if inventory "$url" "$output" 2>/dev/null && grep -q "^seed.import.count=$expected_seed_count$" "$output"; then
      return 0
    fi
    if ! kill -0 "$app_pid" 2>/dev/null; then
      echo "migration application stopped unexpectedly; log=$4" >&2
      return 1
    fi
    sleep .25
  done
  echo "migration application did not become ready; log=$4" >&2
  return 1
}

stop_platform() {
  kill "$app_pid"
  wait "$app_pid" || true
  app_pid=""
}

# Establish the fully migrated schema before importing any V1.x/V2 legacy facts.
start_platform "$pre_url" false "$drill_root/pre.log"
wait_for_inventory "$pre_url" "$drill_root/pre.inventory" 0 "$drill_root/pre.log"
stop_platform

# Take the required indivisible rollback point: database + release + secret recovery material.
printf 'migration-drill-secret-recovery-placeholder\n' >"$drill_root/secret.bundle"
export ASKDATA_BACKUP_OUTPUT="$drill_root/backup" ASKDATA_PLATFORM_DB_URL="$pre_url"
export ASKDATA_PLATFORM_DB_USERNAME=sa ASKDATA_PLATFORM_DB_PASSWORD=migration
export ASKDATA_RELEASE_PACKAGE="$jar_file" ASKDATA_SECRET_BUNDLE="$drill_root/secret.bundle"
export ASKDATA_APP_VERSION=2.0.0-SNAPSHOT ASKDATA_SOURCE_COMMIT="$(git -C "$repo_root" rev-parse HEAD)" ASKDATA_DB_ENGINE=h2 ASKDATA_H2_JAR="$h2_jar"
"$repo_root/scripts/v2-backup.sh"
backup_id="$(python -c 'import json,os; print(json.load(open(os.environ["ASKDATA_BACKUP_OUTPUT"]+"/manifest.json"))["backupId"])')"

# Forward import official baseline, runtime defaults and the five exported sample-management resources.
start_platform "$pre_url" true "$drill_root/forward.log"
wait_for_inventory "$pre_url" "$drill_root/forward.inventory" 4 "$drill_root/forward.log"
stop_platform
grep -q '^flyway.version=15$' "$drill_root/forward.inventory"
grep -q '^role.count=3$' "$drill_root/forward.inventory"
grep -q '^scenario.count=8$' "$drill_root/forward.inventory"
grep -q '^scenario.case.count=24$' "$drill_root/forward.inventory"
grep -q '^scenario.turn.count=33$' "$drill_root/forward.inventory"
grep -q '^release.item.count=6$' "$drill_root/forward.inventory"
grep -q '^role.org.scope.count=7$' "$drill_root/forward.inventory"
grep -q '^role.metric.scope.count=7$' "$drill_root/forward.inventory"
grep -q '^role.table.scope.count=3$' "$drill_root/forward.inventory"
grep -q '^migration.audit.count=1$' "$drill_root/forward.inventory"
grep -q '^orphan.link.count=0$' "$drill_root/forward.inventory"

# Re-running the importer must be a no-op, including its audit record.
start_platform "$pre_url" true "$drill_root/idempotent.log"
wait_for_inventory "$pre_url" "$drill_root/idempotent.inventory" 4 "$drill_root/idempotent.log"
stop_platform
cmp "$drill_root/forward.inventory" "$drill_root/idempotent.inventory"

# Restore the pre-import rollback point, then apply the same forward import again.
export ASKDATA_BACKUP_INPUT="$ASKDATA_BACKUP_OUTPUT" ASKDATA_RESTORE_CONFIRM="RESTORE:$backup_id"
export ASKDATA_RESTORE_DB_URL="$rollback_url" ASKDATA_RESTORE_DB_USERNAME=sa ASKDATA_RESTORE_DB_PASSWORD=migration
export ASKDATA_RESTORE_RELEASE_OUTPUT="$drill_root/restored-release.jar" ASKDATA_RESTORE_SECRET_OUTPUT="$drill_root/restored-secret.bundle"
export ASKDATA_EXPECTED_APP_VERSION=2.0.0-SNAPSHOT
"$repo_root/scripts/v2-restore.sh"
inventory "$rollback_url" "$drill_root/rollback.inventory"
grep -q '^seed.import.count=0$' "$drill_root/rollback.inventory"
grep -q '^migration.audit.count=0$' "$drill_root/rollback.inventory"

start_platform "$rollback_url" true "$drill_root/reforward.log"
wait_for_inventory "$rollback_url" "$drill_root/reforward.inventory" 4 "$drill_root/reforward.log"
stop_platform
cmp "$drill_root/forward.inventory" "$drill_root/reforward.inventory"
cmp "$jar_file" "$drill_root/restored-release.jar"
cmp "$drill_root/secret.bundle" "$drill_root/restored-secret.bundle"
echo "MIGRATION_DRILL_PASS flyway=15 roles=3 scenarios=8 cases=24 turns=33 legacy_resources=5 backup=$backup_id"

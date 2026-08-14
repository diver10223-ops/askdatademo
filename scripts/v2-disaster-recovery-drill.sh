#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
drill_root=$(mktemp -d /tmp/askdata-v2-drill-XXXXXX)
[[ "$drill_root" == /tmp/askdata-v2-drill-* ]] || exit 2
cleanup(){
  [[ -z "${app_pid:-}" ]] || kill "$app_pid" 2>/dev/null || true
  rm -rf -- "$drill_root"
}
trap cleanup EXIT

JAVA_HOME=${JAVA_HOME:-/tmp/askdata-jdk21}
export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"
"$repo_root/platform-service/mvnw" -f "$repo_root/platform-service/pom.xml" -q -DskipTests package
jar_file="$repo_root/platform-service/target/platform-service-2.0.0.jar"
source_url="jdbc:h2:file:$drill_root/source;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE"
target_url="jdbc:h2:file:$drill_root/target;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE"
app_port="${ASKDATA_RECOVERY_DRILL_PORT:-18364}"
ASKDATA_PLATFORM_DB_URL="$source_url" ASKDATA_MIGRATION_DB_URL="$source_url" ASKDATA_PLATFORM_DB_USERNAME=sa ASKDATA_PLATFORM_DB_PASSWORD=drill ASKDATA_MIGRATION_DB_USERNAME=sa ASKDATA_MIGRATION_DB_PASSWORD=drill ASKDATA_INTERNAL_SERVICE_TOKEN=askdata-recovery-isolated-test-token ASKDATA_PLATFORM_API_TOKEN=askdata-recovery-platform-api-token-32-bytes-minimum ASKDATA_PLATFORM_PORT="$app_port" java -jar "$jar_file" >"$drill_root/app.log" 2>&1 &
app_pid=$!
h2_jar=$(find "$HOME/.m2/repository/com/h2database/h2" -name 'h2-*.jar' -type f | sort -V | tail -1)
ready=false
for _ in $(seq 1 240); do
  if curl -fsS "http://127.0.0.1:$app_port/api/v2/health" >/dev/null 2>&1; then
    ready=true; break
  fi
  kill -0 "$app_pid" 2>/dev/null || { cat "$drill_root/app.log" >&2; exit 1; }
  sleep .25
done
[[ "$ready" == true ]] || { cat "$drill_root/app.log" >&2; echo "recovery drill startup timed out" >&2; exit 1; }
kill "$app_pid"
wait "$app_pid" || true
app_pid=""
java -cp "$repo_root/platform-service/target/classes:$h2_jar" com.askdata.platform.recovery.DatabaseRecoveryTool inventory "$source_url" sa drill "$drill_root/probe.properties" h2
grep -q '^flyway.version=16$' "$drill_root/probe.properties"
java -cp "$repo_root/platform-service/target/classes:$h2_jar" com.askdata.platform.recovery.DatabaseRecoveryTool seed-drill "$source_url" sa drill "$drill_root/unused" h2
cp "$jar_file" "$drill_root/release.jar"
printf 'encrypted-drill-key-material-not-a-real-secret\n' > "$drill_root/secret.bundle"

export ASKDATA_BACKUP_OUTPUT="$drill_root/backup" ASKDATA_PLATFORM_DB_URL="$source_url" ASKDATA_PLATFORM_DB_USERNAME=sa ASKDATA_PLATFORM_DB_PASSWORD=drill
export ASKDATA_RELEASE_PACKAGE="$drill_root/release.jar" ASKDATA_SECRET_BUNDLE="$drill_root/secret.bundle" ASKDATA_APP_VERSION=2.0.0 ASKDATA_SOURCE_COMMIT="$(git -C "$repo_root" rev-parse HEAD)" ASKDATA_DB_ENGINE=h2 ASKDATA_H2_JAR="$h2_jar"
"$repo_root/scripts/v2-backup.sh"
backup_id=$(python -c 'import json,os;print(json.load(open(os.environ["ASKDATA_BACKUP_OUTPUT"]+"/manifest.json"))["backupId"])')
export ASKDATA_BACKUP_INPUT="$ASKDATA_BACKUP_OUTPUT" ASKDATA_RESTORE_CONFIRM="RESTORE:$backup_id" ASKDATA_RESTORE_DB_URL="$target_url" ASKDATA_RESTORE_DB_USERNAME=sa ASKDATA_RESTORE_DB_PASSWORD=restored
export ASKDATA_RESTORE_RELEASE_OUTPUT="$drill_root/restored-release.jar" ASKDATA_RESTORE_SECRET_OUTPUT="$drill_root/restored-secret.bundle" ASKDATA_EXPECTED_APP_VERSION=2.0.0

mkdir "$drill_root/incomplete"
cp "$ASKDATA_BACKUP_INPUT"/manifest.json "$ASKDATA_BACKUP_INPUT"/SHA256SUMS "$ASKDATA_BACKUP_INPUT"/database-inventory.properties "$ASKDATA_BACKUP_INPUT"/platform-database.zip "$ASKDATA_BACKUP_INPUT"/release-package.bin "$drill_root/incomplete/"
if ASKDATA_BACKUP_INPUT="$drill_root/incomplete" ASKDATA_RESTORE_DB_URL="jdbc:h2:file:$drill_root/must-not-exist" ASKDATA_RESTORE_RELEASE_OUTPUT="$drill_root/rejected-release" ASKDATA_RESTORE_SECRET_OUTPUT="$drill_root/rejected-secret" "$repo_root/scripts/v2-restore.sh" >/dev/null 2>&1; then
  echo "incomplete recovery bundle was incorrectly accepted" >&2;exit 1
fi
if ASKDATA_EXPECTED_APP_VERSION=9.9.9 ASKDATA_RESTORE_DB_URL="jdbc:h2:file:$drill_root/must-not-exist-version" ASKDATA_RESTORE_RELEASE_OUTPUT="$drill_root/rejected-version-release" ASKDATA_RESTORE_SECRET_OUTPUT="$drill_root/rejected-version-secret" "$repo_root/scripts/v2-restore.sh" >/dev/null 2>&1; then
  echo "mismatched application version was incorrectly accepted" >&2;exit 1
fi
"$repo_root/scripts/v2-restore.sh"
cmp "$drill_root/release.jar" "$drill_root/restored-release.jar"
cmp "$drill_root/secret.bundle" "$drill_root/restored-secret.bundle"
grep -q '^release.count=1$' "$ASKDATA_BACKUP_INPUT/database-inventory.properties"
grep -q '^secret.reference.count=1$' "$ASKDATA_BACKUP_INPUT/database-inventory.properties"
echo "DISASTER_RECOVERY_DRILL_PASS flyway=16 bundle=$backup_id"

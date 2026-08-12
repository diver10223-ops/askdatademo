#!/usr/bin/env bash
set -euo pipefail
umask 077

required=(ASKDATA_BACKUP_INPUT ASKDATA_RESTORE_CONFIRM ASKDATA_RESTORE_DB_URL ASKDATA_RESTORE_DB_USERNAME ASKDATA_RESTORE_DB_PASSWORD ASKDATA_RESTORE_RELEASE_OUTPUT ASKDATA_RESTORE_SECRET_OUTPUT ASKDATA_EXPECTED_APP_VERSION)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "missing required environment: $name" >&2; exit 2; }
done
[[ -d "$ASKDATA_BACKUP_INPUT" ]] || { echo "backup input not found" >&2; exit 2; }
for file in manifest.json SHA256SUMS database-inventory.properties release-package.bin secret-recovery.bundle; do
  [[ -f "$ASKDATA_BACKUP_INPUT/$file" ]] || { echo "incomplete recovery bundle: $file" >&2; exit 2; }
done
(cd "$ASKDATA_BACKUP_INPUT" && sha256sum --check --strict SHA256SUMS)

readarray -t metadata < <(python - "$ASKDATA_BACKUP_INPUT/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding="utf-8"))
print(m["backupId"]);print(m["databaseEngine"]);print(m["applicationVersion"]);print(m["sourceCommit"])
PY
)
backup_id=${metadata[0]};engine=${metadata[1]};app_version=${metadata[2]};source_commit=${metadata[3]}
[[ "$ASKDATA_RESTORE_CONFIRM" == "RESTORE:$backup_id" ]] || { echo "confirmation must equal RESTORE:$backup_id" >&2; exit 2; }
[[ "$ASKDATA_EXPECTED_APP_VERSION" == "$app_version" ]] || { echo "application version mismatch: backup=$app_version expected=$ASKDATA_EXPECTED_APP_VERSION" >&2; exit 2; }
[[ ! -e "$ASKDATA_RESTORE_RELEASE_OUTPUT" && ! -e "$ASKDATA_RESTORE_SECRET_OUTPUT" ]] || { echo "recovery outputs must not already exist" >&2; exit 2; }

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
verification=""
cleanup(){ [[ -z "$verification" ]] || rm -f -- "$verification"; }
trap cleanup EXIT
if [[ "$engine" == h2 ]]; then
  database_file="$ASKDATA_BACKUP_INPUT/platform-database.zip"
  [[ -f "$database_file" ]] || { echo "database backup missing" >&2; exit 2; }
  h2_jar=${ASKDATA_H2_JAR:-$(find "$HOME/.m2/repository/com/h2database/h2" -name 'h2-*.jar' -type f 2>/dev/null | sort -V | tail -1)}
  [[ -f "$h2_jar" ]] || { echo "H2 driver not found; set ASKDATA_H2_JAR" >&2; exit 2; }
  recovery_cp="$repo_root/platform-service/target/classes:$h2_jar"
  java -cp "$recovery_cp" com.askdata.platform.recovery.DatabaseRecoveryTool restore-h2 "$ASKDATA_RESTORE_DB_URL" "$ASKDATA_RESTORE_DB_USERNAME" "$ASKDATA_RESTORE_DB_PASSWORD" "$database_file" h2
  verification=$(mktemp /tmp/askdata-v2-restore-inventory-XXXXXX)
  java -cp "$recovery_cp" com.askdata.platform.recovery.DatabaseRecoveryTool inventory "$ASKDATA_RESTORE_DB_URL" "$ASKDATA_RESTORE_DB_USERNAME" "$ASKDATA_RESTORE_DB_PASSWORD" "$verification" h2
  diff -u "$ASKDATA_BACKUP_INPUT/database-inventory.properties" "$verification"
elif [[ "$engine" == postgresql ]]; then
  command -v pg_restore >/dev/null || { echo "pg_restore not found" >&2; exit 2; }
  PGPASSWORD="$ASKDATA_RESTORE_DB_PASSWORD" pg_restore --exit-on-error --no-owner --no-acl --dbname="$ASKDATA_RESTORE_DB_URL" "$ASKDATA_BACKUP_INPUT/platform-database.dump"
  echo "PostgreSQL post-restore inventory adapter must be completed in M8" >&2
  exit 3
else
  echo "unsupported database engine: $engine" >&2
  exit 2
fi

install -m 600 "$ASKDATA_BACKUP_INPUT/release-package.bin" "$ASKDATA_RESTORE_RELEASE_OUTPUT"
install -m 600 "$ASKDATA_BACKUP_INPUT/secret-recovery.bundle" "$ASKDATA_RESTORE_SECRET_OUTPUT"
echo "RESTORE_OK id=$backup_id appVersion=$app_version sourceCommit=$source_commit"

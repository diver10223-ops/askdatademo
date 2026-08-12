#!/usr/bin/env bash
set -euo pipefail
umask 077

required=(ASKDATA_BACKUP_OUTPUT ASKDATA_PLATFORM_DB_URL ASKDATA_PLATFORM_DB_USERNAME ASKDATA_PLATFORM_DB_PASSWORD ASKDATA_RELEASE_PACKAGE ASKDATA_SECRET_BUNDLE ASKDATA_APP_VERSION ASKDATA_SOURCE_COMMIT)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "missing required environment: $name" >&2; exit 2; }
done
[[ -f "$ASKDATA_RELEASE_PACKAGE" ]] || { echo "release package not found" >&2; exit 2; }
[[ -f "$ASKDATA_SECRET_BUNDLE" ]] || { echo "encrypted secret recovery bundle not found" >&2; exit 2; }
[[ ! -e "$ASKDATA_BACKUP_OUTPUT" ]] || { echo "backup output already exists" >&2; exit 2; }

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
engine=${ASKDATA_DB_ENGINE:-h2}
backup_id="v2-$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4)"
mkdir -m 700 "$ASKDATA_BACKUP_OUTPUT"
staging="$ASKDATA_BACKUP_OUTPUT/.staging"
mkdir -m 700 "$staging"

cp -- "$ASKDATA_RELEASE_PACKAGE" "$staging/release-package.bin"
cp -- "$ASKDATA_SECRET_BUNDLE" "$staging/secret-recovery.bundle"
chmod 600 "$staging/release-package.bin" "$staging/secret-recovery.bundle"

if [[ "$engine" == h2 ]]; then
  h2_jar=${ASKDATA_H2_JAR:-$(find "$HOME/.m2/repository/com/h2database/h2" -name 'h2-*.jar' -type f 2>/dev/null | sort -V | tail -1)}
  [[ -f "$h2_jar" ]] || { echo "H2 driver not found; set ASKDATA_H2_JAR" >&2; exit 2; }
  [[ -f "$repo_root/platform-service/target/classes/com/askdata/platform/recovery/DatabaseRecoveryTool.class" ]] || { echo "recovery tool not compiled" >&2; exit 2; }
  recovery_cp="$repo_root/platform-service/target/classes:$h2_jar"
  java -cp "$recovery_cp" com.askdata.platform.recovery.DatabaseRecoveryTool backup-h2 "$ASKDATA_PLATFORM_DB_URL" "$ASKDATA_PLATFORM_DB_USERNAME" "$ASKDATA_PLATFORM_DB_PASSWORD" "$staging/platform-database.zip" h2
  java -cp "$recovery_cp" com.askdata.platform.recovery.DatabaseRecoveryTool inventory "$ASKDATA_PLATFORM_DB_URL" "$ASKDATA_PLATFORM_DB_USERNAME" "$ASKDATA_PLATFORM_DB_PASSWORD" "$staging/database-inventory.properties" h2
elif [[ "$engine" == postgresql ]]; then
  command -v pg_dump >/dev/null || { echo "pg_dump not found" >&2; exit 2; }
  PGPASSWORD="$ASKDATA_PLATFORM_DB_PASSWORD" pg_dump --format=custom --no-owner --no-acl --file="$staging/platform-database.dump" "$ASKDATA_PLATFORM_DB_URL"
  echo "PostgreSQL inventory adapter requires target-environment completion in M8" >&2
  exit 3
else
  echo "unsupported database engine: $engine" >&2
  exit 2
fi

export BACKUP_ID="$backup_id" BACKUP_ENGINE="$engine" BACKUP_CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python - "$staging/manifest.json" <<'PY'
import json, os, pathlib, sys
manifest={
  "formatVersion":"1.0", "backupId":os.environ["BACKUP_ID"], "createdAt":os.environ["BACKUP_CREATED_AT"],
  "databaseEngine":os.environ["BACKUP_ENGINE"], "applicationVersion":os.environ["ASKDATA_APP_VERSION"],
  "sourceCommit":os.environ["ASKDATA_SOURCE_COMMIT"],
  "requiredComponents":["platform-database","database-inventory","release-package","secret-recovery-bundle","checksums"]
}
pathlib.Path(sys.argv[1]).write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
PY
(cd "$staging" && sha256sum database-inventory.properties manifest.json platform-database.* release-package.bin secret-recovery.bundle > SHA256SUMS)
mv -- "$staging"/* "$ASKDATA_BACKUP_OUTPUT"/
rmdir "$staging"
echo "BACKUP_OK id=$backup_id path=$ASKDATA_BACKUP_OUTPUT"

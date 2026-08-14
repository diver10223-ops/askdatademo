#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${1:-2.0.0}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "version must be semantic X.Y.Z" >&2; exit 2; }
cd "$repo_root"
[[ -z "$(git status --porcelain)" ]] || { echo "release packaging requires a clean worktree" >&2; exit 2; }
command -v java >/dev/null 2>&1 || { echo "Java 21 is required" >&2; exit 2; }
source_commit="$(git rev-parse HEAD)"
python -m json.tool contracts/internal-execution-v1.openapi.json >/dev/null
python -m json.tool contracts/platform-v2.openapi.json >/dev/null
output_root="${ASKDATA_RELEASE_OUTPUT_DIR:-$repo_root/artifacts/product-v${version}}"
staging="$(mktemp -d /tmp/askdata-v2-release.XXXXXX)"
[[ "$staging" == /tmp/askdata-v2-release.* ]] || exit 2
trap 'rm -rf -- "$staging"' EXIT
package_root="$staging/askdata-product-v${version}"
mkdir -p "$package_root"/{runtime/backend,runtime/frontend,migrations,fixtures,deploy,contracts,docs}

./platform-service/mvnw -f platform-service/pom.xml -q -DskipTests package
npm --prefix frontend run build >/dev/null
cp "platform-service/target/platform-service-${version}.jar" "$package_root/runtime/askdata-platform-${version}.jar"
git archive HEAD backend/app | tar -x -C "$package_root/runtime/backend" --strip-components=1
cp backend/requirements.txt "$package_root/runtime/backend/"
cp -R frontend/dist/. "$package_root/runtime/frontend/"
cp -R platform-service/src/main/resources/db/migration/. "$package_root/migrations/"
cp fixtures/official_baseline_v1.json fixtures/demo_runtime_defaults.json "$package_root/fixtures/"
cp -R deploy/product-v2/. "$package_root/deploy/"
mkdir -p "$package_root/deploy/database/postgresql"
cp deploy/database/postgresql/create-roles.sql.example "$package_root/deploy/database/postgresql/"
cp contracts/internal-execution-v1.openapi.json contracts/platform-v2.openapi.json "$package_root/contracts/"

for document in \
  PRODUCT_V2_SERVICE_BOUNDARY.md PRODUCT_V2_LOGICAL_DATA_MODEL.md PRODUCT_V2_USER_GUIDE.md \
  PRODUCT_V2_ADMIN_GUIDE.md PRODUCT_V2_SECURITY_GUIDE.md PRODUCT_V2_TEST_STRATEGY.md \
  PRODUCT_V2_CAPACITY_REPORT.md PRODUCT_V2_OBSERVABILITY.md PRODUCT_V2_DATABASE_MIGRATION_RUNBOOK.md \
  PRODUCT_V2_RECOVERY_RUNBOOK.md PRODUCT_V2_RELEASE_NOTES.md; do
  cp "docs/$document" "$package_root/docs/"
done

python - "$package_root/VERSION.json" "$version" "$source_commit" <<'PY'
import json,sys
from datetime import datetime,timezone
path,version,commit=sys.argv[1:]
with open(path,'w',encoding='utf-8') as output:
    json.dump({'product':'AskData','version':version,'sourceCommit':commit,
               'builtAt':datetime.now(timezone.utc).isoformat(),
               'scope':'environment-neutral product baseline; customer acceptance requires M8/M9'},output,ensure_ascii=False,indent=2)
    output.write('\n')
PY

if find "$package_root" -type f | grep -E '(^|/)(CODEX_SKILLS_DESIGN\.md|SKILL\.md|\.env|.*\.(pyc|db|sqlite|mv\.db|trace\.db|pem|key|p12|pfx|jks|log))$|(^|/)(__pycache__|\.pytest_cache|node_modules)/'; then
  echo "FAIL release contains an excluded internal, runtime or secret file" >&2
  exit 1
fi
if grep -RInE '(gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' "$package_root"; then
  echo "FAIL release contains a credential-shaped value" >&2
  exit 1
fi
if grep -RIlE 'askdata-(test|capacity|migration|recovery|p313|performance)-.*token' "$package_root" | grep .; then
  echo "FAIL release contains an isolated test token" >&2
  exit 1
fi

(cd "$package_root" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
mkdir -p "$output_root"
archive="$output_root/askdata-product-v${version}.tar.gz"
tar -C "$staging" -czf "$archive" "askdata-product-v${version}"
(cd "$output_root" && sha256sum "$(basename "$archive")" > "$(basename "$archive").sha256")
tar -tzf "$archive" | grep -Eq '(^|/)CODEX_SKILLS_DESIGN\.md$|(^|/)(skills|\.codex)/' && {
  echo "FAIL archive contains internal Skill assets" >&2; exit 1;
}
echo "V2_RELEASE_PACKAGE_PASS version=$version commit=$source_commit archive=$archive sha256=$(sha256sum "$archive" | cut -d' ' -f1)"

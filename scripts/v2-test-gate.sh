#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

# Never inherit customer endpoints or credentials into the product-baseline gate.
if [[ "${ASKDATA_V2_GATE_SANITIZED:-}" != 1 ]]; then
  exec env \
    -u ASKDATA_CREDENTIAL_KEY \
    -u ASKDATA_PLATFORM_DB_URL -u ASKDATA_PLATFORM_DB_USERNAME -u ASKDATA_PLATFORM_DB_PASSWORD \
    -u ASKDATA_MIGRATION_DB_URL -u ASKDATA_MIGRATION_DB_USERNAME -u ASKDATA_MIGRATION_DB_PASSWORD \
    -u ASKDATA_EXECUTION_BASE_URL -u ASKDATA_INTERNAL_SERVICE_TOKEN \
    ASKDATA_V2_GATE_SANITIZED=1 "$0" "$@"
fi

python_bin="${ASKDATA_V2_GATE_PYTHON:-$root_dir/.venv/bin/python}"
[[ -x "$python_bin" ]] || { echo "FAIL environment: run .devcontainer/init.sh first" >&2; exit 2; }
command -v java >/dev/null 2>&1 || { echo "FAIL environment: Java 21 is required; rebuild the dev container" >&2; exit 2; }
command -v node >/dev/null 2>&1 || { echo "FAIL environment: Node.js is required; rebuild the dev container" >&2; exit 2; }
command -v npm >/dev/null 2>&1 || { echo "FAIL environment: npm is required; rebuild the dev container" >&2; exit 2; }

python_version="$($python_bin -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
java_version="$(java -version 2>&1 | sed -n '1s/.*version "\([0-9]*\).*/\1/p')"
node_version="$(node -p 'process.versions.node.split(".")[0]')"
[[ "$python_version" == 3.12 ]] || { echo "FAIL environment: expected Python 3.12, got $python_version" >&2; exit 2; }
[[ "$java_version" == 21 ]] || { echo "FAIL environment: expected Java 21, got ${java_version:-unknown}" >&2; exit 2; }
[[ "$node_version" == 22 ]] || { echo "FAIL environment: expected Node.js 22, got ${node_version:-unknown}" >&2; exit 2; }

gate_data="$(mktemp -d /tmp/askdata-v2-test-gate.XXXXXX)"
export ASKDATA_DATA_DIR="$gate_data/python-data"
export PYTHONPATH="$root_dir/backend"
echo "V2_TEST_GATE environment=isolated python=$python_version java=$java_version node=$node_version data=$gate_data"

run() {
  local name="$1"
  shift
  echo "V2_TEST_GATE_START $name"
  "$@"
  echo "V2_TEST_GATE_PASS $name"
}

run python-full "$python_bin" -m pytest -q backend/tests
run java-full ./platform-service/mvnw -f platform-service/pom.xml -q test
run contract "$python_bin" scripts/check-contract-compatibility.py
run phase1-regression "$python_bin" scripts/phase1-matrix.py
run phase2-regression "$python_bin" scripts/phase2-matrix.py
run cross-service-e2e bash scripts/v2-p313-smoke.sh
run frontend-typecheck npm --prefix frontend run typecheck
run frontend-build npm --prefix frontend run build
run frontend-offline npm --prefix frontend run build:offline
offline_file="frontend/offline-dist/askdata-offline.html"
[[ -f "$offline_file" ]] || { echo "FAIL offline artifact missing" >&2; exit 1; }
if rg -n '<(link|script)[^>]+(href|src)=["]https?://|fetch\(["]https?://|new (WebSocket|EventSource)\(["]https?://' "$offline_file"; then
  echo "FAIL offline artifact contains an external runtime dependency" >&2
  exit 1
fi
echo "V2_TEST_GATE_PASS offline-external-dependency-scan"
run performance-smoke "$python_bin" scripts/v2-performance-smoke.py
run migration-drill bash scripts/v2-migration-drill.sh
run recovery-drill bash scripts/v2-disaster-recovery-drill.sh
run patch-integrity git diff --check
echo "V2_TEST_GATE_PASS all customer_credentials=absent artifacts=$gate_data"

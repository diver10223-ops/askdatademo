#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python_bin="$repo_root/.venv/bin/python"
command -v java >/dev/null 2>&1 || { echo "Java 21 is required" >&2; exit 2; }
"$python_bin" -c 'import pip_audit' 2>/dev/null || {
  echo "pip-audit is required for the security gate: .venv/bin/python -m pip install pip-audit" >&2
  exit 2
}

if git grep -nEI '(gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' -- . ':(exclude)docs/reference-screenshots/**'; then
  echo "FAIL tracked source contains a high-confidence credential-shaped value" >&2
  exit 1
fi
echo "SECURITY_PASS tracked-credential-patterns=absent"

prohibited="$(git ls-files | grep -E '(^|/)(\.env($|\.)|.*\.(pem|key|p12|pfx|jks|keystore|db|sqlite|sqlite3|mv\.db|trace\.db)|\.credential-key)$' || true)"
if [[ -n "$prohibited" ]]; then
  echo "$prohibited" >&2
  echo "FAIL prohibited sensitive/runtime files are tracked" >&2
  exit 1
fi
echo "SECURITY_PASS prohibited-tracked-files=absent"

if rg -n '\$\{ASKDATA_(INTERNAL_SERVICE_TOKEN|PLATFORM_API_TOKEN|PLATFORM_DB_PASSWORD|MIGRATION_DB_PASSWORD):' platform-service/src/main/resources backend/app; then
  echo "FAIL security-sensitive configuration has a built-in fallback" >&2
  exit 1
fi
echo "SECURITY_PASS sensitive-defaults=absent"

"$python_bin" -m pip_audit -r backend/requirements-dev.txt
(cd frontend && npm audit --omit=dev --audit-level=high)
trivy_bin="${TRIVY_BIN:-$(command -v trivy || true)}"
[[ -x "$trivy_bin" ]] || { echo "Trivy is required; set TRIVY_BIN to a verified executable" >&2; exit 2; }
"$trivy_bin" fs --scanners vuln --severity HIGH,CRITICAL --exit-code 1 \
  --skip-dirs .git --skip-dirs .venv --skip-dirs frontend/node_modules \
  --format json --output "$repo_root/platform-service/target/trivy-security-report.json" "$repo_root"
echo "SECURITY_DEPENDENCY_PASS python=0-known npm-production=0-high-or-critical repository=0-high-or-critical"

security_data="$(mktemp -d /tmp/askdata-v2-security.XXXXXX)"
[[ "$security_data" == /tmp/askdata-v2-security.* ]] || exit 2
trap 'rm -rf -- "$security_data"' EXIT
ASKDATA_DATA_DIR="$security_data/data" PYTHONPATH=backend "$python_bin" -m pytest -q \
  backend/tests/test_sql_security_ast.py backend/tests/test_ai_layer_boundaries.py \
  backend/tests/test_phase2.py backend/tests/test_seven_layer_regression.py
"$repo_root/platform-service/mvnw" -f "$repo_root/platform-service/pom.xml" -q \
  -Dtest=PermissionDecisionTests,TamperEvidentAuditTests,ProviderManagementTests,ApprovalReleaseWorkflowTests,PlatformApiAuthenticationFilterTests,ExecutionClientSecurityTests test
echo "V2_SECURITY_GATE_PASS"

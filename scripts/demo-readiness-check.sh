#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
fail(){ echo "FAIL: $*" >&2; exit 1; }
python -m json.tool fixtures/official_baseline_v1.json >/dev/null || fail baseline-json
python -m json.tool schemas/phase1-contract.schema.json >/dev/null || fail contract-schema
PYTHONPATH=backend python - <<'PY' || exit 1
import json
from app.db import restore_baseline,connect
from app.config import PLATFORM_DB,WAREHOUSE_DB
restore_baseline(); b=json.load(open('fixtures/official_baseline_v1.json'))
assert len(b['roles'])==3 and len(b['scenarios'])==8
assert all(len(x['cases'])==3 for x in b['scenarios'])
with connect(WAREHOUSE_DB) as c: assert c.execute('select count(*) from dws_loan_aggr_wide').fetchone()[0]==3
with connect(PLATFORM_DB) as c: assert c.execute("select official from config_versions where id='official-v1'").fetchone()[0]==1
print('OK: baseline, 3 roles × 8 scenarios, dual databases')
PY
npm --prefix frontend run typecheck || fail frontend-typecheck
npm --prefix frontend run build || fail frontend-build
npm --prefix frontend run build:offline || fail offline-build
OFF=frontend/offline-dist/askdata-offline.html
[ -f "$OFF" ] || fail offline-file
! rg -n 'https?://|<link[^>]+href=|<script[^>]+src=' "$OFF" || fail offline-external-resource
PYTHONPATH=backend pytest -q backend/tests || fail backend-tests
git diff --check || fail diff-check
echo 'READY: Phase 1 acceptance checks passed'

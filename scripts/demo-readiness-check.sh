#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
PYTHON=python; [ -x .venv/bin/python ] && PYTHON=.venv/bin/python
fail(){ echo "FAIL: $*" >&2; exit 1; }
$PYTHON -m json.tool fixtures/official_baseline_v1.json >/dev/null || fail baseline-json
$PYTHON -m json.tool schemas/phase1-contract.schema.json >/dev/null || fail contract-schema
PYTHONPATH=backend $PYTHON - <<'PY' || exit 1
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
PYTHONPATH=backend $PYTHON -c 'from app.main import app; assert app.title' || fail backend-import
PYTHONPATH=backend $PYTHON scripts/phase1-matrix.py || fail poc-matrix
npm --prefix frontend run typecheck || fail frontend-typecheck
npm --prefix frontend run build || fail frontend-build
npm --prefix frontend run build:offline || fail offline-build
OFF=frontend/offline-dist/askdata-offline.html
[ -f "$OFF" ] || fail offline-file
! rg -n '<(link|script)[^>]+(href|src)=["]https?://|fetch\(["]https?://|new WebSocket\(["]https?://|new EventSource\(["]https?://' "$OFF" || fail offline-external-resource
if $PYTHON -c 'import pytest' 2>/dev/null; then
  PYTHONPATH=backend $PYTHON -m pytest -q backend/tests || fail backend-tests
else
  PYTHONPATH=backend pytest -q backend/tests || fail backend-tests
fi
git diff --check || fail diff-check
echo 'READY: Phase 1 acceptance checks passed'

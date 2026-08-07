#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
PYTHON=python; [ -x .venv/bin/python ] && PYTHON=.venv/bin/python
fail(){ echo "FAIL: $*" >&2; exit 1; }
PYTHONPATH=backend "$PYTHON" -m pytest -q backend/tests/test_phase2.py || fail phase2-tests
PYTHONPATH=backend "$PYTHON" scripts/phase2-matrix.py || fail phase2-matrix
npm --prefix frontend run typecheck || fail frontend-typecheck
npm --prefix frontend run build || fail frontend-build
bash scripts/demo-readiness-check.sh || fail phase1-regression
git diff --check || fail diff-check
echo 'READY: Phase 2 checks passed; Phase 1 regression passed'

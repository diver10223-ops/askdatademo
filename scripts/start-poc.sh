#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
[ -d frontend/dist ] || npm --prefix frontend run build
PY=${PYTHON:-python}; [ -x .venv/bin/python ] && PY=.venv/bin/python
PYTHONPATH=backend exec "$PY" -m uvicorn app.main:app --host "${ASKDATA_HOST:-0.0.0.0}" --port "${ASKDATA_PORT:-8000}"

#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
[ -d frontend/dist ] || npm --prefix frontend run build
PY=${PYTHON:-python}; [ -x .venv/bin/python ] && PY=.venv/bin/python
if [ -x "$ROOT/tools/clickhouse/clickhouse" ] && ! curl -fsS --max-time 1 http://127.0.0.1:8123/ping >/dev/null 2>&1; then
  nohup "$ROOT/scripts/start-clickhouse-poc.sh" >"$ROOT/data/clickhouse-server.log" 2>&1 &
  echo $! >"$ROOT/data/clickhouse-server.pid"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl -fsS --max-time 1 http://127.0.0.1:8123/ping >/dev/null 2>&1 && break
    sleep 1
  done
fi
if [ -z "${ASKDATA_CREDENTIAL_KEY:-}" ]; then
  CREDENTIAL_FILE="$ROOT/data/.credential-key"
  mkdir -p "$ROOT/data"
  if [ ! -f "$CREDENTIAL_FILE" ]; then
    umask 077
    "$PY" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > "$CREDENTIAL_FILE"
  fi
  chmod 600 "$CREDENTIAL_FILE"
  ASKDATA_CREDENTIAL_KEY=$(<"$CREDENTIAL_FILE")
  export ASKDATA_CREDENTIAL_KEY
fi
PYTHONPATH=backend exec "$PY" -m uvicorn app.main:app --host "${ASKDATA_HOST:-0.0.0.0}" --port "${ASKDATA_PORT:-8000}"

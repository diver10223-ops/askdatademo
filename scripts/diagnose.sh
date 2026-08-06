#!/usr/bin/env bash
set -u
printf 'Python: '; python --version
printf 'Node: '; node --version
printf 'npm: '; npm --version
for f in fixtures/official_baseline_v1.json schemas/phase1-contract.schema.json schemas/baseline.schema.json; do python -m json.tool "$f" >/dev/null && echo "OK $f" || echo "FAIL $f"; done
[ -f data/platform.db ] && echo 'OK platform.db' || echo 'MISSING platform.db'
[ -f data/mock_warehouse.db ] && echo 'OK mock_warehouse.db' || echo 'MISSING mock_warehouse.db'
curl -fsS "http://127.0.0.1:${ASKDATA_PORT:-8000}/api/v1/health" 2>/dev/null || echo 'POC is not currently running'

#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=backend python -c 'from app.db import restore_baseline; restore_baseline()'
echo 'platform.db and mock_warehouse.db initialized'

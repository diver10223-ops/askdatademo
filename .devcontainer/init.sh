#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend ci
bash scripts/init-db.sh

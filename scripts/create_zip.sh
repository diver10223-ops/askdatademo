#!/usr/bin/env bash
# create_zip.sh — package the 10 core changed files from branch codex-zk25m7
# Usage: bash scripts/create_zip.sh
set -euo pipefail

OUTPUT="codex-zk25m7-modified-files.zip"

FILES=(
  "backend/app/layers/l2_understanding.py"
  "backend/app/layers/l3_semantic.py"
  "backend/app/layers/l5_query.py"
  "backend/app/layers/l7_interpretation.py"
  "backend/app/runtime/publisher.py"
  "backend/tests/test_phase1.py"
  "backend/tests/test_phase2.py"
  "fixtures/demo_runtime_defaults.json"
  "frontend/src/App.vue"
  "frontend/src/App.vue.js"
)

rm -f "$OUTPUT"
zip "$OUTPUT" "${FILES[@]}"
echo "Created $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"

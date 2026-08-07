#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT_DIR/tools/clickhouse/clickhouse" server -- \
  --path="$ROOT_DIR/data/clickhouse" \
  --http_port=8123 \
  --tcp_port=9000 \
  --listen_host=127.0.0.1 \
  --logger.console=true \
  --logger.level=warning

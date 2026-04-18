#!/usr/bin/env bash
set -euo pipefail
exec uv run uvicorn backend.main:app \
    --host "${BACKEND_HOST:-0.0.0.0}" \
    --port "${BACKEND_PORT:-8080}" \
    --reload

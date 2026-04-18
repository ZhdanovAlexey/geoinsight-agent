#!/usr/bin/env bash
set -euo pipefail
PGDSN="${POSTGRES_DSN:-postgresql://geoinsight:geoinsight@localhost:5433/geoinsight}"

echo "==> Dropping and recreating database..."
psql "$PGDSN" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "==> Running migrations..."
psql "$PGDSN" -f backend/db/migrations/001_schema.sql
psql "$PGDSN" -f backend/db/migrations/002_indices.sql

echo "==> Loading demo data..."
uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset

echo "==> Done."

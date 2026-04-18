# GeoInsight Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MVP AI agent that turns telecom geodata into business analytics via a chat interface with maps, tables, and charts.

**Architecture:** FastAPI backend exposes OpenAI-compatible `/v1/chat/completions` endpoint. OpenAI Agents SDK orchestrates gpt-oss-120b via vLLM with 7 tools (3 full, 4 stubs). Streamlit demo UI streams SSE events and renders pydeck maps. PostgreSQL+PostGIS stores zone geometries and demographics. Langfuse provides LLM observability via OpenTelemetry.

**Tech Stack:** Python 3.12, uv, FastAPI, OpenAI Agents SDK, SQLAlchemy 2.x, PostGIS, Streamlit, pydeck, structlog, Langfuse, Docker Compose.

**Source of truth:** `docs/geoinsight-agent-tz.md` (ТЗ sections referenced as `TZ:N`). On conflict with design doc, ТЗ wins.

**Dataset facts (from exploration):**
- `dim_zid_town_Olmaliq.csv`: 162 zones, tab-separated, columns: `zid, city_id, net_type, wkt`
- `geo_olmaliq_cnt.csv`: 87,115 rows, columns: `zid, ts, income, age, gender, cnt, home_zid, job_zid` (ts always 57.0 — batch id, ignore)
- `geo_olmaliq_dyn_all.csv`: 745,357 rows, columns: `zid, ts, income, age, gender, cnt` (ts is absolute hour counter, range 83232-84719 = 62 days, hour_of_day = ts % 24, epoch ~2014-01-01)
- `tav_geo_tosh_1806_2_new_202307301408.csv`: 500k trajectories from Tashkent, columns: `code, age, home_zid, job_zid, count, roaming_type, country_name, int_06_07..int_00_01`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Create: `CLAUDE.md`
- Create: `STATUS.md`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/a.zhdanov/claude/pet-projects/geo-bot
git init
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.venv/

# Environment
.env

# Data
data/raw/
dataset/
*.csv

# Logs
*.log

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Docker volumes
postgres_data/
langfuse_data/
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "geoinsight-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "openai-agents",
    "openai>=1.50",
    "fastapi",
    "uvicorn[standard]",
    "httpx",
    "pydantic>=2.7",
    "pydantic-settings",
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.2",
    "geoalchemy2",
    "shapely",
    "structlog",
    "langfuse>=3.0",
    "opentelemetry-api",
    "opentelemetry-sdk",
    "opentelemetry-exporter-otlp-proto-http",
]

[project.optional-dependencies]
demo = ["streamlit", "pydeck", "pandas"]
dev = ["pytest", "pytest-asyncio", "ruff", "mypy"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.mypy]
python_version = "3.12"
strict = false
warn_return_any = true
warn_unused_configs = true
```

- [ ] **Step 4: Create `.env.example`**

As specified in TZ:5.2 — copy verbatim from spec.

```dotenv
# vLLM (gpt-oss-120b — already deployed externally)
LLM_BASE_URL=http://109.230.162.92:44334/v1
LLM_API_KEY=your-vllm-api-key-here
LLM_MODEL=gpt-oss-120b
LLM_REASONING_EFFORT=medium

# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8080
LOG_LEVEL=INFO
LOG_FORMAT=json

# Postgres
POSTGRES_DSN=postgresql+psycopg://geoinsight:geoinsight@localhost:5432/geoinsight

# Langfuse (fill after first docker-compose up and creating project in UI)
LANGFUSE_HOST=http://localhost:3030
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_ENABLED=true

# Streamlit
BACKEND_URL=http://localhost:8080
```

- [ ] **Step 5: Create `backend/__init__.py` and `backend/config.py`**

`backend/__init__.py` — empty file.

`backend/config.py` — pydantic-settings as per TZ:5.2:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # vLLM
    llm_base_url: str = "http://109.230.162.92:44334/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "gpt-oss-120b"
    llm_reasoning_effort: str = "medium"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8080
    log_level: str = "INFO"
    log_format: str = "json"

    # Postgres
    postgres_dsn: str = "postgresql+psycopg://geoinsight:geoinsight@localhost:5432/geoinsight"

    # Langfuse
    langfuse_host: str = "http://localhost:3030"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_enabled: bool = True

    # Streamlit
    backend_url: str = "http://localhost:8080"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 6: Create `CLAUDE.md`**

```markdown
# GeoInsight Agent

## Quick Start

```bash
uv sync --all-extras
docker compose up -d          # Postgres + Langfuse
uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8080
uv run streamlit run streamlit_app/app.py
```

## Project Structure

- `backend/` — FastAPI + Agents SDK + tools
- `streamlit_app/` — Streamlit demo UI
- `data/` — ETL scripts
- `dataset/` — raw CSV data (gitignored)
- `docs/` — specs and plans

## Conventions

- All async where possible
- Type hints required
- `ruff format && ruff check --fix` before commit
- Line length: 100
- SQLAlchemy Core (not ORM) for queries
- structlog JSON logging with trace_id
- Tests: pytest-asyncio

## Key Decisions

- vLLM is external — not managed by this repo
- Langfuse + Postgres run via docker-compose
- Backend + Streamlit run locally (not in Docker)
- ТЗ (`docs/geoinsight-agent-tz.md`) is source of truth on conflicts
```

- [ ] **Step 7: Create `STATUS.md`**

```markdown
# GeoInsight Agent — Status

## Current Stage: 0 — Infrastructure

### Completed
- [ ] Project scaffolding (pyproject.toml, config, gitignore)
- [ ] Docker Compose (Postgres + Langfuse)
- [ ] Scripts (start_backend, start_streamlit, reset_db)
- [ ] README.md

### Next: Stage 1 — DB & Data
- [ ] SQL migrations
- [ ] ETL script
- [ ] DB engine + queries

### Stage 2 — Minimal Backend
### Stage 3 — Agent + Tools
### Stage 4 — Streamlit UI
### Stage 5 — Extended Tools
### Stage 6 — Polish
```

- [ ] **Step 8: Run `uv sync`**

```bash
uv sync --all-extras
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .gitignore .env.example backend/__init__.py backend/config.py CLAUDE.md STATUS.md
git commit -m "feat: project scaffolding — pyproject, config, gitignore"
```

---

## Task 2: Docker Compose

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

Postgres+PostGIS for app data. Langfuse v3 self-hosted with its own Postgres, ClickHouse, Redis, MinIO (per TZ:5.3, TZ:12.1).

```yaml
services:
  # === App Database ===
  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_USER: geoinsight
      POSTGRES_PASSWORD: geoinsight
      POSTGRES_DB: geoinsight
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U geoinsight"]
      interval: 5s
      timeout: 5s
      retries: 5

  # === Langfuse v3 ===
  langfuse-postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U langfuse"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-clickhouse:
    image: clickhouse/clickhouse-server:24.3
    environment:
      CLICKHOUSE_USER: langfuse
      CLICKHOUSE_PASSWORD: langfuse
    volumes:
      - langfuse_ch_data:/var/lib/clickhouse
    healthcheck:
      test: ["CMD", "clickhouse-client", "--query", "SELECT 1"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: langfuse
      MINIO_ROOT_PASSWORD: langfuse123
    volumes:
      - langfuse_minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-redis:
    image: redis:7
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-web:
    image: langfuse/langfuse:3
    depends_on:
      langfuse-postgres:
        condition: service_healthy
      langfuse-clickhouse:
        condition: service_healthy
      langfuse-redis:
        condition: service_healthy
      langfuse-minio:
        condition: service_healthy
    ports:
      - "3030:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-postgres:5432/langfuse
      CLICKHOUSE_URL: http://langfuse-clickhouse:8123
      CLICKHOUSE_USER: langfuse
      CLICKHOUSE_PASSWORD: langfuse
      REDIS_HOST: langfuse-redis
      REDIS_PORT: 6379
      S3_ENDPOINT: http://langfuse-minio:9000
      S3_ACCESS_KEY_ID: langfuse
      S3_SECRET_ACCESS_KEY: langfuse123
      S3_BUCKET_NAME: langfuse
      S3_REGION: auto
      NEXTAUTH_SECRET: mysecretkey-change-in-prod
      NEXTAUTH_URL: http://localhost:3030
      SALT: mysalt-change-in-prod
      LANGFUSE_INIT_ORG_ID: geoinsight-org
      LANGFUSE_INIT_ORG_NAME: GeoInsight
      LANGFUSE_INIT_PROJECT_ID: geoinsight-dev
      LANGFUSE_INIT_PROJECT_NAME: geoinsight-dev
      LANGFUSE_INIT_USER_EMAIL: admin@local.dev
      LANGFUSE_INIT_USER_PASSWORD: admin123
      LANGFUSE_INIT_USER_NAME: Admin

  langfuse-worker:
    image: langfuse/langfuse-worker:3
    depends_on:
      langfuse-postgres:
        condition: service_healthy
      langfuse-clickhouse:
        condition: service_healthy
      langfuse-redis:
        condition: service_healthy
      langfuse-minio:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-postgres:5432/langfuse
      CLICKHOUSE_URL: http://langfuse-clickhouse:8123
      CLICKHOUSE_USER: langfuse
      CLICKHOUSE_PASSWORD: langfuse
      REDIS_HOST: langfuse-redis
      REDIS_PORT: 6379
      S3_ENDPOINT: http://langfuse-minio:9000
      S3_ACCESS_KEY_ID: langfuse
      S3_SECRET_ACCESS_KEY: langfuse123
      S3_BUCKET_NAME: langfuse
      S3_REGION: auto

volumes:
  postgres_data:
  langfuse_pg_data:
  langfuse_ch_data:
  langfuse_minio_data:
```

- [ ] **Step 2: Verify docker compose config**

```bash
docker compose config --quiet
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "infra: docker-compose for Postgres+PostGIS and Langfuse v3"
```

---

## Task 3: Scripts and README

**Files:**
- Create: `scripts/start_backend.sh`
- Create: `scripts/start_streamlit.sh`
- Create: `scripts/reset_db.sh`
- Create: `README.md`
- Create: `data/README.md`

- [ ] **Step 1: Create scripts**

`scripts/start_backend.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
exec uv run uvicorn backend.main:app \
    --host "${BACKEND_HOST:-0.0.0.0}" \
    --port "${BACKEND_PORT:-8080}" \
    --reload
```

`scripts/start_streamlit.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
exec uv run streamlit run streamlit_app/app.py --server.port 8501
```

`scripts/reset_db.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
PGDSN="${POSTGRES_DSN:-postgresql://geoinsight:geoinsight@localhost:5432/geoinsight}"

echo "==> Dropping and recreating database..."
psql "$PGDSN" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "==> Running migrations..."
psql "$PGDSN" -f backend/db/migrations/001_schema.sql
psql "$PGDSN" -f backend/db/migrations/002_indices.sql

echo "==> Loading demo data..."
uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset

echo "==> Done."
```

```bash
chmod +x scripts/*.sh
```

- [ ] **Step 2: Create `README.md`**

```markdown
# GeoInsight Agent

AI assistant that turns telecom geodata into business analytics via chat.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker & Docker Compose
- vLLM running externally with gpt-oss-120b:

```bash
vllm serve openai/gpt-oss-120b \
  --tensor-parallel-size 2 \
  --tool-call-parser openai \
  --enable-auto-tool-choice \
  --reasoning-parser openai_gptoss \
  --max-model-len 131072
```

## Quick Start

### 1. Install dependencies

```bash
uv sync --all-extras
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts:
- PostgreSQL + PostGIS on port 5432
- Langfuse v3 on port 3000

### 3. Setup Langfuse

Open http://localhost:3000, log in with `admin@local.dev` / `admin123`.
Create API keys in project settings, add to `.env`:

```bash
cp .env.example .env
# Edit .env — fill LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY
```

### 4. Load demo data

```bash
# Run migrations
psql postgresql://geoinsight:geoinsight@localhost:5432/geoinsight \
  -f backend/db/migrations/001_schema.sql
psql postgresql://geoinsight:geoinsight@localhost:5432/geoinsight \
  -f backend/db/migrations/002_indices.sql

# Load Olmaliq data
uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset
```

### 5. Start backend

```bash
./scripts/start_backend.sh
```

### 6. Start Streamlit demo

```bash
./scripts/start_streamlit.sh
```

Open http://localhost:8501 and ask: "Где открыть кофейню для аудитории 25-35 в Олмалике?"

## Architecture

```
Streamlit UI  ──HTTP/SSE──►  FastAPI backend
                              ├── OpenAI Agents SDK
                              ├── Tools (find_zones, zone_demographics, zone_traffic, ...)
                              └── PostgreSQL + PostGIS
                              
vLLM (external) ◄── Agents SDK
Langfuse (docker) ◄── OpenTelemetry
```

## Development

```bash
uv run ruff format .
uv run ruff check --fix .
uv run mypy backend
uv run pytest
```
```

- [ ] **Step 3: Create `data/README.md`**

```markdown
# Demo Data

CSV files are not committed to git. Place them in this directory or `dataset/` at repo root.

## Required files for Olmaliq

| File | Description |
|---|---|
| `dim_zid_town_Olmaliq.csv` | Zone polygons (zid, city_id, net_type, wkt) |
| `geo_olmaliq_cnt.csv` | Zone demographics aggregate (zid, ts, income, age, gender, cnt, home_zid, job_zid) |
| `geo_olmaliq_dyn_all.csv` | Zone dynamics with time axis (zid, ts, income, age, gender, cnt) |

## Loading

```bash
uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset
```
```

- [ ] **Step 4: Commit**

```bash
git add scripts/ README.md data/README.md
git commit -m "infra: scripts, README, data README"
```

---

## Task 4: SQL Migrations

**Files:**
- Create: `backend/db/__init__.py`
- Create: `backend/db/migrations/001_schema.sql`
- Create: `backend/db/migrations/002_indices.sql`

- [ ] **Step 1: Create migration files**

`backend/db/__init__.py` — empty.

`backend/db/migrations/001_schema.sql` (per TZ:13.1):

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

-- Zones (250x250m polygons)
CREATE TABLE zones (
    zid           BIGINT PRIMARY KEY,
    city          TEXT NOT NULL,
    geom          GEOMETRY(Polygon, 4326) NOT NULL,
    centroid      GEOMETRY(Point, 4326) GENERATED ALWAYS AS (ST_Centroid(geom)) STORED
);

-- Zone demographics (aggregates)
CREATE TABLE zone_demographics (
    zid       BIGINT NOT NULL REFERENCES zones(zid),
    income    SMALLINT NOT NULL,
    age       SMALLINT NOT NULL,
    gender    SMALLINT NOT NULL,
    cnt       INTEGER NOT NULL,
    home_zid  BIGINT,
    job_zid   BIGINT,
    PRIMARY KEY (zid, income, age, gender, COALESCE(home_zid, 0), COALESCE(job_zid, 0))
);

-- Zone dynamics (time series)
CREATE TABLE zone_dynamics (
    zid       BIGINT NOT NULL REFERENCES zones(zid),
    ts        TIMESTAMPTZ NOT NULL,
    income    SMALLINT NOT NULL,
    age       SMALLINT NOT NULL,
    gender    SMALLINT NOT NULL,
    cnt       INTEGER NOT NULL
);

-- Trajectories (optional for MVP, needed for home_work_flow and roaming_analysis)
CREATE TABLE trajectories (
    code         TEXT NOT NULL,
    age_group    TEXT,
    home_zid     BIGINT,
    job_zid      BIGINT,
    hourly_zids  JSONB,
    roaming_type TEXT,
    country_name TEXT
);
```

`backend/db/migrations/002_indices.sql` (per TZ:13.2):

```sql
CREATE INDEX zones_city_idx ON zones (city);
CREATE INDEX zones_geom_gist ON zones USING GIST (geom);
CREATE INDEX zones_centroid_gist ON zones USING GIST (centroid);

CREATE INDEX zd_zid_idx ON zone_demographics (zid);
CREATE INDEX zd_filter_idx ON zone_demographics (income, age, gender);

CREATE INDEX zdyn_zid_ts_idx ON zone_dynamics (zid, ts);

CREATE INDEX traj_home_idx ON trajectories (home_zid);
CREATE INDEX traj_job_idx ON trajectories (job_zid);
CREATE INDEX traj_country_idx ON trajectories (country_name) WHERE country_name IS NOT NULL;
```

- [ ] **Step 2: Commit**

```bash
git add backend/db/
git commit -m "feat: SQL migrations — schema and indices"
```

---

## Task 5: DB Engine

**Files:**
- Create: `backend/db/engine.py`

- [ ] **Step 1: Create `backend/db/engine.py`**

```python
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.config import settings

engine: AsyncEngine = create_async_engine(
    settings.postgres_dsn,
    echo=False,
    pool_size=10,
    max_overflow=5,
)


async def check_db() -> bool:
    """Return True if database is reachable."""
    async with engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    return True
```

- [ ] **Step 2: Commit**

```bash
git add backend/db/engine.py
git commit -m "feat: async SQLAlchemy engine"
```

---

## Task 6: ETL Script

**Files:**
- Create: `data/load_demo.py`

- [ ] **Step 1: Create `data/load_demo.py`**

Reads tab-separated CSVs and inserts into Postgres via psycopg (sync, since it's a one-off script). Handles the 3 Olmaliq files: zones, demographics, dynamics. Per TZ:13.3.

```python
"""ETL script: load demo CSV data into PostGIS.

Usage:
    uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

# Dynamics ts is absolute hour counter with epoch ~2014-01-01 UTC
TS_EPOCH = datetime(2014, 1, 1, tzinfo=timezone.utc)


def load_zones(cur: psycopg.Cursor, city: str, path: Path) -> int:
    """Load zone polygons from dim_zid_town CSV."""
    count = 0
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            zid = int(row["zid"])
            wkt = row["wkt"]
            cur.execute(
                """
                INSERT INTO zones (zid, city, geom)
                VALUES (%s, %s, ST_GeomFromText(%s, 4326))
                ON CONFLICT (zid) DO NOTHING
                """,
                (zid, city, wkt),
            )
            count += 1
    return count


def load_demographics(cur: psycopg.Cursor, path: Path) -> int:
    """Load zone demographics from geo_*_cnt CSV."""
    count = 0
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            zid = int(row["zid"])
            income = int(float(row["income"]))
            age = int(float(row["age"]))
            gender = int(float(row["gender"]))
            cnt = int(float(row["cnt"]))
            home_zid = int(float(row["home_zid"])) if row.get("home_zid") else None
            job_zid = int(float(row["job_zid"])) if row.get("job_zid") else None
            # Skip rows referencing zones not in zones table (foreign key)
            cur.execute(
                """
                INSERT INTO zone_demographics (zid, income, age, gender, cnt, home_zid, job_zid)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (zid, income, age, gender, cnt, home_zid or None, job_zid or None),
            )
            count += 1
    return count


def load_dynamics(cur: psycopg.Cursor, path: Path) -> int:
    """Load zone dynamics from geo_*_dyn_all CSV."""
    count = 0
    batch = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            ts_hours = int(row["ts"])
            ts_dt = TS_EPOCH + timedelta(hours=ts_hours)
            batch.append((
                int(row["zid"]),
                ts_dt,
                int(float(row["income"])),
                int(float(row["age"])),
                int(float(row["gender"])),
                int(float(row["cnt"])),
            ))
            count += 1
            if len(batch) >= 5000:
                _insert_dynamics_batch(cur, batch)
                batch.clear()
    if batch:
        _insert_dynamics_batch(cur, batch)
    return count


def _insert_dynamics_batch(cur: psycopg.Cursor, batch: list[tuple]) -> None:
    cur.executemany(
        """
        INSERT INTO zone_dynamics (zid, ts, income, age, gender, cnt)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        batch,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Load demo data into PostGIS")
    parser.add_argument("--city", required=True, help="City name (e.g. Olmaliq)")
    parser.add_argument("--data-dir", required=True, help="Directory with CSV files")
    parser.add_argument(
        "--dsn",
        default="postgresql://geoinsight:geoinsight@localhost:5432/geoinsight",
        help="Postgres DSN",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    city_lower = args.city.lower()

    zones_file = data_dir / f"dim_zid_town_{args.city}.csv"
    demo_file = data_dir / f"geo_{city_lower}_cnt.csv"
    dyn_file = data_dir / f"geo_{city_lower}_dyn_all.csv"

    missing = [f for f in [zones_file, demo_file, dyn_file] if not f.exists()]
    if missing:
        print(f"Missing files: {missing}", file=sys.stderr)
        sys.exit(1)

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            print(f"Loading zones from {zones_file}...")
            n = load_zones(cur, args.city, zones_file)
            print(f"  -> {n} zones")

            print(f"Loading demographics from {demo_file}...")
            n = load_demographics(cur, demo_file)
            print(f"  -> {n} rows")

            print(f"Loading dynamics from {dyn_file}...")
            n = load_dynamics(cur, dyn_file)
            print(f"  -> {n} rows")

        conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test ETL with live Postgres**

```bash
docker compose up -d postgres
psql postgresql://geoinsight:geoinsight@localhost:5432/geoinsight \
  -f backend/db/migrations/001_schema.sql
psql postgresql://geoinsight:geoinsight@localhost:5432/geoinsight \
  -f backend/db/migrations/002_indices.sql
uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset
```

Verify:
```bash
psql postgresql://geoinsight:geoinsight@localhost:5432/geoinsight \
  -c "SELECT count(*) FROM zones; SELECT count(*) FROM zone_demographics; SELECT count(*) FROM zone_dynamics;"
```

Expected: ~162 zones, ~87k demographics, ~745k dynamics.

- [ ] **Step 3: Commit**

```bash
git add data/load_demo.py
git commit -m "feat: ETL script for loading Olmaliq demo data"
```

---

## Task 7: DB Queries Module

**Files:**
- Create: `backend/db/queries.py`
- Create: `tests/__init__.py`
- Create: `tests/test_queries.py`

- [ ] **Step 1: Create `backend/db/queries.py`**

SQLAlchemy Core queries returning dataclass results (per TZ:13.4). Implements `query_find_zones`, `query_zone_demographics`, `query_zone_traffic`.

```python
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.db.engine import engine


@dataclass
class ZoneResult:
    zid: int
    score: float
    total: int
    geometry_geojson: dict


@dataclass
class DemographicRow:
    income: int
    age: int
    gender: int
    cnt: int


@dataclass
class TrafficRow:
    hour: int
    cnt: int


async def query_find_zones(
    city: str,
    age: list[int] | None = None,
    income: list[int] | None = None,
    gender: list[int] | None = None,
    min_total: int | None = None,
    top_n: int = 20,
) -> list[ZoneResult]:
    """Find zones matching demographic criteria, ranked by score."""
    conditions = ["z.city = :city"]
    params: dict = {"city": city, "top_n": top_n}

    if age:
        conditions.append("zd.age = ANY(:age)")
        params["age"] = age
    if income:
        conditions.append("zd.income = ANY(:income)")
        params["income"] = income
    if gender:
        conditions.append("zd.gender = ANY(:gender)")
        params["gender"] = gender

    where = " AND ".join(conditions)

    having = ""
    if min_total:
        having = "HAVING SUM(zd.cnt) >= :min_total"
        params["min_total"] = min_total

    sql = sa.text(f"""
        SELECT
            z.zid,
            SUM(zd.cnt) AS total,
            ST_AsGeoJSON(z.geom)::json AS geometry_geojson
        FROM zones z
        JOIN zone_demographics zd ON zd.zid = z.zid
        WHERE {where}
        GROUP BY z.zid, z.geom
        {having}
        ORDER BY total DESC
        LIMIT :top_n
    """)

    async with engine.connect() as conn:
        rows = (await conn.execute(sql, params)).mappings().all()

    max_total = rows[0]["total"] if rows else 1
    return [
        ZoneResult(
            zid=r["zid"],
            score=round(r["total"] / max_total * 10, 2),
            total=r["total"],
            geometry_geojson=r["geometry_geojson"],
        )
        for r in rows
    ]


async def query_zone_demographics(
    zid: int,
    income: list[int] | None = None,
    age: list[int] | None = None,
    gender: list[int] | None = None,
) -> list[DemographicRow]:
    """Get demographic breakdown for a zone."""
    conditions = ["zid = :zid"]
    params: dict = {"zid": zid}

    if income:
        conditions.append("income = ANY(:income)")
        params["income"] = income
    if age:
        conditions.append("age = ANY(:age)")
        params["age"] = age
    if gender:
        conditions.append("gender = ANY(:gender)")
        params["gender"] = gender

    where = " AND ".join(conditions)

    sql = sa.text(f"""
        SELECT income, age, gender, SUM(cnt) AS cnt
        FROM zone_demographics
        WHERE {where}
        GROUP BY income, age, gender
        ORDER BY cnt DESC
    """)

    async with engine.connect() as conn:
        rows = (await conn.execute(sql, params)).mappings().all()

    return [DemographicRow(income=r["income"], age=r["age"], gender=r["gender"], cnt=r["cnt"]) for r in rows]


async def query_zone_traffic(
    zid: int,
    hours: list[int] | None = None,
) -> list[TrafficRow]:
    """Get hourly traffic for a zone from dynamics data."""
    conditions = ["zid = :zid"]
    params: dict = {"zid": zid}

    hour_filter = ""
    if hours:
        hour_filter = "HAVING EXTRACT(HOUR FROM ts)::int = ANY(:hours)"
        params["hours"] = hours

    sql = sa.text(f"""
        SELECT EXTRACT(HOUR FROM ts)::int AS hour, SUM(cnt) AS cnt
        FROM zone_dynamics
        WHERE {" AND ".join(conditions)}
        GROUP BY hour
        {hour_filter}
        ORDER BY hour
    """)

    async with engine.connect() as conn:
        rows = (await conn.execute(sql, params)).mappings().all()

    return [TrafficRow(hour=r["hour"], cnt=r["cnt"]) for r in rows]
```

- [ ] **Step 2: Commit**

```bash
mkdir -p tests && touch tests/__init__.py
git add backend/db/queries.py tests/__init__.py
git commit -m "feat: DB query functions — find_zones, zone_demographics, zone_traffic"
```

---

## Task 8: Logging Configuration

**Files:**
- Create: `backend/logging_config.py`

- [ ] **Step 1: Create `backend/logging_config.py`**

Per TZ:11.1, structlog with JSON or console rendering.

```python
import logging

import structlog

from backend.config import settings


def configure_logging() -> None:
    """Configure structlog with JSON or console output."""
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/logging_config.py
git commit -m "feat: structlog configuration"
```

---

## Task 9: API Schemas

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/schemas.py`

- [ ] **Step 1: Create `backend/api/schemas.py`**

Per TZ:7 and TZ:8 — request/response models and artifact types.

```python
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


# === Request ===

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "geoinsight-v1"
    messages: list[ChatMessage]
    stream: bool = False


# === Artifacts (TZ:8) ===

class MapArtifact(BaseModel):
    id: str = ""
    type: Literal["map"] = "map"
    viz: Literal["choropleth", "heatmap", "points"] = "choropleth"
    geojson: dict = Field(default_factory=dict)
    color_metric: str | None = None
    legend: dict | None = None
    bbox: list[float] | None = None
    tooltip_fields: list[str] = Field(default_factory=list)


class FlowMapArtifact(BaseModel):
    id: str = ""
    type: Literal["flow_map"] = "flow_map"
    flows: list[dict] = Field(default_factory=list)
    bbox: list[float] | None = None


class TableArtifact(BaseModel):
    id: str = ""
    type: Literal["table"] = "table"
    title: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)


class ChartArtifact(BaseModel):
    id: str = ""
    type: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "pie"] = "bar"
    title: str | None = None
    data: dict = Field(default_factory=dict)


Artifact = MapArtifact | FlowMapArtifact | TableArtifact | ChartArtifact


# === Response ===

class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "geoinsight-v1"
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)
    trace_id: str | None = None
    artifacts: list[dict] = Field(default_factory=list)
```

- [ ] **Step 2: Commit**

```bash
mkdir -p backend/api && touch backend/api/__init__.py
git add backend/api/
git commit -m "feat: API schemas — request, response, artifacts"
```

---

## Task 10: SSE Formatter

**Files:**
- Create: `backend/api/sse.py`

- [ ] **Step 1: Create `backend/api/sse.py`**

Per TZ:7.3 — SSE formatting with standard `data:` and custom `event:` lines.

```python
import json
from typing import Any


def sse_event(data: Any, event: str | None = None) -> str:
    """Format a single SSE event.

    Standard chunks: data: {...}\n\n
    Custom events: event: <type>\ndata: {...}\n\n
    """
    payload = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
    lines = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {payload}")
    return "\n".join(lines) + "\n\n"


def sse_done() -> str:
    """Format the [DONE] terminator."""
    return "data: [DONE]\n\n"
```

- [ ] **Step 2: Commit**

```bash
git add backend/api/sse.py
git commit -m "feat: SSE event formatter"
```

---

## Task 11: FastAPI App with Stub Endpoint

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: Create `backend/main.py`**

Per TZ:7 — FastAPI with `/healthz` and stub `/v1/chat/completions`.

```python
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.api.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
)
from backend.api.sse import sse_done, sse_event
from backend.config import settings
from backend.db.engine import check_db
from backend.logging_config import configure_logging

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    log.info("app.starting", backend_port=settings.backend_port)
    yield
    log.info("app.stopping")


app = FastAPI(title="GeoInsight Agent", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    """Health check: verify Postgres and vLLM are reachable (TZ:7.4)."""
    checks: dict = {}

    # Postgres
    try:
        await check_db()
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # vLLM
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.llm_base_url}/models")
            r.raise_for_status()
            checks["vllm"] = "ok"
    except Exception as e:
        checks["vllm"] = f"error: {e}"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, raw_request: Request) -> StreamingResponse | JSONResponse:
    """OpenAI-compatible chat completions endpoint (TZ:7)."""
    trace_id = raw_request.headers.get("x-trace-id", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    log.info(
        "request.received",
        messages_count=len(request.messages),
        last_user_msg_preview=request.messages[-1].content[:100] if request.messages else "",
    )

    if request.stream:
        return StreamingResponse(
            _stream_stub(trace_id),
            media_type="text/event-stream",
            headers={"X-Trace-Id": trace_id},
        )

    response = ChatCompletionResponse(
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(
                    role="assistant",
                    content="GeoInsight Agent is starting up. Tools not yet connected.",
                ),
            )
        ],
        trace_id=trace_id,
    )
    return JSONResponse(
        content=response.model_dump(),
        headers={"X-Trace-Id": trace_id},
    )


async def _stream_stub(trace_id: str) -> AsyncGenerator[str, None]:
    """Stub SSE stream for testing before agent is wired up."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    yield sse_event({"trace_id": trace_id}, event="trace_started")

    # Role chunk
    yield sse_event({
        "id": completion_id,
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    })

    # Content chunk
    content = "GeoInsight Agent is starting up. Tools not yet connected."
    yield sse_event({
        "id": completion_id,
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
    })

    # Finish
    yield sse_event({
        "id": completion_id,
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    })
    yield sse_done()
```

- [ ] **Step 2: Test the server manually**

```bash
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8080 &
sleep 2
# Health check (postgres should be up from Task 6)
curl -s http://localhost:8080/healthz | python3 -m json.tool
# SSE stream
curl -s -N -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}],"stream":true}'
kill %1
```

Expected: SSE stream with `event: trace_started`, role delta, content delta, finish, `[DONE]`.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: FastAPI app with healthz and stub chat endpoint"
```

---

## Task 12: Langfuse Observability

**Files:**
- Create: `backend/observability.py`

- [ ] **Step 1: Create `backend/observability.py`**

Per TZ:12.2 — OTEL integration for Langfuse.

```python
import base64
import os

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from backend.config import settings

log = structlog.get_logger()


def init_langfuse() -> None:
    """Initialize Langfuse via OpenTelemetry OTLP exporter.

    If LANGFUSE_ENABLED is false or keys are missing, skip silently (TZ:12.5).
    """
    if not settings.langfuse_enabled:
        log.info("langfuse.disabled")
        return

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        log.warning("langfuse.missing_keys", hint="Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY")
        return

    try:
        auth = base64.b64encode(
            f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
        ).decode()

        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = (
            f"{settings.langfuse_host}/api/public/otel"
        )
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth}"

        provider = TracerProvider()
        processor = BatchSpanProcessor(OTLPSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        log.info("langfuse.initialized", host=settings.langfuse_host)
    except Exception:
        log.warning("langfuse.init_failed", exc_info=True)
```

- [ ] **Step 2: Wire into FastAPI lifespan**

In `backend/main.py`, update the lifespan to call `init_langfuse()`:

```python
# Add import at top:
from backend.observability import init_langfuse

# Update lifespan:
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    init_langfuse()
    log.info("app.starting", backend_port=settings.backend_port)
    yield
    log.info("app.stopping")
```

- [ ] **Step 3: Commit**

```bash
git add backend/observability.py backend/main.py
git commit -m "feat: Langfuse observability via OTEL"
```

---

## Task 13: Tools — Base and Stubs

**Files:**
- Create: `backend/tools/__init__.py`
- Create: `backend/tools/base.py`
- Create: `backend/tools/home_work_flow.py`
- Create: `backend/tools/catchment_area.py`
- Create: `backend/tools/compare_zones.py`
- Create: `backend/tools/roaming_analysis.py`

- [ ] **Step 1: Create `backend/tools/base.py`**

Per TZ:9.1 — GeoContext with emit_artifact.

```python
from dataclasses import dataclass, field


@dataclass
class GeoContext:
    """Context passed through Agent Runner to all tools."""

    trace_id: str
    artifacts: list[dict] = field(default_factory=list)

    def emit_artifact(self, artifact: dict) -> str:
        """Register an artifact for the UI and return its id."""
        artifact_id = f"art_{len(self.artifacts) + 1}"
        artifact["id"] = artifact_id
        self.artifacts.append(artifact)
        return artifact_id


def safe_args_preview(args: dict, max_list: int = 10, max_str: int = 200) -> dict:
    """Truncate large args for logging (TZ:11.4)."""
    preview = {}
    for k, v in args.items():
        if isinstance(v, list) and len(v) > max_list:
            preview[k] = f"[{len(v)} items]"
        elif isinstance(v, str) and len(v) > max_str:
            preview[k] = v[:max_str] + "..."
        else:
            preview[k] = v
    return preview
```

- [ ] **Step 2: Create stub tools**

Per TZ:9.2 — stubs return `{"status": "not_implemented"}`.

`backend/tools/home_work_flow.py`:
```python
from agents import function_tool, RunContextWrapper

from backend.tools.base import GeoContext


@function_tool
async def home_work_flow(
    ctx: RunContextWrapper[GeoContext],
    zid: int,
    direction: str = "both",
    top_n: int = 10,
) -> dict:
    """Анализ потоков дом-работа для зоны.

    Args:
        zid: идентификатор зоны
        direction: направление потока — "from_home", "to_work", "both"
        top_n: количество топ-зон в результате
    """
    return {"status": "not_implemented"}
```

`backend/tools/catchment_area.py`:
```python
from agents import function_tool, RunContextWrapper

from backend.tools.base import GeoContext


@function_tool
async def catchment_area(
    ctx: RunContextWrapper[GeoContext],
    zid: int,
    radius_m: int = 1000,
) -> dict:
    """Анализ зоны охвата — зоны в заданном радиусе с профилем аудитории.

    Args:
        zid: идентификатор центральной зоны
        radius_m: радиус в метрах
    """
    return {"status": "not_implemented"}
```

`backend/tools/compare_zones.py`:
```python
from agents import function_tool, RunContextWrapper

from backend.tools.base import GeoContext


@function_tool
async def compare_zones(
    ctx: RunContextWrapper[GeoContext],
    zids: list[int],
) -> dict:
    """Сравнение 2-5 зон по демографии и трафику.

    Args:
        zids: список zid для сравнения (2-5 штук)
    """
    return {"status": "not_implemented"}
```

`backend/tools/roaming_analysis.py`:
```python
from agents import function_tool, RunContextWrapper

from backend.tools.base import GeoContext


@function_tool
async def roaming_analysis(
    ctx: RunContextWrapper[GeoContext],
    city: str,
    roaming_type: str = "Международный",
    country: str | None = None,
) -> dict:
    """Анализ визитов по роумингу — количество, география, время.

    Args:
        city: город для анализа
        roaming_type: тип роуминга ("Международный", "Внутрисетевой")
        country: страна (опционально, для фильтрации)
    """
    return {"status": "not_implemented"}
```

- [ ] **Step 3: Create `backend/tools/__init__.py`**

```python
from backend.tools.catchment_area import catchment_area
from backend.tools.compare_zones import compare_zones
from backend.tools.home_work_flow import home_work_flow
from backend.tools.roaming_analysis import roaming_analysis

__all__ = [
    "catchment_area",
    "compare_zones",
    "home_work_flow",
    "roaming_analysis",
]
```

- [ ] **Step 4: Commit**

```bash
git add backend/tools/
git commit -m "feat: tool base context and 4 stub tools"
```

---

## Task 14: Tool — find_zones

**Files:**
- Create: `backend/tools/find_zones.py`
- Modify: `backend/tools/__init__.py`

- [ ] **Step 1: Create `backend/tools/find_zones.py`**

Full implementation per TZ:9.3.

```python
import time

import structlog
from agents import RunContextWrapper, function_tool

from backend.db.queries import query_find_zones
from backend.tools.base import GeoContext

log = structlog.get_logger()


@function_tool
async def find_zones(
    ctx: RunContextWrapper[GeoContext],
    city: str,
    age: list[int] | None = None,
    income: list[int] | None = None,
    gender: list[int] | None = None,
    min_total: int | None = None,
    top_n: int = 20,
) -> dict:
    """Найти зоны (~250x250м), удовлетворяющие критериям демографии.

    Args:
        city: название города (например, "Olmaliq", "Tashkent")
        age: список возрастных групп 0-5 (0=<18, 1=18-25, 2=26-35, 3=36-45, 4=46-60, 5=>60)
        income: список категорий дохода 0-6 (0=неизвестно, 1=низкий, ..., 6=очень высокий)
        gender: список 0 (м) или 1 (ж)
        min_total: минимум суммарного населения зоны
        top_n: количество лучших зон в результате

    Returns:
        Сводка для LLM — количество найденных зон и топ-5 с метриками (без полигонов).
    """
    t0 = time.monotonic()
    zones = await query_find_zones(
        city=city, age=age, income=income, gender=gender,
        min_total=min_total, top_n=top_n,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)

    log.info(
        "tool.find_zones.done",
        trace_id=ctx.context.trace_id,
        rows=len(zones),
        duration_ms=duration_ms,
    )

    if zones:
        bbox = _calc_bbox(zones)
        ctx.context.emit_artifact({
            "type": "map",
            "viz": "choropleth",
            "geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": z.geometry_geojson,
                        "properties": {
                            "zid": z.zid,
                            "score": z.score,
                            "total": z.total,
                        },
                    }
                    for z in zones
                ],
            },
            "color_metric": "score",
            "legend": {"title": "Рейтинг зоны", "min": 0, "max": 10},
            "bbox": bbox,
            "tooltip_fields": ["zid", "score", "total"],
        })

    return {
        "count": len(zones),
        "top": [
            {"zid": z.zid, "score": z.score, "total": z.total}
            for z in zones[:5]
        ],
        "summary": f"Найдено {len(zones)} зон в {city}",
    }


def _calc_bbox(zones: list) -> list[float]:
    """Calculate bounding box from zone GeoJSON geometries."""
    lons, lats = [], []
    for z in zones:
        geom = z.geometry_geojson
        if geom.get("type") == "Polygon":
            for ring in geom.get("coordinates", []):
                for coord in ring:
                    lons.append(coord[0])
                    lats.append(coord[1])
    if not lons:
        return [69.5, 40.8, 69.8, 41.0]
    return [min(lons), min(lats), max(lons), max(lats)]
```

- [ ] **Step 2: Update `backend/tools/__init__.py`**

Add `find_zones` to imports and `__all__`.

```python
from backend.tools.catchment_area import catchment_area
from backend.tools.compare_zones import compare_zones
from backend.tools.find_zones import find_zones
from backend.tools.home_work_flow import home_work_flow
from backend.tools.roaming_analysis import roaming_analysis

__all__ = [
    "catchment_area",
    "compare_zones",
    "find_zones",
    "home_work_flow",
    "roaming_analysis",
]
```

- [ ] **Step 3: Commit**

```bash
git add backend/tools/find_zones.py backend/tools/__init__.py
git commit -m "feat: find_zones tool — full implementation"
```

---

## Task 15: Tool — zone_demographics

**Files:**
- Create: `backend/tools/zone_demographics.py`
- Modify: `backend/tools/__init__.py`

- [ ] **Step 1: Create `backend/tools/zone_demographics.py`**

Per TZ:9.2 item 1.

```python
import time

import structlog
from agents import RunContextWrapper, function_tool

from backend.db.queries import query_zone_demographics
from backend.tools.base import GeoContext

log = structlog.get_logger()

AGE_LABELS = {0: "<18", 1: "18-25", 2: "26-35", 3: "36-45", 4: "46-60", 5: ">60"}
INCOME_LABELS = {
    0: "неизвестно", 1: "низкий", 2: "ниже среднего", 3: "средний",
    4: "выше среднего", 5: "высокий", 6: "очень высокий",
}
GENDER_LABELS = {0: "мужской", 1: "женский"}


@function_tool
async def zone_demographics(
    ctx: RunContextWrapper[GeoContext],
    zid: int,
    income: list[int] | None = None,
    age: list[int] | None = None,
    gender: list[int] | None = None,
) -> dict:
    """Демографический профиль зоны — распределение по доходу, возрасту, полу.

    Args:
        zid: идентификатор зоны
        income: фильтр по категориям дохода 0-6
        age: фильтр по возрастным группам 0-5
        gender: фильтр по полу — 0 (м) или 1 (ж)

    Returns:
        Распределение населения зоны по категориям.
    """
    t0 = time.monotonic()
    rows = await query_zone_demographics(zid=zid, income=income, age=age, gender=gender)
    duration_ms = int((time.monotonic() - t0) * 1000)

    log.info(
        "tool.zone_demographics.done",
        trace_id=ctx.context.trace_id,
        zid=zid,
        rows=len(rows),
        duration_ms=duration_ms,
    )

    total = sum(r.cnt for r in rows)

    # Aggregate by dimension
    by_income: dict[str, int] = {}
    by_age: dict[str, int] = {}
    by_gender: dict[str, int] = {}

    for r in rows:
        label = INCOME_LABELS.get(r.income, str(r.income))
        by_income[label] = by_income.get(label, 0) + r.cnt

        label = AGE_LABELS.get(r.age, str(r.age))
        by_age[label] = by_age.get(label, 0) + r.cnt

        label = GENDER_LABELS.get(r.gender, str(r.gender))
        by_gender[label] = by_gender.get(label, 0) + r.cnt

    # Table artifact
    table_rows = []
    for r in rows[:20]:
        table_rows.append([
            r.income, INCOME_LABELS.get(r.income, "?"),
            r.age, AGE_LABELS.get(r.age, "?"),
            GENDER_LABELS.get(r.gender, "?"),
            r.cnt,
        ])

    ctx.context.emit_artifact({
        "type": "table",
        "title": f"Демография зоны {zid}",
        "columns": ["income_code", "income", "age_code", "age", "gender", "cnt"],
        "rows": table_rows,
    })

    return {
        "zid": zid,
        "total": total,
        "by_income": by_income,
        "by_age": by_age,
        "by_gender": by_gender,
    }
```

- [ ] **Step 2: Update `backend/tools/__init__.py`** — add `zone_demographics` import.

- [ ] **Step 3: Commit**

```bash
git add backend/tools/zone_demographics.py backend/tools/__init__.py
git commit -m "feat: zone_demographics tool — full implementation"
```

---

## Task 16: Tool — zone_traffic

**Files:**
- Create: `backend/tools/zone_traffic.py`
- Modify: `backend/tools/__init__.py`

- [ ] **Step 1: Create `backend/tools/zone_traffic.py`**

Per TZ:9.2 item 3.

```python
import time

import structlog
from agents import RunContextWrapper, function_tool

from backend.db.queries import query_zone_traffic
from backend.tools.base import GeoContext

log = structlog.get_logger()


@function_tool
async def zone_traffic(
    ctx: RunContextWrapper[GeoContext],
    zid: int,
    hours: list[int] | None = None,
) -> dict:
    """Почасовая динамика трафика в зоне.

    Args:
        zid: идентификатор зоны
        hours: список часов 0-23 для фильтрации (опционально)

    Returns:
        Почасовое распределение трафика, пиковый час и значение.
    """
    t0 = time.monotonic()
    rows = await query_zone_traffic(zid=zid, hours=hours)
    duration_ms = int((time.monotonic() - t0) * 1000)

    log.info(
        "tool.zone_traffic.done",
        trace_id=ctx.context.trace_id,
        zid=zid,
        rows=len(rows),
        duration_ms=duration_ms,
    )

    by_hour = {r.hour: r.cnt for r in rows}
    peak_hour = max(by_hour, key=by_hour.get, default=0) if by_hour else 0
    peak_value = by_hour.get(peak_hour, 0)

    # Chart artifact
    ctx.context.emit_artifact({
        "type": "chart",
        "chart_type": "bar",
        "title": f"Трафик зоны {zid} по часам",
        "data": {
            "labels": [f"{h:02d}:00" for h in sorted(by_hour.keys())],
            "values": [by_hour[h] for h in sorted(by_hour.keys())],
        },
    })

    return {
        "zid": zid,
        "by_hour": by_hour,
        "peak_hour": peak_hour,
        "peak_value": peak_value,
    }
```

- [ ] **Step 2: Update `backend/tools/__init__.py`** — add `zone_traffic` import.

- [ ] **Step 3: Commit**

```bash
git add backend/tools/zone_traffic.py backend/tools/__init__.py
git commit -m "feat: zone_traffic tool — full implementation"
```

---

## Task 17: System Prompt

**Files:**
- Create: `backend/agent/system_prompt.py`
- Create: `backend/agent/__init__.py`

- [ ] **Step 1: Create system prompt**

Per TZ:10 — role, data descriptions, field encodings, rules.

`backend/agent/__init__.py` — empty.

`backend/agent/system_prompt.py`:

```python
SYSTEM_PROMPT = """\
Ты — GeoInsight Agent, AI-аналитик геоданных мобильного оператора. \
Помогаешь B2B-клиентам (ритейл, недвижимость, реклама, транспорт, туризм) \
получать бизнес-аналитику из телеком-данных.

## Доступные данные

Ты работаешь с геоданными по зонам ~250x250м. Данные включают:
- **Справочник зон** — полигоны с привязкой к городу
- **Демография зон** — доход, возраст, пол, количество людей (агрегат)
- **Динамика зон** — как меняется население зоны по часам
- **Траектории** — перемещения дом-работа (в разработке)

## Кодировки полей

**income** (доход):
- 0 = неизвестно
- 1 = низкий
- 2 = ниже среднего
- 3 = средний
- 4 = выше среднего
- 5 = высокий
- 6 = очень высокий

**age** (возраст):
- 0 = <18 лет
- 1 = 18-25 лет
- 2 = 26-35 лет
- 3 = 36-45 лет
- 4 = 46-60 лет
- 5 = >60 лет

**gender** (пол):
- 0 = мужской
- 1 = женский

## Доступные города

Olmaliq, Tashkent

## Правила

1. **Конвертируй** пользовательские запросы в коды полей. Например, \
"аудитория 25-35" → age=[2], "доход выше среднего" → income=[4,5,6].

2. **Никогда не выдумывай zid** — используй только те, что вернулись из инструментов.

3. **Отвечай кратко** — бизнес-вывод + предложение углубить анализ. \
Стиль: деловой, на русском языке.

4. **Выбор инструмента:**
   - Ищешь зоны по критериям → find_zones
   - Нужен профиль конкретной зоны → zone_demographics
   - Нужна почасовая динамика → zone_traffic
   - Потоки дом-работа → home_work_flow (в разработке)
   - Зона охвата → catchment_area (в разработке)
   - Сравнение зон → compare_zones (в разработке)
   - Анализ туристов/роуминга → roaming_analysis (в разработке)

5. **Многошаговые сценарии:** можешь вызывать несколько инструментов \
последовательно. Например: find_zones → zone_demographics для детализации \
топ-зоны → zone_traffic для анализа пиков.

6. Ответ всегда содержит **краткий вывод** и **предложение углубить анализ**.
"""
```

- [ ] **Step 2: Commit**

```bash
git add backend/agent/
git commit -m "feat: system prompt with field encodings and tool rules"
```

---

## Task 18: Agent Definition

**Files:**
- Create: `backend/agent/geo_agent.py`

- [ ] **Step 1: Create `backend/agent/geo_agent.py`**

Per TZ:6 — Agent definition with vLLM as OpenAI client.

```python
from agents import Agent, set_default_openai_client
from openai import AsyncOpenAI

from backend.agent.system_prompt import SYSTEM_PROMPT
from backend.config import settings
from backend.tools import (
    catchment_area,
    compare_zones,
    find_zones,
    home_work_flow,
    roaming_analysis,
)
from backend.tools.base import GeoContext
from backend.tools.zone_demographics import zone_demographics
from backend.tools.zone_traffic import zone_traffic

# Point Agents SDK at vLLM
_client = AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)
set_default_openai_client(_client)

geo_agent = Agent[GeoContext](
    name="GeoInsight",
    model=settings.llm_model,
    instructions=SYSTEM_PROMPT,
    tools=[
        find_zones,
        zone_demographics,
        zone_traffic,
        home_work_flow,
        catchment_area,
        compare_zones,
        roaming_analysis,
    ],
)
```

- [ ] **Step 2: Commit**

```bash
git add backend/agent/geo_agent.py
git commit -m "feat: Agent definition — GeoInsight with 7 tools on vLLM"
```

---

## Task 19: Agent Runner + SSE Mapper

**Files:**
- Create: `backend/agent/runner.py`
- Modify: `backend/main.py`

This is the core integration task: wiring `Runner.run_streamed()` output to SSE events.

- [ ] **Step 1: Create `backend/agent/runner.py`**

Per TZ:9.3 reference and TZ:7.3 — maps Agents SDK stream events to SSE.

```python
import time
import uuid
from typing import AsyncGenerator

import structlog
from agents import Runner, RawResponsesStreamEvent, RunItemStreamEvent
from agents.items import (
    ToolCallItem,
    ToolCallOutputItem,
    MessageOutputItem,
)

from backend.agent.geo_agent import geo_agent
from backend.api.schemas import ChatMessage
from backend.api.sse import sse_done, sse_event
from backend.tools.base import GeoContext, safe_args_preview

log = structlog.get_logger()


async def run_agent_stream(
    messages: list[ChatMessage],
    trace_id: str,
) -> AsyncGenerator[str, None]:
    """Run the agent and yield SSE events.

    Maps Agents SDK stream events to the SSE contract from TZ:7.3.
    """
    ctx = GeoContext(trace_id=trace_id)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    t0 = time.monotonic()

    # Emit trace_started
    langfuse_url = None  # Will be set if Langfuse is configured
    yield sse_event(
        {"trace_id": trace_id, "langfuse_url": langfuse_url},
        event="trace_started",
    )

    log.info("agent.started", trace_id=trace_id, model=geo_agent.model)

    # Convert messages to format expected by runner
    input_messages = [
        {"role": m.role, "content": m.content} for m in messages
    ]

    tool_timers: dict[str, float] = {}
    tools_called: list[str] = []

    try:
        result = Runner.run_streamed(
            geo_agent,
            input=input_messages,
            context=ctx,
        )

        # Role chunk
        yield sse_event({
            "id": completion_id,
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        })

        async for event in result.stream_events():
            if isinstance(event, RawResponsesStreamEvent):
                # Raw LLM token — extract text delta
                data = event.data
                if hasattr(data, "choices") and data.choices:
                    for choice in data.choices:
                        delta = choice.delta
                        if hasattr(delta, "content") and delta.content:
                            yield sse_event({
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": delta.content},
                                    "finish_reason": None,
                                }],
                            })

            elif isinstance(event, RunItemStreamEvent):
                item = event.item

                if isinstance(item, ToolCallItem):
                    call_id = item.call_id or str(uuid.uuid4())
                    tool_name = item.type if hasattr(item, "type") else "unknown"
                    # Try to get tool name from the agent's tools
                    if hasattr(item, "raw_item") and hasattr(item.raw_item, "name"):
                        tool_name = item.raw_item.name
                    args = {}
                    if hasattr(item, "raw_item") and hasattr(item.raw_item, "arguments"):
                        import json
                        try:
                            args = json.loads(item.raw_item.arguments or "{}")
                        except (json.JSONDecodeError, TypeError):
                            args = {}

                    tool_timers[call_id] = time.monotonic()
                    tools_called.append(tool_name)

                    log.info(
                        "tool.started",
                        trace_id=trace_id,
                        tool=tool_name,
                        args_preview=safe_args_preview(args),
                    )
                    yield sse_event(
                        {"call_id": call_id, "name": tool_name, "args": args},
                        event="tool_started",
                    )

                elif isinstance(item, ToolCallOutputItem):
                    call_id = item.call_id or ""
                    duration_ms = int(
                        (time.monotonic() - tool_timers.pop(call_id, time.monotonic())) * 1000
                    )

                    log.info(
                        "tool.finished",
                        trace_id=trace_id,
                        tool=item.raw_item.get("name", "") if isinstance(item.raw_item, dict) else "",
                        duration_ms=duration_ms,
                    )
                    yield sse_event(
                        {"call_id": call_id, "duration_ms": duration_ms, "status": "ok"},
                        event="tool_finished",
                    )

                    # Emit any new artifacts
                    for art in ctx.artifacts:
                        if not art.get("_emitted"):
                            art["_emitted"] = True
                            art_copy = {k: v for k, v in art.items() if k != "_emitted"}
                            log.info(
                                "artifact.emitted",
                                trace_id=trace_id,
                                artifact_id=art_copy["id"],
                                artifact_type=art_copy["type"],
                            )
                            yield sse_event(art_copy, event="artifact")

    except Exception:
        log.exception("agent.failed", trace_id=trace_id)
        yield sse_event({
            "id": completion_id,
            "object": "chat.completion.chunk",
            "choices": [{
                "index": 0,
                "delta": {"content": "Произошла ошибка при обработке запроса."},
                "finish_reason": None,
            }],
        })

    total_duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "agent.finished",
        trace_id=trace_id,
        total_duration_ms=total_duration_ms,
        tools_called=tools_called,
        artifacts_count=len(ctx.artifacts),
    )

    # Finish chunk
    yield sse_event({
        "id": completion_id,
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    })
    yield sse_done()
```

- [ ] **Step 2: Update `backend/main.py`** — replace stub with real agent runner

Replace the `chat_completions` endpoint and remove `_stream_stub`:

```python
# Add import:
from backend.agent.runner import run_agent_stream

# Replace the streaming branch in chat_completions:
@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest, raw_request: Request
) -> StreamingResponse | JSONResponse:
    """OpenAI-compatible chat completions endpoint (TZ:7)."""
    trace_id = raw_request.headers.get("x-trace-id", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    log.info(
        "request.received",
        messages_count=len(request.messages),
        last_user_msg_preview=request.messages[-1].content[:100] if request.messages else "",
    )

    if request.stream:
        return StreamingResponse(
            run_agent_stream(request.messages, trace_id),
            media_type="text/event-stream",
            headers={"X-Trace-Id": trace_id},
        )

    # Non-streaming: collect full response
    chunks = []
    async for chunk in run_agent_stream(request.messages, trace_id):
        chunks.append(chunk)

    # Extract text from collected chunks
    import json as _json
    text = ""
    artifacts = []
    for raw in chunks:
        for line in raw.strip().split("\n"):
            if line.startswith("event: artifact"):
                continue
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    data = _json.loads(line[6:])
                    if "choices" in data:
                        content = data["choices"][0].get("delta", {}).get("content", "")
                        text += content
                    elif "type" in data and data.get("id", "").startswith("art_"):
                        artifacts.append(data)
                except (ValueError, KeyError, IndexError):
                    pass

    response = ChatCompletionResponse(
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=text),
            )
        ],
        trace_id=trace_id,
        artifacts=[a for a in artifacts],
    )
    return JSONResponse(
        content=response.model_dump(),
        headers={"X-Trace-Id": trace_id},
    )
```

Remove the `_stream_stub` function.

- [ ] **Step 3: Commit**

```bash
git add backend/agent/runner.py backend/main.py
git commit -m "feat: agent runner — stream events to SSE"
```

---

## Task 20: Streamlit Client

**Files:**
- Create: `streamlit_app/__init__.py`
- Create: `streamlit_app/client.py`

- [ ] **Step 1: Create `streamlit_app/client.py`**

Per TZ:14.2 — SSE parser using httpx.

```python
import json
from dataclasses import dataclass
from typing import Iterator

import httpx


@dataclass
class SSEEvent:
    event: str | None
    data: dict | str


class GeoInsightClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url

    def stream_chat(self, messages: list[dict]) -> Iterator[SSEEvent]:
        """Stream chat completions via SSE."""
        with httpx.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json={"model": "geoinsight-v1", "messages": messages, "stream": True},
            timeout=120,
        ) as r:
            event_type = None
            for line in r.iter_lines():
                if not line:
                    event_type = None
                    continue
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    raw = line[6:]
                    if raw == "[DONE]":
                        return
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        data = raw
                    yield SSEEvent(event=event_type, data=data)
                    event_type = None
```

- [ ] **Step 2: Commit**

```bash
mkdir -p streamlit_app && touch streamlit_app/__init__.py
git add streamlit_app/__init__.py streamlit_app/client.py
git commit -m "feat: Streamlit SSE client"
```

---

## Task 21: Streamlit Artifact Renderers

**Files:**
- Create: `streamlit_app/artifacts.py`

- [ ] **Step 1: Create `streamlit_app/artifacts.py`**

Per TZ:14.4 — pydeck map, dataframe table, bar/line chart.

```python
import pandas as pd
import pydeck as pdk
import streamlit as st


def render_artifact(art: dict) -> None:
    """Dispatch artifact rendering by type."""
    t = art.get("type")
    if t == "map":
        _render_map(art)
    elif t == "flow_map":
        _render_flow_map(art)
    elif t == "table":
        _render_table(art)
    elif t == "chart":
        _render_chart(art)
    else:
        st.warning(f"Unknown artifact type: {t}")


def _render_map(art: dict) -> None:
    geojson = art.get("geojson", {})
    color_metric = art.get("color_metric")

    features = geojson.get("features", [])
    values = [f["properties"].get(color_metric, 0) for f in features] if color_metric else []
    vmin = min(values) if values else 0
    vmax = max(values) if values else 1
    denom = vmax - vmin if vmax > vmin else 1

    layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        get_fill_color=f"[255 * (properties.{color_metric} - {vmin}) / {denom}, 100, 50, 180]"
        if color_metric
        else [100, 150, 200, 180],
        get_line_color=[0, 0, 0],
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
    )

    bbox = art.get("bbox")
    if bbox and len(bbox) == 4:
        view_state = pdk.ViewState(
            longitude=(bbox[0] + bbox[2]) / 2,
            latitude=(bbox[1] + bbox[3]) / 2,
            zoom=12,
        )
    else:
        view_state = pdk.ViewState(longitude=69.6, latitude=40.85, zoom=12)

    tooltip_fields = art.get("tooltip_fields", [])
    tooltip_html = "<br/>".join(f"<b>{f}:</b> {{{f}}}" for f in tooltip_fields)

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"html": tooltip_html} if tooltip_html else None,
        map_style="light",
    )
    st.pydeck_chart(deck)

    legend = art.get("legend")
    if legend:
        st.caption(f"{legend.get('title', '')}: {legend.get('min', 0)} — {legend.get('max', 10)}")


def _render_flow_map(art: dict) -> None:
    flows = art.get("flows", [])
    if not flows:
        st.info("No flow data")
        return

    layer = pdk.Layer(
        "ArcLayer",
        data=flows,
        get_source_position="from",
        get_target_position="to",
        get_width="weight",
        get_source_color=[0, 128, 255],
        get_target_color=[255, 0, 128],
        pickable=True,
    )

    bbox = art.get("bbox")
    if bbox and len(bbox) == 4:
        view_state = pdk.ViewState(
            longitude=(bbox[0] + bbox[2]) / 2,
            latitude=(bbox[1] + bbox[3]) / 2,
            zoom=11,
        )
    else:
        view_state = pdk.ViewState(longitude=69.6, latitude=40.85, zoom=11)

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))


def _render_table(art: dict) -> None:
    title = art.get("title")
    if title:
        st.subheader(title)
    columns = art.get("columns", [])
    rows = art.get("rows", [])
    if columns and rows:
        df = pd.DataFrame(rows, columns=columns)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No table data")


def _render_chart(art: dict) -> None:
    title = art.get("title")
    if title:
        st.subheader(title)
    data = art.get("data", {})
    labels = data.get("labels", [])
    values = data.get("values", [])
    chart_type = art.get("chart_type", "bar")

    if labels and values:
        df = pd.DataFrame({"label": labels, "value": values}).set_index("label")
        if chart_type == "bar":
            st.bar_chart(df)
        elif chart_type == "line":
            st.line_chart(df)
        else:
            st.bar_chart(df)
    else:
        st.info("No chart data")
```

- [ ] **Step 2: Commit**

```bash
git add streamlit_app/artifacts.py
git commit -m "feat: Streamlit artifact renderers — map, table, chart"
```

---

## Task 22: Streamlit Chat UI

**Files:**
- Create: `streamlit_app/chat.py`

- [ ] **Step 1: Create `streamlit_app/chat.py`**

Per TZ:14.3 — chat with real-time tool progress.

```python
import streamlit as st

from streamlit_app.artifacts import render_artifact
from streamlit_app.client import SSEEvent


def render_chat() -> None:
    """Render chat history and handle new input."""
    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for art in msg.get("artifacts", []):
                render_artifact(art)

    user_input = st.chat_input("Спросите про геоданные...")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        status = st.status("Думаю...", expanded=True)
        text_placeholder = st.empty()
        text = ""
        artifacts = []
        trace_url = None

        for ev in st.session_state.client.stream_chat(
            [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        ):
            if ev.event == "trace_started":
                if isinstance(ev.data, dict):
                    trace_url = ev.data.get("langfuse_url")

            elif ev.event == "tool_started":
                if isinstance(ev.data, dict):
                    with status:
                        st.write(
                            f"**{ev.data.get('name', '?')}** — "
                            f"`{_summarize_args(ev.data.get('args', {}))}`"
                        )
                        status.update(label=f"Выполняю {ev.data.get('name', '')}...")

            elif ev.event == "tool_finished":
                if isinstance(ev.data, dict):
                    with status:
                        st.write(f"Готово за {ev.data.get('duration_ms', '?')}мс")

            elif ev.event == "tool_failed":
                if isinstance(ev.data, dict):
                    with status:
                        st.error(f"Ошибка: {ev.data.get('error', '?')}")

            elif ev.event == "artifact":
                if isinstance(ev.data, dict):
                    artifacts.append(ev.data)

            elif ev.event is None:
                # Standard OpenAI chunk
                if isinstance(ev.data, dict):
                    try:
                        delta = ev.data["choices"][0]["delta"].get("content", "")
                        if delta:
                            text += delta
                            text_placeholder.markdown(text + "...")
                    except (KeyError, IndexError):
                        pass

        text_placeholder.markdown(text)
        status.update(label="Готово", state="complete", expanded=False)

        for art in artifacts:
            render_artifact(art)

        if trace_url:
            st.caption(f"[Trace в Langfuse]({trace_url})")

        st.session_state.messages.append({
            "role": "assistant",
            "content": text,
            "artifacts": artifacts,
        })


def _summarize_args(args: dict) -> str:
    items = []
    for k, v in args.items():
        if isinstance(v, list) and len(v) > 5:
            items.append(f"{k}=[{len(v)} items]")
        else:
            items.append(f"{k}={v}")
    return ", ".join(items)
```

- [ ] **Step 2: Commit**

```bash
git add streamlit_app/chat.py
git commit -m "feat: Streamlit chat with tool progress"
```

---

## Task 23: Streamlit App Entry Point

**Files:**
- Create: `streamlit_app/app.py`

- [ ] **Step 1: Create `streamlit_app/app.py`**

Per TZ:14.1 and TZ:14.5 — main app with sidebar.

```python
import os

import streamlit as st

from streamlit_app.chat import render_chat
from streamlit_app.client import GeoInsightClient

st.set_page_config(page_title="GeoInsight Agent", layout="wide")
st.title("GeoInsight Agent")

# Sidebar (TZ:14.5)
with st.sidebar:
    backend_url = st.text_input(
        "Backend URL",
        value=os.environ.get("BACKEND_URL", "http://localhost:8080"),
    )

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

    show_raw = st.checkbox("Show raw SSE events", value=False)

# Init state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "client" not in st.session_state or st.session_state.get("_backend_url") != backend_url:
    st.session_state.client = GeoInsightClient(base_url=backend_url)
    st.session_state._backend_url = backend_url

render_chat()
```

- [ ] **Step 2: Commit**

```bash
git add streamlit_app/app.py
git commit -m "feat: Streamlit app entry point with sidebar"
```

---

## Task 24: Tests

**Files:**
- Create: `tests/test_sse.py`
- Create: `tests/test_artifacts.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Create `tests/test_sse.py`**

```python
import json

from backend.api.sse import sse_done, sse_event


def test_sse_event_standard():
    result = sse_event({"key": "value"})
    assert result == 'data: {"key": "value"}\n\n'


def test_sse_event_custom():
    result = sse_event({"key": "value"}, event="tool_started")
    assert result.startswith("event: tool_started\n")
    assert "data: " in result


def test_sse_done():
    assert sse_done() == "data: [DONE]\n\n"


def test_sse_event_unicode():
    result = sse_event({"text": "Привет"})
    data_line = result.strip().split("data: ")[1]
    parsed = json.loads(data_line)
    assert parsed["text"] == "Привет"
```

- [ ] **Step 2: Create `tests/test_artifacts.py`**

```python
from backend.api.schemas import ChartArtifact, MapArtifact, TableArtifact


def test_map_artifact_defaults():
    art = MapArtifact()
    assert art.type == "map"
    assert art.viz == "choropleth"
    assert art.geojson == {}


def test_table_artifact():
    art = TableArtifact(
        title="Test",
        columns=["a", "b"],
        rows=[[1, 2], [3, 4]],
    )
    assert art.type == "table"
    assert len(art.rows) == 2


def test_chart_artifact():
    art = ChartArtifact(
        chart_type="bar",
        title="Traffic",
        data={"labels": ["00:00", "01:00"], "values": [10, 20]},
    )
    assert art.type == "chart"
    assert art.data["values"] == [10, 20]
```

- [ ] **Step 3: Create `tests/test_tools.py`**

```python
from backend.tools.base import GeoContext, safe_args_preview


def test_geo_context_emit_artifact():
    ctx = GeoContext(trace_id="test-123")
    aid = ctx.emit_artifact({"type": "map", "geojson": {}})
    assert aid == "art_1"
    assert len(ctx.artifacts) == 1
    assert ctx.artifacts[0]["id"] == "art_1"


def test_geo_context_multiple_artifacts():
    ctx = GeoContext(trace_id="test-123")
    ctx.emit_artifact({"type": "map"})
    ctx.emit_artifact({"type": "table"})
    assert len(ctx.artifacts) == 2
    assert ctx.artifacts[1]["id"] == "art_2"


def test_safe_args_preview_truncates_list():
    result = safe_args_preview({"ids": list(range(20))})
    assert result["ids"] == "[20 items]"


def test_safe_args_preview_truncates_string():
    result = safe_args_preview({"text": "x" * 300})
    assert len(result["text"]) <= 203  # 200 + "..."


def test_safe_args_preview_normal():
    result = safe_args_preview({"city": "Olmaliq", "age": [1, 2]})
    assert result == {"city": "Olmaliq", "age": [1, 2]}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: SSE, artifacts, tools base"
```

---

## Task 25: Update STATUS.md and Finalize

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Update `STATUS.md`**

Mark all stages as implemented. Update with the current state.

- [ ] **Step 2: Run lint and format**

```bash
uv run ruff format .
uv run ruff check --fix .
```

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: lint, format, update status"
```

---

## Verification Plan

After all tasks are complete, verify end-to-end:

1. **Infrastructure:** `docker compose up -d` starts Postgres and Langfuse without errors
2. **Data:** `uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset` loads 162 zones, ~87k demographics, ~745k dynamics
3. **Backend:** `uv run uvicorn backend.main:app --port 8080` starts without errors
4. **Health:** `curl http://localhost:8080/healthz` returns postgres=ok (vllm may be degraded if not running)
5. **SSE stream:** `curl -N -X POST http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"Найди зоны для молодёжи в Олмалике"}],"stream":true}'` returns SSE events including tool_started, tool_finished, artifact, and text content
6. **Streamlit:** `uv run streamlit run streamlit_app/app.py` opens UI, chat works, maps render
7. **Tests:** `uv run pytest tests/ -v` all pass
8. **Lint:** `uv run ruff check .` no errors

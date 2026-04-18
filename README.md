# GeoInsight Agent

AI assistant that turns telecom geodata into business analytics via chat.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker & Docker Compose
- vLLM running externally with gpt-oss-120b:

```bash
vllm serve gpt-oss-120b \
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
- Langfuse v3 on port 3030

### 3. Setup Langfuse

Open http://localhost:3030, log in with `admin@local.dev` / `admin123`.
Create API keys in project settings, add to `.env`:

```bash
cp .env.example .env
# Edit .env — fill LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY
```

### 4. Load demo data

```bash
psql postgresql://geoinsight:geoinsight@localhost:5433/geoinsight \
  -f backend/db/migrations/001_schema.sql
psql postgresql://geoinsight:geoinsight@localhost:5433/geoinsight \
  -f backend/db/migrations/002_indices.sql

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

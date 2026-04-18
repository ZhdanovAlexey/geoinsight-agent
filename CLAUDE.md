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
- TZ (`docs/geoinsight-agent-tz.md`) is source of truth on conflicts

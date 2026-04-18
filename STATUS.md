# GeoInsight Agent — Status

## Current Stage: MVP Complete

### Stage 0 — Infrastructure [DONE]
- [x] Project scaffolding (pyproject.toml, config, gitignore)
- [x] Docker Compose (Postgres:5433 + Langfuse:3030)
- [x] Scripts (start_backend, start_streamlit, reset_db)
- [x] README.md, CLAUDE.md

### Stage 1 — DB & Data [DONE]
- [x] SQL migrations (001_schema, 002_indices)
- [x] ETL script (load_demo.py)
- [x] DB engine (async SQLAlchemy)
- [x] DB queries (find_zones, zone_demographics, zone_traffic)
- [x] Data loaded: 162 zones, 87k demographics, 745k dynamics

### Stage 2 — Backend [DONE]
- [x] FastAPI app with lifespan
- [x] /healthz endpoint
- [x] /v1/chat/completions (stream + non-stream)
- [x] structlog configuration
- [x] API schemas (request, response, artifacts)
- [x] SSE formatter

### Stage 3 — Agent + Tools [DONE]
- [x] Langfuse observability via OTEL
- [x] System prompt with field encodings
- [x] Agent definition (GeoInsight, 7 tools)
- [x] GeoContext + emit_artifact
- [x] find_zones (full)
- [x] zone_demographics (full)
- [x] zone_traffic (full)
- [x] 4 stub tools (home_work_flow, catchment_area, compare_zones, roaming_analysis)
- [x] Runner: Agents SDK stream -> SSE mapper

### Stage 4 — Streamlit UI [DONE]
- [x] SSE client (httpx streaming)
- [x] Artifact renderers (pydeck map, table, bar/line chart, flow map)
- [x] Chat component with tool progress
- [x] App entry point with sidebar

### Stage 5 — Tests [DONE]
- [x] test_sse (4 tests)
- [x] test_artifacts (3 tests)
- [x] test_tools (5 tests)
- [x] ruff format + check clean

### Environment Notes
- Postgres port: 5433 (5432 occupied)
- Langfuse port: 3030 (3000 occupied)
- vLLM: http://109.230.162.92:44334/v1
- Model: gpt-oss-120b
- Python: 3.14.3 (>=3.12 required)
- GitHub: https://github.com/ZhdanovAlexey/geoinsight-agent

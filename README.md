# GeoInsight Agent

AI-аналитик геоданных мобильного оператора. Превращает телеком-данные в бизнес-аналитику через чат: ритейл, недвижимость, реклама, транспорт.

Агент анализирует зоны ~250x250м с демографией (возраст, доход, пол), почасовым трафиком и пространственными связями. Отвечает на вопросы вроде "Где открыть кофейню для аудитории 25-35?" или "Сколько людей в радиусе 2 км от центра города?".

## Architecture

```
                         ┌─────────────────────────────────────┐
                         │           Streamlit UI              │
                         │   (чат, карты, графики, таблицы)    │
                         └──────────────┬──────────────────────┘
                                        │ HTTP / SSE
                         ┌──────────────▼──────────────────────┐
                         │         FastAPI Backend             │
                         │                                     │
                         │   OpenAI Agents SDK (agent loop)    │
                         │   ┌────────────────────────────┐    │
                         │   │        8 Tools             │    │
                         │   │  find_zones, demographics, │    │
                         │   │  traffic, geocode, compare,│    │
                         │   │  catchment, home_work, roam│    │
                         │   └─────────────┬──────────────┘    │
                         └─────────────────┼───────────────────┘
                              ┌────────────┼────────────┐
                              ▼            ▼            ▼
                         ┌────────┐  ┌──────────┐  ┌──────────┐
                         │  vLLM  │  │ Postgres │  │ Langfuse │
                         │  (LLM) │  │ + PostGIS│  │   (obs)  │
                         └────────┘  └──────────┘  └──────────┘
```

**Stack:** Python 3.12+, FastAPI, OpenAI Agents SDK, SQLAlchemy Core, PostGIS, Streamlit, pydeck

## Tools

| Tool | Description |
|------|-------------|
| `find_zones` | Поиск зон по демографическим фильтрам (возраст, доход, пол). Карта + рейтинг |
| `zone_demographics` | Детальный профиль зоны: распределение по доходу, возрасту, полу |
| `zone_traffic` | Почасовая динамика посещаемости зоны. График по часам |
| `geocode_zone` | Поиск ближайшей зоны по адресу/улице через OpenStreetMap Nominatim |
| `catchment_area` | Анализ зоны охвата: все зоны в заданном радиусе с населением |
| `compare_zones` | Сравнительная таблица 2-5 зон по демографии и пиковому трафику |
| `home_work_flow` | Потоки дом-работа *(в разработке)* |
| `roaming_analysis` | Анализ роуминга/туристов *(в разработке)* |

Агент сам выбирает инструменты и комбинирует их в цепочки. Например: `geocode_zone` -> `catchment_area` -> `compare_zones` для вопроса "Сколько людей живёт рядом с базаром?".

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose
- vLLM с моделью gpt-oss-120b (внешний сервер)

### 1. Install

```bash
uv sync --all-extras
cp .env.example .env
# Edit .env — fill LLM endpoint, Langfuse keys
```

### 2. Infrastructure

```bash
docker compose up -d
```

Services: PostgreSQL + PostGIS (5433), Langfuse v3 (3030), ClickHouse, Redis, MinIO.

### 3. Langfuse setup

Open http://localhost:3030, login: `admin@local.dev` / `admin123`.
Create project, copy API keys into `.env`.

### 4. Load data

```bash
psql postgresql://geoinsight:geoinsight@localhost:5433/geoinsight \
  -f backend/db/migrations/001_schema.sql
psql postgresql://geoinsight:geoinsight@localhost:5433/geoinsight \
  -f backend/db/migrations/002_indices.sql

uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset
```

### 5. Run

```bash
# Terminal 1: backend
./scripts/start_backend.sh

# Terminal 2: UI
./scripts/start_streamlit.sh
```

Open http://localhost:8501

## Data Model

```
zones                    zone_demographics           zone_dynamics
┌─────────────────┐      ┌──────────────────┐       ┌──────────────────┐
│ zid (PK)        │◄────│ zid (FK)          │       │ zid (FK)         │
│ city            │      │ income (0-6)      │       │ ts (timestamp)   │
│ geom (Polygon)  │      │ age (0-5)         │       │ income, age, gen │
│ centroid (Point)│      │ gender (0-1)      │       │ cnt              │
└─────────────────┘      │ cnt               │       └──────────────────┘
                         │ home_zid, job_zid │
                         └──────────────────┘
```

**Города:** Алмалык (162 зоны, ~63k аудитория), Ташкент

**Кодировки:**
- income: 0=unknown, 1=low ... 6=very high
- age: 0=<18, 1=18-25, 2=26-35, 3=36-45, 4=46-60, 5=>60
- gender: 0=male, 1=female

## API

OpenAI-compatible endpoint:

```bash
curl -N http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "geoinsight-v1",
    "messages": [{"role": "user", "content": "Где молодёжи больше всего в Алмалыке?"}],
    "stream": true
  }'
```

SSE events: `trace_started`, `tool_call` (name + args + output), `artifact` (map/table/chart), content delta, `[DONE]`.

Health check: `GET /healthz`

## Project Structure

```
backend/
  agent/           # Agent definition, system prompt, runner
  api/             # Schemas, SSE helpers
  db/              # Engine, queries (SQLAlchemy Core), migrations
  tools/           # 8 tool implementations
  config.py        # Settings (pydantic-settings)
  observability.py # Langfuse integration
  main.py          # FastAPI app

streamlit_app/
  app.py           # Entry point, sidebar, suggestions
  chat.py          # Chat rendering, SSE consumption
  client.py        # HTTP/SSE client
  artifacts.py     # Map (pydeck), table, chart renderers

data/              # ETL scripts
scripts/           # start_backend.sh, start_streamlit.sh, reset_db.sh
tests/             # pytest-asyncio tests
```

## Development

```bash
uv run ruff format .         # Format
uv run ruff check --fix .    # Lint
uv run pytest -v             # Tests
```

## License

MIT

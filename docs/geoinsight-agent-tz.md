# GeoInsight Agent — Техническое задание

**Адресат:** Claude Code (Opus 4.6) для локальной разработки
**Цель:** реализовать MVP агента, который превращает телеком-геоданные в бизнес-аналитику через чат
**Режим разработки:** локально → потом push на GitHub

---

## 1. Контекст проекта

GeoInsight Agent — AI-ассистент для B2B-клиентов мобильного оператора (ритейл, недвижимость, реклама, транспорт, туризм). Принимает бизнес-вопрос на естественном языке, через tool-calling вытаскивает данные из PostgreSQL+PostGIS, возвращает текстовый ответ + интерактивную карту/таблицу.

Полная спецификация продукта — в файле `docs/2026-04-17-geoinsight-agent-design.md` (предполагается, что он будет положен в репозиторий).

**Этот документ описывает только техническую реализацию MVP**, не повторяя бизнес-контекст. Если возникает противоречие между этим ТЗ и спецификацией продукта — следовать этому ТЗ.

---

## 2. Технологический стек

| Слой | Технология | Версия (минимум) |
|---|---|---|
| LLM | `openai/gpt-oss-120b` через **vLLM** | — (уже развёрнут отдельно) |
| Агентный фреймворк | **OpenAI Agents SDK** (Python) | latest stable |
| HTTP API | **FastAPI** + Uvicorn | latest |
| Стриминг | **SSE** (Server-Sent Events) поверх FastAPI | — |
| БД | **PostgreSQL + PostGIS** | PG 16+, PostGIS 3.4+ |
| ORM/SQL | **SQLAlchemy 2.x** + `psycopg[binary]` | — |
| Demo UI | **Streamlit** + **pydeck** | latest |
| Логирование | **structlog** (JSON) | — |
| Observability | **Langfuse** (self-hosted) | latest |
| Конфиг | **pydantic-settings** + `.env` | — |
| Менеджер пакетов | **uv** | latest |
| Python | **3.12** | — |
| Контейнеризация (для Postgres + Langfuse) | **Docker Compose** | — |

---

## 3. Высокоуровневая архитектура

```
┌─────────────────────┐     HTTP/SSE      ┌───────────────────────────────┐
│  Streamlit UI       │ ◄────────────────► │  FastAPI backend              │
│  (демо-клиент)      │                    │                               │
│  - st.chat_message  │                    │  POST /v1/chat/completions    │
│  - st.status        │                    │  GET  /healthz                │
│  - pydeck карта     │                    │                               │
└─────────────────────┘                    │  ┌─────────────────────────┐  │
                                           │  │ OpenAI Agents SDK       │  │
                                           │  │ Runner.run_streamed()   │  │
                                           │  └────────┬────────────────┘  │
                                           │           │                   │
                                           │           ▼                   │
                                           │  ┌─────────────────────────┐  │
                                           │  │ Tools layer (8 шт)      │  │
                                           │  │ + ctx.emit_artifact()   │  │
                                           │  └────────┬────────────────┘  │
                                           │           │                   │
                                           └───────────┼───────────────────┘
                                                       │
                  ┌────────────────────────────────────┼─────────────────┐
                  │                                    │                 │
                  ▼                                    ▼                 ▼
          ┌─────────────────┐                ┌──────────────┐    ┌──────────────┐
          │ vLLM            │                │ PostgreSQL   │    │ Langfuse     │
          │ gpt-oss-120b    │                │ + PostGIS    │    │ (self-hosted)│
          │ :8000/v1        │                │ :5432        │    │ :3000        │
          └─────────────────┘                └──────────────┘    └──────────────┘
```

**Принципы:**
- Streamlit **не содержит** логики агента — общается с бэкендом через HTTP/SSE.
- Backend выставляет **OpenAI-совместимый** `/v1/chat/completions` endpoint, поэтому в продакшене UI можно заменить на любой совместимый клиент.
- vLLM считается внешней зависимостью — конфигурируется через env, не поднимается этим репозиторием.
- Langfuse и Postgres поднимаются через `docker-compose.yml` для удобства локальной разработки.

---

## 4. Структура репозитория

```
geoinsight-agent/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── docker-compose.yml              # Postgres+PostGIS + Langfuse
├── docs/
│   └── 2026-04-17-geoinsight-agent-design.md   # бизнес-спецификация
│
├── backend/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, эндпоинты
│   ├── config.py                   # pydantic-settings
│   ├── logging_config.py           # structlog setup
│   ├── observability.py            # Langfuse + OTEL
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── geo_agent.py            # Agent definition
│   │   ├── system_prompt.py        # системный промпт + кодировки полей
│   │   └── runner.py               # обёртка Runner.run_streamed + SSE-маппер
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                 # ToolContext, emit_artifact, общие хелперы
│   │   ├── zone_demographics.py
│   │   ├── zone_traffic.py
│   │   ├── find_zones.py
│   │   ├── home_work_flow.py
│   │   ├── catchment_area.py
│   │   ├── compare_zones.py
│   │   └── roaming_analysis.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── schemas.py              # ChatCompletionRequest/Response, Artifact, etc.
│   │   └── sse.py                  # SSE-форматтер
│   │
│   └── db/
│       ├── __init__.py
│       ├── engine.py               # SQLAlchemy engine
│       ├── queries.py              # SQL-запросы под тулы
│       └── migrations/
│           ├── 001_schema.sql
│           └── 002_indices.sql
│
├── streamlit_app/
│   ├── app.py                      # точка входа streamlit
│   ├── chat.py                     # рендеринг чата + SSE-парсер
│   ├── artifacts.py                # рендеры артефактов (pydeck, dataframe)
│   └── client.py                   # httpx-клиент к /v1/chat/completions
│
├── data/
│   ├── README.md                   # инструкция как загрузить демо-датасет
│   └── load_demo.py                # ETL-скрипт: CSV → PostGIS
│
├── tests/
│   ├── test_tools.py
│   ├── test_sse.py
│   └── test_artifacts.py
│
└── scripts/
    ├── start_backend.sh
    ├── start_streamlit.sh
    └── reset_db.sh
```

---

## 5. Окружение и зависимости

### 5.1. `pyproject.toml` — ключевые зависимости

```toml
[project]
name = "geoinsight-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "openai-agents",            # OpenAI Agents SDK
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
    "opentelemetry-exporter-otlp",
]

[project.optional-dependencies]
demo = ["streamlit", "pydeck", "pandas"]
dev = ["pytest", "pytest-asyncio", "ruff", "mypy"]
```

### 5.2. `.env.example`

```dotenv
# vLLM (gpt-oss-120b уже развёрнут)
LLM_BASE_URL=http://localhost:8000/v1
LLM_API_KEY=EMPTY
LLM_MODEL=openai/gpt-oss-120b
LLM_REASONING_EFFORT=medium

# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8080
LOG_LEVEL=INFO
LOG_FORMAT=json                  # json | console

# Postgres
POSTGRES_DSN=postgresql+psycopg://geoinsight:geoinsight@localhost:5432/geoinsight

# Langfuse (заполнить после первого запуска docker-compose и создания проекта в UI)
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_ENABLED=true

# Streamlit
BACKEND_URL=http://localhost:8080
```

### 5.3. `docker-compose.yml`

Должен поднимать:
- `postgis/postgis:16-3.4` на порту 5432
- Langfuse v3 (см. https://langfuse.com/self-hosting/docker-compose) — обычно это `langfuse-web`, `langfuse-worker`, `clickhouse`, `minio`, `redis`, `postgres` (отдельный для Langfuse, **не использовать тот же**, что для приложения).

Бэкенд и Streamlit запускаются **локально** (не в Docker), чтобы Claude Code мог быстро итерировать.

---

## 6. Подключение к vLLM (gpt-oss-120b)

vLLM считается **уже запущенным внешне** со следующими ключевыми флагами (зафиксировать в `README.md` как требование к окружению):

```bash
vllm serve openai/gpt-oss-120b \
  --tensor-parallel-size 2 \
  --tool-call-parser openai \
  --enable-auto-tool-choice \
  --reasoning-parser openai_gptoss \
  --max-model-len 131072
```

В коде Agents SDK перенаправляется на vLLM так:

```python
# backend/agent/geo_agent.py
from agents import Agent, set_default_openai_client
from openai import AsyncOpenAI
from backend.config import settings

set_default_openai_client(AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
))
```

**Reasoning content** (chain-of-thought от gpt-oss) логируется в Langfuse и structured logs, но **не отдаётся** клиенту в `/v1/chat/completions`.

---

## 7. Контракт `/v1/chat/completions`

### 7.1. Запрос

Стандартный OpenAI Chat Completions request:

```json
{
  "model": "geoinsight-v1",
  "messages": [
    {"role": "user", "content": "Где открыть кофейню для аудитории 25-35?"}
  ],
  "stream": true
}
```

Поддерживаемые поля: `model` (игнорируется, всегда используется gpt-oss-120b), `messages`, `stream`. Остальные принимаются, но не обязательно учитываются в MVP.

### 7.2. Ответ при `stream: false`

Стандартный `ChatCompletion`-объект с дополнительным полем `artifacts` на верхнем уровне:

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1745000000,
  "model": "geoinsight-v1",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Нашёл 12 зон. Топ-5 — на карте.",
      "tool_calls": [...]
    },
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
  "trace_id": "lf-trace-uuid",
  "artifacts": [
    {
      "id": "art_1",
      "type": "map",
      "viz": "choropleth",
      "geojson": {"type": "FeatureCollection", "features": [...]},
      "color_metric": "score",
      "legend": {"title": "Рейтинг", "min": 0, "max": 10},
      "bbox": [69.5, 40.8, 69.8, 41.0]
    },
    {
      "id": "art_2",
      "type": "table",
      "title": "Топ-5 зон",
      "columns": ["zid", "людей/день", "18-35 лет", "рейтинг"],
      "rows": [[4277303, 8450, "62%", 9.2]]
    }
  ]
}
```

### 7.3. Ответ при `stream: true` (SSE)

**Стандартные** OpenAI SSE-чанки идут как `data: {...}` без `event:` (для совместимости с `openai` Python SDK).

**Кастомные** события идут с `event:` префиксом — стандартные клиенты их проигнорируют.

```
data: {"id":"...","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant"}}]}

event: trace_started
data: {"trace_id":"lf-trace-uuid","langfuse_url":"http://localhost:3000/trace/..."}

event: tool_started
data: {"call_id":"call_1","name":"find_zones","args":{"age":[1,2],"income":[2,3,4]}}

event: tool_finished
data: {"call_id":"call_1","duration_ms":2340,"rows":127,"status":"ok"}

event: artifact
data: {"id":"art_1","type":"map","viz":"choropleth","geojson":{...},...}

data: {"choices":[{"delta":{"content":"Нашёл "}}]}
data: {"choices":[{"delta":{"content":"12 зон..."}}]}
data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

**Кастомные event types (полный перечень):**

| event | payload | когда отправлять |
|---|---|---|
| `trace_started` | `{trace_id, langfuse_url?}` | в самом начале, после создания Langfuse-трейса |
| `tool_started` | `{call_id, name, args}` | перед вызовом тула |
| `tool_progress` | `{call_id, progress: 0..1, message?}` | опционально, для долгих тулов |
| `tool_finished` | `{call_id, duration_ms, status, rows?, output_preview?}` | после успешного завершения |
| `tool_failed` | `{call_id, duration_ms, error, error_type}` | при исключении в туле |
| `artifact` | объект Artifact (см. раздел 8) | сразу после `tool_finished`, который этот артефакт породил |

### 7.4. Endpoint `/healthz`

Простой `200 OK` с проверкой:
- доступности Postgres (`SELECT 1`)
- доступности vLLM (`GET {LLM_BASE_URL}/models`)

---

## 8. Контракт UI-артефактов

```python
# backend/api/schemas.py
from typing import Literal, Any
from pydantic import BaseModel

class MapArtifact(BaseModel):
    id: str
    type: Literal["map"] = "map"
    viz: Literal["choropleth", "heatmap", "points"]
    geojson: dict
    color_metric: str | None = None
    legend: dict | None = None
    bbox: list[float] | None = None      # [lon_min, lat_min, lon_max, lat_max]
    tooltip_fields: list[str] = []

class FlowMapArtifact(BaseModel):
    id: str
    type: Literal["flow_map"] = "flow_map"
    flows: list[dict]                     # [{from:[lon,lat], to:[lon,lat], weight, ...}]
    bbox: list[float] | None = None

class TableArtifact(BaseModel):
    id: str
    type: Literal["table"] = "table"
    title: str | None = None
    columns: list[str]
    rows: list[list[Any]]

class ChartArtifact(BaseModel):
    id: str
    type: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "pie"]
    title: str | None = None
    data: dict                            # формат под выбранный chart_type

Artifact = MapArtifact | FlowMapArtifact | TableArtifact | ChartArtifact
```

**Принцип разделения данных:**
- В `tool_call_output` (что видит модель) идёт **компактный summary**: количество, top-N, агрегаты. Без полных полигонов.
- В `artifact` (что видит UI) идёт **полная геометрия / все строки**.

Это экономит контекст модели и ускоряет повторные turns.

---

## 9. Реализация Tools

### 9.1. Базовый паттерн

```python
# backend/tools/base.py
from agents import function_tool, RunContextWrapper
from dataclasses import dataclass, field

@dataclass
class GeoContext:
    """Контекст, протаскиваемый через Runner."""
    trace_id: str
    artifacts: list[dict] = field(default_factory=list)
    
    def emit_artifact(self, artifact: dict) -> str:
        artifact_id = f"art_{len(self.artifacts) + 1}"
        artifact["id"] = artifact_id
        self.artifacts.append(artifact)
        return artifact_id
```

### 9.2. Перечень тулов для MVP

**Реализовать в полном объёме (для приёмки MVP):**

1. **`zone_demographics(zid, filters?) -> dict`**
   - вход: `zid: int`, опц. `income: list[int]`, `age: list[int]`, `gender: list[int]`
   - выход для модели: `{total: int, by_income: {...}, by_age: {...}, by_gender: {...}, home_count: int, job_count: int}`
   - артефакт: `TableArtifact` с распределением

2. **`find_zones(criteria) -> dict`**
   - вход: `city: str`, `age: list[int]?`, `income: list[int]?`, `gender: list[int]?`, `min_total: int?`, `top_n: int = 20`
   - выход для модели: `{count, top: [{zid, score, total, age_match_pct, income_match_pct}]}`
   - артефакт: `MapArtifact` (choropleth по score)

3. **`zone_traffic(zid, hours?) -> dict`**
   - вход: `zid: int`, `hours: list[int]?` (0..23)
   - выход для модели: `{by_hour: {0: count, 1: count, ...}, peak_hour, peak_value}`
   - артефакт: `ChartArtifact` (bar chart по часам)

**Реализовать как stub (возвращают `{"status": "not_implemented"}`):**

4. `home_work_flow`
5. `catchment_area`
6. `compare_zones`
7. `roaming_analysis`

Stub нужны, чтобы system prompt описывал полный набор возможностей и модель могла планировать многошаговые сценарии — позже эти тулы заполнят данными по мере готовности.

### 9.3. Пример полной реализации `find_zones`

```python
# backend/tools/find_zones.py
from agents import function_tool, RunContextWrapper
from backend.tools.base import GeoContext
from backend.db.queries import query_find_zones
import structlog
import time

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
    """
    Найти зоны (~250x250м), удовлетворяющие критериям демографии.
    
    Args:
        city: название города (например, "Olmaliq", "Tashkent")
        age: список возрастных групп 0-5 (см. system prompt)
        income: список категорий дохода 0-6
        gender: 0 (м) или 1 (ж)
        min_total: минимум суммарного населения зоны
        top_n: количество лучших зон в результате
    
    Returns:
        Сводка для LLM (не содержит полигонов).
    """
    t0 = time.monotonic()
    zones = await query_find_zones(
        city=city, age=age, income=income, gender=gender,
        min_total=min_total, top_n=top_n,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    
    log.info("tool.find_zones.query_done",
             trace_id=ctx.context.trace_id,
             rows=len(zones), duration_ms=duration_ms)
    
    # Артефакт для UI — полный GeoJSON
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
                        "zid": z.zid, "score": z.score,
                        "total": z.total,
                    },
                } for z in zones
            ],
        },
        "color_metric": "score",
        "legend": {"title": "Рейтинг зоны", "min": 0, "max": 10},
        "bbox": _calc_bbox(zones),
        "tooltip_fields": ["zid", "score", "total"],
    })
    
    # Сводка для модели — без геометрии
    return {
        "count": len(zones),
        "top": [
            {"zid": z.zid, "score": round(z.score, 2),
             "total": z.total} for z in zones[:5]
        ],
        "summary": f"Найдено {len(zones)} зон в {city}",
    }
```

### 9.4. Соглашения по тулам

- Все тулы **async**.
- Все тулы принимают `ctx: RunContextWrapper[GeoContext]` первым аргументом.
- Все тулы пишут `structlog`-события с `trace_id`, `tool`, `duration_ms`, `rows`/`status`.
- Все тулы имеют **детальный docstring** — он используется как описание тула для модели.
- Параметры — простые типы (`int`, `str`, `list[int]`). Большие массивы (>100 элементов) **не передавать** через arguments — для этого делать reference-by-id.

---

## 10. System prompt

Файл: `backend/agent/system_prompt.py`

Содержит:
1. Роль агента и стиль ответов (на русском, бизнес-фокус, кратко).
2. Описание доступных данных (зоны, демография, динамика, траектории).
3. **Кодировки полей** (критично!):
   - `income`: 0=неизвестно, 1=низкий, 2=ниже среднего, 3=средний, 4=выше среднего, 5=высокий, 6=очень высокий *(точные категории согласовать; для MVP использовать эту схему)*
   - `age`: 0=<18, 1=18-25, 2=26-35, 3=36-45, 4=46-60, 5=>60
   - `gender`: 0=мужской, 1=женский
4. Перечень доступных городов (для MVP: `Olmaliq`, `Tashkent`).
5. Правила выбора тулов (когда использовать `find_zones` vs `zone_demographics` и т.д.).
6. Правило: **никогда не выдумывать zid'ы** — только те, что вернулись из тулов.
7. Правило: ответ всегда содержит краткий вывод + предложение углубить анализ.

Промпт хранить как многострочную f-string или загружать из `prompts/geoagent_system.md` для удобства редактирования.

---

## 11. Логирование (structlog)

### 11.1. Конфигурация

```python
# backend/logging_config.py
import structlog
import logging
from backend.config import settings

def configure_logging():
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    
    processors = [
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
            getattr(logging, settings.log_level)
        ),
        cache_logger_on_first_use=True,
    )
```

### 11.2. Обязательные события

| Event name | Когда | Поля |
|---|---|---|
| `request.received` | вход в `/v1/chat/completions` | `trace_id`, `messages_count`, `last_user_msg_preview` |
| `agent.started` | перед `Runner.run_streamed` | `trace_id`, `model` |
| `tool.started` | в Agents SDK callback | `trace_id`, `tool`, `args_preview` |
| `tool.finished` | после тула | `trace_id`, `tool`, `duration_ms`, `rows` |
| `tool.failed` | в except | `trace_id`, `tool`, `error`, `error_type` |
| `artifact.emitted` | при `emit_artifact` | `trace_id`, `artifact_id`, `artifact_type` |
| `agent.finished` | конец run | `trace_id`, `total_duration_ms`, `tools_called`, `artifacts_count` |
| `request.failed` | глобальный exception handler | `trace_id`, `error`, `error_type` |

### 11.3. Trace ID

В каждом запросе:
1. Генерируется UUID `trace_id` (или берётся из `X-Trace-Id` request header, если есть).
2. Кладётся в `structlog.contextvars` → автоматически попадает во все логи.
3. Возвращается в response (`trace_id` поле в JSON и `X-Trace-Id` header).
4. Используется как Langfuse `trace_id`.

### 11.4. Маскирование

В `tool.started` логировать `args_preview` через хелпер `safe_args_preview()`, который обрезает массивы > 10 элементов и строки > 200 символов. **Никаких** идентификаторов абонентов (`code` из траекторий) в логи **на уровне INFO** не попадает.

---

## 12. Langfuse (observability) — обязательно

### 12.1. Развёртывание

В `docker-compose.yml` поднимать Langfuse v3 self-hosted (см. https://langfuse.com/self-hosting/docker-compose).

После первого запуска:
1. Открыть `http://localhost:3000`.
2. Создать аккаунт + проект `geoinsight-dev`.
3. Сгенерировать API keys → положить в `.env`.

В `README.md` описать эту последовательность.

### 12.2. Интеграция с OpenAI Agents SDK

OpenAI Agents SDK эмитит OpenTelemetry-трейсы. Langfuse v3 принимает OTLP. Конфигурация:

```python
# backend/observability.py
import os
import base64
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import trace
from backend.config import settings

def init_langfuse():
    if not settings.langfuse_enabled:
        return
    
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
```

Вызов `init_langfuse()` — в `lifespan` FastAPI приложения.

### 12.3. Что должно попадать в Langfuse

- **Каждый HTTP-запрос** = 1 trace.
- Внутри trace — span'ы:
  - `agent.run` (root span)
  - `llm.completion` (вызов vLLM, с input/output, токенами)
  - `tool.{name}` (каждый вызов тула, с args и output)
- **reasoning_content** модели (из gpt-oss harmony) сохранять как metadata span'а `llm.completion`.
- В trace metadata: `messages_count`, `tools_called`, `artifacts_count`, `total_duration_ms`.

### 12.4. Связь с пользовательским UI

Поле `trace_id` в ответе `/v1/chat/completions` = Langfuse trace ID. URL вида `{LANGFUSE_HOST}/trace/{trace_id}` отдавать в `event: trace_started` SSE-событии. Streamlit показывает «🔍 Trace в Langfuse» с этой ссылкой — для дебага во время демо.

### 12.5. Fallback при недоступности

Если `LANGFUSE_ENABLED=false` или Langfuse недоступен — приложение **не падает**, продолжает работать с одними structlog-логами. Ошибки экспорта OTEL — только в `WARNING` лог.

---

## 13. База данных

### 13.1. Схема (`backend/db/migrations/001_schema.sql`)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

-- Зоны (полигоны 250x250м)
CREATE TABLE zones (
    zid           BIGINT PRIMARY KEY,
    city          TEXT NOT NULL,
    geom          GEOMETRY(Polygon, 4326) NOT NULL,
    centroid      GEOMETRY(Point, 4326) GENERATED ALWAYS AS (ST_Centroid(geom)) STORED
);

-- Демография зон (агрегаты)
CREATE TABLE zone_demographics (
    zid       BIGINT NOT NULL REFERENCES zones(zid),
    income    SMALLINT NOT NULL,         -- 0..6
    age       SMALLINT NOT NULL,         -- 0..5
    gender    SMALLINT NOT NULL,         -- 0/1
    cnt       INTEGER NOT NULL,
    home_zid  BIGINT,
    job_zid   BIGINT,
    PRIMARY KEY (zid, income, age, gender, COALESCE(home_zid, 0), COALESCE(job_zid, 0))
);

-- Динамика зон (с временной осью)
CREATE TABLE zone_dynamics (
    zid       BIGINT NOT NULL REFERENCES zones(zid),
    ts        TIMESTAMPTZ NOT NULL,
    income    SMALLINT NOT NULL,
    age       SMALLINT NOT NULL,
    gender    SMALLINT NOT NULL,
    cnt       INTEGER NOT NULL
);

-- Траектории (для MVP — опционально, нужно для home_work_flow и roaming_analysis)
CREATE TABLE trajectories (
    code         TEXT NOT NULL,
    age_group    TEXT,                    -- "18-25", "26-35"
    home_zid     BIGINT,
    job_zid      BIGINT,
    hourly_zids  JSONB,                   -- {"00": zid, "01": zid, ...}
    roaming_type TEXT,
    country_name TEXT
);
```

### 13.2. Индексы (`002_indices.sql`)

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

### 13.3. ETL (`data/load_demo.py`)

Скрипт, читающий CSV из спецификации (`dim_zid_town_*.csv`, `geo_*_cnt.csv`, `geo_*_dyn_all.csv`, `tav_geo_*.csv`) и заливающий в Postgres. WKT-полигоны → `ST_GeomFromText`.

Запуск: `uv run python data/load_demo.py --city Olmaliq --data-dir ./data/raw`.

Файлы CSV в репозиторий **не коммитить** (добавить в `.gitignore`). В `data/README.md` описать, откуда их получить.

### 13.4. Запросы (`backend/db/queries.py`)

Все запросы — через SQLAlchemy Core (не ORM, проще для аналитических SELECT'ов с JOIN'ами и агрегатами). Возвращают `dataclass`-объекты.

**Важно для `find_zones`:** `geometry` возвращается уже как GeoJSON (`ST_AsGeoJSON(geom)::json AS geometry_geojson`), не как WKT/WKB.

---

## 14. Streamlit UI (демо-клиент)

### 14.1. Структура

`streamlit_app/app.py` — точка входа:

```python
import streamlit as st
from streamlit_app.chat import render_chat
from streamlit_app.client import GeoInsightClient

st.set_page_config(page_title="GeoInsight Agent", layout="wide")
st.title("🗺️ GeoInsight Agent — демо")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "client" not in st.session_state:
    st.session_state.client = GeoInsightClient()

render_chat()
```

### 14.2. SSE-парсер (`streamlit_app/client.py`)

```python
import httpx
import json
from typing import Iterator
from backend.config import settings  # или дублировать env-чтение

class SSEEvent:
    def __init__(self, event: str | None, data: dict | str):
        self.event = event
        self.data = data

class GeoInsightClient:
    def __init__(self):
        self.base_url = settings.backend_url
    
    def stream_chat(self, messages: list[dict]) -> Iterator[SSEEvent]:
        with httpx.stream(
            "POST", f"{self.base_url}/v1/chat/completions",
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
                    yield SSEEvent(event_type, data)
                    event_type = None
```

### 14.3. Чат с прогрессом (`streamlit_app/chat.py`)

```python
import streamlit as st
from streamlit_app.client import SSEEvent
from streamlit_app.artifacts import render_artifact

def render_chat():
    # история
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
        status = st.status("🤔 Думаю...", expanded=True)
        text_placeholder = st.empty()
        text = ""
        artifacts = []
        trace_url = None
        tool_starts = {}
        
        for ev in st.session_state.client.stream_chat(
            [m for m in st.session_state.messages if m["role"] != "system"]
        ):
            if ev.event == "trace_started":
                trace_url = ev.data.get("langfuse_url")
            
            elif ev.event == "tool_started":
                call_id = ev.data["call_id"]
                tool_starts[call_id] = ev.data
                with status:
                    st.write(
                        f"🔧 **{ev.data['name']}** — "
                        f"`{_summarize_args(ev.data['args'])}`"
                    )
                    status.update(label=f"⚙️ Выполняю {ev.data['name']}...")
            
            elif ev.event == "tool_finished":
                with status:
                    rows = ev.data.get("rows", "?")
                    st.write(f"✓ готово за {ev.data['duration_ms']}мс, {rows} записей")
            
            elif ev.event == "tool_failed":
                with status:
                    st.error(f"✗ {ev.data['error']}")
            
            elif ev.event == "artifact":
                artifacts.append(ev.data)
            
            elif ev.event is None:
                # стандартный OpenAI чанк
                try:
                    delta = ev.data["choices"][0]["delta"].get("content", "")
                    if delta:
                        text += delta
                        text_placeholder.markdown(text + "▌")
                except (KeyError, IndexError):
                    pass
        
        text_placeholder.markdown(text)
        status.update(label="✅ Готово", state="complete", expanded=False)
        
        for art in artifacts:
            render_artifact(art)
        
        if trace_url:
            st.caption(f"🔍 [Trace в Langfuse]({trace_url})")
        
        st.session_state.messages.append({
            "role": "assistant", "content": text, "artifacts": artifacts,
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

### 14.4. Рендереры артефактов (`streamlit_app/artifacts.py`)

Использовать **pydeck** через `st.pydeck_chart`. Минимальные рецепты:

**MapArtifact (choropleth):**

```python
import pydeck as pdk
import streamlit as st

def render_map(art: dict):
    geojson = art["geojson"]
    color_metric = art.get("color_metric")
    
    # вычислить min/max для нормализации цвета
    values = [f["properties"].get(color_metric, 0) for f in geojson["features"]]
    vmin, vmax = (min(values), max(values)) if values else (0, 1)
    
    layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        get_fill_color=f"[255 * (properties.{color_metric} - {vmin}) / "
                       f"({vmax - vmin if vmax > vmin else 1}), 100, 50, 180]",
        get_line_color=[0, 0, 0],
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
    )
    
    bbox = art.get("bbox")
    if bbox:
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
        tooltip={"html": tooltip_html} if tooltip_html else True,
        map_style="light",
    )
    st.pydeck_chart(deck)
```

**TableArtifact:** `st.dataframe(pd.DataFrame(art["rows"], columns=art["columns"]))`

**ChartArtifact:** `st.bar_chart` / `st.line_chart` в зависимости от `chart_type`.

**FlowMapArtifact:** `pdk.Layer("ArcLayer", ...)` с `get_source_position`, `get_target_position`, `get_width`.

```python
def render_artifact(art: dict):
    t = art["type"]
    if t == "map":
        render_map(art)
    elif t == "flow_map":
        render_flow_map(art)
    elif t == "table":
        render_table(art)
    elif t == "chart":
        render_chart(art)
    else:
        st.warning(f"Неизвестный тип артефакта: {t}")
```

### 14.5. Sidebar — служебное

В sidebar:
- Кнопка **Clear chat** (сброс `st.session_state.messages`).
- Поле **Backend URL** (по дефолту из env, можно переопределить).
- Чекбокс **Show raw SSE events** (для дебага — складывать в `st.expander` рядом со status).

---

## 15. План разработки

### Этап 0 — Инфраструктура (день 1)

- [ ] `pyproject.toml`, `uv sync`
- [ ] `.env.example`, `backend/config.py`
- [ ] `docker-compose.yml`: Postgres+PostGIS, Langfuse v3
- [ ] `README.md` с инструкцией: запуск vLLM (внешне), `docker compose up`, создание Langfuse-проекта, `.env`
- [ ] `scripts/start_backend.sh`, `scripts/start_streamlit.sh`
- [ ] `.gitignore` (включая `data/raw/`, `.env`, `*.db`, `__pycache__`)

**Acceptance:** `docker compose up` поднимает Postgres и Langfuse, оба доступны по портам.

### Этап 1 — БД и данные (день 2)

- [ ] Миграции `001_schema.sql`, `002_indices.sql`
- [ ] `data/load_demo.py` (минимум для Olmaliq: zones + zone_demographics)
- [ ] `backend/db/engine.py`, `backend/db/queries.py` с функцией `query_find_zones`
- [ ] Скрипт `scripts/reset_db.sh`: drop+create+migrate+load

**Acceptance:** в БД лежат полигоны Olmaliq, `query_find_zones(city="Olmaliq", age=[1,2])` возвращает непустой список.

### Этап 2 — Минимальный backend без агента (день 3)

- [ ] `backend/main.py` с FastAPI app
- [ ] `backend/logging_config.py` (structlog)
- [ ] `/healthz` (проверка Postgres + vLLM)
- [ ] `backend/api/schemas.py` (request/response модели + Artifact-типы)
- [ ] `backend/api/sse.py` (SSE-форматтер)
- [ ] Заглушка `/v1/chat/completions`: возвращает фиксированный ответ + один тестовый MapArtifact

**Acceptance:** `curl POST /v1/chat/completions` возвращает корректный SSE-стрим со стандартными чанками + один кастомный `event: artifact`.

### Этап 3 — Agents SDK + один тул (день 4-5)

- [ ] `backend/observability.py`, init Langfuse в lifespan
- [ ] `backend/agent/system_prompt.py` (с кодировками)
- [ ] `backend/agent/geo_agent.py` (Agent + AsyncOpenAI на vLLM)
- [ ] `backend/tools/base.py` (GeoContext, emit_artifact)
- [ ] `backend/tools/find_zones.py` (полная реализация)
- [ ] `backend/agent/runner.py`: `Runner.run_streamed` → SSE-маппер с `tool_started`/`tool_finished`/`artifact`/`trace_started`
- [ ] Stub-реализации остальных 6 тулов

**Acceptance:**
1. `curl` запрос «Найди зоны для аудитории 18-35 в Olmaliq» возвращает SSE с tool_started(find_zones), tool_finished, artifact (map), и текстовым ответом.
2. В Langfuse появляется trace со span'ами agent.run → llm.completion → tool.find_zones.
3. В JSON-логах видны все tool.* события с одним trace_id.

### Этап 4 — Streamlit (день 6)

- [ ] `streamlit_app/client.py` (SSE-парсер)
- [ ] `streamlit_app/artifacts.py` (рендерер map + table)
- [ ] `streamlit_app/chat.py` (st.status + st.chat_message)
- [ ] `streamlit_app/app.py`

**Acceptance:**
1. В Streamlit виден чат, сообщения сохраняются.
2. При запросе «Найди зоны...» в `st.status` появляется блок с вызовом тула, прогрессом, временем выполнения.
3. После ответа рендерится pydeck-карта + ссылка на Langfuse trace.

### Этап 5 — Расширение тулов (день 7-8)

- [ ] Полная реализация `zone_demographics`
- [ ] Полная реализация `zone_traffic` (требует загрузки `zone_dynamics`)
- [ ] Расширение ETL под dynamics
- [ ] Тесты `tests/test_tools.py`

**Acceptance:** агент может ответить на вопросы:
- «Какая демография зоны 4277303?»
- «Как меняется трафик в зоне 4277303 в течение дня?»
- «Найди топ-10 зон с молодой аудиторией и покажи демографию первой»
  (multi-step: `find_zones` → `zone_demographics`)

### Этап 6 — Полировка и документация (день 9)

- [ ] `README.md` с гифкой/скринами
- [ ] Структурированные ошибки (tool_failed гарантированно эмитится при exception)
- [ ] Health checks работают
- [ ] `LICENSE` (Apache 2.0)
- [ ] `.github/workflows/lint.yml` (ruff + mypy)
- [ ] Push на GitHub

---

## 16. Acceptance criteria для MVP

Демо должно показывать end-to-end сценарий:

1. **Пользователь:** «Хочу открыть кофейню для аудитории 25-35 со средним доходом в Олмалике. Где лучше?»
2. **Streamlit показывает в реальном времени:**
   - 🔧 `find_zones` — `city=Olmaliq, age=[2], income=[3,4]`
   - ✓ готово за ~2с, ~30 записей
   - 🔧 `zone_demographics` — `zid=<top-1 zid>` *(если модель решит углубиться)*
   - ✓ готово за ~0.3с
3. **Появляется текстовый ответ** с рекомендацией топ-3 зон и обоснованием.
4. **Появляется карта** (pydeck choropleth) с подсветкой зон по рейтингу.
5. **Появляется таблица** с топ-зонами.
6. **Внизу — ссылка на Langfuse trace.**
7. В Langfuse открывается trace с полным деревом span'ов, виден промпт, видно reasoning от gpt-oss, видны args/output каждого тула, видны токены.
8. В файле `backend.log` (или stdout) — JSON-события всего пайплайна с одним `trace_id`.

---

## 17. Что НЕ входит в MVP

Чтобы не размывать scope — явно фиксируем:

- ❌ Аутентификация / API keys на бэкенде (для демо `api_key` игнорируется)
- ❌ Multi-tenant / разделение по клиентам
- ❌ Rate limiting
- ❌ Кеширование ответов модели
- ❌ Полная реализация `home_work_flow`, `catchment_area`, `compare_zones`, `roaming_analysis` — только stub'ы
- ❌ Геокодинг адресов (zid → coordinates вход уже есть, address → zid пока нет)
- ❌ Поддержка городов кроме Olmaliq и Tashkent
- ❌ Деплой в облако / Kubernetes — только локально + GitHub репозиторий
- ❌ Тесты с покрытием >50% — только smoke-тесты ключевых тулов и SSE-парсера

---

## 18. Гайдлайны для Claude Code

1. **Идти этапами** строго по разделу 15. После каждого этапа — `git commit` с осмысленным сообщением.
2. **Не реализовывать впрок** функции, не указанные в текущем этапе.
3. **При неясности контракта** — следовать разделам 7 (API) и 8 (артефакты) как источнику истины.
4. **При расхождениях** между этим ТЗ и `docs/2026-04-17-geoinsight-agent-design.md` — следовать ТЗ, расхождение фиксировать комментарием в коде или в TODO.
5. **Все async** где возможно. Не смешивать sync и async DB-операции.
6. **Type hints обязательны.** Прогонять `mypy backend` перед коммитом.
7. **Формат:** `ruff format`, `ruff check --fix`. Длина строки 100.
8. **Тесты** для тулов — pytest-asyncio, БД мокается через тестовую схему.
9. **Когда что-то не получается с gpt-oss-120b harmony форматом** — **не пытаться** обходить vLLM руками, просто проверять флаги `--tool-call-parser openai --enable-auto-tool-choice --reasoning-parser openai_gptoss` на vLLM-стороне и обновлять `openai-agents` SDK.
10. **Никогда не коммитить** содержимое `.env`, CSV-датасеты, `data/raw/`, `*.log`.

---

## 19. Источники для уточнения деталей

При необходимости свериться с актуальной документацией:

- vLLM + gpt-oss: https://cookbook.openai.com/articles/gpt-oss/run-vllm
- vLLM tool calling: https://docs.vllm.ai/en/latest/features/tool_calling/
- OpenAI Agents SDK (Python): https://openai.github.io/openai-agents-python/
- Langfuse self-hosted: https://langfuse.com/self-hosting/docker-compose
- Langfuse + OTEL: https://langfuse.com/docs/opentelemetry/get-started
- pydeck в Streamlit: https://docs.streamlit.io/develop/api-reference/charts/st.pydeck_chart
- structlog: https://www.structlog.org/

---

**Конец ТЗ.**

import json
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
from backend.config import settings
from backend.db.engine import check_db
from backend.logging_config import configure_logging
from backend.observability import init_langfuse

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    init_langfuse()
    log.info("app.starting", backend_port=settings.backend_port)
    yield
    log.info("app.stopping")


app = FastAPI(title="GeoInsight Agent", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    """Health check: verify Postgres and vLLM are reachable (TZ:7.4)."""
    checks: dict = {}

    try:
        await check_db()
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

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

    # Lazy import to avoid circular imports at startup
    from backend.agent.runner import run_agent_stream

    if request.stream:
        return StreamingResponse(
            run_agent_stream(request.messages, trace_id),
            media_type="text/event-stream",
            headers={"X-Trace-Id": trace_id},
        )

    # Non-streaming: collect full response
    text = ""
    artifacts = []
    async for chunk in run_agent_stream(request.messages, trace_id):
        for line in chunk.strip().split("\n"):
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    data = json.loads(line[6:])
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
        artifacts=artifacts,
    )
    return JSONResponse(
        content=response.model_dump(),
        headers={"X-Trace-Id": trace_id},
    )

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


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: ChatCompletionRequest, raw_request: Request):
    """OpenAI-compatible chat completions endpoint (TZ:7)."""
    trace_id = raw_request.headers.get("x-trace-id", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    log.info(
        "request.received",
        messages_count=len(request.messages),
        last_user_msg_preview=request.messages[-1].content[:100] if request.messages else "",
    )

    from backend.agent.runner import run_agent_non_stream
    from backend.api.sse import sse_done, sse_event

    text, artifacts, tool_steps, langfuse_url = await run_agent_non_stream(
        request.messages, trace_id
    )

    if request.stream:

        async def _sse_from_result():
            cid = f"chatcmpl-{trace_id[:12]}"
            yield sse_event(
                {"trace_id": trace_id, "langfuse_url": langfuse_url}, event="trace_started"
            )
            yield sse_event(
                {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "choices": [
                        {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
                    ],
                }
            )
            # Tool steps with args and outputs
            for step in tool_steps:
                yield sse_event(step, event="tool_call")
            # Artifacts
            for art in artifacts:
                yield sse_event(art, event="artifact")
            # Final text
            if text:
                yield sse_event(
                    {
                        "id": cid,
                        "object": "chat.completion.chunk",
                        "choices": [
                            {"index": 0, "delta": {"content": text}, "finish_reason": None}
                        ],
                    }
                )
            yield sse_event(
                {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
            )
            yield sse_done()

        return StreamingResponse(
            _sse_from_result(),
            media_type="text/event-stream",
            headers={"X-Trace-Id": trace_id},
        )

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

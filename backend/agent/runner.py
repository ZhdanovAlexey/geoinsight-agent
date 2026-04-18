import json
import time
import uuid
from typing import AsyncGenerator

import structlog
from agents import RawResponsesStreamEvent, RunItemStreamEvent, Runner
from agents.items import (
    ToolCallItem,
    ToolCallOutputItem,
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

    yield sse_event(
        {"trace_id": trace_id, "langfuse_url": None},
        event="trace_started",
    )

    log.info("agent.started", trace_id=trace_id, model=geo_agent.model)

    input_messages = [{"role": m.role, "content": m.content} for m in messages]

    tool_timers: dict[str, float] = {}
    tools_called: list[str] = []
    emitted_artifact_count = 0

    try:
        result = Runner.run_streamed(
            geo_agent,
            input=input_messages,
            context=ctx,
        )

        # Role chunk
        yield sse_event(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
        )

        async for event in result.stream_events():
            if isinstance(event, RawResponsesStreamEvent):
                data = event.data
                if hasattr(data, "choices") and data.choices:
                    for choice in data.choices:
                        delta = choice.delta
                        if hasattr(delta, "content") and delta.content:
                            yield sse_event(
                                {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": delta.content},
                                            "finish_reason": None,
                                        }
                                    ],
                                }
                            )

            elif isinstance(event, RunItemStreamEvent):
                item = event.item

                if isinstance(item, ToolCallItem):
                    call_id = getattr(item, "call_id", None) or str(uuid.uuid4())
                    tool_name = "unknown"
                    args = {}
                    if hasattr(item, "raw_item") and hasattr(item.raw_item, "name"):
                        tool_name = item.raw_item.name
                    if hasattr(item, "raw_item") and hasattr(item.raw_item, "arguments"):
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
                    call_id = getattr(item, "call_id", "") or ""
                    duration_ms = int(
                        (time.monotonic() - tool_timers.pop(call_id, time.monotonic())) * 1000
                    )

                    log.info(
                        "tool.finished",
                        trace_id=trace_id,
                        duration_ms=duration_ms,
                    )
                    yield sse_event(
                        {"call_id": call_id, "duration_ms": duration_ms, "status": "ok"},
                        event="tool_finished",
                    )

                    # Emit any new artifacts
                    while emitted_artifact_count < len(ctx.artifacts):
                        art = ctx.artifacts[emitted_artifact_count]
                        emitted_artifact_count += 1
                        log.info(
                            "artifact.emitted",
                            trace_id=trace_id,
                            artifact_id=art["id"],
                            artifact_type=art["type"],
                        )
                        yield sse_event(art, event="artifact")

    except Exception:
        log.exception("agent.failed", trace_id=trace_id)
        yield sse_event(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "Произошла ошибка при обработке запроса."},
                        "finish_reason": None,
                    }
                ],
            }
        )

    total_duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "agent.finished",
        trace_id=trace_id,
        total_duration_ms=total_duration_ms,
        tools_called=tools_called,
        artifacts_count=len(ctx.artifacts),
    )

    yield sse_event(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
    )
    yield sse_done()

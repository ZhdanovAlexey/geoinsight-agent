import json
import time

import structlog
from agents import Runner

from backend.agent.geo_agent import geo_agent
from backend.api.schemas import ChatMessage
from backend.observability import langfuse_span, langfuse_trace
from backend.tools.base import GeoContext

log = structlog.get_logger()


async def run_agent_non_stream(
    messages: list[ChatMessage],
    trace_id: str,
) -> tuple[str, list[dict], list[dict], str | None]:
    """Run the agent and return (text, artifacts, tool_steps, langfuse_url)."""
    ctx = GeoContext(trace_id=trace_id)

    log.info("agent.started", trace_id=trace_id, model=geo_agent.model)

    input_messages = [{"role": m.role, "content": m.content} for m in messages]

    t0 = time.monotonic()
    result = await Runner.run(
        geo_agent,
        input=input_messages,
        context=ctx,
    )
    total_duration_ms = int((time.monotonic() - t0) * 1000)

    final_text = result.final_output or ""

    # Collect tool steps: pair ToolCallItem with ToolCallOutputItem
    tool_steps = []
    pending_call = None
    for item in result.new_items:
        item_type = type(item).__name__

        if item_type == "ToolCallItem":
            tool_name = (
                getattr(item.raw_item, "name", "unknown")
                if hasattr(item, "raw_item")
                else "unknown"
            )
            args = {}
            if hasattr(item, "raw_item") and hasattr(item.raw_item, "arguments"):
                try:
                    args = json.loads(item.raw_item.arguments or "{}")
                except (json.JSONDecodeError, TypeError):
                    pass
            pending_call = {"name": tool_name, "args": args, "output": None}

        elif item_type == "ToolCallOutputItem":
            output = getattr(item, "output", None)
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except (json.JSONDecodeError, TypeError):
                    pass
            if pending_call:
                pending_call["output"] = output
                tool_steps.append(pending_call)
                pending_call = None
            else:
                tool_steps.append({"name": "unknown", "args": {}, "output": output})

    # Flush any pending call without output
    if pending_call:
        tool_steps.append(pending_call)

    log.info(
        "agent.finished",
        trace_id=trace_id,
        total_duration_ms=total_duration_ms,
        tools_called=[t["name"] for t in tool_steps],
        artifacts_count=len(ctx.artifacts),
    )

    # Send to Langfuse
    langfuse_url = langfuse_trace(
        trace_id=trace_id,
        name="chat_completion",
        input_data={"messages": input_messages},
        output_data={"text": final_text[:500], "artifacts_count": len(ctx.artifacts)},
        metadata={
            "tools_called": [t["name"] for t in tool_steps],
            "total_duration_ms": total_duration_ms,
            "model": geo_agent.model,
        },
    )

    for step in tool_steps:
        # Truncate output for Langfuse (avoid huge GeoJSON)
        output_for_lf = step["output"]
        if isinstance(output_for_lf, dict):
            output_for_lf = {k: v for k, v in output_for_lf.items() if k != "geojson"}
        langfuse_span(
            trace_id=trace_id,
            name=f"tool.{step['name']}",
            input_data=step["args"],
            output_data=output_for_lf,
        )

    return final_text, ctx.artifacts, tool_steps, langfuse_url

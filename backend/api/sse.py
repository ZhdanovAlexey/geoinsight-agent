import json
from typing import Any


def sse_event(data: Any, event: str | None = None) -> str:
    """Format a single SSE event.

    Standard chunks: data: {...}\\n\\n
    Custom events: event: <type>\\ndata: {...}\\n\\n
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

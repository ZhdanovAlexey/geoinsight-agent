import json
from dataclasses import dataclass
from typing import Iterator

import httpx


@dataclass
class SSEEvent:
    event: str | None
    data: dict | str


class GeoInsightClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url

    def stream_chat(self, messages: list[dict]) -> Iterator[SSEEvent]:
        """Stream chat completions via SSE."""
        with httpx.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
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
                    yield SSEEvent(event=event_type, data=data)
                    event_type = None

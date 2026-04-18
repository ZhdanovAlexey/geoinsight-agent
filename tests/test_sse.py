import json

from backend.api.sse import sse_done, sse_event


def test_sse_event_standard():
    result = sse_event({"key": "value"})
    assert result == 'data: {"key": "value"}\n\n'


def test_sse_event_custom():
    result = sse_event({"key": "value"}, event="tool_started")
    assert result.startswith("event: tool_started\n")
    assert "data: " in result


def test_sse_done():
    assert sse_done() == "data: [DONE]\n\n"


def test_sse_event_unicode():
    result = sse_event({"text": "Привет"})
    data_line = result.strip().split("data: ")[1]
    parsed = json.loads(data_line)
    assert parsed["text"] == "Привет"

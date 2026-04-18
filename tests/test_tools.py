from backend.tools.base import GeoContext, safe_args_preview


def test_geo_context_emit_artifact():
    ctx = GeoContext(trace_id="test-123")
    aid = ctx.emit_artifact({"type": "map", "geojson": {}})
    assert aid == "art_1"
    assert len(ctx.artifacts) == 1
    assert ctx.artifacts[0]["id"] == "art_1"


def test_geo_context_multiple_artifacts():
    ctx = GeoContext(trace_id="test-123")
    ctx.emit_artifact({"type": "map"})
    ctx.emit_artifact({"type": "table"})
    assert len(ctx.artifacts) == 2
    assert ctx.artifacts[1]["id"] == "art_2"


def test_safe_args_preview_truncates_list():
    result = safe_args_preview({"ids": list(range(20))})
    assert result["ids"] == "[20 items]"


def test_safe_args_preview_truncates_string():
    result = safe_args_preview({"text": "x" * 300})
    assert len(result["text"]) <= 203  # 200 + "..."


def test_safe_args_preview_normal():
    result = safe_args_preview({"city": "Olmaliq", "age": [1, 2]})
    assert result == {"city": "Olmaliq", "age": [1, 2]}

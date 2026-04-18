import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

# === Request ===


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "geoinsight-v1"
    messages: list[ChatMessage]
    stream: bool = False


# === Artifacts (TZ:8) ===


class MapArtifact(BaseModel):
    id: str = ""
    type: Literal["map"] = "map"
    viz: Literal["choropleth", "heatmap", "points"] = "choropleth"
    geojson: dict = Field(default_factory=dict)
    color_metric: str | None = None
    legend: dict | None = None
    bbox: list[float] | None = None
    tooltip_fields: list[str] = Field(default_factory=list)


class FlowMapArtifact(BaseModel):
    id: str = ""
    type: Literal["flow_map"] = "flow_map"
    flows: list[dict] = Field(default_factory=list)
    bbox: list[float] | None = None


class TableArtifact(BaseModel):
    id: str = ""
    type: Literal["table"] = "table"
    title: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)


class ChartArtifact(BaseModel):
    id: str = ""
    type: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "pie"] = "bar"
    title: str | None = None
    data: dict = Field(default_factory=dict)


Artifact = MapArtifact | FlowMapArtifact | TableArtifact | ChartArtifact


# === Response ===


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "geoinsight-v1"
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)
    trace_id: str | None = None
    artifacts: list[dict] = Field(default_factory=list)

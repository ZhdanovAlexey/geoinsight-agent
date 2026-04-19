import uuid
from datetime import datetime, timezone

import httpx
import structlog

from backend.config import settings

log = structlog.get_logger()

_auth: tuple[str, str] | None = None


def init_langfuse() -> None:
    """Initialize Langfuse connection via direct ingestion API."""
    global _auth

    if not settings.langfuse_enabled:
        log.info("langfuse.disabled")
        return

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        log.warning("langfuse.missing_keys")
        return

    _auth = (settings.langfuse_public_key, settings.langfuse_secret_key)
    log.info("langfuse.initialized", host=settings.langfuse_host)


def langfuse_trace(
    trace_id: str,
    name: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    metadata: dict | None = None,
) -> str | None:
    """Create a trace in Langfuse. Returns trace URL or None."""
    if not _auth:
        return None

    now = datetime.now(timezone.utc).isoformat()
    body = {
        "batch": [
            {
                "id": str(uuid.uuid4()),
                "type": "trace-create",
                "timestamp": now,
                "body": {
                    "id": trace_id,
                    "name": name,
                    "input": input_data,
                    "output": output_data,
                    "metadata": metadata,
                },
            }
        ]
    }

    try:
        r = httpx.post(
            f"{settings.langfuse_host}/api/public/ingestion",
            json=body,
            auth=_auth,
            timeout=5,
        )
        if r.status_code not in (200, 207):
            log.warning("langfuse.trace_failed", status=r.status_code)
    except Exception:
        log.warning("langfuse.trace_error", exc_info=True)

    public_url = settings.langfuse_public_url or settings.langfuse_host
    return f"{public_url}/trace/{trace_id}"


def langfuse_span(
    trace_id: str,
    name: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    metadata: dict | None = None,
) -> None:
    """Create a span (child of trace) in Langfuse."""
    if not _auth:
        return

    now = datetime.now(timezone.utc).isoformat()
    span_id = str(uuid.uuid4())
    body = {
        "batch": [
            {
                "id": str(uuid.uuid4()),
                "type": "span-create",
                "timestamp": now,
                "body": {
                    "id": span_id,
                    "traceId": trace_id,
                    "name": name,
                    "input": input_data,
                    "output": output_data,
                    "metadata": metadata,
                    "startTime": now,
                    "endTime": now,
                },
            }
        ]
    }

    try:
        httpx.post(
            f"{settings.langfuse_host}/api/public/ingestion",
            json=body,
            auth=_auth,
            timeout=5,
        )
    except Exception:
        pass

import base64
import os

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from backend.config import settings

log = structlog.get_logger()


def init_langfuse() -> None:
    """Initialize Langfuse via OpenTelemetry OTLP exporter.

    If LANGFUSE_ENABLED is false or keys are missing, skip silently (TZ:12.5).
    """
    if not settings.langfuse_enabled:
        log.info("langfuse.disabled")
        return

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        log.warning("langfuse.missing_keys", hint="Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY")
        return

    try:
        auth = base64.b64encode(
            f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
        ).decode()

        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{settings.langfuse_host}/api/public/otel"
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth}"

        provider = TracerProvider()
        processor = BatchSpanProcessor(OTLPSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        log.info("langfuse.initialized", host=settings.langfuse_host)
    except Exception:
        log.warning("langfuse.init_failed", exc_info=True)

"""
Observability bootstrap.

- OpenTelemetry: instruments FastAPI HTTP spans. ConsoleSpanExporter in dev,
  no exporter in production (wire up OTLP in Phase 13 / CI).
- Langfuse: returns a per-request LangChain CallbackHandler that traces every
  LLM call inside the agent graph. Returns None silently when keys are absent.
"""
from __future__ import annotations

from rootcause.core.logging import get_logger

log = get_logger(__name__)


def init_otel(app_env: str = "development") -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        provider = TracerProvider()
        if app_env != "production":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        log.info("otel_initialized", exporter="console" if app_env != "production" else "none")
    except Exception as exc:
        log.warning("otel_init_failed", error=str(exc))


def instrument_app(app) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        log.info("otel_fastapi_instrumented")
    except Exception as exc:
        log.warning("otel_fastapi_instrument_failed", error=str(exc))


def get_langfuse_callback(session_id: str | None = None):
    """Return a Langfuse LangChain CallbackHandler, or None if keys are absent."""
    from rootcause.core.config import get_settings

    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse.callback import CallbackHandler  # type: ignore[import]

        return CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            session_id=session_id,
        )
    except Exception as exc:
        log.warning("langfuse_callback_failed", error=str(exc))
        return None

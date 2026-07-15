"""
LangFuse tracing via OpenTelemetry (Agent Master Guide §8.6).
No-op when LANGFUSE keys are absent — safe in every environment.
"""
from __future__ import annotations
import base64
import os


def configure_langfuse() -> bool:
    """
    Wire Pydantic AI instrumentation to LangFuse over OTLP.
    Returns True when tracing is active.
    """
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sk = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not pk or not sk:
        return False

    host = (
        os.getenv("LANGFUSE_BASE_URL")
        or os.getenv("LANGFUSE_HOST")
        or "https://cloud.langfuse.com"
    ).rstrip("/")

    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host}/api/public/otel"
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"]  = f"Authorization=Basic {auth}"

    try:
        from pydantic_ai import Agent
        Agent.instrument_all()
        return True
    except Exception as e:
        print(f"[observability] LangFuse instrumentation failed: {e}")
        return False

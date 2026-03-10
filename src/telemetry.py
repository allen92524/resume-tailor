"""OpenTelemetry and Prometheus instrumentation setup."""

import os
import time
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from prometheus_client import Counter, Histogram, Gauge

# ── OpenTelemetry tracing setup ──────────────────────────────────────

_otel_disabled = os.environ.get("OTEL_SDK_DISABLED", "").lower() == "true"

if not _otel_disabled:
    _resource = Resource.create({"service.name": "resume-tailor"})
    _provider = TracerProvider(resource=_resource)

    # Only export to console when running as API server (RESUME_TAILOR_API=1)
    _api_mode = os.environ.get("RESUME_TAILOR_API", "").lower() in ("1", "true")
    if _api_mode:
        _provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # Export to an OTLP endpoint when configured
    _otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if _otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        _provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=_otlp_endpoint))
        )

    trace.set_tracer_provider(_provider)

tracer = trace.get_tracer("resume-tailor")

# ── Prometheus metrics ───────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)

ACTIVE_REQUESTS = Gauge(
    "http_active_requests",
    "Number of active HTTP requests",
)

CLAUDE_API_CALL_COUNT = Counter(
    "claude_api_calls_total",
    "Total Claude API calls",
    ["model", "status"],
)

CLAUDE_API_DURATION = Histogram(
    "claude_api_call_duration_seconds",
    "Claude API call duration in seconds",
    ["model"],
    buckets=(0.5, 1, 2.5, 5, 10, 15, 30, 60),
)

RESUME_GENERATION_COUNT = Counter(
    "resume_generations_total",
    "Total successful resume generations",
)


@contextmanager
def track_claude_api_call(model: str):
    """Context manager to track Claude API call metrics and create a trace span."""
    with tracer.start_as_current_span(
        "claude_api_call", attributes={"claude.model": model}
    ) as span:
        start = time.perf_counter()
        try:
            yield span
            duration = time.perf_counter() - start
            CLAUDE_API_CALL_COUNT.labels(model=model, status="success").inc()
            CLAUDE_API_DURATION.labels(model=model).observe(duration)
            span.set_attribute("claude.duration_s", duration)
            span.set_attribute("claude.status", "success")
        except Exception as exc:
            duration = time.perf_counter() - start
            CLAUDE_API_CALL_COUNT.labels(model=model, status="error").inc()
            CLAUDE_API_DURATION.labels(model=model).observe(duration)
            span.set_attribute("claude.status", "error")
            span.set_attribute("claude.error", str(exc))
            span.record_exception(exc)
            raise

"""OpenTelemetry initialization for Way2AGI services."""

import os

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource


def init_telemetry(service_name: str = "way2agi"):
    """Initialize OpenTelemetry tracing + metrics. Call once at app startup."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    resource = Resource(attributes={"service.name": service_name})

    # Tracing
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)

    # Metrics
    metrics.set_meter_provider(MeterProvider(resource=resource))

    print(f"[Telemetry] {service_name} -> {endpoint}")
    return trace.get_tracer(service_name)

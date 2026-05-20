from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .config import config

_INITIALIZED = False


def setup_telemetry() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return

    service_name = config.env.otel_service_name
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if config.env.otel_enabled:
        exporter = OTLPSpanExporter(
            endpoint=config.env.otel_exporter_otlp_endpoint,
            insecure=config.env.otel_exporter_otlp_insecure,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _INITIALIZED = True


def get_tracer():
    setup_telemetry()
    return trace.get_tracer(config.env.otel_service_name)

"""OpenTelemetry setup shared by the frontend and inference services.

Traces and metrics are pushed over OTLP/HTTP, so the same code works in k3s
(pushing to an in-cluster Alloy collector) and on Cloud Run (pushing straight to
Grafana Cloud), where instances are too short-lived to be scraped.

Telemetry is enabled only when OTEL_EXPORTER_OTLP_ENDPOINT is set, so local
runs and tests need no collector. Everything else is configured through the
standard OTEL_* environment variables, read by the SDK:

    OTEL_EXPORTER_OTLP_ENDPOINT   e.g. http://alloy.monitoring.svc:4318
    OTEL_EXPORTER_OTLP_HEADERS    e.g. Authorization=Basic <token> (Grafana Cloud)
    OTEL_SERVICE_NAME             overrides the service name passed in code
    OTEL_RESOURCE_ATTRIBUTES      e.g. deployment.environment=prod
    OTEL_TRACES_SAMPLER(_ARG)     sampling, defaults to recording every trace
"""

import os

from fastapi import FastAPI


def telemetry_enabled() -> bool:
    if os.getenv("OTEL_SDK_DISABLED", "").lower() == "true":
        return False
    return bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))


def setup_telemetry(app: FastAPI, service_name: str, db_engine=None) -> bool:
    """Install trace/metric providers and auto-instrument the app.

    Returns True if telemetry was enabled. Module-level tracers and meters
    created before this call (e.g. in pipelines/inference.py) start exporting
    once the global providers are set.
    """
    if not telemetry_enabled():
        return False

    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", service_name)}
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[metric_reader])
    )

    # Server spans + HTTP server metrics for every route except health checks.
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health")
    # Client spans for outgoing calls; also injects the traceparent header so
    # the frontend -> inference call continues the same trace.
    RequestsInstrumentor().instrument()

    if db_engine is not None:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=db_engine)

    return True

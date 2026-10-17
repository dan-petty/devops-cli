"""Telemetry and Prometheus metrics REST API endpoints."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from prometheus_client.core import GaugeMetricFamily
from pydantic import BaseModel, Field

from devops_cli import __version__
from devops_cli.security.sanitizer import sanitize_telemetry_endpoint
from devops_cli.telemetry.tracer import get_tracer

router = APIRouter(tags=["Telemetry & Metrics"])

_SERVICE_START_TIME = time.time()
_REQUEST_COUNTER: dict[str, int] = {}


class TelemetryStatusResponse(BaseModel):
    """Telemetry status schema."""

    enabled: bool = Field(..., description="Whether OpenTelemetry exporter is active")
    endpoint: str = Field(..., description="Target OTLP HTTP endpoint")
    service_name: str = Field(default="devops-cli", description="Service name attribute")
    service_version: str = Field(default=__version__, description="Service version attribute")
    ping_ok: bool = Field(..., description="Whether OTLP collector is reachable")
    ping_message: str = Field(..., description="Ping probe details")
    ping_latency_ms: float = Field(..., description="Ping roundtrip latency in ms")


@router.get(
    "/api/v1/telemetry",
    response_model=TelemetryStatusResponse,
    summary="OpenTelemetry status and probe",
)
async def get_telemetry() -> TelemetryStatusResponse:
    """Inspect OpenTelemetry configuration and ping the OTLP collector endpoint."""
    tracer = get_tracer()
    ok, _msg, latency = tracer.test_connection(timeout=0.5)
    safe_msg = "Connected successfully" if ok else "Collector probe failed or unreachable"
    safe_endpoint = sanitize_telemetry_endpoint(tracer.endpoint)
    return TelemetryStatusResponse(
        enabled=tracer.enabled,
        endpoint=safe_endpoint,
        service_name="devops-cli",
        service_version=__version__,
        ping_ok=ok,
        ping_message=safe_msg,
        ping_latency_ms=round(latency, 2),
    )


class _ServerTelemetryCollector:
    """Collector combining server metadata, in-memory metrics, and AI spend metrics."""

    def collect(self) -> Iterator[Any]:
        from devops_cli.ai.spend.prometheus import AISpendCollector
        from devops_cli.telemetry.metrics import GLOBAL_METRICS

        uptime = time.time() - _SERVICE_START_TIME
        info_family = GaugeMetricFamily(
            "devops_cli_info",
            "DevOps CLI version and runtime metadata",
            labels=["service", "version"],
        )
        info_family.add_metric(["devops-cli", __version__], 1)
        yield info_family
        yield GaugeMetricFamily(
            "devops_cli_uptime_seconds",
            "Process uptime in seconds",
            value=round(uptime, 2),
        )
        yield GaugeMetricFamily(
            "devops_cli_telemetry_enabled",
            "Whether OpenTelemetry is enabled (1=yes, 0=no)",
            value=1 if get_tracer().enabled else 0,
        )
        yield from GLOBAL_METRICS.registry.collect()
        yield from AISpendCollector().collect()


@router.get(
    "/metrics",
    response_class=Response,
    summary="Prometheus metrics scrape endpoint",
)
async def get_metrics() -> Response:
    """Expose Prometheus formatted metric series for scraping."""
    registry = CollectorRegistry(auto_describe=True)
    registry.register(_ServerTelemetryCollector())
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )

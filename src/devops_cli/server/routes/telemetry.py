"""Telemetry and Prometheus metrics REST API endpoints."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from devops_cli import __version__
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
async def get_telemetry() -> dict[str, Any]:
    """Inspect OpenTelemetry configuration and ping the OTLP collector endpoint."""
    tracer = get_tracer()
    ok, _msg, latency = tracer.test_connection(timeout=2.0)
    safe_msg = "Connected successfully" if ok else "Collector probe failed or unreachable"
    return {
        "enabled": tracer.enabled,
        "endpoint": tracer.endpoint,
        "service_name": "devops-cli",
        "service_version": __version__,
        "ping_ok": ok,
        "ping_message": safe_msg,
        "ping_latency_ms": round(latency, 2),
    }


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus metrics scrape endpoint",
)
async def get_metrics() -> str:
    """Expose Prometheus formatted metric series for scraping."""
    uptime = time.time() - _SERVICE_START_TIME
    lines = [
        "# HELP devops_cli_info DevOps CLI version and runtime metadata",
        "# TYPE devops_cli_info gauge",
        f'devops_cli_info{{version="{__version__}",service="devops-cli"}} 1',
        "",
        "# HELP devops_cli_uptime_seconds Process uptime in seconds",
        "# TYPE devops_cli_uptime_seconds gauge",
        f"devops_cli_uptime_seconds {uptime:.2f}",
        "",
        "# HELP devops_cli_telemetry_enabled Whether OpenTelemetry is enabled (1=yes, 0=no)",
        "# TYPE devops_cli_telemetry_enabled gauge",
        f"devops_cli_telemetry_enabled {1 if get_tracer().enabled else 0}",
    ]
    return "\n".join(lines) + "\n"

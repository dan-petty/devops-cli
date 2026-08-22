"""Lightweight OpenTelemetry OTLP tracing and metrics emitter for devops-cli."""

from __future__ import annotations

import contextlib
import logging
import os
import secrets
import time
from collections.abc import Generator
from typing import Any

import httpx2

logger = logging.getLogger(__name__)


def _generate_trace_id() -> str:
    return secrets.token_hex(16)


def _generate_span_id() -> str:
    return secrets.token_hex(8)


class OTelTelemetryClient:
    """Emits OpenTelemetry traces and metrics via OTLP HTTP/JSON."""

    def __init__(
        self,
        endpoint: str = "http://localhost:4318",
        *,
        service_name: str = "devops-cli",
        enabled: bool = True,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.service_name = service_name
        self.enabled = enabled
        self._current_trace_id: str | None = None

    def record_metric(
        self,
        name: str,
        value: float,
        *,
        unit: str = "1",
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Emit a metric data point to OTLP collector asynchronously."""
        if not self.enabled:
            return

        now_nano = int(time.time() * 1e9)
        attr_list = [
            {"key": k, "value": {"stringValue": str(v)}} for k, v in (attributes or {}).items()
        ]

        payload = {
            "resourceMetrics": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": self.service_name}}
                        ]
                    },
                    "scopeMetrics": [
                        {
                            "scope": {"name": "devops-cli.telemetry"},
                            "metrics": [
                                {
                                    "name": name,
                                    "unit": unit,
                                    "gauge": {
                                        "dataPoints": [
                                            {
                                                "timeUnixNano": str(now_nano),
                                                "asDouble": float(value),
                                                "attributes": attr_list,
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        self._send_payload("/v1/metrics", payload)

    @contextlib.contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[str]:
        """Context manager to measure and emit a trace span."""
        if not self.enabled:
            yield ""
            return

        trace_id = self._current_trace_id or _generate_trace_id()
        span_id = _generate_span_id()
        parent_id = self._current_trace_id
        start_nano = int(time.time() * 1e9)
        prev_trace = self._current_trace_id
        self._current_trace_id = trace_id

        attrs = dict(attributes or {})
        status_code = "STATUS_CODE_OK"
        error_msg = ""

        try:
            yield span_id
        except Exception as exc:
            status_code = "STATUS_CODE_ERROR"
            error_msg = str(exc)
            attrs["error"] = True
            attrs["exception.message"] = error_msg
            raise
        finally:
            end_nano = int(time.time() * 1e9)
            self._current_trace_id = prev_trace

            span_data: dict[str, Any] = {
                "traceId": trace_id,
                "spanId": span_id,
                "name": name,
                "kind": "SPAN_KIND_INTERNAL",
                "startTimeUnixNano": str(start_nano),
                "endTimeUnixNano": str(end_nano),
                "attributes": [
                    {"key": k, "value": {"stringValue": str(v)}} for k, v in attrs.items()
                ],
                "status": {"code": status_code, "message": error_msg},
            }
            if parent_id and parent_id != trace_id:
                span_data["parentSpanId"] = parent_id

            payload = {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {
                                    "key": "service.name",
                                    "value": {"stringValue": self.service_name},
                                }
                            ]
                        },
                        "scopeSpans": [
                            {
                                "scope": {"name": "devops-cli.telemetry"},
                                "spans": [span_data],
                            }
                        ],
                    }
                ]
            }
            self._send_payload("/v1/traces", payload)

    def _send_payload(self, path: str, payload: dict[str, Any]) -> None:
        """Send payload over HTTP with short timeout."""
        try:
            url = f"{self.endpoint}{path}"
            with httpx2.Client(timeout=0.5) as client:
                client.post(url, json=payload)
        except Exception as exc:
            logger.debug("OTel payload send failed to %s%s: %s", self.endpoint, path, exc)


_GLOBAL_TRACER: OTelTelemetryClient | None = None


def get_tracer() -> OTelTelemetryClient:
    """Return the global singleton OTelTelemetryClient instance."""
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is None:
        from devops_cli.config.settings import load_settings

        try:
            settings = load_settings()
            telemetry_cfg = getattr(settings, "telemetry", None) or getattr(settings, "otel", None)
            cfg_endpoint = (
                telemetry_cfg.endpoint
                if telemetry_cfg and hasattr(telemetry_cfg, "endpoint")
                else None
            )
            cfg_enabled = (
                telemetry_cfg.enabled
                if telemetry_cfg and hasattr(telemetry_cfg, "enabled")
                else True
            )
        except Exception:
            cfg_endpoint = None
            cfg_enabled = True

        endpoint = os.getenv("DEVOPS_OTEL_ENDPOINT") or cfg_endpoint or "http://localhost:4318"
        env_enabled = os.getenv("DEVOPS_TELEMETRY_ENABLED")
        enabled = (
            (env_enabled.lower() in ("true", "1")) if env_enabled is not None else bool(cfg_enabled)
        )
        _GLOBAL_TRACER = OTelTelemetryClient(endpoint=endpoint, enabled=enabled)
    return _GLOBAL_TRACER


@contextlib.contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[str]:
    """Convenience context manager for tracing a block of execution."""
    tracer = get_tracer()
    with tracer.span(name, attributes=attributes) as span_id:
        yield span_id


def record_metric(
    name: str,
    value: float,
    unit: str = "1",
    attributes: dict[str, Any] | None = None,
) -> None:
    """Convenience function to record a metric data point."""
    get_tracer().record_metric(name, value, unit=unit, attributes=attributes)

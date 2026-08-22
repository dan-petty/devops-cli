"""Lightweight OpenTelemetry OTLP tracing and metrics emitter for devops-cli."""

from __future__ import annotations

import contextlib
import functools
import logging
import os
import secrets
import time
from collections.abc import Callable, Generator
from typing import Any, TypeVar

import httpx2

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


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
        self._current_span_id: str | None = None

    @property
    def current_trace_id(self) -> str | None:
        return self._current_trace_id

    @property
    def current_span_id(self) -> str | None:
        return self._current_span_id

    def inject_trace_context(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """Inject W3C traceparent (00-{trace_id}-{span_id}-01) into headers dict."""
        out = dict(headers or {})
        if not self.enabled:
            return out
        trace_id = self._current_trace_id or _generate_trace_id()
        span_id = self._current_span_id or _generate_span_id()
        out["traceparent"] = f"00-{trace_id}-{span_id}-01"
        return out

    def extract_trace_context(self, headers: dict[str, str]) -> tuple[str | None, str | None]:
        """Extract trace_id and span_id from incoming W3C traceparent header."""
        tp = headers.get("traceparent") or headers.get("Traceparent")
        if not tp:
            return None, None
        parts = tp.split("-")
        if len(parts) >= 4 and parts[0] == "00":
            return parts[1], parts[2]
        return None, None

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

    def increment_counter(
        self,
        name: str,
        amount: float = 1.0,
        *,
        unit: str = "1",
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Convenience method to record an incremented counter metric."""
        self.record_metric(name, amount, unit=unit, attributes=attributes)

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
        parent_id = self._current_span_id
        start_nano = int(time.time() * 1e9)
        prev_trace = self._current_trace_id
        prev_span = self._current_span_id
        self._current_trace_id = trace_id
        self._current_span_id = span_id

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
            self._current_span_id = prev_span

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
            if parent_id and parent_id != span_id:
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

    def test_connection(self, timeout: float = 2.0) -> tuple[bool, str, float]:
        """Test reachability of the OTLP collector endpoint and measure latency."""
        start = time.perf_counter()
        try:
            url = f"{self.endpoint}/v1/traces"
            test_trace_id = _generate_trace_id()
            test_span_id = _generate_span_id()
            now_nano = str(int(time.time() * 1e9))
            payload = {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {
                                    "key": "service.name",
                                    "value": {"stringValue": "devops-cli-ping"},
                                }
                            ]
                        },
                        "scopeSpans": [
                            {
                                "scope": {"name": "devops-cli.telemetry.ping"},
                                "spans": [
                                    {
                                        "traceId": test_trace_id,
                                        "spanId": test_span_id,
                                        "name": "ping",
                                        "startTimeUnixNano": now_nano,
                                        "endTimeUnixNano": now_nano,
                                        "status": {"code": "STATUS_CODE_OK"},
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
            with httpx2.Client(timeout=timeout) as client:
                res = client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - start) * 1000
                if res.status_code in (200, 202):
                    return True, f"HTTP {res.status_code} OK", elapsed_ms
                return False, f"HTTP {res.status_code}: {res.text[:100]}", elapsed_ms
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return False, str(exc), elapsed_ms

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


def reset_tracer() -> None:
    """Reset global singleton tracer instance (useful in tests)."""
    global _GLOBAL_TRACER
    _GLOBAL_TRACER = None


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


def inject_trace_context(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Convenience function to inject W3C traceparent into outgoing HTTP headers."""
    return get_tracer().inject_trace_context(headers)


def traced(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Decorator to trace a function execution as an OpenTelemetry span."""

    def decorator(fn: F) -> F:
        span_name = name or f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_span(span_name, attributes=attributes):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator

"""Lightweight OpenTelemetry OTLP tracing and metrics emitter for devops-cli."""

from __future__ import annotations

import atexit
import contextlib
import contextvars
import functools
import logging
import os
import platform
import secrets
import threading
import time
from collections.abc import Callable, Generator
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import ContextVar
from typing import Any, TypeVar

import httpx2

from devops_cli.config.constants import (
    CONST_OTEL_METRIC_UNIT_ONE,
    CONST_OTEL_SCOPE_NAME,
    CONST_OTEL_SERVICE_NAME,
    CONST_OTEL_SPAN_KIND_INTERNAL,
)
from devops_cli.config.defaults import (
    DEFAULT_OTEL_COUNTER_AMOUNT,
    DEFAULT_OTEL_ENDPOINT,
    DEFAULT_OTEL_HTTP_TIMEOUT_SECONDS,
    DEFAULT_OTEL_SHUTDOWN_TIMEOUT_MS,
    DEFAULT_OTEL_TEST_TIMEOUT,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class ContextPropagatingThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor that automatically propagates ContextVar snapshots to worker threads."""

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:  # type: ignore[override]
        ctx = contextvars.copy_context()
        return super().submit(ctx.run, fn, *args, **kwargs)


def _generate_trace_id() -> str:
    return secrets.token_hex(16)


def _generate_span_id() -> str:
    return secrets.token_hex(8)


def _to_otlp_any_value(val: Any) -> dict[str, Any]:
    """Convert a Python scalar or sequence into a strongly-typed OpenTelemetry AnyValue dict."""
    if isinstance(val, bool):
        return {"boolValue": val}
    elif isinstance(val, int):
        return {"intValue": str(val)}
    elif isinstance(val, float):
        return {"doubleValue": val}
    elif isinstance(val, (list, tuple, set)):
        return {"arrayValue": {"values": [_to_otlp_any_value(v) for v in val]}}
    elif isinstance(val, dict):
        kv_list = [{"key": str(k), "value": _to_otlp_any_value(v)} for k, v in val.items()]
        return {"kvlistValue": {"values": kv_list}}
    return {"stringValue": str(val)}


_SPAN_KINDS: dict[str, str] = {
    "internal": "SPAN_KIND_INTERNAL",
    "server": "SPAN_KIND_SERVER",
    "client": "SPAN_KIND_CLIENT",
    "producer": "SPAN_KIND_PRODUCER",
    "consumer": "SPAN_KIND_CONSUMER",
}


class SpanHandle(str):
    """Handle yielded by trace_span allowing dynamic attribute updates, links, and event logging while
    behaving as span_id string."""

    _attributes: dict[str, Any]
    _events: list[dict[str, Any]]
    _links: list[dict[str, Any]]

    def __new__(
        cls,
        span_id: str,
        attributes: dict[str, Any] | None = None,
        events: list[dict[str, Any]] | None = None,
        links: list[dict[str, Any]] | None = None,
    ) -> SpanHandle:
        obj = str.__new__(cls, span_id)
        obj._attributes = attributes if attributes is not None else {}
        obj._events = events if events is not None else []
        obj._links = links if links is not None else []
        return obj

    def set_attribute(self, key: str, value: Any) -> None:
        """Set or update a single attribute on the active span."""
        self._attributes[key] = value

    def set_attributes(self, mapping: dict[str, Any]) -> None:
        """Set or update multiple attributes on the active span."""
        self._attributes.update(mapping)

    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        timestamp_ns: int | None = None,
    ) -> None:
        """Add a timestamped event / log annotation to the active span."""
        t_nano = timestamp_ns if timestamp_ns is not None else int(time.time() * 1e9)
        attr_list = [
            {"key": k, "value": _to_otlp_any_value(v)} for k, v in (attributes or {}).items()
        ]
        self._events.append(
            {
                "timeUnixNano": str(t_nano),
                "name": name,
                "attributes": attr_list,
            }
        )

    def add_link(
        self,
        trace_id: str,
        span_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add a causal span link to correlate with external or asynchronous trace contexts."""
        attr_list = [
            {"key": k, "value": _to_otlp_any_value(v)} for k, v in (attributes or {}).items()
        ]
        self._links.append(
            {
                "traceId": trace_id,
                "spanId": span_id,
                "attributes": attr_list,
            }
        )

    def record_exception(
        self, exc: BaseException, attributes: dict[str, Any] | None = None
    ) -> None:
        """Record structured exception details and event to the active span."""
        import traceback

        exc_type = type(exc).__name__
        exc_msg = str(exc)
        exc_stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        self._attributes["error"] = True
        self._attributes["otel.status_code"] = "ERROR"
        self._attributes["exception.type"] = exc_type
        self._attributes["exception.message"] = exc_msg
        self._attributes["exception.stacktrace"] = exc_stack
        event_attrs: dict[str, Any] = {
            "exception.type": exc_type,
            "exception.message": exc_msg,
            "exception.stacktrace": exc_stack,
        }
        if attributes:
            event_attrs.update(attributes)
        self.add_event("exception", event_attrs)

    def record_llm_metrics(
        self,
        *,
        provider: str,
        model: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        ttft_ms: float | None = None,
        duration_s: float | None = None,
        token_rate: float | None = None,
    ) -> None:
        """Record standard OpenTelemetry GenAI attributes on the active span."""
        self._attributes["gen_ai.system"] = provider
        self._attributes["gen_ai.request.model"] = model
        if prompt_tokens is not None:
            self._attributes["gen_ai.usage.prompt_tokens"] = prompt_tokens
            self._attributes["gen_ai.usage.input_tokens"] = prompt_tokens
        if completion_tokens is not None:
            self._attributes["gen_ai.usage.completion_tokens"] = completion_tokens
            self._attributes["gen_ai.usage.output_tokens"] = completion_tokens
        if total_tokens is not None:
            self._attributes["gen_ai.usage.total_tokens"] = total_tokens
        if ttft_ms is not None:
            self._attributes["gen_ai.time_to_first_token_ms"] = round(ttft_ms, 2)
        if duration_s is not None:
            self._attributes["gen_ai.duration_seconds"] = round(duration_s, 4)
        if token_rate is not None:
            self._attributes["gen_ai.token_rate_tok_per_sec"] = round(token_rate, 2)


_ATTRIBUTE_NORMALIZATION: dict[str, str] = {
    "cli.command": "process.command_line",
    "cli.function": "code.function",
    "file_path": "code.filepath",
    "file.path": "code.filepath",
    "subprocess.bin": "process.executable.name",
    "subprocess.cmd": "process.command_line",
    "subprocess.cwd": "process.working_directory",
    "subprocess.exit_code": "process.exit.code",
    "http.method": "http.request.method",
    "http.status_code": "http.response.status_code",
    "http.url": "url.full",
    "http.route": "url.path",
    "git.branch": "vcs.branch",
    "git.commit": "vcs.commit",
    "git.operation": "vcs.operation",
    "k8s.namespace": "k8s.namespace.name",
    "k8s.pod": "k8s.pod.name",
    "k8s.deployment": "k8s.deployment.name",
    "argo.app": "argo.application.name",
}


_current_trace_id_ctx: ContextVar[str | None] = ContextVar("otel_current_trace_id", default=None)
_current_span_id_ctx: ContextVar[str | None] = ContextVar("otel_current_span_id", default=None)


class OTelTelemetryClient:
    """Emits OpenTelemetry traces and metrics via OTLP HTTP/JSON."""

    def __init__(
        self,
        endpoint: str = DEFAULT_OTEL_ENDPOINT,
        *,
        protocol: str | None = None,
        service_name: str = CONST_OTEL_SERVICE_NAME,
        service_version: str | None = None,
        enabled: bool = True,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        env_protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")
        self.protocol = (
            protocol
            or env_protocol
            or (
                "grpc"
                if (":4317" in self.endpoint or self.endpoint.startswith("grpc://"))
                else "http/json"
            )
        )
        self.service_name = service_name
        self.service_version = service_version or self._detect_version()
        self.host_name = platform.node() or "localhost"
        self.os_type = platform.system().lower() or "linux"
        self.enabled = enabled
        self._http_client: httpx2.Client | None = None
        self._grpc_exporter: Any = None
        self._executor: ContextPropagatingThreadPoolExecutor | None = None
        self._client_lock = threading.Lock()

        # Cache pre-computed resource attributes for zero-allocation reuse across all spans and metrics
        self._cached_resource_attributes: list[dict[str, Any]] = [
            {"key": "service.name", "value": {"stringValue": self.service_name}},
            {"key": "service.version", "value": {"stringValue": self.service_version}},
            {"key": "host.name", "value": {"stringValue": self.host_name}},
            {"key": "os.type", "value": {"stringValue": self.os_type}},
            {"key": "process.pid", "value": {"stringValue": str(os.getpid())}},
            {"key": "process.runtime.name", "value": {"stringValue": "cpython"}},
            {"key": "process.runtime.version", "value": {"stringValue": platform.python_version()}},
            {"key": "telemetry.sdk.name", "value": {"stringValue": "devops-cli-otel"}},
            {"key": "telemetry.sdk.language", "value": {"stringValue": "python"}},
        ]

    @staticmethod
    def _detect_version() -> str:
        try:
            from devops_cli import __version__

            return __version__
        except Exception:
            return "0.1.0"

    def _get_resource_attributes(self) -> list[dict[str, Any]]:
        """Return standardized OpenTelemetry resource attributes."""
        return self._cached_resource_attributes

    @property
    def current_trace_id(self) -> str | None:
        return _current_trace_id_ctx.get()

    @property
    def current_span_id(self) -> str | None:
        return _current_span_id_ctx.get()

    def inject_trace_context(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """Inject W3C traceparent (00-{trace_id}-{span_id}-01) into headers dict."""
        out = dict(headers or {})
        if not self.enabled:
            return out
        trace_id = _current_trace_id_ctx.get() or _generate_trace_id()
        span_id = _current_span_id_ctx.get() or _generate_span_id()
        out["traceparent"] = f"00-{trace_id}-{span_id}-01"
        return out

    def extract_trace_context(self, headers: dict[str, str]) -> tuple[str | None, str | None]:
        """Extract trace_id and parent span_id from incoming W3C traceparent header."""
        tp = headers.get("traceparent") or headers.get("Traceparent")
        if not tp:
            return None, None
        parts = tp.strip().split("-")
        if len(parts) >= 4 and parts[0] == "00":
            return parts[1], parts[2]
        return None, None

    def _build_metrics_payload(
        self,
        name: str,
        value: float,
        unit: str,
        timestamp_ns: int,
        attributes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build structured OTLP resourceMetrics payload."""
        data_point = {
            "timeUnixNano": str(timestamp_ns),
            "asDouble": float(value),
            "attributes": attributes,
        }
        metric_entry = {
            "name": name,
            "unit": unit,
            "gauge": {"dataPoints": [data_point]},
        }
        scope_entry = {
            "scope": {"name": "devops-cli.telemetry"},
            "metrics": [metric_entry],
        }
        return {
            "resourceMetrics": [
                {
                    "resource": {"attributes": self._get_resource_attributes()},
                    "scopeMetrics": [scope_entry],
                }
            ]
        }

    def _build_traces_payload(
        self,
        spans: list[dict[str, Any]],
        resource_attributes: list[dict[str, Any]] | None = None,
        scope_name: str = CONST_OTEL_SCOPE_NAME,
    ) -> dict[str, Any]:
        """Build structured OTLP resourceSpans payload."""
        res_attrs = resource_attributes or self._get_resource_attributes()
        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": res_attrs},
                    "scopeSpans": [{"scope": {"name": scope_name}, "spans": spans}],
                }
            ]
        }

    def record_metric(
        self,
        name: str,
        value: float,
        *,
        unit: str = CONST_OTEL_METRIC_UNIT_ONE,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Emit a metric data point to OTLP collector asynchronously."""
        if not self.enabled:
            return

        now_nano = int(time.time() * 1e9)
        attr_list = [
            {"key": k, "value": _to_otlp_any_value(v)} for k, v in (attributes or {}).items()
        ]
        payload = self._build_metrics_payload(name, value, unit, now_nano, attr_list)
        self._send_payload("/v1/metrics", payload)

    def increment_counter(
        self,
        name: str,
        amount: float = DEFAULT_OTEL_COUNTER_AMOUNT,
        *,
        unit: str = CONST_OTEL_METRIC_UNIT_ONE,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Convenience method to record an incremented counter metric."""
        self.record_metric(name, amount, unit=unit, attributes=attributes)

    @contextlib.contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        *,
        kind: str = CONST_OTEL_SPAN_KIND_INTERNAL,
        links: list[dict[str, Any]] | None = None,
        parent_context: dict[str, str] | None = None,
        parent_trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Generator[SpanHandle]:
        """Context manager to measure and emit a trace span with thread-safe context propagation."""
        if not self.enabled:
            yield SpanHandle("", {})
            return

        parent_trace = parent_trace_id or _current_trace_id_ctx.get()
        parent_id = parent_span_id or _current_span_id_ctx.get()

        if parent_context:
            ext_trace, ext_span = self.extract_trace_context(parent_context)
            if ext_trace:
                parent_trace = ext_trace
                parent_id = ext_span

        if not parent_trace:
            tp = os.environ.get("TRACEPARENT") or os.environ.get("traceparent")
            if tp:
                ext_trace, ext_span = self.extract_trace_context({"traceparent": tp})
                if ext_trace:
                    parent_trace = ext_trace
                    parent_id = ext_span

        trace_id = parent_trace or _generate_trace_id()
        span_id = _generate_span_id()
        start_nano = int(time.time() * 1e9)

        token_trace = _current_trace_id_ctx.set(trace_id)
        token_span = _current_span_id_ctx.set(span_id)

        attrs = dict(attributes or {})
        # Auto-normalize legacy attribute names to OTel semantic conventions
        for legacy_k, otel_k in _ATTRIBUTE_NORMALIZATION.items():
            if legacy_k in attrs and otel_k not in attrs:
                attrs[otel_k] = attrs[legacy_k]

        handle = SpanHandle(span_id, attrs)
        status_code = "STATUS_CODE_OK"
        error_msg = ""
        span_kind = _SPAN_KINDS.get(kind.lower(), "SPAN_KIND_INTERNAL")

        try:
            yield handle
        except BaseException as exc:
            exit_code = getattr(exc, "exit_code", getattr(exc, "code", None))
            if exit_code == 0:
                # Clean exit (e.g. typer.Exit(0), click.exceptions.Exit(0), SystemExit(0))
                status_code = "STATUS_CODE_OK"
                attrs.setdefault("cli.exit_code", 0)
                attrs.setdefault("process.exit.code", 0)
                raise

            status_code = "STATUS_CODE_ERROR"
            error_msg = str(exc) or exc.__class__.__name__
            if isinstance(exc, KeyboardInterrupt):
                attrs["error.type"] = "KeyboardInterrupt"
                attrs["cli.interrupted"] = True
                error_msg = "Command cancelled by user (SIGINT / KeyboardInterrupt)"
            else:
                attrs["error.type"] = exc.__class__.__name__
                attrs["error.message"] = str(exc)
                if exit_code is not None:
                    attrs["cli.exit_code"] = exit_code
                    attrs["process.exit.code"] = exit_code
            if not isinstance(exc, (SystemExit, KeyboardInterrupt)):
                handle.record_exception(exc)
            raise
        finally:
            end_nano = int(time.time() * 1e9)
            _current_trace_id_ctx.reset(token_trace)
            _current_span_id_ctx.reset(token_span)

            span_data: dict[str, Any] = {
                "traceId": trace_id,
                "spanId": span_id,
                "name": name,
                "kind": span_kind,
                "startTimeUnixNano": str(start_nano),
                "endTimeUnixNano": str(end_nano),
                "attributes": [
                    {"key": k, "value": _to_otlp_any_value(v)} for k, v in attrs.items()
                ],
                "status": {"code": status_code, "message": error_msg},
            }
            if handle._events:
                span_data["events"] = handle._events
            if handle._links:
                span_data["links"] = handle._links
            elif links:
                span_data["links"] = links
            if parent_id and parent_id != span_id:
                span_data["parentSpanId"] = parent_id

            payload = self._build_traces_payload([span_data])
            self._send_payload("/v1/traces", payload)

    def _get_grpc_exporter(self) -> Any:
        """Get or initialize thread-safe gRPC span exporter with persistent multiplexed connection."""
        with self._client_lock:
            if self._grpc_exporter is None:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                clean_ep = (
                    self.endpoint.replace("http://", "")
                    .replace("https://", "")
                    .replace("grpc://", "")
                )
                if not clean_ep:
                    clean_ep = "localhost:4317"
                insecure = not self.endpoint.startswith("https://")
                self._grpc_exporter = OTLPSpanExporter(
                    endpoint=clean_ep,
                    insecure=insecure,
                    timeout=DEFAULT_OTEL_HTTP_TIMEOUT_SECONDS,
                )
            return self._grpc_exporter

    def test_connection(
        self, timeout: float = DEFAULT_OTEL_TEST_TIMEOUT
    ) -> tuple[bool, str, float]:
        """Test reachability of the OTLP collector endpoint and measure latency."""
        start = time.perf_counter()
        if self.protocol == "grpc" or ":4317" in self.endpoint:
            try:
                import socket

                clean_ep = (
                    self.endpoint.replace("http://", "")
                    .replace("https://", "")
                    .replace("grpc://", "")
                )
                host, _, port_str = clean_ep.partition(":")
                port = int(port_str) if port_str else 4317
                sock = socket.create_connection((host, port), timeout=timeout)
                sock.close()
                elapsed_ms = (time.perf_counter() - start) * 1000
                return True, "gRPC connection OK", elapsed_ms
            except Exception as exc:
                logger.debug("OTel gRPC probe failed to %s: %s", self.endpoint, exc)
                elapsed_ms = (time.perf_counter() - start) * 1000
                return False, f"gRPC probe failed: {exc}", elapsed_ms

        try:
            url = f"{self.endpoint}/v1/traces"
            test_trace_id = _generate_trace_id()
            test_span_id = _generate_span_id()
            now_nano = str(int(time.time() * 1e9))
            ping_span = {
                "traceId": test_trace_id,
                "spanId": test_span_id,
                "name": "ping",
                "kind": "SPAN_KIND_INTERNAL",
                "startTimeUnixNano": now_nano,
                "endTimeUnixNano": now_nano,
                "status": {"code": "STATUS_CODE_OK"},
            }
            ping_res_attrs = [{"key": "service.name", "value": {"stringValue": "devops-cli-ping"}}]
            payload = self._build_traces_payload(
                [ping_span],
                resource_attributes=ping_res_attrs,
                scope_name="devops-cli.telemetry.ping",
            )
            import httpx2

            timeout_cfg = httpx2.Timeout(
                connect=1.0,
                read=timeout,
                write=timeout,
                pool=1.0,
            )
            with httpx2.Client(timeout=timeout_cfg) as client:
                res = client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - start) * 1000
                if res.status_code in (200, 202):
                    return True, f"HTTP {res.status_code} OK", elapsed_ms
                return False, f"HTTP {res.status_code} probe failed", elapsed_ms
        except Exception as exc:
            logger.debug("OTel connection probe failed to %s: %s", self.endpoint, exc)
            elapsed_ms = (time.perf_counter() - start) * 1000
            return False, "Connection probe failed", elapsed_ms

    def _get_executor(self) -> ContextPropagatingThreadPoolExecutor:
        """Get or initialize thread-safe background thread executor for non-blocking payload emission."""
        with self._client_lock:
            if self._executor is None:
                self._executor = ContextPropagatingThreadPoolExecutor(
                    max_workers=2,
                    thread_name_prefix="devops-otel",
                )
            return self._executor

    def _get_http_client(self) -> httpx2.Client:
        """Get or initialize thread-safe pooled HTTP client with short connect timeout."""
        with self._client_lock:
            if self._http_client is None or getattr(self._http_client, "is_closed", False):
                import httpx2

                timeout_cfg = httpx2.Timeout(
                    connect=1.0,
                    read=DEFAULT_OTEL_HTTP_TIMEOUT_SECONDS,
                    write=DEFAULT_OTEL_HTTP_TIMEOUT_SECONDS,
                    pool=1.0,
                )
                self._http_client = httpx2.Client(timeout=timeout_cfg)
            return self._http_client

    def _send_payload_sync(self, path: str, payload: dict[str, Any]) -> None:
        """Execute synchronous HTTP payload delivery."""
        if not self.enabled:
            return
        try:
            url = f"{self.endpoint}{path}"
            client = self._get_http_client()
            client.post(url, json=payload)
        except Exception as exc:
            logger.debug("OTel payload send failed to %s%s: %s", self.endpoint, path, exc)

    def _send_payload(self, path: str, payload: dict[str, Any]) -> None:
        """Send payload asynchronously via background thread executor to prevent blocking CLI execution."""
        if not self.enabled:
            return
        try:
            executor = self._get_executor()
            executor.submit(self._send_payload_sync, path, payload)
        except Exception as exc:
            logger.debug("Failed submitting OTel payload to executor: %s", exc)

    def shutdown(self, timeout_millis: int = DEFAULT_OTEL_SHUTDOWN_TIMEOUT_MS) -> None:
        """Cleanly close background executor, gRPC exporter, and pooled HTTP transport with bounded drain timeout."""
        with self._client_lock:
            if self._executor is not None:
                try:
                    self._executor.shutdown(wait=False, cancel_futures=True)
                except Exception as exc:
                    logger.debug("Failed closing OTel executor: %s", exc)
                self._executor = None
            if self._grpc_exporter is not None:
                try:
                    self._grpc_exporter.shutdown()
                except Exception as exc:
                    logger.debug("Failed shutting down gRPC exporter: %s", exc)
                self._grpc_exporter = None
            if self._http_client is not None:
                try:
                    self._http_client.close()
                except Exception as exc:
                    logger.debug("Failed closing OTel HTTP client: %s", exc)
                self._http_client = None


_GLOBAL_TRACER: OTelTelemetryClient | None = None
_GLOBAL_TRACER_LOCK = threading.Lock()


def get_tracer() -> OTelTelemetryClient:
    """Return the thread-safe global OTelTelemetryClient singleton instance."""
    global _GLOBAL_TRACER
    with _GLOBAL_TRACER_LOCK:
        if _GLOBAL_TRACER is None:
            endpoint = (
                os.getenv("DEVOPS_OTEL_ENDPOINT")
                or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
                or os.getenv("DEVOPS_CLI_OTEL_ENDPOINT")
            )
            env_enabled = os.getenv("DEVOPS_TELEMETRY_ENABLED")

            if endpoint is None or env_enabled is None:
                try:
                    from devops_cli.config.settings import load_settings

                    settings = load_settings()
                    telemetry_cfg = getattr(settings, "telemetry", None) or getattr(
                        settings, "otel", None
                    )
                    if endpoint is None and telemetry_cfg and hasattr(telemetry_cfg, "endpoint"):
                        endpoint = telemetry_cfg.endpoint
                    if env_enabled is None and telemetry_cfg and hasattr(telemetry_cfg, "enabled"):
                        cfg_enabled = telemetry_cfg.enabled
                    else:
                        cfg_enabled = True
                except Exception:
                    cfg_enabled = True
            else:
                cfg_enabled = True

            final_endpoint = endpoint or DEFAULT_OTEL_ENDPOINT
            if env_enabled is not None:
                is_enabled = env_enabled.lower() in ("true", "1")
            else:
                is_enabled = bool(cfg_enabled)

            service_name = os.getenv("OTEL_SERVICE_NAME", CONST_OTEL_SERVICE_NAME)
            protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")
            _GLOBAL_TRACER = OTelTelemetryClient(
                endpoint=final_endpoint,
                service_name=service_name,
                protocol=protocol,
                enabled=is_enabled,
            )
        return _GLOBAL_TRACER


def reset_tracer() -> None:
    """Reset the global tracer instance (used for testing)."""
    global _GLOBAL_TRACER
    _GLOBAL_TRACER = None


@contextlib.contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    *,
    kind: str = CONST_OTEL_SPAN_KIND_INTERNAL,
    links: list[dict[str, Any]] | None = None,
    parent_context: dict[str, str] | None = None,
    parent_trace_id: str | None = None,
    parent_span_id: str | None = None,
) -> Generator[SpanHandle]:
    """Convenience context manager for tracing a block of execution with span kind and optional links."""
    tracer = get_tracer()
    with tracer.span(
        name,
        attributes=attributes,
        kind=kind,
        links=links,
        parent_context=parent_context,
        parent_trace_id=parent_trace_id,
        parent_span_id=parent_span_id,
    ) as handle:
        yield handle


def record_metric(
    name: str,
    value: float,
    unit: str = CONST_OTEL_METRIC_UNIT_ONE,
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
    *,
    kind: str = CONST_OTEL_SPAN_KIND_INTERNAL,
) -> Callable[[F], F]:
    """Decorator to trace a function execution as an OpenTelemetry span."""

    def decorator(fn: F) -> F:
        span_name = name or f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_span(span_name, attributes=attributes, kind=kind):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def get_current_span_context() -> dict[str, str | None]:
    """Retrieve the current active span and trace IDs as a dictionary."""
    return {
        "trace_id": _current_trace_id_ctx.get(),
        "span_id": _current_span_id_ctx.get(),
    }


def shutdown_tracer(timeout_millis: int = DEFAULT_OTEL_SHUTDOWN_TIMEOUT_MS) -> None:
    """Flush and shut down global tracer instance with bounded timeout."""
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is not None:
        _GLOBAL_TRACER.shutdown(timeout_millis=timeout_millis)


atexit.register(shutdown_tracer)

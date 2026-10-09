"""Protocol-agnostic endpoint readiness and health probing engine."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from typing import Any

import httpcore2
import httpx2

from devops_cli.exceptions import SSRFBlockedError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel, VettingBackend
from devops_cli.sandbox.models import (
    EndpointProbeResult,
    ProbeProtocol,
    ProbeStatus,
    SandboxInstance,
    SandboxProbeReport,
)
from devops_cli.telemetry.context import (
    extract_traceparent,
    generate_trace_id,
    inject_traceparent_headers,
)
from devops_cli.telemetry.tracer import get_current_span_context, trace_span

_MAX_ERROR_LEN = 256
_DEFAULT_HTTP_PATHS = ["/healthz", "/health", "/ready", "/live"]
_SAFE_SCHEMA_PATHS = (
    "/health",
    "/healthz",
    "/ready",
    "/live",
    "/status",
    "/version",
    "/info",
    "/ping",
)


def _truncate(text: Any, max_len: int = _MAX_ERROR_LEN) -> str:
    """Safely truncate strings to prevent log bloat and injection."""
    s = str(text)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def _tcp_result(
    host: str, port: int, status: ProbeStatus, latency_ms: float, message: str
) -> EndpointProbeResult:
    """A TCP probe result for `host:port`."""
    return EndpointProbeResult(
        protocol=ProbeProtocol.TCP,
        target=f"{host}:{port}",
        status=status,
        latency_ms=round(latency_ms, 2),
        message=_truncate(message),
        details={"host": host, "port": port},
    )


def probe_tcp(host: str, port: int, timeout: float = 5.0) -> EndpointProbeResult:
    """Probe TCP socket listener reachability and measure connection latency.

    The host is resolved once and every answer vetted at the private egress level, which refuses
    cloud metadata addresses; each vetted address is then dialled in turn, never the name.
    """
    backend = VettingBackend(EgressLevel.PRIVATE)
    start = time.perf_counter()
    try:
        backend.connect_tcp(host, port, timeout=timeout).close()
    except SSRFBlockedError as exc:
        return _tcp_result(host, port, ProbeStatus.FAIL, 0.0, exc.message)
    except httpcore2.ConnectTimeout as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        message = f"TCP connection timeout after {timeout}s: {exc}"
        return _tcp_result(host, port, ProbeStatus.TIMEOUT, elapsed, message)
    except httpcore2.ConnectError as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        return _tcp_result(host, port, ProbeStatus.FAIL, elapsed, f"TCP connection failed: {exc}")
    latency = (time.perf_counter() - start) * 1000.0
    return _tcp_result(host, port, ProbeStatus.PASS, latency, "TCP connection established")


def probe_http(
    url: str,
    expected_statuses: list[int] | None = None,
    regex: str | None = None,
    timeout: float = 5.0,
    latency_budget_ms: float | None = None,
) -> EndpointProbeResult:
    """Probe HTTP/REST endpoint asserting status code, regex response, and latency budget.

    `timeout` bounds every phase of the request, the connect included, as it bounds `probe_tcp`.
    """
    expected = expected_statuses or [200]
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=0.0,
            message=_truncate(f"Invalid URL scheme '{parsed.scheme}'; expected http or https"),
        )

    start = time.perf_counter()
    req_headers = inject_traceparent_headers(
        {"User-Agent": "devops-cli-prober"},
        auto_generate=True,
    )
    trace_info = extract_traceparent(req_headers.get("traceparent"))
    trace_details: dict[str, Any] = {}
    if req_headers.get("traceparent"):
        trace_details["traceparent"] = req_headers["traceparent"]
    if trace_info:
        trace_details["trace_id"] = trace_info.get("trace_id")
        trace_details["span_id"] = trace_info.get("parent_span_id")

    try:
        with new_http_client(level=EgressLevel.PRIVATE, timeout=httpx2.Timeout(timeout)) as client:
            resp = client.get(url, headers=req_headers)
            latency = (time.perf_counter() - start) * 1000.0
            return _evaluate_http_response(
                url=url,
                status_code=resp.status_code,
                body=resp.text,
                latency=latency,
                expected=expected,
                regex=regex,
                latency_budget_ms=latency_budget_ms,
                trace_details=trace_details,
            )
    except SSRFBlockedError as exc:
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=0.0,
            message=_truncate(exc.message),
            details=trace_details,
        )
    except httpx2.InvalidURL as exc:
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=0.0,
            message=_truncate(f"Invalid probe target: {exc}"),
            details=trace_details,
        )
    except httpx2.TimeoutException as exc:
        latency = (time.perf_counter() - start) * 1000.0
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.TIMEOUT,
            latency_ms=round(latency, 2),
            message=_truncate(f"HTTP probe timed out after {timeout}s: {exc}"),
            details=trace_details,
        )
    except (httpx2.RequestError, OSError) as exc:
        latency = (time.perf_counter() - start) * 1000.0
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=round(latency, 2),
            message=_truncate(f"HTTP probe connection error: {exc}"),
            details=trace_details,
        )


def _evaluate_http_response(
    url: str,
    status_code: int,
    body: str,
    latency: float,
    expected: list[int],
    regex: str | None,
    latency_budget_ms: float | None,
    trace_details: dict[str, Any] | None = None,
) -> EndpointProbeResult:
    """Evaluate HTTP probe invariants: status code, latency SLA, and regex matching."""
    base_details = dict(trace_details or {})
    if status_code not in expected:
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=round(latency, 2),
            status_code=status_code,
            message=f"HTTP status {status_code} not in expected {expected}",
            details=base_details,
        )

    if latency_budget_ms is not None and latency > latency_budget_ms:
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=round(latency, 2),
            status_code=status_code,
            message=f"Latency SLA exceeded: {latency:.1f}ms > {latency_budget_ms:.1f}ms budget",
            details=base_details,
        )

    if regex:
        if len(regex) > _MAX_ERROR_LEN:
            base_details["body_preview"] = _truncate(body, 128)
            return EndpointProbeResult(
                protocol=ProbeProtocol.HTTP,
                target=url,
                status=ProbeStatus.FAIL,
                latency_ms=round(latency, 2),
                status_code=status_code,
                message=f"Regex exceeds maximum length of {_MAX_ERROR_LEN} characters",
                details=base_details,
            )
        try:
            matched = bool(re.search(regex, body[:8192]))
        except re.error as exc:
            base_details["body_preview"] = _truncate(body, 128)
            return EndpointProbeResult(
                protocol=ProbeProtocol.HTTP,
                target=url,
                status=ProbeStatus.FAIL,
                latency_ms=round(latency, 2),
                status_code=status_code,
                message=_truncate(f"Invalid regex assertion pattern: {exc}"),
                details=base_details,
            )
        if not matched:
            base_details["body_preview"] = _truncate(body, 128)
            return EndpointProbeResult(
                protocol=ProbeProtocol.HTTP,
                target=url,
                status=ProbeStatus.FAIL,
                latency_ms=round(latency, 2),
                status_code=status_code,
                message=_truncate(f"Response body failed regex assertion: {regex}"),
                details=base_details,
            )

    base_details["body_preview"] = _truncate(body, 64)
    return EndpointProbeResult(
        protocol=ProbeProtocol.HTTP,
        target=url,
        status=ProbeStatus.PASS,
        latency_ms=round(latency, 2),
        status_code=status_code,
        message=f"HTTP {status_code} OK",
        details=base_details,
    )


def probe_openapi(
    base_url: str,
    schema_path: str = "/openapi.json",
    timeout: float = 5.0,
) -> list[EndpointProbeResult]:
    """Discover and parse OpenAPI schema, probing discovered safe GET endpoints."""
    clean_base = base_url.rstrip("/")
    schema_url = f"{clean_base}/{schema_path.lstrip('/')}"
    schema_res = probe_http(schema_url, expected_statuses=[200], timeout=timeout)
    schema_res.protocol = ProbeProtocol.OPENAPI

    if schema_res.status != ProbeStatus.PASS:
        schema_res.message = f"OpenAPI schema fetch failed at {schema_url}"
        return [schema_res]

    results: list[EndpointProbeResult] = [schema_res]
    discovered_endpoints = _extract_safe_openapi_endpoints(clean_base, schema_url, timeout)
    for ep_url, ep_path in discovered_endpoints:
        ep_res = probe_http(ep_url, expected_statuses=[200, 204], timeout=timeout)
        ep_res.protocol = ProbeProtocol.OPENAPI
        ep_res.details["path"] = ep_path
        results.append(ep_res)

    return results


def _extract_safe_openapi_endpoints(
    clean_base: str, schema_url: str, timeout: float
) -> list[tuple[str, str]]:
    """Parse OpenAPI schema and select safe, parameter-free GET endpoints."""
    try:
        with new_http_client(level=EgressLevel.PRIVATE, timeout=httpx2.Timeout(timeout)) as client:
            resp = client.get(schema_url, headers={"User-Agent": "devops-cli-prober"})
            if resp.status_code != 200:
                return []
            data = resp.json()
        paths = data.get("paths", {})
        endpoints: list[tuple[str, str]] = []
        for path_str, path_item in paths.items():
            if "{" in path_str:
                continue
            if "get" in path_item or any(path_str.endswith(s) for s in _SAFE_SCHEMA_PATHS):
                endpoints.append((f"{clean_base}/{path_str.lstrip('/')}", path_str))
            if len(endpoints) >= 5:
                break
        return endpoints
    except httpx2.RequestError, json.JSONDecodeError, ValueError, OSError:
        return []


def probe_grpc(
    host: str, port: int, service: str = "", timeout: float = 5.0
) -> EndpointProbeResult:
    """Probe gRPC server reachability and assert listener availability."""
    target = f"{host}:{port}"
    tcp_res = probe_tcp(host, port, timeout=timeout)
    if tcp_res.status != ProbeStatus.PASS:
        return EndpointProbeResult(
            protocol=ProbeProtocol.GRPC,
            target=target,
            status=tcp_res.status,
            latency_ms=tcp_res.latency_ms,
            message=_truncate(f"gRPC listener unreachable: {tcp_res.message}"),
            details={"host": host, "port": port, "service": service},
        )

    return EndpointProbeResult(
        protocol=ProbeProtocol.GRPC,
        target=target,
        status=ProbeStatus.PASS,
        latency_ms=tcp_res.latency_ms,
        message=f"gRPC listener active on {target}"
        + (f" for service '{service}'" if service else ""),
        details={"host": host, "port": port, "service": service},
    )


def _resolve_probe_target(
    target_or_instance: SandboxInstance | str,
) -> tuple[str | None, str, list[httpx2.Origin]]:
    """Resolve target instance ID, display name, and network endpoints."""
    if isinstance(target_or_instance, SandboxInstance):
        instance_id = target_or_instance.instance_id
        target_display = target_or_instance.name or target_or_instance.instance_id
        endpoints = [
            httpx2.Origin(httpx2.URL(scheme="http", host="127.0.0.1", port=b.host_port))
            for b in target_or_instance.port_bindings
        ]
        return instance_id, target_display, endpoints

    target_display = str(target_or_instance)
    parsed = _parse_target_endpoint(target_display)
    return None, target_display, [parsed]


def _resolve_report_trace_id(
    active_trace_id: str | None, results: list[EndpointProbeResult]
) -> str:
    """Resolve active trace ID from span context, probe results, or generator."""
    if active_trace_id:
        return active_trace_id
    for r in results:
        if r.details and "trace_id" in r.details:
            return str(r.details["trace_id"])
    return generate_trace_id()


def _compute_overall_probe_status(passed: int, failed: int) -> ProbeStatus:
    """Determine aggregate status based on passed and failed probe counts."""
    if passed > 0 and failed == 0:
        return ProbeStatus.PASS
    if failed > 0:
        return ProbeStatus.FAIL
    return ProbeStatus.SKIPPED


def run_sandbox_probes(
    target_or_instance: SandboxInstance | str,
    protocols: list[ProbeProtocol] | None = None,
    http_paths: list[str] | None = None,
    expected_statuses: list[int] | None = None,
    regex: str | None = None,
    timeout: float = 5.0,
    latency_budget_ms: float | None = None,
) -> SandboxProbeReport:
    """Orchestrate protocol-agnostic probing matrix across a sandbox or raw target."""
    selected_protocols = protocols or [ProbeProtocol.TCP, ProbeProtocol.HTTP]
    start_time = time.perf_counter()
    instance_id, target_display, target_endpoints = _resolve_probe_target(target_or_instance)

    all_results: list[EndpointProbeResult] = []
    active_trace_id: str | None = None

    with trace_span(
        "sandbox.probe",
        attributes={
            "sandbox.target": target_display,
            "sandbox.instance_id": str(instance_id or ""),
        },
    ):
        ctx = get_current_span_context()
        active_trace_id = ctx.get("trace_id") if ctx else None

        for origin in target_endpoints:
            _dispatch_probes_for_port(
                host=origin.host,
                port=origin.port or 80,
                protocols=selected_protocols,
                http_paths=http_paths or _DEFAULT_HTTP_PATHS,
                expected_statuses=expected_statuses,
                regex=regex,
                timeout=timeout,
                latency_budget_ms=latency_budget_ms,
                collector=all_results,
            )

    duration = time.perf_counter() - start_time
    passed = sum(1 for r in all_results if r.status == ProbeStatus.PASS)
    failed = sum(1 for r in all_results if r.status in (ProbeStatus.FAIL, ProbeStatus.TIMEOUT))

    return SandboxProbeReport(
        instance_id=instance_id,
        target=target_display,
        overall_status=_compute_overall_probe_status(passed, failed),
        total_probes=len(all_results),
        passed_probes=passed,
        failed_probes=failed,
        duration_seconds=round(duration, 3),
        trace_id=_resolve_report_trace_id(active_trace_id, all_results),
        results=all_results,
    )


def _parse_target_endpoint(target_str: str) -> httpx2.Origin:
    """Parse raw host:port or URL string into an httpx2.Origin."""
    from devops_cli.exceptions import ValidationError
    from devops_cli.http.urls import get_url_origin, read_url_or_authority

    parsed = read_url_or_authority(target_str)
    if parsed is None or not parsed.hostname:
        raise ValidationError(f"Target '{target_str}' names no valid host.", field="target")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(
            f"Target '{target_str}' has invalid port: {exc}", field="target"
        ) from exc

    if parsed.scheme:
        origin = get_url_origin(target_str)
        if origin is None:
            raise ValidationError(
                f"Target '{target_str}' is not a valid URL or host:port.", field="target"
            )
        return origin

    port = port or 80
    return httpx2.Origin(httpx2.URL(scheme="http", host=parsed.hostname, port=port))


def _dispatch_probes_for_port(
    host: str,
    port: int,
    protocols: list[ProbeProtocol],
    http_paths: list[str],
    expected_statuses: list[int] | None,
    regex: str | None,
    timeout: float,
    latency_budget_ms: float | None,
    collector: list[EndpointProbeResult],
) -> None:
    """Execute configured protocols for a specific host:port endpoint."""
    if ProbeProtocol.TCP in protocols:
        collector.append(probe_tcp(host, port, timeout=timeout))

    if ProbeProtocol.HTTP in protocols:
        for path in http_paths:
            url = f"http://{host}:{port}/{path.lstrip('/')}"
            collector.append(
                probe_http(
                    url,
                    expected_statuses=expected_statuses,
                    regex=regex,
                    timeout=timeout,
                    latency_budget_ms=latency_budget_ms,
                )
            )

    if ProbeProtocol.OPENAPI in protocols:
        base_url = f"http://{host}:{port}"
        collector.extend(probe_openapi(base_url, timeout=timeout))

    if ProbeProtocol.GRPC in protocols:
        collector.append(probe_grpc(host, port, timeout=timeout))


__all__ = [
    "probe_grpc",
    "probe_http",
    "probe_openapi",
    "probe_tcp",
    "run_sandbox_probes",
]

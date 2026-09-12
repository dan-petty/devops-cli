"""Protocol-agnostic endpoint readiness and health probing engine."""

from __future__ import annotations

import json
import re
import socket
import time
import urllib.parse
from typing import Any

import httpx2

from devops_cli.sandbox.models import (
    EndpointProbeResult,
    ProbeProtocol,
    ProbeStatus,
    SandboxInstance,
    SandboxProbeReport,
)

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


def probe_tcp(host: str, port: int, timeout: float = 5.0) -> EndpointProbeResult:
    """Probe TCP socket listener reachability and measure connection latency."""
    target = f"{host}:{port}"
    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.connect((host, port))
        latency = (time.perf_counter() - start) * 1000.0
        return EndpointProbeResult(
            protocol=ProbeProtocol.TCP,
            target=target,
            status=ProbeStatus.PASS,
            latency_ms=round(latency, 2),
            message="TCP connection established",
            details={"host": host, "port": port},
        )
    except TimeoutError as exc:
        latency = (time.perf_counter() - start) * 1000.0
        return EndpointProbeResult(
            protocol=ProbeProtocol.TCP,
            target=target,
            status=ProbeStatus.TIMEOUT,
            latency_ms=round(latency, 2),
            message=_truncate(f"TCP connection timeout after {timeout}s: {exc}"),
            details={"host": host, "port": port},
        )
    except OSError as exc:
        latency = (time.perf_counter() - start) * 1000.0
        return EndpointProbeResult(
            protocol=ProbeProtocol.TCP,
            target=target,
            status=ProbeStatus.FAIL,
            latency_ms=round(latency, 2),
            message=_truncate(f"TCP connection failed: {exc}"),
            details={"host": host, "port": port},
        )
    finally:
        sock.close()


def probe_http(
    url: str,
    expected_statuses: list[int] | None = None,
    regex: str | None = None,
    timeout: float = 5.0,
    latency_budget_ms: float | None = None,
) -> EndpointProbeResult:
    """Probe HTTP/REST endpoint asserting status code, regex response, and latency budget."""
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
    try:
        with httpx2.Client(timeout=timeout) as client:
            resp = client.get(url, headers={"User-Agent": "devops-cli-prober"})
            latency = (time.perf_counter() - start) * 1000.0
            return _evaluate_http_response(
                url=url,
                status_code=resp.status_code,
                body=resp.text,
                latency=latency,
                expected=expected,
                regex=regex,
                latency_budget_ms=latency_budget_ms,
            )
    except httpx2.TimeoutException as exc:
        latency = (time.perf_counter() - start) * 1000.0
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.TIMEOUT,
            latency_ms=round(latency, 2),
            message=_truncate(f"HTTP probe timed out after {timeout}s: {exc}"),
        )
    except (httpx2.RequestError, OSError) as exc:
        latency = (time.perf_counter() - start) * 1000.0
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=round(latency, 2),
            message=_truncate(f"HTTP probe connection error: {exc}"),
        )


def _evaluate_http_response(
    url: str,
    status_code: int,
    body: str,
    latency: float,
    expected: list[int],
    regex: str | None,
    latency_budget_ms: float | None,
) -> EndpointProbeResult:
    """Evaluate HTTP probe invariants: status code, latency SLA, and regex matching."""
    if status_code not in expected:
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=round(latency, 2),
            status_code=status_code,
            message=f"HTTP status {status_code} not in expected {expected}",
        )

    if latency_budget_ms is not None and latency > latency_budget_ms:
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=round(latency, 2),
            status_code=status_code,
            message=f"Latency SLA exceeded: {latency:.1f}ms > {latency_budget_ms:.1f}ms budget",
        )

    if regex and not re.search(regex, body):
        return EndpointProbeResult(
            protocol=ProbeProtocol.HTTP,
            target=url,
            status=ProbeStatus.FAIL,
            latency_ms=round(latency, 2),
            status_code=status_code,
            message=_truncate(f"Response body failed regex assertion: {regex}"),
            details={"body_preview": _truncate(body, 128)},
        )

    return EndpointProbeResult(
        protocol=ProbeProtocol.HTTP,
        target=url,
        status=ProbeStatus.PASS,
        latency_ms=round(latency, 2),
        status_code=status_code,
        message=f"HTTP {status_code} OK",
        details={"body_preview": _truncate(body, 64)},
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
        with httpx2.Client(timeout=timeout) as client:
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

    instance_id: str | None = None
    target_endpoints: list[tuple[str, int]] = []

    if isinstance(target_or_instance, SandboxInstance):
        instance_id = target_or_instance.instance_id
        target_display = target_or_instance.name or target_or_instance.instance_id
        for binding in target_or_instance.port_bindings:
            target_endpoints.append(("127.0.0.1", binding.host_port))
    else:
        target_display = str(target_or_instance)
        parsed = _parse_target_endpoint(target_display)
        target_endpoints.append(parsed)

    all_results: list[EndpointProbeResult] = []
    for host, port in target_endpoints:
        _dispatch_probes_for_port(
            host=host,
            port=port,
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
    overall = (
        ProbeStatus.PASS
        if (passed > 0 and failed == 0)
        else (ProbeStatus.FAIL if failed > 0 else ProbeStatus.SKIPPED)
    )

    return SandboxProbeReport(
        instance_id=instance_id,
        target=target_display,
        overall_status=overall,
        total_probes=len(all_results),
        passed_probes=passed,
        failed_probes=failed,
        duration_seconds=round(duration, 3),
        results=all_results,
    )


def _parse_target_endpoint(target_str: str) -> tuple[str, int]:
    """Parse raw host:port or URL string into host and port."""
    if "://" in target_str:
        parsed = urllib.parse.urlparse(target_str)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return host, port
    if ":" in target_str:
        parts = target_str.split(":", 1)
        return parts[0], int(parts[1])
    return target_str, 80


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

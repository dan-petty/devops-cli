"""Submodule-aligned test suite for sandbox endpoint readiness and health probing subsystem."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable, Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions import ValidationError
from devops_cli.exceptions.sandbox import SandboxNotFoundError
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    EndpointProbeResult,
    PortBinding,
    ProbeProtocol,
    ProbeStatus,
    SandboxInstance,
    SandboxProbeReport,
    SandboxStatus,
)
from devops_cli.sandbox.probe import (
    probe_grpc,
    probe_http,
    probe_openapi,
    probe_tcp,
    run_sandbox_probes,
)
from tests.support.fakes.dns import DnsFake
from tests.support.waits import POLL_INTERVAL_SECONDS

# ─────────────────────────────────────────────────────────────────────────────
# 1. Models Serialization Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_probe_models_serialization() -> None:
    """Test serialization and deserialization of probe models."""
    result = EndpointProbeResult(
        protocol=ProbeProtocol.HTTP,
        target="http://127.0.0.1:8080/healthz",
        status=ProbeStatus.PASS,
        latency_ms=12.4,
        status_code=200,
        message="HTTP 200 OK",
        details={"path": "/healthz"},
        timestamp="2026-09-12T12:00:00Z",
    )
    dumped = result.model_dump()
    assert dumped["protocol"] == "http"
    assert dumped["status"] == "pass"
    assert dumped["latency_ms"] == 12.4
    assert dumped["status_code"] == 200

    report = SandboxProbeReport(
        instance_id="sandbox-test-107",
        target="127.0.0.1:8080",
        overall_status=ProbeStatus.PASS,
        total_probes=1,
        passed_probes=1,
        failed_probes=0,
        duration_seconds=0.015,
        results=[result],
        created_at="2026-09-12T12:00:00Z",
    )
    report_dump = report.model_dump()
    assert report_dump["instance_id"] == "sandbox-test-107"
    assert report_dump["overall_status"] == "pass"
    assert len(report_dump["results"]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 2. TCP Probing Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_probe_tcp_success() -> None:
    """Test TCP socket probe against an active local listener."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    try:
        res = probe_tcp(host, port, timeout=2.0)
        assert res.protocol == ProbeProtocol.TCP
        assert res.status == ProbeStatus.PASS
        assert res.latency_ms > 0
        assert f"{host}:{port}" in res.target
    finally:
        server.close()


def test_probe_tcp_connection_refused(refusing_port: int) -> None:
    """Test TCP probe against a port that refuses connections."""
    res = probe_tcp("127.0.0.1", refusing_port, timeout=1.0)
    assert res.protocol == ProbeProtocol.TCP
    assert res.status == ProbeStatus.FAIL
    assert res.message is not None
    assert len(res.message) <= 256


def test_probe_tcp_timeout() -> None:
    """Test TCP probe timeout handling."""
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = TimeoutError("timed out")
        mock_sock_cls.return_value = mock_sock

        res = probe_tcp("127.0.0.1", 9999, timeout=0.1)
        assert res.status == ProbeStatus.TIMEOUT
        assert "timeout" in (res.message or "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# 3. HTTP Probing Tests
# ─────────────────────────────────────────────────────────────────────────────


class _MockHTTPHandler(BaseHTTPRequestHandler):
    request_headers: ClassVar[list[dict[str, str]]] = []

    def do_GET(self) -> None:
        self.request_headers.append(dict(self.headers))
        if self.path in ("/healthz", "/health", "/ready"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"catalog"}')
        elif self.path == "/error":
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Internal Server Error")
        elif self.path == "/openapi.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            schema = {
                "openapi": "3.0.0",
                "info": {"title": "Test API", "version": "1.0.0"},
                "paths": {
                    "/healthz": {"get": {"summary": "Health check"}},
                    "/version": {"get": {"summary": "Version check"}},
                },
            }
            self.wfile.write(json.dumps(schema).encode("utf-8"))
        elif self.path == "/version":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"version":"1.0.0"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass  # suppress logging during test execution


@pytest.fixture
def http_server() -> Generator[str]:
    """Spin up an ephemeral local HTTP test server."""
    _MockHTTPHandler.request_headers.clear()
    server = HTTPServer(("127.0.0.1", 0), _MockHTTPHandler)
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": POLL_INTERVAL_SECONDS}, daemon=True
    )
    thread.start()
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


def test_probe_http_success(http_server: str) -> None:
    """Test HTTP probe with matching status code and regex assertion."""
    url = f"{http_server}/healthz"
    res = probe_http(url, expected_statuses=[200], regex=r'"status":\s*"ok"', timeout=2.0)
    assert res.protocol == ProbeProtocol.HTTP
    assert res.status == ProbeStatus.PASS
    assert res.status_code == 200
    assert res.latency_ms > 0


def test_probe_http_status_mismatch(http_server: str) -> None:
    """Test HTTP probe when server returns unexpected error code."""
    url = f"{http_server}/error"
    res = probe_http(url, expected_statuses=[200], timeout=2.0)
    assert res.protocol == ProbeProtocol.HTTP
    assert res.status == ProbeStatus.FAIL
    assert res.status_code == 500
    assert "status" in (res.message or "").lower()


def test_probe_http_regex_mismatch(http_server: str) -> None:
    """Test HTTP probe when response body does not match regex."""
    url = f"{http_server}/healthz"
    res = probe_http(url, expected_statuses=[200], regex=r'"status":\s*"unhealthy"', timeout=2.0)
    assert res.protocol == ProbeProtocol.HTTP
    assert res.status == ProbeStatus.FAIL
    assert "regex" in (res.message or "").lower()


def test_probe_http_latency_sla_exceeded(http_server: str) -> None:
    """Test HTTP probe failing SLA when latency budget is exceeded."""
    url = f"{http_server}/healthz"
    res = probe_http(url, latency_budget_ms=0.0001, timeout=2.0)
    assert res.protocol == ProbeProtocol.HTTP
    assert res.status == ProbeStatus.FAIL
    assert "sla" in (res.message or "").lower()


def test_probe_http_unreachable(refusing_port: int) -> None:
    """Test HTTP probe against unreachable server."""
    res = probe_http(f"http://127.0.0.1:{refusing_port}/healthz", timeout=1.0)
    assert res.protocol == ProbeProtocol.HTTP
    assert res.status == ProbeStatus.FAIL
    assert res.message is not None


# ─────────────────────────────────────────────────────────────────────────────
# 4. OpenAPI Probing Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_probe_openapi_schema_success(http_server: str) -> None:
    """Test OpenAPI schema crawler discovering and executing safe GET probes."""
    results = probe_openapi(http_server, schema_path="/openapi.json", timeout=2.0)
    assert len(results) >= 2  # schema probe itself + /healthz + /version
    # Verify the schema was retrieved successfully
    schema_res = results[0]
    assert schema_res.protocol == ProbeProtocol.OPENAPI
    assert schema_res.status == ProbeStatus.PASS
    # Verify discovered endpoints
    discovered_paths = [r.details.get("path") for r in results if "path" in r.details]
    assert "/healthz" in discovered_paths or "/version" in discovered_paths


def test_probe_openapi_missing(http_server: str) -> None:
    """Test OpenAPI crawler against missing schema."""
    results = probe_openapi(http_server, schema_path="/nonexistent.json", timeout=2.0)
    assert len(results) == 1
    assert results[0].protocol == ProbeProtocol.OPENAPI
    assert results[0].status == ProbeStatus.FAIL


# ─────────────────────────────────────────────────────────────────────────────
# 5. gRPC Probing Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_probe_grpc_reachability() -> None:
    """Test gRPC health probing asserting socket connection and health protocol."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    try:
        res = probe_grpc(host, port, service="test.Service", timeout=2.0)
        assert res.protocol == ProbeProtocol.GRPC
        assert res.status in (ProbeStatus.PASS, ProbeStatus.SKIPPED)
        assert res.latency_ms >= 0
    finally:
        server.close()


def test_probe_grpc_unreachable(refusing_port: int) -> None:
    """Test gRPC probe on unreachable host:port."""
    res = probe_grpc("127.0.0.1", refusing_port, timeout=1.0)
    assert res.protocol == ProbeProtocol.GRPC
    assert res.status == ProbeStatus.FAIL


# ─────────────────────────────────────────────────────────────────────────────
# 6. High-Level Orchestrator Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_run_sandbox_probes_with_instance(http_server: str, tmp_path: Path) -> None:
    """Test run_sandbox_probes against a SandboxInstance object."""
    port = int(http_server.split(":")[-1])
    instance = SandboxInstance(
        instance_id="sandbox-test-instance-1",
        container_id="cont-123456",
        name="web-svc",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=80, host_port=port, protocol="tcp")],
        workspace_dir=str(tmp_path / "workspace"),
        created_at="2026-09-12T12:00:00Z",
        uptime_seconds=60.0,
    )

    report = run_sandbox_probes(
        instance,
        protocols=[ProbeProtocol.TCP, ProbeProtocol.HTTP],
        http_paths=["/healthz"],
        timeout=2.0,
    )
    assert report.instance_id == "sandbox-test-instance-1"
    assert report.overall_status == ProbeStatus.PASS
    assert report.total_probes >= 2
    assert report.passed_probes >= 2
    assert report.failed_probes == 0


def test_run_sandbox_probes_with_raw_url(http_server: str) -> None:
    """Test run_sandbox_probes against raw host:port or URL string."""
    report = run_sandbox_probes(
        http_server,
        protocols=[ProbeProtocol.HTTP],
        http_paths=["/healthz"],
        timeout=2.0,
    )
    assert report.overall_status == ProbeStatus.PASS
    assert report.passed_probes >= 1


# ─────────────────────────────────────────────────────────────────────────────
# 7. CLI Command Tests (`devops sandbox probe`)
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_sandbox_probe_dry_run(cli: Callable[..., Any]) -> None:
    """Test sandbox probe in dry-run mode."""
    result = cli("sandbox", "probe", "sandbox-123", "--dry-run")
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "probe" in result.output.lower()


def test_cli_sandbox_probe_by_instance_id_success(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], http_server: str
) -> None:
    """Test sandbox probe CLI command against existing sandbox instance."""
    register_sandbox("sandbox-test-123", host_ports=[int(http_server.split(":")[-1])])

    result = cli("sandbox", "probe", "sandbox-test-123", "-p", "tcp,http", "--path", "/healthz")

    assert result.exit_code == 0
    assert "PASS" in result.output
    assert "/healthz" in result.output


def test_cli_sandbox_probe_json_output(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], http_server: str
) -> None:
    """Test sandbox probe CLI command with JSON output format."""
    port = int(http_server.split(":")[-1])
    register_sandbox("sandbox-json-123", host_ports=[port])

    result = cli("sandbox", "probe", "sandbox-json-123", "-p", "tcp", "--json")

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert (parsed["instance_id"], parsed["overall_status"]) == ("sandbox-json-123", "pass")
    assert [(r["protocol"], r["target"]) for r in parsed["results"]] == [
        ("tcp", f"127.0.0.1:{port}")
    ]


def test_cli_sandbox_probe_instance_not_found(cli: Callable[..., Any], docker_daemon: Any) -> None:
    """Test sandbox probe with non-existent instance identifier."""
    result = cli("sandbox", "probe", "nonexistent-instance")

    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_engine_probe_reports_on_a_registered_instance(
    register_sandbox: Callable[..., SandboxInstance], http_server: str
) -> None:
    """The engine probes the published ports of a registered sandbox."""
    register_sandbox("sandbox-probe-unit-1", host_ports=[int(http_server.split(":")[-1])])

    report = WorkloadSandboxEngine().probe("sandbox-probe-unit-1", protocols=[ProbeProtocol.TCP])

    assert (report.instance_id, report.overall_status, report.total_probes) == (
        "sandbox-probe-unit-1",
        ProbeStatus.PASS,
        1,
    )


def test_engine_probe_raises_when_not_found() -> None:
    """Test WorkloadSandboxEngine.probe raises SandboxNotFoundError if not found."""
    with pytest.raises(SandboxNotFoundError) as raised:
        WorkloadSandboxEngine().probe("missing-id")
    assert raised.value.error_code == "SANDBOX_NOT_FOUND_ERROR"


@pytest.mark.parametrize(
    ("target", "probed_url"),
    [
        ("127.0.0.1:{port}", "http://127.0.0.1:{port}/x"),
        ("localhost:{port}", "http://localhost:{port}/x"),
        ("[::1]:{port}", "http://[::1]:{port}/x"),
        ("HTTPS://127.0.0.1:{port}", "https://127.0.0.1:{port}/x"),
    ],
)
def test_a_probe_target_names_its_scheme_host_and_port(
    refusing_port: int, target: str, probed_url: str
) -> None:
    """A target is a URL or host:port; without a scheme it is http."""
    report = run_sandbox_probes(
        target.format(port=refusing_port),
        protocols=[ProbeProtocol.HTTP],
        http_paths=["/x"],
        timeout=0.5,
    )

    assert [result.target for result in report.results] == [probed_url.format(port=refusing_port)]


@pytest.mark.parametrize("invalid_target", ["http://:8080", "example.com:abc"])
def test_a_probe_target_without_a_host_or_with_a_bad_port_is_refused(invalid_target: str) -> None:
    """A target that names no host, or a port that is no number, fails validation."""
    with pytest.raises(ValidationError) as exc_info:
        run_sandbox_probes(invalid_target, protocols=[ProbeProtocol.TCP])
    assert invalid_target in str(exc_info.value)


def test_run_sandbox_probes_with_openapi_and_grpc(refusing_port: int) -> None:
    """Test run_sandbox_probes with OPENAPI and GRPC protocols."""
    report = run_sandbox_probes(
        f"127.0.0.1:{refusing_port}",
        protocols=[ProbeProtocol.OPENAPI, ProbeProtocol.GRPC],
        timeout=1.0,
    )
    assert [result.protocol for result in report.results] == [
        ProbeProtocol.OPENAPI,
        ProbeProtocol.GRPC,
    ]


def test_probe_http_w3c_traceparent_propagation(http_server: str) -> None:
    """Verify probe_http automatically propagates W3C traceparent headers."""
    result = probe_http(f"{http_server}/health")

    sent = _MockHTTPHandler.request_headers[-1]
    assert result.status == ProbeStatus.PASS
    assert sent["traceparent"].startswith("00-")
    assert result.details.get("traceparent") == sent["traceparent"]
    assert "trace_id" in result.details


def test_run_sandbox_probes_generates_and_links_trace_id(http_server: str) -> None:
    """Verify run_sandbox_probes generates and correlates trace_id in report."""
    report = run_sandbox_probes(http_server, protocols=[ProbeProtocol.TCP])
    assert report.overall_status == ProbeStatus.PASS
    assert report.trace_id is not None
    assert len(report.trace_id) > 0


def test_probe_tcp_metadata_endpoint_blocked() -> None:
    """Verify probe_tcp refuses cloud metadata addresses and names, with no connect."""
    results = [probe_tcp("169.254.169.254", 80), probe_tcp("metadata.google.internal", 80)]

    assert [(result.status, "cloud metadata" in result.message) for result in results] == [
        (ProbeStatus.FAIL, True),
        (ProbeStatus.FAIL, True),
    ]


def test_probe_http_metadata_endpoint_blocked() -> None:
    """Verify probe_http refuses cloud metadata addresses and names, with no connect."""
    results = [
        probe_http("http://169.254.169.254/latest/meta-data"),
        probe_http("http://metadata.google.internal/computeMetadata/v1"),
    ]

    assert [(result.status, "cloud metadata" in result.message) for result in results] == [
        (ProbeStatus.FAIL, True),
        (ProbeStatus.FAIL, True),
    ]


@pytest.mark.parametrize(
    ("regex", "message"),
    [("a" * 300, "exceeds maximum length"), ("[unclosed-bracket", "Invalid regex")],
)
def test_probe_http_refuses_a_regex_that_is_too_long_or_not_valid(
    http_server: str, regex: str, message: str
) -> None:
    """Verify regex length limits and syntax error handling during HTTP response evaluation."""
    res = probe_http(f"{http_server}/health", expected_statuses=[200], regex=regex)

    assert res.status == ProbeStatus.FAIL
    assert message in (res.message or "")


def test_probe_tcp_metadata_trailing_dot_and_dns_blocked(dns: DnsFake) -> None:
    """Verify probe_tcp refuses a name that answers a metadata address, trailing dot or not.

    `169.254.169.254.` is a DNS name to glibc, not an address, so its answers are vetted like
    any other name's.
    """
    dns.script("169.254.169.254.", ["169.254.169.254"])
    dns.script("example.com", ["169.254.169.254"])
    results = [probe_tcp("169.254.169.254.", 80), probe_tcp("example.com", 80)]

    assert [(result.status, "cloud metadata" in result.message) for result in results] == [
        (ProbeStatus.FAIL, True),
        (ProbeStatus.FAIL, True),
    ]


def test_endpoint_probe_result_recursive_sanitizer() -> None:
    """Verify EndpointProbeResult recursively masks secrets and bounds oversized nested details."""
    raw_details = {
        "nested": {
            "token": "ghp_123456789012345678901234567890123456",
            "long_str": "x" * 2000,
        },
        "list_data": [
            "sk-ant-api03-12345678901234567890123456789012",
            {"key": "A" * 1500},
        ],
    }
    result = EndpointProbeResult(
        protocol=ProbeProtocol.HTTP,
        target="http://localhost:8080",
        status=ProbeStatus.PASS,
        details=raw_details,
    )
    assert "ghp_123456789012345678901234567890123456" not in result.details["nested"]["token"]
    assert "<masked-github-token>" in result.details["nested"]["token"]
    assert len(result.details["nested"]["long_str"]) <= 1024
    assert result.details["nested"]["long_str"].endswith("...")
    assert "<masked-anthropic-key>" in result.details["list_data"][0]
    assert len(result.details["list_data"][1]["key"]) <= 1024
    assert result.details["list_data"][1]["key"].endswith("...")


def test_probe_tcp_connects_to_vetted_sockaddr(dns: DnsFake) -> None:
    """Verify probe_tcp connects to the address it vetted, so a rebinding name cannot change it."""
    dns.script("example.com", ["127.0.0.1"], ["192.0.2.1"])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        res = probe_tcp("example.com", listener.getsockname()[1], timeout=2.0)

    assert (res.status, len(dns.lookups_of("example.com"))) == (ProbeStatus.PASS, 1)


def test_probe_http_metadata_blocked(dns: DnsFake) -> None:
    """Verify probe_http refuses cloud metadata at the private level, by address or by answer."""
    literal = probe_http("http://169.254.169.254/latest/meta-data")
    dns.script("example.com", ["169.254.169.254"])
    answered = probe_http("http://example.com/computeMetadata/v1")

    assert [
        (result.status, "cloud metadata" in result.message) for result in (literal, answered)
    ] == [
        (ProbeStatus.FAIL, True),
        (ProbeStatus.FAIL, True),
    ]


def test_the_probe_timeout_bounds_every_connect(
    monkeypatch: pytest.MonkeyPatch, dns: DnsFake
) -> None:
    """`devops sandbox probe --timeout N` bounds each connect by N, for HTTP and OpenAPI as for TCP.

    A factory client given a bare number reads it as the read timeout and keeps a 1 s connect, so a
    probe whose first SYN was dropped would report a timeout 'after N s' it never waited.
    """
    dns.answer_every_name()
    from tests.support.fakes.dial import http_response, record_connects
    from tests.support.fakes.dns import PUBLIC_ADDRESS

    schema = json.dumps({"paths": {"/healthz": {"get": {}}}})
    recorder = record_connects(
        monkeypatch,
        [http_response(200, schema), http_response(200, schema), http_response(200, "ok")],
    )

    results = probe_openapi("http://example.com", timeout=7.0)
    tcp = probe_tcp("example.com", 80, timeout=7.0)

    assert (
        [result.status for result in results],
        tcp.status,
        recorder.timeouts_of(PUBLIC_ADDRESS),
    ) == ([ProbeStatus.PASS, ProbeStatus.PASS], ProbeStatus.PASS, [7.0, 7.0, 7.0, 7.0])


def test_a_probe_status_is_stored_in_lower_case() -> None:
    """A probe report stores each status as the lower-case member name (#1538)."""
    assert [str(status) for status in ProbeStatus] == ["pass", "fail", "timeout", "skipped"]

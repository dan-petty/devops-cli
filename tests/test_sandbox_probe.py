"""Submodule-aligned test suite for sandbox endpoint readiness and health probing subsystem."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.exceptions.sandbox import SandboxNotFoundError
from devops_cli.main import app
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

runner = CliRunner()


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


def test_probe_tcp_connection_refused() -> None:
    """Test TCP probe against an unused closed port."""
    # Find a port that is immediately closed
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    res = probe_tcp("127.0.0.1", port, timeout=1.0)
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
    def do_GET(self) -> None:  # noqa: N802
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
    server = HTTPServer(("127.0.0.1", 0), _MockHTTPHandler)
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
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


def test_probe_http_unreachable() -> None:
    """Test HTTP probe against unreachable server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    res = probe_http(f"http://127.0.0.1:{port}/healthz", timeout=1.0)
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


def test_probe_grpc_unreachable() -> None:
    """Test gRPC probe on unreachable host:port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    res = probe_grpc("127.0.0.1", port, timeout=1.0)
    assert res.protocol == ProbeProtocol.GRPC
    assert res.status == ProbeStatus.FAIL


# ─────────────────────────────────────────────────────────────────────────────
# 6. High-Level Orchestrator Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_run_sandbox_probes_with_instance(http_server: str) -> None:
    """Test run_sandbox_probes against a SandboxInstance object."""
    port = int(http_server.split(":")[-1])
    instance = SandboxInstance(
        instance_id="sandbox-test-instance-1",
        container_id="cont-123456",
        name="web-svc",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=80, host_port=port, protocol="tcp")],
        workspace_dir="/tmp/workspace",
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


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_probe_dry_run(mock_engine_cls: MagicMock) -> None:
    """Test sandbox probe in dry-run mode."""
    result = runner.invoke(app, ["sandbox", "probe", "sandbox-123", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "probe" in result.output.lower()


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_probe_by_instance_id_success(
    mock_engine_cls: MagicMock, http_server: str
) -> None:
    """Test sandbox probe CLI command against existing sandbox instance."""
    port = int(http_server.split(":")[-1])
    mock_engine = MagicMock()
    mock_instance = SandboxInstance(
        instance_id="sandbox-test-123",
        container_id="cont-123",
        name="api-svc",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=80, host_port=port, protocol="tcp")],
        workspace_dir="/tmp/workspace",
        created_at="2026-09-12T12:00:00Z",
    )
    mock_engine.status.return_value = [mock_instance]
    mock_engine.probe.return_value = SandboxProbeReport(
        instance_id="sandbox-test-123",
        target="api-svc",
        overall_status=ProbeStatus.PASS,
        total_probes=1,
        passed_probes=1,
        failed_probes=0,
        duration_seconds=0.01,
        results=[
            EndpointProbeResult(
                protocol=ProbeProtocol.TCP,
                target=f"127.0.0.1:{port}",
                status=ProbeStatus.PASS,
                latency_ms=1.5,
                message="TCP connection established",
            )
        ],
    )
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(
        app,
        ["sandbox", "probe", "sandbox-test-123", "-p", "tcp,http", "--path", "/healthz"],
    )
    assert result.exit_code == 0
    assert "PASS" in result.output or "pass" in result.output.lower()


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_probe_json_output(mock_engine_cls: MagicMock, http_server: str) -> None:
    """Test sandbox probe CLI command with JSON output format."""
    port = int(http_server.split(":")[-1])
    mock_engine = MagicMock()
    mock_instance = SandboxInstance(
        instance_id="sandbox-json-123",
        container_id="cont-json-123",
        name="api-svc",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=80, host_port=port, protocol="tcp")],
        workspace_dir="/tmp/workspace",
        created_at="2026-09-12T12:00:00Z",
    )
    mock_engine.status.return_value = [mock_instance]
    mock_engine.probe.return_value = SandboxProbeReport(
        instance_id="sandbox-json-123",
        target="api-svc",
        overall_status=ProbeStatus.PASS,
        total_probes=1,
        passed_probes=1,
        failed_probes=0,
        duration_seconds=0.01,
        results=[
            EndpointProbeResult(
                protocol=ProbeProtocol.TCP,
                target=f"127.0.0.1:{port}",
                status=ProbeStatus.PASS,
                latency_ms=1.5,
                message="TCP connection established",
            )
        ],
    )
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(
        app,
        ["sandbox", "probe", "sandbox-json-123", "-p", "tcp", "--json"],
    )
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["instance_id"] == "sandbox-json-123"
    assert "overall_status" in parsed
    assert len(parsed["results"]) >= 1


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_probe_instance_not_found(mock_engine_cls: MagicMock) -> None:
    """Test sandbox probe with non-existent instance identifier."""
    mock_engine = MagicMock()
    mock_engine.status.side_effect = SandboxNotFoundError("Instance not found")
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(app, ["sandbox", "probe", "nonexistent-instance"])
    assert result.exit_code != 0


def test_engine_probe_method_delegation() -> None:
    """Test WorkloadSandboxEngine.probe delegates to run_sandbox_probes."""
    from devops_cli.sandbox.engine import WorkloadSandboxEngine

    engine = WorkloadSandboxEngine()
    mock_inst = SandboxInstance(
        instance_id="sandbox-probe-unit-1",
        container_id="cont-probe-1",
        name="probe-test-svc",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=80, host_port=18080, protocol="tcp")],
        workspace_dir="/tmp",
        created_at="2026-09-12T12:00:00Z",
    )
    with patch.object(engine.registry, "get_instance", return_value=mock_inst):
        with patch("devops_cli.sandbox.probe.probe_tcp") as mock_tcp:
            mock_tcp.return_value = EndpointProbeResult(
                protocol=ProbeProtocol.TCP,
                target="127.0.0.1:18080",
                status=ProbeStatus.PASS,
                latency_ms=1.0,
            )
            report = engine.probe("sandbox-probe-unit-1", protocols=[ProbeProtocol.TCP])
            assert report.instance_id == "sandbox-probe-unit-1"
            assert report.overall_status == ProbeStatus.PASS


def test_engine_probe_raises_when_not_found() -> None:
    """Test WorkloadSandboxEngine.probe raises SandboxNotFoundError if not found."""
    from devops_cli.sandbox.engine import WorkloadSandboxEngine

    engine = WorkloadSandboxEngine()
    with patch.object(engine.registry, "get_instance", return_value=None):
        with pytest.raises(SandboxNotFoundError):
            engine.probe("missing-id")


def test_parse_target_endpoint_variations() -> None:
    """Test _parse_target_endpoint with multiple formats and schemes."""
    from devops_cli.sandbox.probe import _parse_target_endpoint

    h1, p1 = _parse_target_endpoint("https://example.com")
    assert h1 == "example.com"
    assert p1 == 443

    h2, p2 = _parse_target_endpoint("127.0.0.1:9090")
    assert h2 == "127.0.0.1"
    assert p2 == 9090

    h3, p3 = _parse_target_endpoint("localhost")
    assert h3 == "localhost"
    assert p3 == 80


def test_run_sandbox_probes_with_openapi_and_grpc() -> None:
    """Test run_sandbox_probes with OPENAPI and GRPC protocols."""
    with patch("devops_cli.sandbox.probe.probe_tcp") as mock_tcp:
        mock_tcp.return_value = EndpointProbeResult(
            protocol=ProbeProtocol.TCP,
            target="127.0.0.1:8080",
            status=ProbeStatus.PASS,
            latency_ms=1.0,
        )
        report = run_sandbox_probes(
            "127.0.0.1:8080",
            protocols=[ProbeProtocol.OPENAPI, ProbeProtocol.GRPC],
            timeout=1.0,
        )
        assert report.total_probes >= 2

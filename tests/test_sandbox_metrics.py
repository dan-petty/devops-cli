"""Comprehensive tests for sandbox cgroup v2 metrics collection and Prometheus scraping."""

from __future__ import annotations

import json
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.exceptions.sandbox import SandboxNotFoundError
from devops_cli.main import app
from devops_cli.sandbox.metrics import (
    collect_sandbox_metrics,
    evaluate_threshold_warnings,
    parse_cgroup_v2_directory,
    parse_prometheus_exposition,
    read_cgroup_v2_metrics,
    scrape_prometheus_metrics,
)
from devops_cli.sandbox.models import (
    CgroupV2Metrics,
    PortBinding,
    PrometheusMetric,
    SandboxInstance,
    SandboxMetricsSnapshot,
    SandboxStatus,
)

runner = CliRunner()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Models & Invariant Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_cgroup_v2_metrics_model() -> None:
    """Test CgroupV2Metrics model instantiation and calculations."""
    metrics = CgroupV2Metrics(
        cpu_percent=45.2,
        memory_current_bytes=104857600,  # 100 MB
        memory_limit_bytes=209715200,  # 200 MB
        memory_peak_bytes=157286400,  # 150 MB
        memory_usage_percent=50.0,
        page_faults_total=1250,
        pids_current=12,
        io_read_bytes=1024000,
        io_write_bytes=2048000,
    )
    assert metrics.cpu_percent == 45.2
    assert metrics.memory_usage_percent == 50.0
    assert metrics.memory_current_mb == 100.0
    assert metrics.memory_limit_mb == 200.0

    dump = metrics.model_dump()
    assert dump["cpu_percent"] == 45.2
    assert dump["pids_current"] == 12


def test_prometheus_metric_model() -> None:
    """Test PrometheusMetric model parsing and validation."""
    metric = PrometheusMetric(
        name="http_requests_total",
        metric_type="counter",
        labels={"method": "GET", "status": "200"},
        value=1542.0,
    )
    assert metric.name == "http_requests_total"
    assert metric.labels["method"] == "GET"
    assert metric.value == 1542.0


def test_sandbox_metrics_snapshot_model() -> None:
    """Test SandboxMetricsSnapshot serialization and properties."""
    snapshot = SandboxMetricsSnapshot(
        instance_id="sandbox-test-108",
        target="api-service",
        cgroup=CgroupV2Metrics(cpu_percent=12.5, memory_current_bytes=52428800),
        prometheus_metrics=[PrometheusMetric(name="up", metric_type="gauge", labels={}, value=1.0)],
        warnings=[],
        timestamp="2026-09-12T13:00:00Z",
    )
    dump = snapshot.model_dump()
    assert dump["instance_id"] == "sandbox-test-108"
    assert len(dump["prometheus_metrics"]) == 1
    assert snapshot.is_healthy is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. Cgroup V2 Parsing Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_cgroup_v2_directory(tmp_path: Path) -> None:
    """Test parsing cgroup v2 filesystem controller files."""
    # Setup mock cgroup v2 controller files
    cgroup_dir = tmp_path / "cgroup" / "sandbox-1"
    cgroup_dir.mkdir(parents=True)

    (cgroup_dir / "memory.current").write_text("104857600\n")
    (cgroup_dir / "memory.peak").write_text("157286400\n")
    (cgroup_dir / "memory.max").write_text("209715200\n")
    (cgroup_dir / "pids.current").write_text("18\n")
    (cgroup_dir / "cpu.stat").write_text(
        "usage_usec 5000000\nuser_usec 4000000\nsystem_usec 1000000\nnr_periods 100\nnr_throttled 5\nthrottled_usec 20000\n"
    )
    (cgroup_dir / "memory.stat").write_text("pgfault 4321\npgmajfault 12\n")
    (cgroup_dir / "io.stat").write_text("8:0 rbytes=5242880 wbytes=10485760\n")

    metrics = parse_cgroup_v2_directory(cgroup_dir)
    assert metrics is not None
    assert metrics.memory_current_bytes == 104857600
    assert metrics.memory_peak_bytes == 157286400
    assert metrics.memory_limit_bytes == 209715200
    assert metrics.memory_usage_percent == pytest.approx(50.0, 0.1)
    assert metrics.pids_current == 18
    assert metrics.page_faults_total == 4321
    assert metrics.io_read_bytes == 5242880
    assert metrics.io_write_bytes == 10485760


def test_parse_cgroup_v2_directory_unlimited_memory(tmp_path: Path) -> None:
    """Test parsing cgroup v2 controller when memory.max is 'max' (unlimited)."""
    cgroup_dir = tmp_path / "cgroup" / "sandbox-2"
    cgroup_dir.mkdir(parents=True)

    (cgroup_dir / "memory.current").write_text("52428800\n")
    (cgroup_dir / "memory.max").write_text("max\n")

    metrics = parse_cgroup_v2_directory(cgroup_dir)
    assert metrics is not None
    assert metrics.memory_current_bytes == 52428800
    assert metrics.memory_limit_bytes is None
    assert metrics.memory_usage_percent is None


def test_parse_cgroup_v2_directory_missing_dir(tmp_path: Path) -> None:
    """Test graceful handling when cgroup directory does not exist."""
    non_existent = tmp_path / "does_not_exist"
    assert parse_cgroup_v2_directory(non_existent) is None


def test_read_cgroup_v2_metrics_fallback_to_docker_stats() -> None:
    """Test read_cgroup_v2_metrics falling back to docker stats inspection."""
    with patch("devops_cli.sandbox.metrics.parse_cgroup_v2_directory", return_value=None):
        with patch("devops_cli.sandbox.metrics._read_container_stats_fallback") as mock_fallback:
            mock_fallback.return_value = CgroupV2Metrics(
                cpu_percent=15.5,
                memory_current_bytes=104857600,
                memory_limit_bytes=524288000,
                memory_usage_percent=20.0,
                pids_current=8,
            )
            metrics = read_cgroup_v2_metrics(container_id="cont-123")
            assert metrics is not None
            assert metrics.cpu_percent == 15.5
            assert metrics.memory_usage_percent == 20.0
            assert metrics.pids_current == 8


# ─────────────────────────────────────────────────────────────────────────────
# 3. Prometheus Parsing & Scraping Tests
# ─────────────────────────────────────────────────────────────────────────────

_SAMPLE_PROMETHEUS_TEXT = """
# HELP http_requests_total The total number of HTTP requests.
# TYPE http_requests_total counter
http_requests_total{method="post",code="200"} 1027
http_requests_total{method="post",code="500"} 42
http_requests_total{method="get",code="200"} 5430
# HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.
# TYPE node_cpu_seconds_total counter
node_cpu_seconds_total{mode="idle"} 80123.45
# HELP process_resident_memory_bytes Resident memory size in bytes.
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 67108864
# HELP http_request_duration_seconds A histogram of the HTTP request durations.
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.05"} 24054
http_request_duration_seconds_bucket{le="0.1"} 33444
http_request_duration_seconds_bucket{le="+Inf"} 35000
http_request_duration_seconds_sum 1234.56
http_request_duration_seconds_count 35000
"""


def test_parse_prometheus_exposition() -> None:
    """Test parsing Prometheus text exposition format into structured models."""
    metrics = parse_prometheus_exposition(_SAMPLE_PROMETHEUS_TEXT)
    assert len(metrics) >= 6

    # Verify counter with labels
    http_200 = next(
        (
            m
            for m in metrics
            if m.name == "http_requests_total"
            and m.labels.get("code") == "200"
            and m.labels.get("method") == "post"
        ),
        None,
    )
    assert http_200 is not None
    assert http_200.value == 1027.0
    assert http_200.metric_type == "counter"

    # Verify gauge
    mem_gauge = next((m for m in metrics if m.name == "process_resident_memory_bytes"), None)
    assert mem_gauge is not None
    assert mem_gauge.value == 67108864.0
    assert mem_gauge.metric_type == "gauge"


class _MockPrometheusHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(_SAMPLE_PROMETHEUS_TEXT.encode("utf-8"))
        elif self.path == "/error":
            self.send_response(500)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def prom_server() -> Generator[str]:
    """Spin up an ephemeral HTTP server exposing Prometheus metrics."""
    server = HTTPServer(("127.0.0.1", 0), _MockPrometheusHandler)
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


def test_scrape_prometheus_metrics_success(prom_server: str) -> None:
    """Test scraping Prometheus endpoint over HTTP."""
    url = f"{prom_server}/metrics"
    metrics = scrape_prometheus_metrics(url, timeout=2.0)
    assert len(metrics) >= 6
    names = {m.name for m in metrics}
    assert "http_requests_total" in names
    assert "process_resident_memory_bytes" in names


def test_scrape_prometheus_metrics_server_error(prom_server: str) -> None:
    """Test scraping Prometheus endpoint returning HTTP 500."""
    url = f"{prom_server}/error"
    metrics = scrape_prometheus_metrics(url, timeout=2.0)
    assert metrics == []


def test_scrape_prometheus_metrics_unreachable() -> None:
    """Test scraping unreachable Prometheus endpoint gracefully returns empty list."""
    metrics = scrape_prometheus_metrics("http://127.0.0.1:9999/metrics", timeout=0.2)
    assert metrics == []


def test_scrape_prometheus_metrics_invalid_scheme() -> None:
    """Test scraping URL with non-http/https scheme is rejected."""
    metrics = scrape_prometheus_metrics("ftp://127.0.0.1:8080/metrics", timeout=1.0)
    assert metrics == []


# ─────────────────────────────────────────────────────────────────────────────
# 4. Threshold Warnings & Anomaly Detection Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_evaluate_threshold_warnings_healthy() -> None:
    """Test evaluation when metrics are within healthy operating parameters."""
    cgroup = CgroupV2Metrics(
        cpu_percent=25.0,
        memory_current_bytes=104857600,
        memory_limit_bytes=524288000,
        memory_usage_percent=20.0,
    )
    prom_metrics = [
        PrometheusMetric(name="http_requests_total", labels={"code": "200"}, value=100.0),
        PrometheusMetric(name="http_requests_total", labels={"code": "500"}, value=1.0),
    ]
    warnings = evaluate_threshold_warnings(
        cgroup, prom_metrics, memory_threshold_pct=80.0, cpu_threshold_pct=85.0
    )
    assert len(warnings) == 0


def test_evaluate_threshold_warnings_high_memory() -> None:
    """Test warning triggered when memory exceeds threshold."""
    cgroup = CgroupV2Metrics(
        cpu_percent=10.0,
        memory_current_bytes=471859200,
        memory_limit_bytes=524288000,
        memory_usage_percent=90.0,
    )
    warnings = evaluate_threshold_warnings(cgroup, [], memory_threshold_pct=80.0)
    assert len(warnings) >= 1
    assert any("memory" in w.lower() for w in warnings)


def test_evaluate_threshold_warnings_high_cpu() -> None:
    """Test warning triggered when CPU utilization exceeds threshold."""
    cgroup = CgroupV2Metrics(
        cpu_percent=92.5,
        memory_current_bytes=52428800,
        memory_limit_bytes=524288000,
        memory_usage_percent=10.0,
    )
    warnings = evaluate_threshold_warnings(cgroup, [], cpu_threshold_pct=85.0)
    assert len(warnings) >= 1
    assert any("cpu" in w.lower() for w in warnings)


def test_evaluate_threshold_warnings_high_error_rate() -> None:
    """Test warning triggered when Prometheus metrics indicate high 5xx error rate."""
    prom_metrics = [
        PrometheusMetric(name="http_requests_total", labels={"code": "200"}, value=80.0),
        PrometheusMetric(name="http_requests_total", labels={"code": "500"}, value=20.0),
    ]
    warnings = evaluate_threshold_warnings(None, prom_metrics)
    assert len(warnings) >= 1
    assert any("error" in w.lower() for w in warnings)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Full Collector Pipeline Tests (`collect_sandbox_metrics`)
# ─────────────────────────────────────────────────────────────────────────────


def test_collect_sandbox_metrics_with_instance(prom_server: str) -> None:
    """Test collect_sandbox_metrics against a SandboxInstance object."""
    port = int(prom_server.split(":")[-1])
    instance = SandboxInstance(
        instance_id="sandbox-test-metrics-1",
        container_id="cont-metrics-1",
        name="web-service",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=8080, host_port=port, protocol="tcp")],
        workspace_dir="/tmp/workspace",
        created_at="2026-09-12T13:00:00Z",
    )

    with patch("devops_cli.sandbox.metrics.read_cgroup_v2_metrics") as mock_read_cgroup:
        mock_read_cgroup.return_value = CgroupV2Metrics(
            cpu_percent=30.0,
            memory_current_bytes=104857600,
            memory_limit_bytes=209715200,
            memory_usage_percent=50.0,
            pids_current=10,
        )
        snapshot = collect_sandbox_metrics(instance, prom_endpoint="/metrics", timeout=2.0)
        assert snapshot.instance_id == "sandbox-test-metrics-1"
        assert snapshot.target == "web-service"
        assert snapshot.cgroup is not None
        assert snapshot.cgroup.cpu_percent == 30.0
        assert len(snapshot.prometheus_metrics) >= 6
        assert snapshot.is_healthy is True


def test_collect_sandbox_metrics_with_raw_url(prom_server: str) -> None:
    """Test collect_sandbox_metrics against a raw URL."""
    snapshot = collect_sandbox_metrics(prom_server, prom_endpoint="/metrics", timeout=2.0)
    assert snapshot.cgroup is None
    assert len(snapshot.prometheus_metrics) >= 6


# ─────────────────────────────────────────────────────────────────────────────
# 6. Engine Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_engine_metrics_method_delegation() -> None:
    """Test WorkloadSandboxEngine.metrics delegates properly."""
    from devops_cli.sandbox.engine import WorkloadSandboxEngine

    engine = WorkloadSandboxEngine()
    mock_inst = SandboxInstance(
        instance_id="sandbox-engine-1",
        container_id="cont-engine-1",
        name="engine-svc",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=80, host_port=18080, protocol="tcp")],
        workspace_dir="/tmp",
        created_at="2026-09-12T13:00:00Z",
    )
    with patch.object(engine.registry, "get_instance", return_value=mock_inst):
        with patch("devops_cli.sandbox.metrics.collect_sandbox_metrics") as mock_collect:
            mock_collect.return_value = SandboxMetricsSnapshot(
                instance_id="sandbox-engine-1",
                target="engine-svc",
                cgroup=CgroupV2Metrics(cpu_percent=5.0),
                prometheus_metrics=[],
                warnings=[],
                timestamp="2026-09-12T13:00:00Z",
            )
            snapshot = engine.metrics("sandbox-engine-1")
            assert snapshot.instance_id == "sandbox-engine-1"
            assert snapshot.target == "engine-svc"


def test_engine_metrics_raises_not_found() -> None:
    """Test WorkloadSandboxEngine.metrics raises SandboxNotFoundError if not found."""
    from devops_cli.sandbox.engine import WorkloadSandboxEngine

    engine = WorkloadSandboxEngine()
    with patch.object(engine.registry, "get_instance", return_value=None):
        with pytest.raises(SandboxNotFoundError):
            engine.metrics("nonexistent-id")


# ─────────────────────────────────────────────────────────────────────────────
# 7. CLI Command Tests (`devops sandbox metrics`)
# ─────────────────────────────────────────────────────────────────────────────


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_metrics_dry_run(mock_engine_cls: MagicMock) -> None:
    """Test sandbox metrics CLI command with --dry-run flag."""
    result = runner.invoke(app, ["sandbox", "metrics", "sandbox-123", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "metrics" in result.output.lower()


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_metrics_success(mock_engine_cls: MagicMock) -> None:
    """Test sandbox metrics CLI command execution and table rendering."""
    mock_engine = MagicMock()
    mock_engine.metrics.return_value = SandboxMetricsSnapshot(
        instance_id="sandbox-metrics-cli",
        target="cli-svc",
        cgroup=CgroupV2Metrics(
            cpu_percent=42.1,
            memory_current_bytes=104857600,
            memory_limit_bytes=209715200,
            memory_usage_percent=50.0,
            pids_current=14,
            page_faults_total=3000,
            io_read_bytes=102400,
            io_write_bytes=204800,
        ),
        prometheus_metrics=[
            PrometheusMetric(
                name="http_requests_total",
                metric_type="counter",
                labels={"code": "200"},
                value=150.0,
            )
        ],
        warnings=[],
        timestamp="2026-09-12T13:00:00Z",
    )
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(app, ["sandbox", "metrics", "sandbox-metrics-cli"])
    assert result.exit_code == 0
    assert "42.1" in result.output or "CPU" in result.output
    assert "100.0" in result.output or "MB" in result.output


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_metrics_with_warnings(mock_engine_cls: MagicMock) -> None:
    """Test sandbox metrics CLI command rendering warning callouts."""
    mock_engine = MagicMock()
    mock_engine.metrics.return_value = SandboxMetricsSnapshot(
        instance_id="sandbox-warn-cli",
        target="warn-svc",
        cgroup=CgroupV2Metrics(
            cpu_percent=95.0,
            memory_current_bytes=471859200,
            memory_limit_bytes=524288000,
            memory_usage_percent=90.0,
        ),
        prometheus_metrics=[],
        warnings=[
            "Memory usage (90.0%) exceeds warning threshold (80.0%)",
            "CPU utilization (95.0%) exceeds 85.0%",
        ],
        timestamp="2026-09-12T13:00:00Z",
    )
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(app, ["sandbox", "metrics", "sandbox-warn-cli"])
    assert result.exit_code == 0
    assert "WARNING" in result.output.upper() or "exceeds" in result.output.lower()


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_metrics_json_output(mock_engine_cls: MagicMock) -> None:
    """Test sandbox metrics CLI command with --json output flag."""
    mock_engine = MagicMock()
    mock_engine.metrics.return_value = SandboxMetricsSnapshot(
        instance_id="sandbox-json-cli",
        target="json-svc",
        cgroup=CgroupV2Metrics(cpu_percent=10.0, memory_current_bytes=10485760),
        prometheus_metrics=[],
        warnings=[],
        timestamp="2026-09-12T13:00:00Z",
    )
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(app, ["sandbox", "metrics", "sandbox-json-cli", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["instance_id"] == "sandbox-json-cli"
    assert data["cgroup"]["cpu_percent"] == 10.0


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_metrics_not_found(mock_engine_cls: MagicMock) -> None:
    """Test sandbox metrics CLI command when target instance is not found."""
    mock_engine = MagicMock()
    mock_engine.metrics.side_effect = SandboxNotFoundError("Sandbox 'missing' not found")
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(app, ["sandbox", "metrics", "missing"])
    assert result.exit_code != 0


def test_parse_size_bytes_all_units() -> None:
    """Test _parse_size_bytes helper across all common byte and binary units."""
    from devops_cli.sandbox.metrics import _parse_size_bytes

    assert _parse_size_bytes("500B") == 500
    assert _parse_size_bytes("10KB") == 10000
    assert _parse_size_bytes("10KiB") == 10240
    assert _parse_size_bytes("5MB") == 5000000
    assert _parse_size_bytes("5MiB") == 5 * 1024 * 1024
    assert _parse_size_bytes("1GB") == 1000000000
    assert _parse_size_bytes("1GiB") == 1024 * 1024 * 1024
    assert _parse_size_bytes("invalid") == 0
    assert _parse_size_bytes("") == 0


def test_read_int_and_str_file_helpers(tmp_path: Path) -> None:
    """Test file reader error handling on missing or malformed content."""
    from devops_cli.sandbox.metrics import _read_int_file, _read_str_file

    missing = tmp_path / "missing.txt"
    assert _read_int_file(missing) is None
    assert _read_str_file(missing) == ""

    bad_int = tmp_path / "bad_int.txt"
    bad_int.write_text("not-an-int\n")
    assert _read_int_file(bad_int) is None


def test_read_container_stats_fallback_subprocesses() -> None:
    """Test _read_container_stats_fallback handling success and process failures."""
    from devops_cli.sandbox.metrics import _read_container_stats_fallback

    # Success case
    mock_success = MagicMock(
        returncode=0,
        stdout=json.dumps(
            {
                "CPUPerc": "25.0%",
                "MemUsage": "50MiB / 200MiB",
                "MemPerc": "25.0%",
                "PIDs": "4",
            }
        ),
    )
    with patch("subprocess.run", return_value=mock_success):
        res = _read_container_stats_fallback("cont-valid")
        assert res is not None
        assert res.cpu_percent == 25.0
        assert res.pids_current == 4

    # Failure case
    mock_fail = MagicMock(returncode=1, stdout="", stderr="Error")
    with patch("subprocess.run", return_value=mock_fail):
        assert _read_container_stats_fallback("cont-failed") is None


def test_read_cgroup_v2_metrics_standard_paths() -> None:
    """Test read_cgroup_v2_metrics finding standard docker slice path."""
    with patch("devops_cli.sandbox.metrics.parse_cgroup_v2_directory") as mock_parse:
        mock_parse.side_effect = lambda p: (
            CgroupV2Metrics(cpu_percent=1.0) if "docker-c1" in str(p) else None
        )
        res = read_cgroup_v2_metrics(container_id="c1")
        assert res is not None
        assert res.cpu_percent == 1.0


def test_resolve_instance_port_fallback() -> None:
    """Test port resolution defaults to 8080 when no bindings present."""
    from devops_cli.sandbox.metrics import _resolve_instance_port

    inst = SandboxInstance(
        instance_id="inst-no-ports",
        container_id="c-no-ports",
        name="no-ports",
        image="alpine",
        status=SandboxStatus.RUNNING,
        port_bindings=[],
        workspace_dir="/tmp",
        created_at="2026-09-12T13:00:00Z",
    )
    assert _resolve_instance_port(inst) == 8080


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_metrics_url_target(mock_engine_cls: MagicMock, prom_server: str) -> None:
    """Test CLI metrics invocation with raw URL target when instance not found."""
    mock_engine = MagicMock()
    mock_engine.metrics.side_effect = SandboxNotFoundError("Not an instance")
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(app, ["sandbox", "metrics", prom_server])
    assert result.exit_code == 0
    assert "Prometheus" in result.output


# ─────────────────────────────────────────────────────────────────────────────
# 8. PR #164 Review Findings Remediation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_sandbox_metrics_help_metrics_timeout() -> None:
    """Test CLI metrics --help displays dedicated Prometheus scrape timeout description."""
    result = runner.invoke(app, ["sandbox", "metrics", "--help"])
    assert result.exit_code == 0
    assert "HTTP timeout in seconds for" in result.output
    assert "Prometheus metrics scraping" in result.output


def test_telemetry_tracing_instrumentation() -> None:
    """Test OpenTelemetry tracing and metric recording in CLI and engine."""
    from devops_cli.sandbox.engine import WorkloadSandboxEngine

    # Test CLI command emits trace span and metric
    with patch("devops_cli.commands.sandbox.trace_span") as mock_cli_span:
        with patch("devops_cli.commands.sandbox.record_metric") as mock_cli_metric:
            mock_cli_span.return_value.__enter__.return_value = MagicMock()
            result = runner.invoke(app, ["sandbox", "metrics", "test-inst", "--dry-run"])
            assert result.exit_code == 0
            mock_cli_span.assert_called_once_with(
                "sandbox.metrics",
                attributes={
                    "sandbox.identifier": "test-inst",
                    "sandbox.prom_endpoint": "/metrics",
                    "sandbox.dry_run": True,
                },
            )
            mock_cli_metric.assert_called_once_with(
                "devops_cli.sandbox.metrics_invoked",
                1.0,
                unit="1",
                attributes={"dry_run": True},
            )

    # Test Engine metrics() emits trace span and metric
    engine = WorkloadSandboxEngine()
    mock_inst = SandboxInstance(
        instance_id="inst-tracer",
        container_id="cont-tracer",
        name="tracer-svc",
        image="alpine",
        status=SandboxStatus.RUNNING,
        port_bindings=[],
        workspace_dir="/tmp",
        created_at="2026-09-12T13:00:00Z",
    )
    with patch.object(engine.registry, "get_instance", return_value=mock_inst):
        with patch("devops_cli.sandbox.engine.trace_span") as mock_eng_span:
            with patch("devops_cli.sandbox.engine.record_metric") as mock_eng_metric:
                with patch("devops_cli.sandbox.metrics.collect_sandbox_metrics") as mock_collect:
                    mock_collect.return_value = SandboxMetricsSnapshot(
                        instance_id="inst-tracer",
                        target="tracer-svc",
                        cgroup=None,
                        prometheus_metrics=[],
                        warnings=[],
                        timestamp="2026-09-12T13:00:00Z",
                    )
                    mock_eng_span.return_value.__enter__.return_value = MagicMock()
                    res = engine.metrics("inst-tracer")
                    assert res.instance_id == "inst-tracer"
                    mock_eng_span.assert_called_once_with(
                        "sandbox.engine.metrics",
                        attributes={
                            "sandbox.identifier": "inst-tracer",
                            "sandbox.container_id": "cont-tracer",
                            "sandbox.prom_endpoint": "/metrics",
                        },
                    )
                    mock_eng_metric.assert_called_once_with(
                        "devops_cli.sandbox.metrics_collected",
                        1.0,
                        unit="1",
                        attributes={"healthy": True},
                    )


def test_parse_cgroup_v2_cpu_delta_calculation(tmp_path: Path) -> None:
    """Test parse_cgroup_v2_directory calculates delta CPU percent and records cpu_usage_usec."""
    cgroup_dir = tmp_path / "cgroup" / "delta-test"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "cpu.stat").write_text("usage_usec 2500000\n")

    # Initial sample without prior interval -> None (unknown) but records usage_usec
    first_sample = parse_cgroup_v2_directory(cgroup_dir)
    assert first_sample is not None
    assert first_sample.cpu_usage_usec == 2500000
    assert first_sample.cpu_percent is None

    # Second sample: previous was 2,000,000 usec, elapsed 1.0 sec -> delta = 500,000 usec -> 50.0%
    second_sample = parse_cgroup_v2_directory(
        cgroup_dir,
        previous_cpu_usec=2000000,
        elapsed_sec=1.0,
    )
    assert second_sample is not None
    assert second_sample.cpu_usage_usec == 2500000
    assert second_sample.cpu_percent == 50.0

    # Read helper test with delta arguments
    read_sample = read_cgroup_v2_metrics(
        cgroup_path=cgroup_dir,
        previous_cpu_usec=2000000,
        elapsed_sec=1.0,
    )
    assert read_sample is not None
    assert read_sample.cpu_percent == 50.0


def test_scrape_prometheus_metrics_ssrf_protection() -> None:
    """Test scrape_prometheus_metrics blocks non-permitted protocols and invalid hosts via SSRF check."""
    from devops_cli.sandbox.metrics import PrometheusScrapeResult

    # Block non-HTTP schemes
    res_ftp = scrape_prometheus_metrics("ftp://127.0.0.1:8080/metrics")
    assert isinstance(res_ftp, PrometheusScrapeResult)
    assert len(res_ftp) == 0
    assert res_ftp.error is not None
    assert "SSRF" in res_ftp.error or "scheme" in res_ftp.error

    res_file = scrape_prometheus_metrics("file:///etc/passwd")
    assert len(res_file) == 0
    assert res_file.error is not None

    # Invalid host
    res_bad_host = scrape_prometheus_metrics("http:///missing-host")
    assert len(res_bad_host) == 0
    assert res_bad_host.error is not None

    # Cloud metadata and RFC1918 private IPs are blocked
    res_metadata = scrape_prometheus_metrics("http://169.254.169.254/latest/meta-data")
    assert len(res_metadata) == 0
    assert res_metadata.error is not None
    assert "SSRF" in res_metadata.error or "private" in res_metadata.error.lower()

    res_rfc1918 = scrape_prometheus_metrics("http://10.0.0.1/metrics")
    assert len(res_rfc1918) == 0
    assert res_rfc1918.error is not None
    assert "SSRF" in res_rfc1918.error or "private" in res_rfc1918.error.lower()


def test_preserve_scrape_error_state_and_unhealthy() -> None:
    """Test that failed metrics scrapes preserve error details and mark snapshot unhealthy."""
    from devops_cli.sandbox.metrics import PrometheusScrapeResult

    # Mock scrape returning error
    with patch("devops_cli.sandbox.metrics.scrape_prometheus_metrics") as mock_scrape:
        mock_scrape.return_value = PrometheusScrapeResult(
            [],
            error="HTTP 502 Bad Gateway response from http://127.0.0.1:8080/metrics",
        )
        snapshot = collect_sandbox_metrics("127.0.0.1:8080")
        assert (
            snapshot.scrape_error
            == "HTTP 502 Bad Gateway response from http://127.0.0.1:8080/metrics"
        )
        assert len(snapshot.warnings) == 0
        assert snapshot.is_healthy is False


def test_parse_prometheus_exposition_label_unescaping() -> None:
    """Test parse_prometheus_exposition unescapes quotes, backslashes, and newlines in labels."""
    exposition = (
        'http_requests_total{path="/api/v1?q=\\"test\\"",note="line1\\nline2",bs="a\\\\b"} 42\n'
    )
    metrics = parse_prometheus_exposition(exposition)
    assert len(metrics) == 1
    m = metrics[0]
    assert m.labels["path"] == '/api/v1?q="test"'
    assert m.labels["note"] == "line1\nline2"
    assert m.labels["bs"] == "a\\b"
    assert m.value == 42.0


def test_evaluate_threshold_warnings_memory_leak_trajectory() -> None:
    """Test evaluate_threshold_warnings detects memory leak trajectory when growth exceeds 20% and 5MB."""
    prior = CgroupV2Metrics(
        cpu_percent=10.0,
        memory_current_bytes=10 * 1024 * 1024,  # 10MB
    )
    current = CgroupV2Metrics(
        cpu_percent=10.0,
        memory_current_bytes=20 * 1024 * 1024,  # 20MB (100% growth, +10MB)
    )
    warnings = evaluate_threshold_warnings(
        cgroup=current,
        prom_metrics=[],
        previous_cgroup=prior,
    )
    assert len(warnings) == 1
    assert "memory leak trajectory" in warnings[0].lower()
    assert "100.0%" in warnings[0]


def test_evaluate_threshold_warnings_histogram_latency_degradation() -> None:
    """Test evaluate_threshold_warnings computes average latency from histogram sum and count."""
    prom_metrics = [
        PrometheusMetric(
            name="http_request_duration_seconds_sum",
            metric_type="histogram",
            labels={"handler": "orders"},
            value=60.0,  # 60 seconds total
        ),
        PrometheusMetric(
            name="http_request_duration_seconds_count",
            metric_type="histogram",
            labels={"handler": "orders"},
            value=50.0,  # across 50 requests -> 1.2s avg = 1200ms
        ),
    ]
    warnings = evaluate_threshold_warnings(
        cgroup=None,
        prom_metrics=prom_metrics,
        latency_threshold_ms=500.0,
    )
    assert len(warnings) == 1
    assert "High average request latency" in warnings[0]
    assert "1200.0ms >= 500.0ms" in warnings[0]


def test_parse_cgroup_v2_network_stat_and_docker_net_io(tmp_path: Path) -> None:
    """Test parsing network stats from cgroup directory and docker stats dict."""
    from devops_cli.sandbox.metrics import _build_metrics_from_docker_dict

    # From cgroup network.stat file
    cgroup_dir = tmp_path / "cgroup" / "net-test"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "network.stat").write_text("rx_bytes 10485760\ntx_bytes 20971520\n")
    cgroup_metrics = parse_cgroup_v2_directory(cgroup_dir)
    assert cgroup_metrics is not None
    assert cgroup_metrics.network_rx_bytes == 10485760
    assert cgroup_metrics.network_tx_bytes == 20971520

    # From docker stats dictionary
    docker_data = {
        "CPUPerc": "12.0%",
        "MemUsage": "100MiB / 500MiB",
        "NetIO": "1.5MB / 3.2MB",
        "PIDs": "6",
    }
    docker_metrics = _build_metrics_from_docker_dict(docker_data)
    assert docker_metrics.network_rx_bytes == 1500000
    assert docker_metrics.network_tx_bytes == 3200000


def test_evaluate_threshold_warnings_status_label_5xx() -> None:
    """Test evaluate_threshold_warnings detects 5xx spikes when metric uses status instead of code."""
    prom_metrics = [
        PrometheusMetric(name="http_requests_total", labels={"status": "200"}, value=80.0),
        PrometheusMetric(name="http_requests_total", labels={"status": "500"}, value=20.0),
    ]
    warnings = evaluate_threshold_warnings(None, prom_metrics)
    assert len(warnings) >= 1
    assert any("5xx" in w for w in warnings)


def test_calculate_memory_percent_zero_current() -> None:
    """Test _calculate_memory_percent returns 0.0 when current bytes is 0."""
    from devops_cli.sandbox.metrics import _calculate_memory_percent

    assert _calculate_memory_percent(0, 1000) == 0.0
    assert _calculate_memory_percent(100, 1000) == 10.0
    assert _calculate_memory_percent(None, 1000) is None
    assert _calculate_memory_percent(100, None) is None
    assert _calculate_memory_percent(100, 0) is None


def test_prometheus_exposition_timestamp_preservation() -> None:
    """Test parse_prometheus_exposition preserves exposition timestamp."""
    text = "http_requests_total 42.0 1716300000000\n"
    metrics = parse_prometheus_exposition(text)
    assert len(metrics) == 1
    assert metrics[0].name == "http_requests_total"
    assert metrics[0].value == 42.0
    assert metrics[0].timestamp == "1716300000000"


def test_scrape_prometheus_metrics_sanitizes_credentials_and_errors() -> None:
    """Test scrape_prometheus_metrics masks credentials in scrape target and error message."""
    url = "http://admin:supersecret@127.0.0.1:65530/metrics"
    res = scrape_prometheus_metrics(url, timeout=0.5)
    assert res.error is not None
    assert "supersecret" not in res.error
    assert "admin:***@" in res.error


def test_parse_open_fds_cgroup_and_docker(tmp_path: Path) -> None:
    """Test parsing open file descriptors count from cgroup stat files and docker stats."""
    from devops_cli.sandbox.metrics import _build_metrics_from_docker_dict, _parse_open_fds

    cgroup_dir = tmp_path / "cgroup" / "fds-test"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "fds.current").write_text("38\n")
    assert _parse_open_fds(cgroup_dir) == 38

    parsed = parse_cgroup_v2_directory(cgroup_dir)
    assert parsed is not None
    assert parsed.open_fds_count == 38

    # From docker dict
    data = {"PIDs": "4", "FDs": "64"}
    metrics = _build_metrics_from_docker_dict(data)
    assert metrics.open_fds_count == 64


def test_evaluate_threshold_warnings_optional_latency_sla() -> None:
    """Test latency SLA is only evaluated when explicitly configured."""
    prom_metrics = [
        PrometheusMetric(
            name="http_request_duration_seconds_sum",
            metric_type="histogram",
            value=100.0,
        ),
        PrometheusMetric(
            name="http_request_duration_seconds_count",
            metric_type="histogram",
            value=10.0,
        ),
    ]
    # No latency SLA configured (None) -> no warnings generated
    warnings_none = evaluate_threshold_warnings(
        cgroup=None,
        prom_metrics=prom_metrics,
        latency_threshold_ms=None,
    )
    assert len(warnings_none) == 0

    # Configured SLA (5000ms < 10000ms average) -> warning generated
    warnings_configured = evaluate_threshold_warnings(
        cgroup=None,
        prom_metrics=prom_metrics,
        latency_threshold_ms=5000.0,
    )
    assert len(warnings_configured) == 1
    assert "High average request latency" in warnings_configured[0]


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_metrics_renders_open_fds_and_scrape_warning(
    mock_engine_cls: MagicMock,
) -> None:
    """Test CLI renders open FDs and separate scrape warnings."""
    mock_engine = MagicMock()
    mock_engine.metrics.return_value = SandboxMetricsSnapshot(
        instance_id="sandbox-test-fds",
        target="fds-svc",
        cgroup=CgroupV2Metrics(cpu_percent=10.0, open_fds_count=42),
        prometheus_metrics=[],
        scrape_error="HTTP 503 Service Unavailable from http://127.0.0.1:8080/metrics",
        warnings=[],
    )
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(app, ["sandbox", "metrics", "sandbox-test-fds"])
    assert result.exit_code == 0
    assert "Open File Descriptors" in result.output
    assert "42" in result.output
    assert "SCRAPE WARNING" in result.output
    assert "HTTP 503" in result.output


@patch("devops_cli.commands.sandbox.WorkloadSandboxEngine")
def test_cli_sandbox_metrics_latency_sla_option(
    mock_engine_cls: MagicMock,
) -> None:
    """Test CLI metrics with --latency-sla-ms flag."""
    mock_engine = MagicMock()
    mock_engine.metrics.return_value = SandboxMetricsSnapshot(
        instance_id="sandbox-test-sla",
        target="sla-svc",
        cgroup=CgroupV2Metrics(cpu_percent=10.0),
        prometheus_metrics=[],
        warnings=[],
    )
    mock_engine_cls.return_value = mock_engine

    result = runner.invoke(
        app,
        ["sandbox", "metrics", "sandbox-test-sla", "--latency-sla-ms", "250.0"],
    )
    assert result.exit_code == 0
    mock_engine.metrics.assert_called_once()
    assert mock_engine.metrics.call_args.kwargs["latency_sla_ms"] == 250.0


def test_read_cgroup_v2_metrics_fallback_when_path_invalid(tmp_path: Path) -> None:
    """Test read_cgroup_v2_metrics falls back to container_id when cgroup_path is invalid."""
    # When cgroup_path does not exist, it should not abort but check container_id
    with patch("devops_cli.sandbox.metrics._read_container_stats_fallback") as mock_docker_fallback:
        mock_docker_fallback.return_value = CgroupV2Metrics(cpu_percent=55.0)
        res = read_cgroup_v2_metrics(
            container_id="cont-fallback-1",
            cgroup_path=tmp_path / "nonexistent",
        )
        assert res is not None
        assert res.cpu_percent == 55.0
        mock_docker_fallback.assert_called_once_with("cont-fallback-1")


def test_workload_sandbox_engine_persists_and_threads_samples() -> None:
    """Test WorkloadSandboxEngine persists samples and calculates CPU delta on consecutive calls."""
    from devops_cli.sandbox.engine import WorkloadSandboxEngine
    from devops_cli.sandbox.metrics import PrometheusScrapeResult

    engine = WorkloadSandboxEngine()
    engine._prior_samples.clear()

    inst = SandboxInstance(
        instance_id="sandbox-delta-inst",
        container_id="cont-delta-1",
        name="delta-svc",
        image="test:latest",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=8080, host_port=18080)],
        workspace_dir="/tmp",
        created_at="2026-09-12T13:00:00Z",
    )

    with patch.object(engine.registry, "get_instance", return_value=inst):
        with patch("devops_cli.sandbox.metrics.scrape_prometheus_metrics") as mock_scrape:
            mock_scrape.return_value = PrometheusScrapeResult([])
            with patch("devops_cli.sandbox.metrics.read_cgroup_v2_metrics") as mock_read:
                # First call returns usage_usec = 1,000,000 without prior delta -> cpu_percent is None
                mock_read.side_effect = [
                    CgroupV2Metrics(cpu_usage_usec=1000000, cpu_percent=None),
                    CgroupV2Metrics(cpu_usage_usec=1500000, cpu_percent=50.0),
                ]
                first = engine.metrics("sandbox-delta-inst")
                assert first.cgroup is not None
                assert first.cgroup.cpu_percent is None

                # Second call should thread previous sample
                second = engine.metrics("sandbox-delta-inst")
                assert second.cgroup is not None
                assert second.cgroup.cpu_percent == 50.0
                assert mock_read.call_count == 2
                # Verify second call received previous_cpu_usec = 1000000
                second_kwargs = mock_read.call_args_list[1].kwargs
                assert second_kwargs.get("previous_cpu_usec") == 1000000

"""Comprehensive tests for sandbox cgroup v2 metrics collection and Prometheus scraping."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable, Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.sandbox import SandboxNotFoundError
from devops_cli.sandbox.engine import WorkloadSandboxEngine
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
from devops_cli.telemetry import get_recent_spans
from tests.support.fakes.docker_engine import DockerEngineFake
from tests.support.fakes.otlp import plain_attributes
from tests.support.waits import POLL_INTERVAL_SECONDS
from tests.web_fakes import PUBLIC_ADDRESS, http_response, record_connects, scripted_resolver


def _engine_stats_frame() -> dict[str, Any]:
    """An Engine API stats frame: 25 percent CPU and memory, 4 pids, 1.5 MB in and 3.2 MB out."""
    return {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 500_000_000},
            "system_cpu_usage": 2_000_000_000,
            "online_cpus": 1,
        },
        "precpu_stats": {"cpu_usage": {"total_usage": 0}, "system_cpu_usage": 0},
        "memory_stats": {"usage": 52_428_800, "limit": 209_715_200, "stats": {"cache": 0}},
        "pids_stats": {"current": 4},
        "networks": {"eth0": {"rx_bytes": 1_500_000, "tx_bytes": 3_200_000}},
    }


def _scraped_request(recorder: Any) -> tuple[str, str]:
    """The request line and the Host header of the scrape the recorder saw."""
    request = next(bytes(w) for w in recorder.written if bytes(w).startswith(b"GET "))
    return request.split(b"\r\n", 1)[0].decode(), recorder.requested_hosts[-1]


def _port_of(url: str) -> int:
    return int(url.rsplit(":", 1)[-1])


# ─────────────────────────────────────────────────────────────────────────────
# 1. Models & Invariant Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("target", "endpoint", "dialled", "request_line", "host"),
    [
        (
            "httpbin.example.com:8080",
            "metrics",
            (PUBLIC_ADDRESS, 8080),
            "GET /metrics HTTP/1.1",
            "httpbin.example.com:8080",
        ),
        (
            "HTTP://example.com",
            "metrics",
            (PUBLIC_ADDRESS, 80),
            "GET /metrics HTTP/1.1",
            "example.com",
        ),
        (
            "http://example.com:9100/prefix",
            "metrics",
            (PUBLIC_ADDRESS, 9100),
            "GET /prefix/metrics HTTP/1.1",
            "example.com:9100",
        ),
        (
            "http://example.com:9100/prefix",
            "/metrics",
            (PUBLIC_ADDRESS, 9100),
            "GET /prefix/metrics HTTP/1.1",
            "example.com:9100",
        ),
    ],
)
def test_a_metrics_target_is_scraped_at_its_host_port_and_path(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    endpoint: str,
    dialled: tuple[str, int],
    request_line: str,
    host: str,
) -> None:
    """A target is scraped over http at its own host and port, below its path prefix."""
    scripted_resolver(
        monkeypatch,
        {"httpbin.example.com": [[PUBLIC_ADDRESS]], "example.com": [[PUBLIC_ADDRESS]]},
    )
    recorder = record_connects(monkeypatch, [http_response(200, "up 1\n")])

    snapshot = collect_sandbox_metrics(target, prom_endpoint=endpoint, timeout=1.0)

    assert (
        snapshot.scrape_error,
        [dial for dial in recorder.dialled if dial[0] == PUBLIC_ADDRESS],
        _scraped_request(recorder),
    ) == (None, [dialled], (request_line, host))


def test_a_metrics_target_with_a_scheme_other_than_http_is_refused() -> None:
    """Only http and https targets are scraped."""
    with pytest.raises(ValueError, match="scheme"):
        collect_sandbox_metrics("ftp://example.com")


def test_an_ipv6_metrics_target_is_scraped_at_its_bracketed_address(refusing_port: int) -> None:
    """An IPv6 target keeps its brackets and its port in the scrape URL."""
    snapshot = collect_sandbox_metrics(f"[::1]:{refusing_port}", timeout=0.5)

    assert f"http://[::1]:{refusing_port}/metrics" in (snapshot.scrape_error or "")


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


def test_parse_cgroup_v2_directory_traversal_and_forbidden_paths() -> None:
    """Verify parse_cgroup_v2_directory rejects traversal sequences and forbidden host system paths."""
    assert parse_cgroup_v2_directory("../../etc") is None
    assert parse_cgroup_v2_directory("/etc") is None
    assert parse_cgroup_v2_directory("/root") is None
    assert parse_cgroup_v2_directory("") is None


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


def test_read_cgroup_v2_metrics_fallback_to_docker_stats(
    docker_daemon: DockerEngineFake, tmp_path: Path
) -> None:
    """With no cgroup tree for the container, its resource use comes from the engine's stats."""
    container_id = docker_daemon.add_container("stats-fallback")
    docker_daemon.script_stats("stats-fallback", [_engine_stats_frame(), _engine_stats_frame()])

    metrics = read_cgroup_v2_metrics(container_id=container_id, cgroup_root=tmp_path)

    assert metrics is not None
    assert (
        metrics.cpu_percent,
        metrics.memory_current_bytes,
        metrics.memory_limit_bytes,
        metrics.memory_usage_percent,
        metrics.pids_current,
    ) == (25.0, 52_428_800, 209_715_200, 25.0, 4)


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


_LONG_LABEL = "a" * 30 + "[/b]tail"
_BRACKETED_PROMETHEUS_TEXT = (
    '# TYPE up gauge\nup{job="[/]",x="[bold red]FAKE[/]"} 1\n'
    '# TYPE hits counter\nhits{path="' + _LONG_LABEL + '"} 2\n'
)


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
    def do_GET(self) -> None:
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(_SAMPLE_PROMETHEUS_TEXT.encode("utf-8"))
        elif self.path == "/bracketed":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(_BRACKETED_PROMETHEUS_TEXT.encode("utf-8"))
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
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": POLL_INTERVAL_SECONDS}, daemon=True
    )
    thread.start()
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def malformed_endpoint() -> Generator[int]:
    """The port of a server that answers a request with a header line no HTTP client accepts."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)

    def serve() -> None:
        while True:
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            with connection:
                connection.recv(4096)
                connection.sendall(b"HTTP/1.1 200 OK\r\n[/x] [link=https://example.com]y\r\n\r\n")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield int(listener.getsockname()[1])
    listener.close()
    thread.join(timeout=2.0)


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


def test_scrape_prometheus_metrics_unreachable(refusing_port: int) -> None:
    """Test scraping unreachable Prometheus endpoint gracefully returns empty list."""
    metrics = scrape_prometheus_metrics(f"http://127.0.0.1:{refusing_port}/metrics", timeout=0.2)
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


def test_collect_sandbox_metrics_with_instance(prom_server: str, tmp_path: Path) -> None:
    """Test collect_sandbox_metrics against a SandboxInstance object."""
    instance = SandboxInstance(
        instance_id="sandbox-test-metrics-1",
        container_id="cont-metrics-1",
        name="web-service",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[
            PortBinding(container_port=8080, host_port=_port_of(prom_server), protocol="tcp")
        ],
        workspace_dir=str(tmp_path / "workspace"),
        created_at="2026-09-12T13:00:00Z",
    )
    cgroup_dir = tmp_path / "cgroup" / "system.slice" / "docker-cont-metrics-1.scope"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "memory.current").write_text("104857600\n")
    (cgroup_dir / "memory.max").write_text("209715200\n")
    (cgroup_dir / "pids.current").write_text("10\n")

    snapshot = collect_sandbox_metrics(
        instance, prom_endpoint="/metrics", timeout=2.0, cgroup_root=tmp_path / "cgroup"
    )

    assert snapshot.instance_id == "sandbox-test-metrics-1"
    assert snapshot.target == "web-service"
    assert snapshot.cgroup is not None
    assert (snapshot.cgroup.memory_usage_percent, snapshot.cgroup.pids_current) == (50.0, 10)
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


def test_engine_metrics_reports_the_resource_use_and_scrape_of_a_registered_sandbox(
    register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """The engine reads the container's resource use and scrapes its published port."""
    register_sandbox("sandbox-engine-1", name="engine-svc", host_ports=[_port_of(prom_server)])

    snapshot = WorkloadSandboxEngine().metrics("sandbox-engine-1")

    assert (
        snapshot.instance_id,
        snapshot.target,
        snapshot.cgroup.cpu_percent if snapshot.cgroup else None,
        len(snapshot.prometheus_metrics) >= 6,
    ) == ("sandbox-engine-1", "engine-svc", 2.0, True)


def test_engine_metrics_raises_not_found() -> None:
    """Test WorkloadSandboxEngine.metrics raises SandboxNotFoundError if not found."""
    with pytest.raises(SandboxNotFoundError) as raised:
        WorkloadSandboxEngine().metrics("nonexistent-id")
    assert raised.value.error_code == "SANDBOX_NOT_FOUND_ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# 7. CLI Command Tests (`devops sandbox metrics`)
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_sandbox_metrics_dry_run(cli: Callable[..., Any]) -> None:
    """Test sandbox metrics CLI command with --dry-run flag."""
    result = cli("sandbox", "metrics", "sandbox-123", "--dry-run")
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "metrics" in result.output.lower()


def test_cli_sandbox_metrics_success(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """Test sandbox metrics CLI command execution and table rendering."""
    register_sandbox("sandbox-metrics-cli", name="cli-svc", host_ports=[_port_of(prom_server)])

    result = cli("sandbox", "metrics", "sandbox-metrics-cli")

    assert result.exit_code == 0
    assert "Cgroup v2 Resource Telemetry: cli-svc" in result.output
    assert "Prometheus Application Metrics: cli-svc" in result.output
    assert "http_requests_total" in result.output


def test_cli_sandbox_metrics_with_warnings(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    docker_daemon: DockerEngineFake,
    prom_server: str,
) -> None:
    """Test sandbox metrics CLI command rendering warning callouts."""
    register_sandbox("sandbox-warn-cli", name="warn-svc", host_ports=[_port_of(prom_server)])
    frame = _engine_stats_frame()
    frame["memory_stats"] = {"usage": 471_859_200, "limit": 524_288_000, "stats": {"cache": 0}}
    docker_daemon.script_stats("sandbox-warn-cli", [frame, frame])

    result = cli("sandbox", "metrics", "sandbox-warn-cli")

    assert result.exit_code == 0
    assert "THRESHOLD ALERT: Memory usage (90.0%) exceeds" in result.output
    assert "Workload 'warn-svc' exceeded 1 operating threshold(s)." in result.output


def test_cli_sandbox_metrics_json_output(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """Test sandbox metrics CLI command with --json output flag."""
    register_sandbox("sandbox-json-cli", name="json-svc", host_ports=[_port_of(prom_server)])

    result = cli("sandbox", "metrics", "sandbox-json-cli", "--json")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert (data["instance_id"], data["target"], data["cgroup"]["cpu_percent"]) == (
        "sandbox-json-cli",
        "json-svc",
        2.0,
    )


def test_cli_sandbox_metrics_not_found(cli: Callable[..., Any], docker_daemon: Any) -> None:
    """Test sandbox metrics CLI command when target instance is not found."""
    result = cli("sandbox", "metrics", "missing")

    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_a_controller_file_that_holds_no_number_reads_as_no_value(tmp_path: Path) -> None:
    """A controller file with text where a number belongs reads as no usage; a missing limit is none."""
    cgroup_dir = tmp_path / "cgroup" / "bad-files"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "memory.current").write_text("not-an-int\n")

    metrics = parse_cgroup_v2_directory(cgroup_dir)

    assert metrics is not None
    assert (metrics.memory_current_bytes, metrics.memory_limit_bytes) == (0, None)


def test_engine_stats_become_cgroup_metrics_and_an_unreachable_engine_gives_none(
    docker_daemon: DockerEngineFake, tmp_path: Path
) -> None:
    """Engine API resource samples project into cgroup metrics, and failures return None."""
    container_id = docker_daemon.add_container("cont-valid")
    docker_daemon.script_stats("cont-valid", [_engine_stats_frame(), _engine_stats_frame()])

    res = read_cgroup_v2_metrics(container_id=container_id, cgroup_root=tmp_path)

    assert res is not None
    assert (
        res.cpu_percent,
        res.memory_current_bytes,
        res.memory_limit_bytes,
        res.pids_current,
        res.network_rx_bytes,
        res.network_tx_bytes,
    ) == (25.0, 52_428_800, 209_715_200, 4, 1_500_000, 3_200_000)

    # An unreachable daemon degrades to None rather than propagating.
    docker_daemon.fail("containers.get", RuntimeError("daemon offline"))
    assert read_cgroup_v2_metrics(container_id="cont-failed", cgroup_root=tmp_path) is None


def test_read_cgroup_v2_metrics_finds_the_docker_scope_of_a_container(tmp_path: Path) -> None:
    """The cgroup of a container is read from its docker scope under the cgroup root."""
    scope = tmp_path / "system.slice" / "docker-c1.scope"
    scope.mkdir(parents=True)
    (scope / "pids.current").write_text("7\n")

    res = read_cgroup_v2_metrics(container_id="c1", cgroup_root=tmp_path)

    assert res is not None
    assert res.pids_current == 7


def test_a_sandbox_with_no_published_port_is_scraped_on_8080(
    monkeypatch: pytest.MonkeyPatch, docker_daemon: DockerEngineFake, tmp_path: Path
) -> None:
    """Test port resolution defaults to 8080 when no bindings present."""
    recorder = record_connects(monkeypatch, [http_response(200, "up 1\n")])
    inst = SandboxInstance(
        instance_id="inst-no-ports",
        container_id="c-no-ports",
        name="no-ports",
        image="alpine",
        status=SandboxStatus.RUNNING,
        port_bindings=[],
        workspace_dir=str(tmp_path),
        created_at="2026-09-12T13:00:00Z",
    )

    collect_sandbox_metrics(inst, cgroup_root=tmp_path)

    assert ("127.0.0.1", 8080) in recorder.dialled


def test_cli_sandbox_metrics_url_target(cli: Callable[..., Any], prom_server: str) -> None:
    """Test CLI metrics invocation with raw URL target when instance not found."""
    result = cli("sandbox", "metrics", prom_server)

    assert result.exit_code == 0
    assert "Prometheus" in result.output


def test_cli_sandbox_metrics_help_metrics_timeout(cli: Callable[..., Any]) -> None:
    """Test CLI metrics --help displays dedicated Prometheus scrape timeout description."""
    result = cli("sandbox", "metrics", "--help")
    assert result.exit_code == 0
    assert "HTTP timeout in seconds for" in result.output
    assert "Prometheus metrics scraping" in result.output


_COMMAND_SPAN_ATTRIBUTES = ("sandbox.identifier", "sandbox.prom_endpoint", "sandbox.dry_run")
_ENGINE_SPAN_ATTRIBUTES = ("sandbox.identifier", "sandbox.container_id", "sandbox.prom_endpoint")


def test_the_metrics_command_and_the_engine_each_record_a_span(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    tracer: Any,
    prom_server: str,
) -> None:
    """The command records `sandbox.metrics`, and the engine `sandbox.engine.metrics`."""
    dry_run = cli("sandbox", "metrics", "test-inst", "--dry-run")
    instance = register_sandbox(
        "inst-tracer", name="tracer-svc", host_ports=[_port_of(prom_server)]
    )
    WorkloadSandboxEngine().metrics("inst-tracer")

    spans = {span["name"]: plain_attributes(span["attributes"]) for span in get_recent_spans()}
    assert dry_run.exit_code == 0
    command_span = {key: spans["sandbox.metrics"][key] for key in _COMMAND_SPAN_ATTRIBUTES}
    engine_span = {key: spans["sandbox.engine.metrics"][key] for key in _ENGINE_SPAN_ATTRIBUTES}
    assert command_span == {
        "sandbox.identifier": "test-inst",
        "sandbox.prom_endpoint": "/metrics",
        "sandbox.dry_run": True,
    }
    assert engine_span == {
        "sandbox.identifier": "inst-tracer",
        "sandbox.container_id": instance.container_id,
        "sandbox.prom_endpoint": "/metrics",
    }


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


def test_a_scrape_looks_up_its_host_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scrape resolves its host one time, at the connect, and dials the address it checked.

    No check before the request resolves the name again, so a rebinding DNS server gets no second
    question (#2431).
    """
    resolver = scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
    recorder = record_connects(monkeypatch, [http_response(200, "up 1\n")])

    result = scrape_prometheus_metrics("http://example.com:9100/metrics", timeout=1.0)

    assert (
        result.error,
        [metric.name for metric in result],
        resolver.lookups,
        [dial for dial in recorder.dialled if dial[0] == PUBLIC_ADDRESS],
    ) == (None, ["up"], {"example.com": 1}, [(PUBLIC_ADDRESS, 9100)])


def test_preserve_scrape_error_state_and_unhealthy(prom_server: str) -> None:
    """Test that failed metrics scrapes preserve error details and mark snapshot unhealthy."""
    snapshot = collect_sandbox_metrics(prom_server, prom_endpoint="/error")

    assert snapshot.scrape_error == f"HTTP 500 response from {prom_server}/error"
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


def test_parse_cgroup_v2_network_stat_and_engine_net_io(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """Test parsing network stats from a cgroup directory and a typed Engine API sample."""
    # From cgroup network.stat file
    cgroup_dir = tmp_path / "cgroup" / "net-test"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "network.stat").write_text("rx_bytes 10485760\ntx_bytes 20971520\n")
    cgroup_metrics = parse_cgroup_v2_directory(cgroup_dir)
    assert cgroup_metrics is not None
    assert cgroup_metrics.network_rx_bytes == 10485760
    assert cgroup_metrics.network_tx_bytes == 20971520

    # From the Engine API stats of a container
    container_id = docker_daemon.add_container("net-test")
    docker_daemon.script_stats("net-test", [_engine_stats_frame(), _engine_stats_frame()])
    engine_metrics = read_cgroup_v2_metrics(container_id=container_id, cgroup_root=tmp_path)
    assert engine_metrics is not None
    assert (engine_metrics.network_rx_bytes, engine_metrics.network_tx_bytes) == (
        1_500_000,
        3_200_000,
    )


def test_evaluate_threshold_warnings_status_label_5xx() -> None:
    """Test evaluate_threshold_warnings detects 5xx spikes when metric uses status instead of code."""
    prom_metrics = [
        PrometheusMetric(name="http_requests_total", labels={"status": "200"}, value=80.0),
        PrometheusMetric(name="http_requests_total", labels={"status": "500"}, value=20.0),
    ]
    warnings = evaluate_threshold_warnings(None, prom_metrics)
    assert len(warnings) >= 1
    assert any("5xx" in w for w in warnings)


def test_memory_percent_of_a_cgroup_is_zero_when_nothing_is_used(tmp_path: Path) -> None:
    """Memory use is 0.0 percent when no byte is used, and unknown when the limit is."""
    results = []
    for name, current, limit in (
        ("zero", "0", "1000"),
        ("tenth", "100", "1000"),
        ("unlimited", "100", "max"),
        ("zero-limit", "100", "0"),
    ):
        cgroup_dir = tmp_path / name
        cgroup_dir.mkdir()
        (cgroup_dir / "memory.current").write_text(f"{current}\n")
        (cgroup_dir / "memory.max").write_text(f"{limit}\n")
        metrics = parse_cgroup_v2_directory(cgroup_dir)
        results.append(metrics.memory_usage_percent if metrics else "no metrics")

    assert results == [0.0, 10.0, None, None]


def test_prometheus_exposition_timestamp_preservation() -> None:
    """Test parse_prometheus_exposition preserves exposition timestamp."""
    text = "http_requests_total 42.0 1716300000000\n"
    metrics = parse_prometheus_exposition(text)
    assert len(metrics) == 1
    assert metrics[0].name == "http_requests_total"
    assert metrics[0].value == 42.0
    assert metrics[0].timestamp == "1716300000000"


def test_scrape_prometheus_metrics_sanitizes_credentials_and_errors(refusing_port: int) -> None:
    """Test scrape_prometheus_metrics masks credentials in scrape target and error message."""
    url = f"http://admin:supersecret@127.0.0.1:{refusing_port}/metrics"
    res = scrape_prometheus_metrics(url, timeout=0.5)
    assert res.error is not None
    assert "supersecret" not in res.error
    assert "admin:***@" in res.error


def test_parse_open_fds_cgroup(tmp_path: Path) -> None:
    """Test parsing open file descriptor counts from cgroup stat files."""
    cgroup_dir = tmp_path / "cgroup" / "fds-test"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "fds.current").write_text("38\n")

    parsed = parse_cgroup_v2_directory(cgroup_dir)

    assert parsed is not None
    assert parsed.open_fds_count == 38


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


def test_cli_sandbox_metrics_renders_a_scrape_warning(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """Test CLI renders the scrape warning apart from the resource table."""
    register_sandbox("sandbox-test-scrape", name="scrape-svc", host_ports=[_port_of(prom_server)])

    result = cli("sandbox", "metrics", "sandbox-test-scrape", "--prom-endpoint", "/error")

    assert result.exit_code == 0
    assert "SCRAPE WARNING" in result.output
    assert "HTTP 500" in result.output


def test_cli_sandbox_metrics_latency_sla_option(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """The --latency-sla-ms flag sets the average request latency that raises an alert."""
    register_sandbox("sandbox-test-sla", name="sla-svc", host_ports=[_port_of(prom_server)])

    within = cli("sandbox", "metrics", "sandbox-test-sla", "--latency-sla-ms", "250.0")
    over = cli("sandbox", "metrics", "sandbox-test-sla", "--latency-sla-ms", "10.0")

    assert (
        within.exit_code,
        "High average request latency" in within.output,
        over.exit_code,
        "High average request latency" in over.output,
    ) == (0, False, 0, True)


def test_read_cgroup_v2_metrics_fallback_when_path_invalid(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """Test read_cgroup_v2_metrics falls back to container_id when cgroup_path is invalid."""
    container_id = docker_daemon.add_container("cont-fallback-1")
    docker_daemon.script_stats("cont-fallback-1", [_engine_stats_frame(), _engine_stats_frame()])

    res = read_cgroup_v2_metrics(
        container_id=container_id,
        cgroup_path=tmp_path / "nonexistent",
        cgroup_root=tmp_path,
    )

    assert res is not None
    assert res.cpu_percent == 25.0


def test_the_engine_threads_the_previous_sample_into_the_next_cpu_reading(
    register_sandbox: Callable[..., SandboxInstance], prom_server: str, tmp_path: Path
) -> None:
    """Consecutive engine readings give a CPU percent from the change in CPU time between them."""
    instance = register_sandbox("sandbox-delta-inst", host_ports=[_port_of(prom_server)])
    scope = tmp_path / "cgroup" / "system.slice" / f"docker-{instance.container_id}.scope"
    scope.mkdir(parents=True)
    (scope / "cpu.stat").write_text("usage_usec 1000000\n")
    engine = WorkloadSandboxEngine(cgroup_root=tmp_path / "cgroup")

    first = engine.metrics("sandbox-delta-inst")
    (scope / "cpu.stat").write_text("usage_usec 1500000\n")
    second = engine.metrics("sandbox-delta-inst")

    assert first.cgroup is not None
    assert second.cgroup is not None
    assert (first.cgroup.cpu_percent, second.cgroup.cpu_percent is not None) == (None, True)
    assert second.cgroup.cpu_usage_usec == 1_500_000


@pytest.mark.parametrize("forbidden", ["/sys/kernel", "/etc", "/var/log", "/usr/bin"])
def test_a_system_directory_outside_the_cgroup_tree_is_never_read_as_a_cgroup(
    forbidden: str,
) -> None:
    """Only the cgroup mount and its descendants are read; /sys siblings and system dirs are not."""
    assert parse_cgroup_v2_directory(forbidden) is None


# ─────────────────────────────────────────────────────────────────────────────
# Scraped Text Prints As Written (#955)
# ─────────────────────────────────────────────────────────────────────────────


def test_prom_table_prints_scraped_labels_as_written(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """Label values come from the scraped endpoint: their brackets print as written instead of
    raising MarkupError or styling the table. A long label string is cut before it is escaped, so
    the cut never lands inside an escape (#955)."""
    register_sandbox("sandbox-brackets", name="svc", host_ports=[_port_of(prom_server)])

    result = cli("sandbox", "metrics", "sandbox-brackets", "--prom-endpoint", "/bracketed")

    assert [
        literal in result.output
        for literal in (
            "Prometheus Application Metrics: svc",
            "job=[/]",
            "[bold red]FAKE",
            "path=" + "a" * 30 + "[/...",
        )
    ] == [True] * 4


def test_parse_prometheus_exposition_braces_in_labels_untyped_and_non_finite() -> None:
    """`text_string_to_metric_families` parses `}` inside quoted label values, maps `unknown`
    families to `untyped`, skips `NaN`/`Inf` samples, and rejects invalid `# TYPE` tokens."""
    exposition = "\n".join(
        [
            "# TYPE http_requests_total counter",
            'http_requests_total{route="/users/{id}",note="a}b"} 12',
            "bare_untyped_metric 7",
            "nan_metric NaN",
            "inf_metric +Inf",
        ]
    )
    parsed = parse_prometheus_exposition(exposition)
    assert [(m.name, m.metric_type, m.labels, m.value) for m in parsed] == [
        ("http_requests_total", "counter", {"route": "/users/{id}", "note": "a}b"}, 12.0),
        ("bare_untyped_metric", "untyped", {}, 7.0),
    ]
    with pytest.raises(ValueError, match="Invalid metric type"):
        parse_prometheus_exposition("# TYPE up [/]\nup 1\n")


def test_metrics_snapshot_prints_scrape_errors_and_target_as_written(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    malformed_endpoint: int,
) -> None:
    """A scrape error carries the HTTP client's exception text, which can quote the endpoint's own
    bytes, as a malformed header line does: it prints as written in the warning and in the error
    line, instead of raising MarkupError. So does the target in the table title (#955)."""
    target = "svc[/x]"
    register_sandbox("sandbox-malformed", name=target, host_ports=[malformed_endpoint])

    result = cli("sandbox", "metrics", "sandbox-malformed")

    assert result.exit_code == 0
    assert [
        literal in result.output
        for literal in (
            f"Cgroup v2 Resource Telemetry: {target}",
            "SCRAPE WARNING: ",
            "[/x] [link=https://example.com]y",
            f"Workload '{target}' encountered telemetry collection error: ",
        )
    ] == [True] * 4


def test_metrics_snapshot_prints_the_target_as_written_in_every_summary_line(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    docker_daemon: DockerEngineFake,
    prom_server: str,
) -> None:
    """The target is the instance name or the URL the user gave, and a URL can hold brackets: it
    prints as written in the healthy line and in the threshold-exceeded line. A threshold alert is
    the CLI's own text and holds no markup, so its line prints it as written too (#955)."""
    target = "svc[/x]"
    register_sandbox("sandbox-healthy", name=target, host_ports=[_port_of(prom_server)])
    register_sandbox("sandbox-loaded", name=target, host_ports=[_port_of(prom_server)])
    loaded = _engine_stats_frame()
    loaded["memory_stats"] = {"usage": 471_859_200, "limit": 524_288_000, "stats": {"cache": 0}}
    docker_daemon.script_stats("sandbox-loaded", [loaded, loaded])

    healthy = cli("sandbox", "metrics", "sandbox-healthy")
    exceeded = cli("sandbox", "metrics", "sandbox-loaded")

    assert [
        literal in output
        for output, literal in (
            (healthy.output, f"Workload '{target}' operating within normal performance bounds."),
            (exceeded.output, "THRESHOLD ALERT: Memory usage (90.0%) exceeds"),
            (exceeded.output, f"Workload '{target}' exceeded 1 operating threshold(s)."),
        )
    ] == [True] * 3

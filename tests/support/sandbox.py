"""A sandbox as `devops sandbox deploy` leaves it: in the registry, with its container in the Docker fake."""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable, Generator, Sequence
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from devops_cli.sandbox.models import PortBinding, SandboxInstance, SandboxStatus
from devops_cli.sandbox.registry import SandboxRegistry
from tests.support.fakes.docker_engine import DockerEngineFake
from tests.support.waits import POLL_INTERVAL_SECONDS, THREAD_HANDOFF_BOUND_SECONDS

CREATED_AT = "2026-09-12T12:00:00Z"


@pytest.fixture
def register_sandbox(
    docker_daemon: DockerEngineFake, tmp_path: Path
) -> Callable[..., SandboxInstance]:
    """Register a sandbox in the test's own registry, with a container for it in the Docker fake.

    The container is named after the instance. The sandbox runs unless `running` is false.
    `host_ports` become the published ports, each mapped to port 80 of the container.
    `log_frames` are the `(stream, bytes)` frames the container's log holds.
    """

    def register(
        instance_id: str = "sandbox-test-1",
        *,
        name: str = "api-svc",
        host_ports: Sequence[int] = (),
        running: bool = True,
        metadata: dict[str, str] | None = None,
        log_frames: Sequence[tuple[str, bytes]] | None = None,
        created_at: str = CREATED_AT,
    ) -> SandboxInstance:
        container_id = docker_daemon.add_container(instance_id, "alpine:3", running=running)
        if log_frames is not None:
            docker_daemon.script_run(instance_id, frames=log_frames)
        instance = SandboxInstance(
            instance_id=instance_id,
            container_id=container_id,
            name=name,
            image="alpine:3",
            status=SandboxStatus.RUNNING if running else SandboxStatus.STOPPED,
            port_bindings=[
                PortBinding(container_port=80, host_port=port, protocol="tcp")
                for port in host_ports
            ],
            workspace_dir=str(tmp_path / "workspace"),
            created_at=created_at,
            metadata=dict(metadata or {}),
        )
        SandboxRegistry().register_instance(instance)
        return instance

    return register


def engine_stats_frame() -> dict[str, Any]:
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


def port_of(url: str) -> int:
    return int(url.rsplit(":", 1)[-1])


SAMPLE_PROMETHEUS_TEXT = """
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


LONG_LABEL = "a" * 30 + "[/b]tail"
BRACKETED_PROMETHEUS_TEXT = (
    '# TYPE up gauge\nup{job="[/]",x="[bold red]FAKE[/]"} 1\n'
    '# TYPE hits counter\nhits{path="' + LONG_LABEL + '"} 2\n'
)


class _MockPrometheusHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(SAMPLE_PROMETHEUS_TEXT.encode("utf-8"))
        elif self.path == "/bracketed":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(BRACKETED_PROMETHEUS_TEXT.encode("utf-8"))
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
    listener.shutdown(socket.SHUT_RDWR)  # close() alone does not wake the accept() of the thread
    listener.close()
    thread.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    assert not thread.is_alive(), "the accept() of the malformed endpoint did not wake"

"""devops-cli telemetry reaches the cluster's collector, or says it does not (#547).

The default endpoint `http://localhost:4318` answered nowhere and the collector was ClusterIP
only, so Jaeger had no services and the devops-cli dashboards were empty. Exports failed without
a word, and exports still queued at exit were cancelled.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands import telemetry as telemetry_commands
from devops_cli.config.settings import load_settings, reset_settings_cache
from devops_cli.k8s import node_port
from devops_cli.k8s.node_port import ServiceNotReachableError
from devops_cli.main import app
from devops_cli.telemetry import tracer
from devops_cli.telemetry.collector import collector_endpoint
from devops_cli.telemetry.tracer import OTelTelemetryClient

cli = CliRunner(env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"})

SERVICE = {
    "spec": {
        "type": "NodePort",
        "ports": [
            {"name": "otlp", "port": 4317, "nodePort": 31317},
            {"name": "otlp-http", "port": 4318, "nodePort": 31318},
        ],
    }
}


def _fake_kubectl(service: dict[str, Any], calls: list[list[str]]) -> Any:
    def run(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        out = json.dumps(service) if "service" in cmd else "https://cluster.example:6443"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    return run


def test_the_endpoint_is_the_clusters_host_and_the_otlp_http_node_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the endpoint is found from the cluster, the context flag going first."""
    calls: list[list[str]] = []
    monkeypatch.setattr(node_port, "run_subprocess", _fake_kubectl(SERVICE, calls))

    endpoint = collector_endpoint("homelab", "otel", "collector")

    assert endpoint == "http://cluster.example:31318"
    assert calls[0][:3] == ["kubectl", "--context", "homelab"]


@pytest.mark.parametrize(
    ("service", "message"),
    [
        ({"spec": {"type": "ClusterIP", "ports": []}}, "reachable only inside the cluster"),
        ({"spec": {"type": "NodePort", "ports": [{"name": "otlp", "port": 4317}]}}, "no OTLP HTTP"),
    ],
)
def test_a_collector_workstations_cannot_reach_is_explained(
    service: dict[str, Any], message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a ClusterIP service or a missing HTTP node port is named, not guessed around."""
    monkeypatch.setattr(node_port, "run_subprocess", _fake_kubectl(service, []))

    with pytest.raises(ServiceNotReachableError, match=message):
        collector_endpoint(None, "otel", "collector")


@pytest.fixture
def own_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    config = tmp_path / "config.yaml"
    config.write_text("telemetry:\n  enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(config))
    monkeypatch.delenv("DEVOPS_OTEL_ENDPOINT", raising=False)
    monkeypatch.setattr("devops_cli.config.settings.CONFIG_PATH", config)
    reset_settings_cache()
    yield config
    reset_settings_cache()


@pytest.mark.usefixtures("own_config")
def test_connect_saves_an_endpoint_that_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `devops telemetry connect` sends telemetry to the collector it found."""
    monkeypatch.setattr(node_port, "run_subprocess", _fake_kubectl(SERVICE, []))
    monkeypatch.setattr(
        telemetry_commands.OTelTelemetryClient,
        "test_connection",
        lambda self, timeout: (True, "HTTP 200 OK", 12.0),
    )

    result = cli.invoke(app, ["telemetry", "connect"])

    reset_settings_cache()
    telemetry = load_settings().telemetry
    assert result.exit_code == 0, result.output
    assert (telemetry.endpoint, telemetry.enabled) == ("http://cluster.example:31318", True)


@pytest.mark.usefixtures("own_config")
def test_connect_keeps_the_configuration_when_the_collector_does_not_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an endpoint that does not answer is reported and not saved."""
    monkeypatch.setattr(node_port, "run_subprocess", _fake_kubectl(SERVICE, []))
    monkeypatch.setattr(
        telemetry_commands.OTelTelemetryClient,
        "test_connection",
        lambda self, timeout: (False, "connection refused", 5.0),
    )

    result = cli.invoke(app, ["telemetry", "connect"])

    reset_settings_cache()
    assert (result.exit_code, load_settings().telemetry.enabled) == (1, False)


def test_failed_exports_are_counted_and_reported_once_a_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify a collector that never answers is reported to an interactive user, once."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    reset_settings_cache()
    client = OTelTelemetryClient(endpoint="http://127.0.0.1:9")
    client._send_payload_sync("/v1/traces", {"resourceSpans": []})
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)

    tracer._warn_if_exports_failed(client)
    tracer._warn_if_exports_failed(client)

    warnings = capsys.readouterr().err
    assert (client.export_failures, client.export_successes) == (1, 0)
    assert warnings.count("Telemetry could not reach http://127.0.0.1:9") == 1
    assert "devops telemetry connect" in warnings


def test_non_interactive_runs_stay_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify CI and tests, which have no terminal, get no warning."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    client = OTelTelemetryClient(endpoint="http://127.0.0.1:9")
    client.export_failures = 3

    tracer._warn_if_exports_failed(client)

    assert capsys.readouterr().err == ""


def test_exports_in_flight_are_drained_at_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify spans queued at a command's end are sent, not cancelled, when the tool exits."""
    delivered = threading.Event()

    def slow_send(self: OTelTelemetryClient, path: str, payload: dict[str, Any]) -> None:
        time.sleep(0.2)
        delivered.set()

    monkeypatch.setattr(OTelTelemetryClient, "_send_payload_sync", slow_send)
    client = OTelTelemetryClient(endpoint="http://127.0.0.1:9")

    client._send_payload("/v1/traces", {"resourceSpans": []})
    client.shutdown()

    assert delivered.is_set()

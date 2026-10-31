"""devops-cli telemetry reaches the cluster's collector, or says it does not (#547).

The default endpoint `http://localhost:4318` answered nowhere and the collector was ClusterIP
only, so Tempo had no services and the devops-cli dashboards were empty. Exports failed without
a word, and exports still queued at exit were cancelled.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.config.settings import load_settings, reset_settings_cache
from devops_cli.k8s import node_port
from devops_cli.k8s.node_port import ServiceNotReachableError
from devops_cli.main import app
from devops_cli.telemetry import tracer
from devops_cli.telemetry.collector import collector_endpoint
from devops_cli.telemetry.exporter import CONNECT_FAILED, OtlpSignal
from devops_cli.telemetry.tracer import OTelTelemetryClient
from tests.support.config_writes import written_keys
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.otlp import FakeCollector

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
    monkeypatch.delenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", raising=False)
    monkeypatch.setattr("devops_cli.config.settings.CONFIG_PATH", config)
    reset_settings_cache()
    yield config
    reset_settings_cache()


def test_connect_saves_an_endpoint_that_answers(
    monkeypatch: pytest.MonkeyPatch, own_config: Path, isolate_data_dir: Path
) -> None:
    """Verify `devops telemetry connect` sends telemetry to the collector it found, and writes
    only `telemetry.enabled` and `telemetry.endpoint` into the config file."""
    monkeypatch.setattr(node_port, "run_subprocess", _fake_kubectl(SERVICE, []))
    monkeypatch.setattr(
        OTelTelemetryClient,
        "test_connection",
        lambda self, timeout: (True, "HTTP 200 OK", 12.0),
    )

    result = cli.invoke(app, ["telemetry", "connect"])

    reset_settings_cache()
    telemetry = load_settings().telemetry
    assert result.exit_code == 0, result.output
    assert (telemetry.endpoint, telemetry.enabled) == ("http://cluster.example:31318", True)
    assert (own_config.read_text(encoding="utf-8"), written_keys(isolate_data_dir)) == (
        "telemetry:\n  enabled: true\n  endpoint: http://cluster.example:31318\n",
        [["telemetry.enabled", "telemetry.endpoint"]],
    )


@pytest.mark.usefixtures("own_config")
def test_connect_keeps_the_configuration_when_the_collector_does_not_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an endpoint that does not answer is reported and not saved."""
    monkeypatch.setattr(node_port, "run_subprocess", _fake_kubectl(SERVICE, []))
    monkeypatch.setattr(
        OTelTelemetryClient,
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
    collector = FakeCollector()
    collector.refuse()
    client = collector.client()
    with client.span("unanswered"):
        pass
    client.flush()
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)

    tracer._warn_if_exports_failed(client)
    tracer._warn_if_exports_failed(client)

    warnings = capsys.readouterr().err
    assert (
        client.export_failures,
        client.export_successes,
        warnings.count(f"Telemetry could not reach {collector.endpoint}"),
        f"({CONNECT_FAILED})" in warnings,
        "devops telemetry connect" in warnings,
    ) == (1, 0, 1, True, True)


def test_non_interactive_runs_stay_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify CI and tests, which have no terminal, get no warning."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    collector = FakeCollector()
    collector.refuse()
    client = collector.client()
    with client.span("unanswered"):
        pass
    client.flush()

    tracer._warn_if_exports_failed(client)

    assert (client.export_failures, capsys.readouterr().err) == (1, "")


class _SlowCollector(FakeCollector):
    """A collector that takes a moment to answer, as one across a network does."""

    def __init__(self, clock: ClockFake | None = None) -> None:
        super().__init__()
        self._clock = clock

    def export(self, signal: OtlpSignal, body: bytes, content_type: str) -> None:
        if self._clock is not None:
            self._clock.sleep(0.2)
        super().export(signal, body, content_type)


def test_exports_in_flight_are_drained_at_shutdown(clock: ClockFake) -> None:
    """Verify spans queued at a command's end are sent, not cancelled, when the tool exits."""
    collector = _SlowCollector(clock)
    client = collector.client()
    with client.span("last_span"):
        pass

    client.shutdown()

    assert [export.signal for export in collector.exports] == [OtlpSignal.TRACES]


def test_a_dry_run_exports_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dry run makes no external request (#412's amendment), the collector export included."""
    collector = FakeCollector()
    client = collector.client()
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    with client.span("dry_run_span"):
        client.increment_counter("devops_cli_dry_run_total", 1, attributes={})
    client.flush()
    monkeypatch.delenv("DEVOPS_CLI_DRY_RUN")
    with client.span("real_run_span"):
        pass

    assert [span.name for span in collector.spans] == ["real_run_span"]
    assert [export.signal for export in collector.exports] == [OtlpSignal.TRACES]


def test_a_commands_own_dry_run_exports_nothing() -> None:
    """`devops k8s push-secrets --dry-run` leaves the dry-run state off, but the invocation
    is a dry run, so its command span and metrics are not exported either."""
    from devops_cli.dry_run.state import mark_dry_run_invocation

    collector = FakeCollector()
    client = collector.client()
    mark_dry_run_invocation(True)
    with client.span("push_secrets_span"):
        pass

    assert collector.spans == []


def test_warning_and_error_logs_export_to_v1_logs() -> None:
    """Verify WARNING and ERROR log records export to /v1/logs with trace correlation (#813)."""
    collector = FakeCollector()
    client = collector.client()

    client.export_log_record(
        {
            "timeUnixNano": "1000",
            "observedTimeUnixNano": "1000",
            "severityNumber": 13,
            "severityText": "WARN",
            "body": {"stringValue": "test warning"},
            "attributes": [],
            "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
            "spanId": "00f067aa0ba902b7",
        }
    )

    assert [(record["traceId"], record["body"]) for record in collector.log_records] == [
        ("4bf92f3577b34da6a3ce929d0e0e4736", {"stringValue": "test warning"})
    ]
    assert [export.signal for export in collector.exports] == [OtlpSignal.LOGS]


def test_dry_run_exports_no_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify dry run suppresses log export to /v1/logs (#813)."""
    collector = FakeCollector()
    client = collector.client()
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")

    client.export_log_record(
        {
            "timeUnixNano": "1000",
            "severityNumber": 13,
            "severityText": "WARN",
            "body": {"stringValue": "dry run warn"},
        }
    )

    assert collector.log_records == []

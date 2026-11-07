"""Unit and CLI tests for devops telemetry subcommands."""

from __future__ import annotations

from typing import Any

from typer.testing import CliRunner

from devops_cli.commands.telemetry import app
from devops_cli.dry_run import set_dry_run
from tests.support.fakes.otlp import FakeCollector

runner = CliRunner()


def test_telemetry_status_dry_run() -> None:
    """devops telemetry status --dry-run returns planned requests."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "devops telemetry status" in result.output
        assert "v1/traces" in result.output
    finally:
        set_dry_run(False)


def test_telemetry_test_dry_run() -> None:
    """devops telemetry test --dry-run returns planned requests."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["test", "--name", "unit_test_span"])
        assert result.exit_code == 0
        assert "devops telemetry test" in result.output
        assert "v1/traces" in result.output
    finally:
        set_dry_run(False)


def test_telemetry_status_live_mocked(cli: Any, otlp: FakeCollector) -> None:
    """devops telemetry status displays formatted table."""
    otlp.answer(200)

    result = cli("telemetry", "status")

    assert result.exit_code == 0
    assert "OpenTelemetry Observability Status" in result.output
    assert "OTLP Endpoint" in result.output
    assert "Connected" in result.output


def test_telemetry_test_live_mocked(cli: Any, otlp: FakeCollector) -> None:
    """devops telemetry test emits span and prints confirmation."""
    result = cli("telemetry", "test", "--name", "custom_test_span")

    assert result.exit_code == 0
    assert "Test span emitted successfully" in result.output
    assert "custom_test_span" in [span.name for span in otlp.spans]


def test_telemetry_open_ui() -> None:
    """devops telemetry open-ui prints Tempo URL."""
    result = runner.invoke(app, ["open-ui"])
    assert result.exit_code == 0
    assert "Tempo HTTP API" in result.output

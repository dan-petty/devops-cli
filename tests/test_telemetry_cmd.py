"""Unit and CLI tests for devops telemetry subcommands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.telemetry import app
from devops_cli.dry_run import set_dry_run

runner = CliRunner()


def test_telemetry_status_dry_run() -> None:
    """devops telemetry status --dry-run returns structured dry-run JSON."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "devops telemetry status" in result.output
        assert "check_telemetry_status" in result.output
    finally:
        set_dry_run(False)


def test_telemetry_test_dry_run() -> None:
    """devops telemetry test --dry-run returns structured dry-run JSON."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["test", "--name", "unit_test_span"])
        assert result.exit_code == 0
        assert "devops telemetry test" in result.output
        assert "emit_test_telemetry" in result.output
    finally:
        set_dry_run(False)


def test_telemetry_status_live_mocked() -> None:
    """devops telemetry status displays formatted table."""
    with patch(
        "devops_cli.telemetry.tracer.OTelTelemetryClient.test_connection",
        return_value=(True, "HTTP 200 OK", 5.2),
    ):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "OpenTelemetry Observability Status" in result.output
        assert "OTLP Endpoint" in result.output
        assert "Connected" in result.output


def test_telemetry_test_live_mocked() -> None:
    """devops telemetry test emits span and prints confirmation."""
    with patch(
        "devops_cli.telemetry.tracer.OTelTelemetryClient._send_payload",
        return_value=None,
    ):
        result = runner.invoke(app, ["test", "--name", "custom_test_span"])
        assert result.exit_code == 0
        assert "Test span emitted successfully" in result.output


def test_telemetry_open_ui() -> None:
    """devops telemetry open-ui prints Jaeger URL."""
    result = runner.invoke(app, ["open-ui"])
    assert result.exit_code == 0
    assert "Jaeger Tracing UI" in result.output

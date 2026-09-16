"""Unit and integration tests for Kubernetes Falco eBPF security stream and anomaly detection."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.k8s.security_stream import (
    generate_simulated_alerts,
    matches_severity_filter,
    parse_falco_alert,
    stream_security_events,
)
from devops_cli.models.k8s import (
    FalcoAlert,
    SecurityStreamRequest,
    SecurityStreamResult,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def test_falco_alert_model_defaults() -> None:
    alert = FalcoAlert(
        time="2026-09-16T04:00:00Z",
        rule="Read sensitive file untrusted",
        priority="Warning",
        output="Sensitive file /etc/shadow opened",
    )
    assert alert.priority == "Warning"
    assert alert.source == "syscall"
    assert alert.tags == []
    assert alert.output_fields == {}


def test_matches_severity_filter() -> None:
    assert matches_severity_filter("Critical", "Warning") is True
    assert matches_severity_filter("Warning", "Critical") is False
    assert matches_severity_filter("Notice", "Notice") is True
    assert matches_severity_filter("DEBUG", "Info") is False
    assert matches_severity_filter("UnknownSeverity", "Warning") is False
    assert matches_severity_filter("Critical", None) is True


def test_parse_falco_alert_json() -> None:
    raw_json = json.dumps(
        {
            "time": "2026-09-16T04:00:00Z",
            "rule": "Terminal shell in container",
            "priority": "Critical",
            "source": "syscall",
            "output": "A shell was spawned in container (user=root)",
            "output_fields": {
                "container.id": "abc1234",
                "container.name": "worker",
                "proc.name": "sh",
                "user.name": "root",
            },
            "tags": ["container", "privilege_escalation"],
        }
    )
    alert = parse_falco_alert(raw_json)
    assert alert is not None
    assert alert.rule == "Terminal shell in container"
    assert alert.priority == "Critical"
    assert alert.output_fields["proc.name"] == "sh"
    assert "privilege_escalation" in alert.tags


def test_parse_falco_alert_text() -> None:
    raw_text = "04:00:00.123456: Warning Sensitive file /etc/shadow opened (user=root proc=cat)"
    alert = parse_falco_alert(raw_text)
    assert alert is not None
    assert alert.priority == "Warning"
    assert "Sensitive file" in alert.output
    assert alert.source == "syscall"


def test_parse_falco_alert_invalid() -> None:
    assert parse_falco_alert("") is None
    assert parse_falco_alert("   ") is None


def test_generate_simulated_alerts() -> None:
    alerts = generate_simulated_alerts(count=3)
    assert len(alerts) == 3
    rules = [a.rule for a in alerts]
    assert any("privilege" in r.lower() or "shell" in r.lower() for r in rules)
    assert any("sensitive" in r.lower() or "file" in r.lower() for r in rules)
    assert any(
        "egress" in r.lower() or "network" in r.lower() or "connection" in r.lower() for r in rules
    )


def test_stream_security_events_dry_run() -> None:
    req = SecurityStreamRequest(namespace="falco", severity="Warning")
    result = stream_security_events(req, dry_run=True)
    assert isinstance(result, SecurityStreamResult)
    assert result.total_alerts > 0
    assert all(matches_severity_filter(a.priority, "Warning") for a in result.alerts)


def test_stream_security_events_simulate() -> None:
    req = SecurityStreamRequest(namespace="falco", simulate=True)
    result = stream_security_events(req, dry_run=False)
    assert isinstance(result, SecurityStreamResult)
    assert result.total_alerts >= 3
    assert result.critical_count >= 1


@patch("devops_cli.k8s.security_stream.run_subprocess")
def test_stream_security_events_live_kubectl(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(
            {
                "time": "2026-09-16T04:00:00Z",
                "rule": "Read sensitive file untrusted",
                "priority": "Warning",
                "output": "read /etc/shadow",
            }
        )
        + "\n"
        + json.dumps(
            {
                "time": "2026-09-16T04:00:01Z",
                "rule": "Privilege escalation",
                "priority": "Critical",
                "output": "root escalation detected",
            }
        ),
        stderr="",
    )

    req = SecurityStreamRequest(namespace="falco", tail_lines=50)
    result = stream_security_events(req, dry_run=False)
    assert result.total_alerts == 2
    assert result.critical_count == 1
    assert result.warning_count == 1
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "kubectl" in call_args
    assert "logs" in call_args
    assert "-n" in call_args
    assert "falco" in call_args


@patch("devops_cli.k8s.security_stream.run_subprocess")
def test_stream_security_events_kubectl_failure(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="Error from server (NotFound): daemonsets.apps 'falco' not found",
    )

    req = SecurityStreamRequest(namespace="falco")
    result = stream_security_events(req, dry_run=False)
    assert result.total_alerts == 0


def test_security_stream_cli_dry_run(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["security-stream", "--dry-run"])
    assert result.exit_code == 0
    assert (
        "Dry-run simulation" in result.output
        or "Falco" in result.output
        or "security-stream" in result.output
    )


def test_security_stream_cli_json(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["security-stream", "--simulate", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "alerts" in data
    assert "total_alerts" in data
    assert data["total_alerts"] >= 3


def test_security_stream_cli_export(
    tmp_path: pytest.TempPathFactory, cli_runner: CliRunner
) -> None:
    out_file = tmp_path / "alerts.json"
    result = cli_runner.invoke(app, ["security-stream", "--simulate", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["total_alerts"] >= 3


def test_security_stream_cli_render(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["security-stream", "--simulate"])
    assert result.exit_code == 0
    assert "Terminal shell in container" in result.output or "CRITICAL" in result.output


def test_render_security_alerts_empty() -> None:
    from devops_cli.k8s.security_stream import render_security_alerts

    empty_result = SecurityStreamResult(alerts=[])
    # Should run without error
    render_security_alerts(empty_result)


def test_get_severity_color() -> None:
    from devops_cli.k8s.security_stream import _get_severity_color

    assert _get_severity_color("Critical") == "bold red"
    assert _get_severity_color("Warning") == "bold yellow"
    assert _get_severity_color("Notice") == "bold blue"


def test_parse_text_falco_alert_fallback() -> None:
    from devops_cli.k8s.security_stream import _parse_text_falco_alert

    alert = _parse_text_falco_alert("raw unstructured anomaly line")
    assert alert is not None
    assert alert.rule == "Raw Syscall Alert"
    assert alert.output == "raw unstructured anomaly line"


@patch("devops_cli.ai.mcp.server._run_mcp_cmd")
def test_fastmcp_k8s_security_stream(mock_run: MagicMock) -> None:
    from devops_cli.ai.mcp.server import k8s_security_stream

    mock_run.return_value = '{"total_alerts": 1}'
    res = k8s_security_stream(namespace="falco", severity="Critical", tail_lines=50, simulate=True)
    assert res == '{"total_alerts": 1}'
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "security-stream" in cmd
    assert "--simulate" in cmd
    assert "--severity" in cmd
    assert "Critical" in cmd

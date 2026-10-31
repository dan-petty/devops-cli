"""Unit and integration tests for Kubernetes Falco eBPF security stream and anomaly detection."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.exceptions.k8s import KubernetesLoggingError
from devops_cli.k8s.security_stream import (
    generate_simulated_alerts,
    get_severity_color,
    matches_severity_filter,
    parse_falco_alert,
    parse_text_falco_alert,
    stream_security_events,
    tally_severity_counts,
)
from devops_cli.models.k8s import (
    FalcoAlert,
    SecurityStreamRequest,
    SecurityStreamResult,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake


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


def test_stream_security_events_live_kubectl(process_fake: ProcessFake) -> None:
    stdout = (
        json.dumps(
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
        )
    )
    process_fake.answer(lambda _call: True, ProcessAnswer(returncode=0, stdout=stdout))

    req = SecurityStreamRequest(namespace="falco", tail_lines=50)
    result = stream_security_events(req, dry_run=False)
    assert result.total_alerts == 2
    assert result.critical_count == 1
    assert result.warning_count == 1
    assert len(process_fake.calls) == 1
    call_args = process_fake.calls[0].argv
    assert "kubectl" in call_args
    assert "logs" in call_args
    assert "-n" in call_args
    assert "falco" in call_args


def test_stream_security_events_reports_kubectl_error(
    process_fake: ProcessFake, caplog: pytest.LogCaptureFixture
) -> None:
    process_fake.answer(
        lambda _call: True,
        ProcessAnswer(
            returncode=1,
            stdout="",
            stderr="Authorization: Bearer super-secret-token",
        ),
    )

    req = SecurityStreamRequest(namespace="falco")
    with caplog.at_level(logging.DEBUG, logger="devops_cli.k8s.security_stream"):
        with pytest.raises(
            KubernetesLoggingError,
            match="Failed to stream security events from Falco",
        ) as exc_info:
            stream_security_events(req, dry_run=False)

    assert (
        "super-secret-token" not in caplog.text,
        "super-secret-token" not in str(exc_info.value),
    ) == (True, True)


def test_stream_security_events_timeout_graceful(process_fake: ProcessFake) -> None:
    import subprocess

    process_fake.answer(
        lambda _call: True,
        ProcessAnswer(
            side_effect=subprocess.TimeoutExpired(
                cmd=["kubectl", "logs"],
                timeout=10,
                output="04:00:00: Warning Suspicious syscall\n",
            )
        ),
    )

    req = SecurityStreamRequest(namespace="falco", follow=True, duration_seconds=10)
    result = stream_security_events(req, dry_run=False)
    assert isinstance(result, SecurityStreamResult)
    assert result.total_alerts == 1
    assert result.warning_count == 1


def test_security_stream_cli_dry_run(cli: Callable[..., Any]) -> None:
    result = cli("k8s", "security-stream", "--dry-run")
    assert result.exit_code == 0
    assert (
        "Dry-run simulation" in result.output
        or "Falco" in result.output
        or "security-stream" in result.output
    )


def test_security_stream_cli_json(cli: Callable[..., Any]) -> None:
    result = cli("k8s", "security-stream", "--simulate", "--json")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "alerts" in data
    assert "total_alerts" in data
    assert data["total_alerts"] >= 3


def test_security_stream_cli_export(
    tmp_path: pytest.TempPathFactory, cli: Callable[..., Any]
) -> None:
    out_file = tmp_path / "alerts.json"
    result = cli("k8s", "security-stream", "--simulate", "--output", str(out_file))
    assert result.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["total_alerts"] >= 3


def test_security_stream_cli_render(cli: Callable[..., Any]) -> None:
    result = cli("k8s", "security-stream", "--simulate")
    assert result.exit_code == 0
    assert "Terminal shell in container" in result.output or "CRITICAL" in result.output


def test_render_security_alerts_empty(capsys: pytest.CaptureFixture[str]) -> None:
    from devops_cli.k8s.security_stream import render_security_alerts

    empty_result = SecurityStreamResult(alerts=[])
    render_security_alerts(empty_result)
    assert "No security anomaly events detected." in capsys.readouterr().out


def test_get_severity_color() -> None:
    assert get_severity_color("Critical") == "bold red"
    assert get_severity_color("Warning") == "bold yellow"
    assert get_severity_color("Notice") == "bold blue"


def test_parse_text_falco_alert_fallback() -> None:
    alert = parse_text_falco_alert("raw unstructured anomaly line")
    assert alert is not None
    assert alert.rule == "Raw Syscall Alert"
    assert alert.output == "raw unstructured anomaly line"


def test_security_stream_request_validation() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="Invalid severity"):
        SecurityStreamRequest(severity="Warnng")

    req = SecurityStreamRequest(severity="warning")
    assert req.severity == "WARNING"

    with pytest.raises(ValidationError):
        SecurityStreamRequest(duration_seconds=0)

    with pytest.raises(ValidationError):
        SecurityStreamRequest(duration_seconds=5000)

    with pytest.raises(ValidationError):
        SecurityStreamRequest(tail_lines=0)

    with pytest.raises(ValidationError):
        SecurityStreamRequest(tail_lines=20000)


def test_security_stream_cli_invalid_severity(cli: Callable[..., Any]) -> None:
    result = cli("k8s", "security-stream", "--severity", "Warnng")
    assert result.exit_code != 0
    assert "Invalid severity" in result.output or "Error:" in result.output


def test_security_stream_cli_failure_exit(
    process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    process_fake.answer(
        lambda _call: True,
        ProcessAnswer(returncode=1, stderr="Failed to stream security events from Falco"),
    )
    result = cli("k8s", "security-stream")
    assert result.exit_code == 1
    assert "Failed to stream security events from Falco" in result.output


def test_render_security_alerts_escapes_markup(capsys: pytest.CaptureFixture[str]) -> None:
    from devops_cli.k8s.security_stream import render_security_alerts

    alert = FalcoAlert(
        time="2026-09-16T04:00:00Z",
        rule="Rule with [markup]",
        priority="Critical",
        output="Alert containing [bold red]unescaped tags[/bold red]",
        output_fields={"test[key]": "value[with]brackets"},
        tags=["tag[one]"],
    )
    result = SecurityStreamResult(alerts=[alert], total_alerts=1)
    render_security_alerts(result)
    captured = capsys.readouterr().out
    assert "unescaped tags" in captured


def test_tally_severity_counts_canonical_ranks() -> None:
    alerts = [
        FalcoAlert(rule="r1", priority="Emergency", output="o1"),
        FalcoAlert(rule="r2", priority="Alert", output="o2"),
        FalcoAlert(rule="r3", priority="Critical", output="o3"),
        FalcoAlert(rule="r4", priority="Error", output="o4"),
        FalcoAlert(rule="r5", priority="Warning", output="o5"),
        FalcoAlert(rule="r6", priority="Notice", output="o6"),
        FalcoAlert(rule="r7", priority="Informational", output="o7"),
        FalcoAlert(rule="r8", priority="Info", output="o8"),
        FalcoAlert(rule="r9", priority="Debug", output="o9"),
    ]
    crit, warn, note = tally_severity_counts(alerts)
    assert crit == 3
    assert warn == 2
    assert note == 4

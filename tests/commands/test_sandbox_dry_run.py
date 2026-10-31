"""Tests for dry-run request plans and classifications across 9 sandbox commands.

Issue #2251: The dry-run rule (#412) states that a dry run makes zero external requests and
returns the requests that the real run would make.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.sandbox import (
    deploy as sandbox_deploy,
)
from devops_cli.commands.sandbox import (
    exec_cmd as sandbox_exec,
)
from devops_cli.commands.sandbox import (
    logs as sandbox_logs,
)
from devops_cli.commands.sandbox import (
    metrics as sandbox_metrics,
)
from devops_cli.commands.sandbox import (
    network_policy as sandbox_network_policy,
)
from devops_cli.commands.sandbox import (
    probe as sandbox_probe,
)
from devops_cli.commands.sandbox import (
    status as sandbox_status,
)
from devops_cli.commands.sandbox import (
    stop as sandbox_stop,
)
from devops_cli.commands.sandbox import (
    traces as sandbox_traces,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

SANDBOX_REQUEST_PLAN_COMMANDS = [
    ("sandbox deploy", sandbox_deploy, ["sandbox", "deploy", "--dry-run"]),
    ("sandbox status", sandbox_status, ["sandbox", "status", "--dry-run"]),
    ("sandbox stop", sandbox_stop, ["sandbox", "stop", "sbx-test", "--dry-run"]),
    ("sandbox exec", sandbox_exec, ["sandbox", "exec", "sbx-test", "ls", "--dry-run"]),
    ("sandbox probe", sandbox_probe, ["sandbox", "probe", "sbx-test", "--dry-run"]),
    ("sandbox metrics", sandbox_metrics, ["sandbox", "metrics", "sbx-test", "--dry-run"]),
    ("sandbox traces", sandbox_traces, ["sandbox", "traces", "sbx-test", "--dry-run"]),
    ("sandbox logs", sandbox_logs, ["sandbox", "logs", "sbx-test", "--dry-run"]),
    ("sandbox network-policy", sandbox_network_policy, ["sandbox", "network-policy", "--dry-run"]),
]


@pytest.fixture
def block_sandbox_externals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no Docker engine, HTTP client, socket, or subprocess executes during dry run."""

    def _fail(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"External call attempted during dry-run: {args} {kwargs}")

    monkeypatch.setattr("docker.from_env", _fail)
    monkeypatch.setattr("docker.DockerClient", _fail)
    monkeypatch.setattr("subprocess.run", _fail)
    monkeypatch.setattr("subprocess.Popen", _fail)
    monkeypatch.setattr("socket.getaddrinfo", _fail)


@pytest.mark.parametrize("name,callback,_argv", SANDBOX_REQUEST_PLAN_COMMANDS)
def test_sandbox_commands_classified_request_plan(
    name: str,
    callback: Any,
    _argv: list[str],
) -> None:
    """Criterion 1: Every sandbox command carries the request-plan classification."""
    assert get_dry_run_class(callback) == "request-plan", (
        f"Command '{name}' must have dry_run_class 'request-plan'"
    )


@pytest.mark.usefixtures("block_sandbox_externals")
@pytest.mark.parametrize("name,_callback,argv", SANDBOX_REQUEST_PLAN_COMMANDS)
def test_sandbox_dry_run_makes_no_external_requests(
    name: str,
    _callback: Any,
    argv: list[str],
    tmp_path: Path,
) -> None:
    """Criterion 3: Dry run makes zero external requests and returns exit code 0."""
    effective_argv = (
        ["sandbox", "deploy", "--workspace", str(tmp_path), "--dry-run"]
        if name == "sandbox deploy"
        else argv
    )
    result = runner.invoke(app, effective_argv)
    assert result.exit_code == 0, f"Command '{name}' dry-run failed:\n{result.output}"
    assert "Planned requests for" in result.output, (
        f"Command '{name}' output must contain 'Planned requests for':\n{result.output}"
    )


@pytest.mark.usefixtures("block_sandbox_externals")
def test_sandbox_deploy_plan_content(tmp_path: Path) -> None:
    """Verify sandbox deploy dry run shows planned container create/start requests."""
    result = runner.invoke(
        app, ["sandbox", "deploy", "--workspace", str(tmp_path), "--name", "my-sbx", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "DOCKER POST /containers/create" in result.output
    assert "my-sbx" in result.output


@pytest.mark.usefixtures("block_sandbox_externals")
def test_sandbox_status_plan_content() -> None:
    """Verify sandbox status dry run shows planned container listing request."""
    result = runner.invoke(app, ["sandbox", "status", "--all", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER GET /containers/json" in result.output


@pytest.mark.usefixtures("block_sandbox_externals")
def test_sandbox_stop_plan_content() -> None:
    """Verify sandbox stop dry run shows planned container stop and remove requests."""
    result = runner.invoke(app, ["sandbox", "stop", "sbx-1234", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER POST /containers/sbx-1234/stop" in result.output
    assert "DOCKER DELETE /containers/sbx-1234" in result.output


@pytest.mark.usefixtures("block_sandbox_externals")
def test_sandbox_exec_plan_content() -> None:
    """Verify sandbox exec dry run shows planned container exec requests."""
    result = runner.invoke(app, ["sandbox", "exec", "sbx-1234", "uptime", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER POST /containers/sbx-1234/exec" in result.output


@pytest.mark.usefixtures("block_sandbox_externals")
def test_sandbox_probe_plan_content() -> None:
    """Verify sandbox probe dry run shows planned probe requests."""
    result = runner.invoke(app, ["sandbox", "probe", "sbx-1234", "--path", "/healthz", "--dry-run"])
    assert result.exit_code == 0
    assert "GET http://sbx-1234" in result.output
    assert "/healthz" in result.output


@pytest.mark.usefixtures("block_sandbox_externals")
def test_sandbox_metrics_plan_content() -> None:
    """Verify sandbox metrics dry run shows planned metrics endpoint request."""
    result = runner.invoke(app, ["sandbox", "metrics", "sbx-1234", "--dry-run"])
    assert result.exit_code == 0
    assert "GET http://sbx-1234" in result.output
    assert "/metrics" in result.output


@pytest.mark.usefixtures("block_sandbox_externals")
def test_sandbox_traces_plan_content() -> None:
    """Verify sandbox traces dry run shows planned trace query request."""
    result = runner.invoke(
        app, ["sandbox", "traces", "sbx-1234", "--trace-id", "trace-xyz", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "trace-xyz" in result.output


@pytest.mark.usefixtures("block_sandbox_externals")
def test_sandbox_logs_plan_content() -> None:
    """Verify sandbox logs dry run shows planned logs request."""
    result = runner.invoke(app, ["sandbox", "logs", "sbx-1234", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER GET /containers/sbx-1234/logs" in result.output


@pytest.mark.usefixtures("block_sandbox_externals")
def test_sandbox_network_policy_plan_content() -> None:
    """Verify sandbox network-policy dry run shows planned policy generation and DNS resolution."""
    result = runner.invoke(
        app,
        [
            "sandbox",
            "network-policy",
            "--public-whitelist",
            "api.example.com",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "DNS resolve api.example.com:443" in result.output

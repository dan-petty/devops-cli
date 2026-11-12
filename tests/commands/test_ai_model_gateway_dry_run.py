"""Tests for dry-run request plans and classifications across 18 AI model and gateway commands.

Issue #2241: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ai import (
    agents,
    chat,
    models,
    preload,
    prewarm,
    prompt_eval_cmd,
)
from devops_cli.commands.ai import (
    test as ai_test_cmd,
)
from devops_cli.commands.ai_chaos import run_chaos_model_cmd
from devops_cli.commands.ai_gateway import (
    connect_cmd,
    failover_cmd,
    load_cmd,
    probe_backend_cmd,
    render_cmd,
    routes_cmd,
    status_cmd,
    tune_cmd,
)
from devops_cli.commands.benchmark import run_benchmark
from devops_cli.main import app
from tests.support.dry_run_classes import misclassified

pytestmark = pytest.mark.usefixtures("refuse_requests")

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("ai agents", agents, ["ai", "agents", "--dry-run"]),
    ("ai benchmark", run_benchmark, ["ai", "benchmark", "--dry-run"]),
    ("ai chaos-model", run_chaos_model_cmd, ["ai", "chaos-model", "--dry-run"]),
    ("ai chat", chat, ["ai", "chat", "--dry-run"]),
    ("ai gateway connect", connect_cmd, ["ai", "gateway", "connect", "--dry-run"]),
    ("ai gateway load", load_cmd, ["ai", "gateway", "load", "--dry-run"]),
    (
        "ai gateway probe-backend",
        probe_backend_cmd,
        ["ai", "gateway", "probe-backend", "ollama", "--dry-run"],
    ),
    ("ai gateway routes", routes_cmd, ["ai", "gateway", "routes", "--dry-run"]),
    ("ai gateway status", status_cmd, ["ai", "gateway", "status", "--dry-run"]),
    ("ai gateway tune", tune_cmd, ["ai", "gateway", "tune", "--dry-run"]),
    ("ai models", models, ["ai", "models", "--dry-run"]),
    ("ai preload", preload, ["ai", "preload", "--dry-run"]),
    ("ai prewarm", prewarm, ["ai", "prewarm", "--dry-run"]),
    ("ai prompt-eval", prompt_eval_cmd, ["ai", "prompt-eval", "--dry-run"]),
    ("ai test", ai_test_cmd, ["ai", "test", "--dry-run"]),
]

NO_EXTERNAL_REQUEST_COMMANDS = [
    (
        "ai gateway failover",
        failover_cmd,
        ["--dry-run", "ai", "gateway", "failover", "devops-chat"],
    ),
    ("ai gateway render", render_cmd, ["--dry-run", "ai", "gateway", "render"]),
]


def test_commands_carry_their_dry_run_class() -> None:
    """Model and gateway commands carry request-plan, and failover and render no-external-request."""
    assert misclassified(REQUEST_PLAN_COMMANDS, "request-plan") == {}
    assert misclassified(NO_EXTERNAL_REQUEST_COMMANDS, "no-external-request") == {}


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_run_cleanly(name: str, callback: Any, argv: list[str]) -> None:
    """Execute each request-plan command with --dry-run and verify clean exit and plan output."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' header in {name} output, got: {result.output}"
    )


def test_ai_gateway_failover_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify ai gateway failover --dry-run prints preview and modifies no state file."""
    fake_state_file = tmp_path / "gateway_state.json"

    def _block_save(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("State file save attempted during failover dry-run preview")

    from devops_cli.ai import gateway

    monkeypatch.setattr(gateway, "_save_gateway_state", _block_save)

    result = runner.invoke(app, ["ai", "gateway", "failover", "devops-chat", "--dry-run"])
    assert result.exit_code == 0, f"failover --dry-run failed: {result.output}"
    assert "Model Failover Execution" in result.output
    assert "Simulated: True (dry run)" in result.output
    assert not fake_state_file.exists()


def test_ai_gateway_failover_reset_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ai gateway failover --reset --dry-run prints reset preview and saves nothing."""

    def _block_save(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("State file save attempted during failover reset dry run")

    from devops_cli.ai import gateway

    monkeypatch.setattr(gateway, "_save_gateway_state", _block_save)

    result = runner.invoke(app, ["ai", "gateway", "failover", "--reset", "--dry-run"])
    assert result.exit_code == 0, f"failover --reset --dry-run failed: {result.output}"
    assert "Model Failover Reset" in result.output


def test_ai_gateway_render_no_external_request() -> None:
    """Verify ai gateway render runs normally under devops --dry-run."""
    result = runner.invoke(app, ["--dry-run", "ai", "gateway", "render"])
    assert result.exit_code == 0, f"render failed under --dry-run: {result.output}"


def test_ai_gateway_status_json_dry_run() -> None:
    """Verify ai gateway status returns GatewayStatus model dump with dry_run=True when format=json."""
    result = runner.invoke(app, ["ai", "gateway", "status", "--dry-run", "--format", "json"])
    assert result.exit_code == 0, f"status --format json failed: {result.output}"
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert "requests" in data
    assert len(data["requests"]) > 0


def test_ai_gateway_tune_json_dry_run() -> None:
    """Verify ai gateway tune returns TuneReport model dump with dry_run=True when format=json."""
    result = runner.invoke(app, ["ai", "gateway", "tune", "--dry-run", "--format", "json"])
    assert result.exit_code == 0, f"tune --format json failed: {result.output}"
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert "requests" in data
    assert len(data["requests"]) > 0


def test_ai_gateway_load_json_dry_run() -> None:
    """Verify ai gateway load returns PoolLoad model dump with dry_run=True when format=json."""
    result = runner.invoke(app, ["ai", "gateway", "load", "--dry-run", "--format", "json"])
    assert result.exit_code == 0, f"load --format json failed: {result.output}"
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert "requests" in data
    assert len(data["requests"]) > 0


def test_ai_chaos_model_json_dry_run() -> None:
    """Verify ai chaos-model returns ModelChaosReport with dry_run=True when format=json."""
    result = runner.invoke(app, ["ai", "chaos-model", "--dry-run", "--format", "json"])
    assert result.exit_code == 0, f"chaos-model --format json failed: {result.output}"
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert "requests" in data
    assert len(data["requests"]) > 0


def test_ai_benchmark_json_dry_run() -> None:
    """Verify ai benchmark returns BenchmarkReport with is_dry_run=True when format=json."""
    result = runner.invoke(app, ["ai", "benchmark", "--dry-run", "--format", "json"])
    assert result.exit_code == 0, f"benchmark --format json failed: {result.output}"
    data = json.loads(result.output)
    assert data.get("is_dry_run") is True
    assert "requests" in data
    assert len(data["requests"]) > 0


def test_ai_prewarm_json_dry_run() -> None:
    """Verify ai prewarm returns JSON output with dry_run=True when --json is given."""
    result = runner.invoke(app, ["ai", "prewarm", "--dry-run", "--json"])
    assert result.exit_code == 0, f"prewarm --json failed: {result.output}"
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert "requests" in data
    assert len(data["requests"]) > 0

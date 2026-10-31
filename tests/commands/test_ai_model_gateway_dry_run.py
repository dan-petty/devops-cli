"""Tests for dry-run request plans and classifications across 18 AI model and gateway commands.

Issue #2241: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.ai import (
    agents,
    chat,
    models,
    pipeline,
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
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

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
    ("ai pipeline", pipeline, ["ai", "pipeline", "test-prompt", "--dry-run"]),
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


@pytest.fixture(autouse=True)
def guard_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real socket, subprocess, or HTTP call executes during dry-run tests."""

    def _block_socket(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Network socket call attempted during dry-run preview")

    def _block_subprocess(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Subprocess execution attempted during dry-run preview")

    def _block_httpx(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("HTTP request attempted during dry-run preview")

    monkeypatch.setattr(socket.socket, "connect", _block_socket)
    monkeypatch.setattr(subprocess, "Popen", _block_subprocess)
    monkeypatch.setattr(subprocess, "run", _block_subprocess)
    monkeypatch.setattr(subprocess, "check_output", _block_subprocess)
    monkeypatch.setattr(httpx2.Client, "send", _block_httpx)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", _block_httpx)


def test_dry_run_classes_decorated() -> None:
    """Verify that each command callback is decorated with its assigned dry-run class."""
    for name, callback, _ in REQUEST_PLAN_COMMANDS:
        assert get_dry_run_class(callback) == "request-plan", (
            f"Expected {name} to have dry-run class 'request-plan'"
        )

    for name, callback, _ in NO_EXTERNAL_REQUEST_COMMANDS:
        assert get_dry_run_class(callback) == "no-external-request", (
            f"Expected {name} to have dry-run class 'no-external-request'"
        )


def test_all_18_commands_removed_from_gaps() -> None:
    """Verify all eighteen commands have been excised from tests/fixtures/dry_run_gaps.json."""
    gaps_path = Path("tests/fixtures/dry_run_gaps.json")
    assert gaps_path.exists()
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))

    expected_removed = [
        "ai agents",
        "ai benchmark",
        "ai chaos-model",
        "ai chat",
        "ai gateway connect",
        "ai gateway failover",
        "ai gateway load",
        "ai gateway probe-backend",
        "ai gateway render",
        "ai gateway routes",
        "ai gateway status",
        "ai gateway tune",
        "ai models",
        "ai pipeline",
        "ai preload",
        "ai prewarm",
        "ai prompt-eval",
        "ai test",
    ]

    for cmd_path in expected_removed:
        assert cmd_path not in gaps, f"Command '{cmd_path}' should be removed from gaps"


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_run_cleanly(name: str, callback: Any, argv: list[str]) -> None:
    """Execute each request-plan command with --dry-run and verify clean exit and plan output."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' header in {name} output, got: {result.output}"
    )


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_flag_order_global_dry_run(name: str, callback: Any, argv: list[str]) -> None:
    """Test global flag order: devops --dry-run <command>."""
    # Convert ['ai', 'models', '--dry-run'] -> ['--dry-run', 'ai', 'models']
    sub_args = [arg for arg in argv if arg != "--dry-run"]
    global_argv = ["--dry-run", *sub_args]
    result = runner.invoke(app, global_argv)
    assert result.exit_code == 0, f"{name} failed with global --dry-run: {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' in global dry run of {name}, got: {result.output}"
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

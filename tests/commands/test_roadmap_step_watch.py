"""`devops roadmap step watch`: command tests for roadmap step watch (#5021)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


def test_watch_cmd_missing_pull_exits_one(cli: Cli) -> None:
    result = cli("roadmap", "step", "watch", "--repo", "owner/repo")
    assert result.exit_code == 1
    assert "Pass --pull" in result.output


def test_watch_cmd_no_block_outputs_json(cli: Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.roadmap.steps import watch as watch_mod
    from devops_cli.roadmap.steps.watch import PRVerdict, WatchVerdict

    def _fake_watch(*args: Any, **kwargs: Any) -> WatchVerdict:
        return WatchVerdict(verdict=PRVerdict.READY, reason="All checks passed.")

    monkeypatch.setattr(watch_mod, "watch", _fake_watch)

    result = cli(
        "roadmap",
        "step",
        "watch",
        "--repo",
        "owner/repo",
        "--pull",
        "42",
        "--no-block",
    )
    assert result.exit_code == 0, result.output
    lines = [
        line for line in result.output.strip().splitlines() if "watch" in line or "verdict" in line
    ]
    assert lines, "Expected json output"
    payload = json.loads(lines[-1])
    assert payload["verdict"] == "ready"
    assert payload["pull"] == 42


def test_watch_cmd_dry_run_exits_zero(cli: Cli) -> None:
    result = cli(
        "roadmap",
        "step",
        "watch",
        "--repo",
        "owner/repo",
        "--pull",
        "42",
        "--dry-run",
    )
    assert result.exit_code == 0

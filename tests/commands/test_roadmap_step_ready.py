"""`devops roadmap step ready`: command tests for roadmap step ready (#5021)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.exceptions import RoadmapImplementError

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


def test_ready_cmd_missing_pull_exits_one(cli: Cli) -> None:
    result = cli("roadmap", "step", "ready", "--repo", "owner/repo")
    assert result.exit_code == 1
    assert "Pass --pull" in result.output


def test_ready_cmd_marks_ready_and_outputs_json(cli: Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.roadmap.steps import ready as ready_mod

    marked: list[tuple[str, int, str | None]] = []

    def _fake_mark_ready(repo: str, pull: int, expected_head: str | None = None) -> None:
        marked.append((repo, pull, expected_head))

    monkeypatch.setattr(ready_mod, "mark_ready", _fake_mark_ready)

    result = cli(
        "roadmap",
        "step",
        "ready",
        "--repo",
        "owner/repo",
        "--pull",
        "42",
        "--head",
        "1234567890ab",
        "--force",
    )
    assert result.exit_code == 0, result.output
    assert marked == [("owner/repo", 42, "1234567890ab")]
    lines = [
        line for line in result.output.strip().splitlines() if "ready" in line or "job" in line
    ]
    assert lines, "Expected json output"
    payload = json.loads(lines[-1])
    assert payload["status"] == "ready"
    assert payload["pull"] == 42


def test_ready_cmd_head_moved_exits_one(cli: Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.roadmap.steps import ready as ready_mod

    def _fail_mark_ready(*args: Any, **kwargs: Any) -> None:
        raise RoadmapImplementError("PR #42 head moved")

    monkeypatch.setattr(ready_mod, "mark_ready", _fail_mark_ready)

    result = cli(
        "roadmap",
        "step",
        "ready",
        "--repo",
        "owner/repo",
        "--pull",
        "42",
        "--head",
        "1234567890ab",
        "--force",
    )
    assert result.exit_code == 1
    assert "head moved" in result.output


def test_ready_cmd_dry_run_exits_zero(cli: Cli) -> None:
    result = cli(
        "roadmap",
        "step",
        "ready",
        "--repo",
        "owner/repo",
        "--pull",
        "42",
        "--dry-run",
    )
    assert result.exit_code == 0

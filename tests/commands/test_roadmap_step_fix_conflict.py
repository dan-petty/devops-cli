"""Tests for `devops roadmap step fix-conflict` CLI command (#5019)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


def test_fix_conflict_help(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-conflict", "--help")
    assert result.exit_code == 0
    assert "--pull" in result.output
    assert "--confirm" in result.output


def test_fix_conflict_missing_pull(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-conflict", "--repo", "example/project")
    assert result.exit_code == 1
    assert "Pass --pull" in result.output


def test_fix_conflict_invalid_repo(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-conflict", "--repo", "invalid", "--pull", "42")
    assert result.exit_code == 1
    assert "Cannot resolve the repository" in result.output


def test_fix_conflict_dry_run(cli: Cli) -> None:
    result = cli(
        "roadmap", "step", "fix-conflict", "--repo", "example/project", "--pull", "42", "--dry-run"
    )
    assert result.exit_code == 0


def test_confirm_outside_a_runner_job_runs_no_step(
    cli: Cli, roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tier 1 runs code of the pull request, so `--confirm` runs only in a runner Job. On a
    workstation the command stops before the step, with the error that names the runner."""
    from devops_cli.roadmap.steps import fix_conflict

    seen: list[str] = []
    monkeypatch.setattr(fix_conflict, "run_fix_conflict", lambda *_, **__: seen.append("step"))

    result = cli(
        "roadmap", "step", "fix-conflict", "--repo", "example/project", "--pull", "42", "--confirm"
    )

    assert (result.exit_code, seen) == (1, [])
    assert "runner" in result.output


def test_a_confirmed_round_in_a_runner_makes_its_process_unreadable_before_the_step(
    cli: Cli, roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tier 1 runs code of the pull request as the user of the Job, so the Job checks that it is a
    runner, clears its dumpable flag and adopts the orphans of that code before the step, as the
    fix-checks Job does. The spies replace the kernel calls, which would change the test run."""
    from devops_cli.core import process_hardening
    from devops_cli.roadmap.implement import implement_run
    from devops_cli.roadmap.steps import fix_conflict
    from devops_cli.roadmap.steps.fix_conflict import FixConflictReport, FixConflictResult

    seen: list[str] = []
    monkeypatch.setattr(implement_run, "require_runner", lambda _repo: seen.append("runner"))
    monkeypatch.setattr(
        process_hardening, "deny_environment_reads", lambda: seen.append("unreadable")
    )
    monkeypatch.setattr(process_hardening, "adopt_orphans", lambda: seen.append("orphans"))

    def step(*_: Any, **kwargs: Any) -> FixConflictReport:
        seen.append(f"step confirm={kwargs['confirm']}")
        return FixConflictReport("example/project", 42, FixConflictResult.NO_CONFLICT)

    monkeypatch.setattr(fix_conflict, "run_fix_conflict", step)

    result = cli(
        "roadmap", "step", "fix-conflict", "--repo", "example/project", "--pull", "42", "--confirm"
    )

    assert result.exit_code == 0
    assert seen == ["runner", "unreadable", "orphans", "step confirm=True"]

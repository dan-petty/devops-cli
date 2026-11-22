"""Tests for `devops roadmap step fix-conflict` CLI command (#5019)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
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
    workstation the command stops before the step, with the error that names the runner. The
    process is unreadable first; the spies replace the kernel calls, which would change the test
    run."""
    from devops_cli.core import process_hardening
    from devops_cli.roadmap.steps import fix_conflict

    monkeypatch.setattr(process_hardening, "deny_environment_reads", lambda: None)
    monkeypatch.setattr(process_hardening, "adopt_orphans", lambda: None)
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
    """Tier 1 runs code of the pull request as the user of the Job, so the Job clears its dumpable
    flag and adopts the orphans of that code first, then checks that it is a runner, as the
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
    assert seen == ["unreadable", "orphans", "runner", "step confirm=True"]


@pytest.mark.parametrize(
    ("phase", "runs", "runner"),
    [
        ("prepare", "prepare_phase", "runner"),
        ("agent", "agent_phase", "agent runner"),
        ("publish", "publish_phase", "runner"),
    ],
)
def test_each_confirmed_phase_makes_its_process_unreadable_before_the_phase(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    phase: str,
    runs: str,
    runner: str,
) -> None:
    """Each phase of a confirmed round clears its dumpable flag and adopts orphans first. The agent
    phase checks that it holds no App key, and the other phases that they act as the App, as the
    phases of fix-checks do (#6703)."""
    from devops_cli.core import process_hardening
    from devops_cli.roadmap.implement import implement_run
    from devops_cli.roadmap.steps import fix_conflict_phases

    seen: list[str] = []
    monkeypatch.setattr(implement_run, "require_runner", lambda _repo: seen.append("runner"))
    monkeypatch.setattr(implement_run, "require_agent_runner", lambda: seen.append("agent runner"))
    monkeypatch.setattr(
        process_hardening, "deny_environment_reads", lambda: seen.append("unreadable")
    )
    monkeypatch.setattr(process_hardening, "adopt_orphans", lambda: seen.append("orphans"))
    monkeypatch.setattr(fix_conflict_phases, runs, lambda *_, **__: seen.append("phase"))

    result = cli(
        "roadmap",
        "step",
        "fix-conflict",
        "--repo",
        "example/project",
        "--pull",
        "42",
        "--confirm",
        "--phase",
        phase,
        "--work",
        str(tmp_path),
    )

    assert result.exit_code == 0, result.output
    assert seen == ["unreadable", "orphans", runner, "phase"]


@pytest.mark.parametrize("phase", ["agent", "publish"])
def test_a_phase_of_a_confirmed_round_needs_a_run_folder(cli: Cli, phase: str) -> None:
    result = cli(
        "roadmap",
        "step",
        "fix-conflict",
        "--repo",
        "example/project",
        "--pull",
        "42",
        "--phase",
        phase,
        "--confirm",
    )

    assert result.exit_code == 1
    assert "--work" in result.output

"""Tests for `devops roadmap step fix-checks` CLI command (#5023)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


def test_fix_checks_help(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-checks", "--help")
    assert result.exit_code == 0
    assert "--pull" in result.output
    assert "--confirm" in result.output
    assert "--dry-run" in result.output


def test_fix_checks_missing_pull(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-checks", "--repo", "example/project")
    assert result.exit_code == 1
    assert "Pass --pull" in result.output


def test_fix_checks_invalid_repo(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-checks", "--repo", "invalid", "--pull", "42")
    assert result.exit_code == 1
    assert "Cannot resolve the repository" in result.output


def test_fix_checks_dry_run(cli: Cli) -> None:
    result = cli(
        "roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42", "--dry-run"
    )
    assert result.exit_code == 0


def test_fix_checks_command_success(cli: Cli) -> None:
    from devops_cli.commands.roadmap_step_fix_checks import set_fix_checks_runner
    from devops_cli.roadmap.steps.fix_checks import FixChecksReport, FixChecksResult

    def fake_runner(*args: Any, **kwargs: Any) -> FixChecksReport:
        return FixChecksReport(
            repo="example/project",
            pull=42,
            result=FixChecksResult.REPAIRED,
            head="abc",
            rounds=1,
            errors=0,
            reason="tier 1",
        )

    set_fix_checks_runner(fake_runner)
    try:
        result = cli("roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42")
        assert result.exit_code == 0
        assert '"result": "repaired"' in result.output
    finally:
        set_fix_checks_runner(None)


def test_fix_checks_command_error(cli: Cli) -> None:
    from devops_cli.commands.roadmap_step_fix_checks import set_fix_checks_runner
    from devops_cli.exceptions import DevOpsCLIError

    def fake_failing_runner(*args: Any, **kwargs: Any) -> Any:
        raise DevOpsCLIError("custom test error")

    set_fix_checks_runner(fake_failing_runner)
    try:
        result = cli("roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42")
        assert result.exit_code == 1
        assert "Could not fix checks on PR #42: custom test error" in result.output
    finally:
        set_fix_checks_runner(None)

"""Tests for `devops roadmap step fix-checks` CLI command (#5023)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from tests.support.fakes.github import github_json

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

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


def test_fix_checks_command_success(
    cli: Cli, github_api: GitHubApiFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    github_api.route(
        "GET",
        "/repos/example/project/pulls/42",
        github_json(
            {
                "state": "closed",
                "draft": True,
                "head": {"ref": "feat/42-foo", "sha": "1" * 40},
                "base": {"ref": "main"},
                "user": {"login": "devops-cli[bot]"},
                "labels": [],
            }
        ),
    )
    result = cli("roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42")
    assert result.exit_code == 0
    assert '"result": "skipped"' in result.output


def test_fix_checks_command_error(
    cli: Cli, github_api: GitHubApiFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    github_api.route(
        "GET",
        "/repos/example/project/pulls/42",
        github_json({"message": "Server error"}, status=500),
    )
    result = cli("roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42")
    assert result.exit_code == 1
    assert "Could not fix checks on PR #42" in result.output

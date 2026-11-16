"""Tests for `devops roadmap step review` (#5969).

GitHub's REST API is faked at its edge. The step itself is tested in
`tests/roadmap/steps/test_roadmap_step_review.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.settings import reset_settings_cache
from tests.support.fakes.github import github_json

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]
REPO = "example/project"


@pytest.fixture
def mode_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_REVIEW_MODE", "on")
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_the_help_names_the_options(cli: Cli) -> None:
    result = cli("roadmap", "step", "review", "--help")

    assert result.exit_code == 0
    assert all(option in result.output for option in ("--pull", "--head", "--confirm"))


def test_a_run_without_a_pull_request_exits_1(cli: Cli) -> None:
    result = cli("roadmap", "step", "review", "--repo", REPO)

    assert result.exit_code == 1
    assert "Pass --pull" in result.output


def test_a_dry_run_sends_no_request(
    cli: Cli, github_api: GitHubApiFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    result = cli("roadmap", "step", "review", "--repo", REPO, "--pull", "42", "--dry-run")

    assert (result.exit_code, github_api.sent) == (0, [])


def test_a_closed_pull_request_is_skipped(
    cli: Cli, github_api: GitHubApiFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls/42",
        github_json(
            {
                "state": "closed",
                "draft": True,
                "head": {"ref": "feat/42-sample", "sha": "1" * 40},
                "base": {"ref": "main"},
                "user": {"login": "devops-cli[bot]"},
                "labels": [],
            }
        ),
    )

    result = cli("roadmap", "step", "review", "--repo", REPO, "--pull", "42")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "job": "review",
        "repo": REPO,
        "pull": 42,
        "result": "skipped",
        "written": False,
        "head": "1" * 40,
        "reason": "The pull request is closed or merged.",
    }


@pytest.mark.usefixtures("mode_on")
def test_confirm_in_the_mode_on_outside_a_runner_job_reads_no_pull_request(
    cli: Cli, github_api: GitHubApiFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    result = cli("roadmap", "step", "review", "--repo", REPO, "--pull", "42", "--confirm")

    assert result.exit_code == 1
    assert "Could not review PR #42" in result.output
    assert github_api.sent == []

"""Tests for `devops roadmap step fix-checks` CLI command (#5023, #5971).

GitHub's REST API and `gh` are faked at their edges. The repair in a runner Job is tested end to
end in `tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from tests.support.fakes.github import github_json
from tests.support.fakes.process import ProcessAnswer

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.process import ProcessFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]

HEAD = "1" * 40
STATIC_FAIL = {
    "name": "Static Analysis",
    "status": "completed",
    "conclusion": "failure",
    "html_url": "https://github.com/example/project/actions/runs/101/job/202",
}
TYPE_ERROR = (
    "src/devops_cli/shout.py:5: error: Incompatible return value type "
    '(got "int", expected "str")  [return-value]\n'
)


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


def test_confirm_outside_a_runner_job_reads_no_pull_request(
    cli: Cli, github_api: GitHubApiFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    result = cli(
        "roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42", "--confirm"
    )

    assert result.exit_code == 1
    assert "Could not fix checks on PR #42" in result.output
    assert github_api.sent == []


def test_the_command_without_confirm_plans_a_repair_and_writes_nothing(
    cli: Cli,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """The case of #5971 in the mode `plan`: a bot draft whose `Static Analysis` check failed with a
    log that names a file of the plan."""
    api, gh = github_api_and_gh
    api.route(
        "GET",
        "/repos/example/project/pulls/42",
        github_json(
            {
                "state": "open",
                "draft": True,
                "head": {"ref": "feat/42-foo", "sha": HEAD},
                "base": {"ref": "main"},
                "user": {"login": "devops-cli[bot]"},
                "labels": [],
            }
        ),
    )
    api.route(
        "GET",
        f"/repos/example/project/commits/{HEAD}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [STATIC_FAIL]}),
    )
    gh.answer(lambda call: call.argv[1:3] == ("run", "view"), ProcessAnswer(stdout=TYPE_ERROR))

    result = cli("roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "job": "fix_checks",
        "repo": "example/project",
        "pull": 42,
        "result": "planned",
        "head": HEAD,
        "errors": 1,
        "reason": "Plan: repair check `Static Analysis` with tier 1, then the model in the plan "
        "scope",
    }
    assert [request.method for request in api.sent] == ["GET", "GET"]

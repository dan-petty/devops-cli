"""`devops pr copilot-pass`: Copilot's passes on the release pull request, held to the budget in
`.github/roadmap.toml` (#1345).

Every read is canned: the pull request through a fake `run_gh`, its reviews and timeline through
the fake GitHub API (`github_api`), and the roadmap configuration through the in-memory roadmap
store. No test starts gh or reaches the network.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.github.copilot_budget import CopilotPasses, count_copilot_passes
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.github_session_fakes import GitHubApiFake, github_json

_REPO = "dan-petty/devops-cli"
_PULL = f"repos/{_REPO}/pulls/7"
_REVIEWS = f"/repos/{_REPO}/pulls/7/reviews?per_page=100"
_TIMELINE = f"/repos/{_REPO}/issues/7/timeline?per_page=100"
_COPILOT = {"login": "copilot-pull-request-reviewer[bot]", "type": "Bot"}
_REQUEST = ["gh", "pr", "edit", "7", "--add-reviewer", "@copilot", "--repo", _REPO]


def _pull_request(head: str = "release/v0.2.37", base: str = "main") -> dict[str, Any]:
    """Pull request #7 as GitHub's REST API answers for it, both sides in this repository."""
    repo = {"full_name": _REPO, "default_branch": "main"}
    return {"number": 7, "head": {"ref": head, "repo": repo}, "base": {"ref": base, "repo": repo}}


def _copilot_review(when: str) -> dict[str, Any]:
    return {
        "user": _COPILOT,
        "state": "COMMENTED",
        "body": "### Changes recommended",
        "submitted_at": when,
    }


class _Gh:
    """`run_gh`, answering the pull request read with `pull_request` and recording every call."""

    def __init__(self, pull_request: dict[str, Any], edit_returncode: int = 0) -> None:
        self.calls: list[list[str]] = []
        self._pull_request = pull_request
        self._edit_returncode = edit_returncode

    def __call__(self, args: list[str], **_: object) -> MagicMock:
        import json

        self.calls.append(list(args))
        if args[:3] == ["gh", "api", _PULL]:
            return MagicMock(returncode=0, stdout=json.dumps(self._pull_request), stderr="")
        if args[:3] == ["gh", "pr", "edit"]:
            failed = "gh: Could not request reviewer (HTTP 422)" if self._edit_returncode else ""
            return MagicMock(returncode=self._edit_returncode, stdout="", stderr=failed)
        return MagicMock(returncode=1, stdout="", stderr=f"unrouted: {args!r}")

    @property
    def requests(self) -> list[list[str]]:
        """The Copilot pass requests made, as gh commands."""
        return [call for call in self.calls if call[:3] == ["gh", "pr", "edit"]]


@pytest.fixture
def budget_roadmap(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The roadmap configuration on the default branch, leaving `release_copilot_passes` at its
    default of 2."""
    roadmap_store.seed_file(".github/roadmap.toml", "board = 2\n")
    return roadmap_store


@pytest.fixture(autouse=True)
def gh_on_path() -> Iterator[None]:
    with patch("devops_cli.commands.pr.check_binary", return_value=True):
        yield


def _run(gh: _Gh, *args: str) -> Any:
    with (
        patch("devops_cli.github.pr_monitor.run_gh", side_effect=gh),
        patch("devops_cli.github.copilot_budget.run_gh", side_effect=gh),
    ):
        return CliRunner().invoke(app, ["copilot-pass", "7", "--repo", _REPO, *args])


def _route(
    github_api: GitHubApiFake, reviews: list[Any], timeline: list[Any] | None = None
) -> None:
    github_api.route("GET", _REVIEWS, github_json(reviews))
    github_api.route("GET", _TIMELINE, github_json(timeline or []))


@pytest.mark.usefixtures("budget_roadmap")
def test_with_no_copilot_review_a_pass_is_requested(github_api: GitHubApiFake) -> None:
    """The ruleset gave no pass when the release pull request opened, so the command asks for
    the first one."""
    _route(github_api, [])
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, "1 of 2" in result.output) == (0, [_REQUEST], True)


@pytest.mark.usefixtures("budget_roadmap")
def test_one_copilot_review_of_two_leaves_a_pass_to_request(github_api: GitHubApiFake) -> None:
    _route(github_api, [_copilot_review("2026-10-18T10:00:00Z")])
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, "2 of 2" in result.output) == (0, [_REQUEST], True)


@pytest.mark.usefixtures("budget_roadmap")
def test_two_copilot_reviews_spend_the_budget_and_nothing_is_requested(
    github_api: GitHubApiFake,
) -> None:
    _route(
        github_api,
        [_copilot_review("2026-10-18T10:00:00Z"), _copilot_review("2026-10-18T12:00:00Z")],
    )
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, "Copilot budget spent: 2 of 2" in result.output) == (
        1,
        [],
        True,
    )


@pytest.mark.usefixtures("budget_roadmap")
def test_a_pass_still_running_counts_against_the_budget(github_api: GitHubApiFake) -> None:
    """One submitted review and a second pass Copilot has started spend a budget of 2."""
    timeline = [
        {"event": "reviewed", "user": _COPILOT},
        {"event": "copilot_work_started", "actor": {"login": "Copilot"}},
    ]
    _route(github_api, [_copilot_review("2026-10-18T10:00:00Z")], timeline)
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, "2 of 2" in result.output) == (1, [], True)


@pytest.mark.usefixtures("budget_roadmap")
def test_a_user_whose_login_contains_copilot_does_not_count(github_api: GitHubApiFake) -> None:
    """Only Copilot's own logins are Copilot's: two reviews by people named after it leave the
    whole budget."""
    people = [
        {"user": {"login": "copilot-fan", "type": "User"}, "state": "COMMENTED", "body": ""},
        {"user": {"login": "my-copilot", "type": "User"}, "state": "APPROVED", "body": ""},
    ]
    _route(github_api, people)
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, "1 of 2" in result.output) == (0, [_REQUEST], True)


@pytest.mark.usefixtures("budget_roadmap")
def test_a_pull_request_that_is_not_the_release_pull_request_is_refused(
    github_api: GitHubApiFake,
) -> None:
    """Copilot reviews only the release pull request (ADR 0004): an item pull request into the
    release branch is refused before its reviews or the budget are read."""
    gh = _Gh(_pull_request(head="feat/1345-copilot-pass-budget", base="release/v0.2.37"))
    result = _run(gh)
    assert (
        result.exit_code,
        gh.requests,
        github_api.requested,
        "not the release pull request" in result.output,
    ) == (1, [], [], True)


@pytest.mark.usefixtures("budget_roadmap")
def test_unread_reviews_fail_with_the_read_error(github_api: GitHubApiFake) -> None:
    """With the reviews unread the passes are unknown, so nothing is requested."""
    github_api.route("GET", _REVIEWS, github_json({"message": "Bad Gateway"}, status=502))
    github_api.route("GET", _TIMELINE, github_json([]))
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, "HTTP 502" in result.output) == (1, [], True)


@pytest.mark.usefixtures("budget_roadmap")
def test_a_refused_request_fails_with_gh_error(github_api: GitHubApiFake) -> None:
    _route(github_api, [])
    gh = _Gh(_pull_request(), edit_returncode=1)
    result = _run(gh)
    assert (result.exit_code, gh.requests, "HTTP 422" in result.output) == (1, [_REQUEST], True)


def test_dry_run_makes_no_request_and_lists_the_requests(
    github_api: GitHubApiFake, roadmap_store_repos: list[str], roadmap_store: InMemoryRoadmapStore
) -> None:
    """`--dry-run` reads nothing either (#412): it prints the reads and the request a real run
    would make, the request under its condition."""
    gh = _Gh(_pull_request())
    result = _run(gh, "--dry-run")
    assert (
        result.exit_code,
        gh.calls,
        github_api.requested,
        roadmap_store_repos,
        " ".join(_REQUEST) in result.output,
        f"{_REPO}/pulls/7/reviews" in result.output,
    ) == (0, [], [], [], True, True)


def test_dry_run_without_a_number_plans_the_branchs_pull_request(
    github_api: GitHubApiFake, roadmap_store_repos: list[str], roadmap_store: InMemoryRoadmapStore
) -> None:
    """Without a number the pull request is the current branch's, which a dry run names with a
    placeholder rather than reading it."""
    gh = _Gh(_pull_request())
    with (
        patch("devops_cli.github.pr_monitor.run_gh", side_effect=gh),
        patch("devops_cli.github.copilot_budget.run_gh", side_effect=gh),
    ):
        result = CliRunner().invoke(app, ["copilot-pass", "--repo", _REPO, "--dry-run"])
    assert (result.exit_code, gh.calls, github_api.requested, roadmap_store_repos) == (
        0,
        [],
        [],
        [],
    )
    assert "gh pr edit '<number>' --add-reviewer @copilot" in result.output


@pytest.mark.parametrize(
    ("submitted", "running", "budget", "used", "spent"),
    [
        (0, False, 2, 0, False),
        (1, False, 2, 1, False),
        (1, True, 2, 2, True),
        (3, False, 2, 3, True),
    ],
)
def test_the_passes_used_are_the_submitted_reviews_and_a_running_one(
    submitted: int, running: bool, budget: int, used: int, spent: bool
) -> None:
    reviews = [_copilot_review(f"2026-10-18T1{n}:00:00Z") for n in range(submitted)]
    passes = count_copilot_passes(reviews, running=running, budget=budget)
    assert (passes, passes.used, passes.spent) == (
        CopilotPasses(submitted=submitted, running=running, budget=budget),
        used,
        spent,
    )


def test_a_review_counts_by_copilots_rest_or_graphql_login_and_by_no_other() -> None:
    reviews = [
        {"user": _COPILOT},
        {"author": {"login": "copilot-pull-request-reviewer"}},
        {"user": {"login": "copilot-pull-request-reviewer-fan", "type": "User"}},
        {"user": {"login": "copilot-swe-agent[bot]", "type": "Bot"}},
        {"user": None},
        "not a review",
    ]
    assert count_copilot_passes(reviews, running=False, budget=2).submitted == 2

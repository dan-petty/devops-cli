"""`devops pr copilot-pass`: Copilot's passes on the release pull request, held to the budget in
`.github/roadmap.toml` (#1345).

Every read is canned: the pull request through a fake `run_gh`, its reviews and timeline through
the fake GitHub API (`github_api`) in the shapes GitHub recorded on #1283
(`tests/copilot_review_payloads.py`), and the roadmap configuration through the in-memory roadmap
store. No test starts gh or reaches the network.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.copilot_budget import (
    CopilotPasses,
    count_copilot_passes,
    plan_copilot_pass,
    read_copilot_passes,
    request_copilot_pass,
)
from devops_cli.github.pr_monitor import resolve_branch_pr_number
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.copilot_review_payloads import (
    FIRST_REVIEW_ID,
    MAINTAINER,
    REVIEWS_COPILOT,
    SECOND_REVIEW_ID,
    copilot_pass,
    copilot_review,
    review_request_removed,
    review_requested,
    work_started,
)
from tests.github_session_fakes import GitHubApiFake, github_json

_REPO = "dan-petty/devops-cli"
_PULL = f"repos/{_REPO}/pulls/7"
_REVIEWS = f"/repos/{_REPO}/pulls/7/reviews?per_page=100"
_TIMELINE = f"/repos/{_REPO}/issues/7/timeline?per_page=100"
_REQUEST = ["gh", "pr", "edit", "7", "--add-reviewer", "@copilot", "--repo", _REPO]
_ONE_PASS = [copilot_review(FIRST_REVIEW_ID)]
_TWO_PASSES = [
    copilot_review(FIRST_REVIEW_ID),
    copilot_review(SECOND_REVIEW_ID, submitted_at="2026-10-07T15:35:57Z"),
]
_TWO_PASSES_TIMELINE = [*copilot_pass(FIRST_REVIEW_ID), *copilot_pass(SECOND_REVIEW_ID)]


def _pull_request(
    head: str = "release/v0.2.37", base: str = "main", *, state: str = "open", merged: bool = False
) -> dict[str, Any]:
    """Pull request #7 as GitHub's REST API answers for it, both sides in this repository."""
    repo = {"full_name": _REPO, "default_branch": "main"}
    sides = {"head": {"ref": head, "repo": repo}, "base": {"ref": base, "repo": repo}}
    return {"number": 7, "state": state, "merged": merged, **sides}


class _Gh:
    """`run_gh`, answering the pull request read with `pull_request` and the request with
    `edit` (exit code, stdout, stderr), and recording every call."""

    def __init__(self, pull_request: dict[str, Any], edit: tuple[int, str, str] = (0, "", "")):
        self.calls: list[list[str]] = []
        self._pull_request = pull_request
        self._edit = edit

    def __call__(self, args: list[str], **_: object) -> MagicMock:
        self.calls.append(list(args))
        if args[:3] == ["gh", "api", _PULL]:
            return MagicMock(returncode=0, stdout=json.dumps(self._pull_request), stderr="")
        if args[:3] == ["gh", "pr", "edit"]:
            returncode, stdout, stderr = self._edit
            return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)
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


@contextmanager
def _gh_patched(gh: _Gh) -> Iterator[None]:
    """`run_gh` replaced by `gh` wherever the pass and its reads run it."""
    with (
        patch("devops_cli.github.pr_monitor.run_gh", side_effect=gh),
        patch("devops_cli.github.copilot_budget.run_gh", side_effect=gh),
    ):
        yield


def _run(gh: _Gh, *args: str) -> Any:
    with _gh_patched(gh):
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
def test_one_finished_pass_as_github_records_it_leaves_pass_2_to_request(
    github_api: GitHubApiFake,
) -> None:
    """The timeline names Copilot `Copilot` and its `reviewed` event carries the review's id, so
    the finished pass counts once, not once more as a pass still running."""
    _route(github_api, _ONE_PASS, copilot_pass(FIRST_REVIEW_ID))
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (
        result.exit_code,
        gh.requests,
        "Requested Copilot pass 2 of 2" in result.output,
    ) == (0, [_REQUEST], True)


@pytest.mark.usefixtures("budget_roadmap")
def test_two_finished_passes_spend_the_budget_and_nothing_is_requested(
    github_api: GitHubApiFake,
) -> None:
    _route(github_api, _TWO_PASSES, _TWO_PASSES_TIMELINE)
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, "Copilot budget spent: 2 of 2" in result.output) == (
        1,
        [],
        True,
    )


@pytest.mark.usefixtures("budget_roadmap")
def test_a_pass_still_running_counts_against_the_budget(github_api: GitHubApiFake) -> None:
    """One finished pass and a second Copilot has started spend a budget of 2."""
    timeline = [*copilot_pass(FIRST_REVIEW_ID), review_requested(), work_started()]
    _route(github_api, _ONE_PASS, timeline)
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, "2 of 2" in result.output) == (1, [], True)


@pytest.mark.usefixtures("budget_roadmap")
@pytest.mark.parametrize(
    ("reviews", "timeline", "exit_code", "requests", "says"),
    [
        pytest.param(
            _ONE_PASS,
            [*copilot_pass(FIRST_REVIEW_ID), review_requested()],
            1,
            [],
            "2 of 2",
            id="a-request-not-yet-started-counts",
        ),
        pytest.param(
            [],
            [review_requested(), review_request_removed()],
            0,
            [_REQUEST],
            "1 of 2",
            id="a-withdrawn-request-does-not-count",
        ),
        pytest.param(
            [],
            [review_requested(MAINTAINER)],
            0,
            [_REQUEST],
            "1 of 2",
            id="a-request-to-a-person-does-not-count",
        ),
    ],
)
def test_a_pending_copilot_request_counts_as_one_pass(
    github_api: GitHubApiFake,
    reviews: list[Any],
    timeline: list[Any],
    exit_code: int,
    requests: list[list[str]],
    says: str,
) -> None:
    """Copilot starts a requested pass up to a minute later, and a second request in that time
    would spend a pass the budget does not have."""
    _route(github_api, reviews, timeline)
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, says in result.output) == (exit_code, requests, True)


def test_a_request_alone_is_one_pass_used(github_api: GitHubApiFake) -> None:
    _route(github_api, [], [review_requested()])
    passes = read_copilot_passes("dan-petty", "devops-cli", 7, budget=2)
    assert (passes.submitted, passes.used) == (0, 1)


@pytest.mark.usefixtures("budget_roadmap")
def test_a_user_whose_login_contains_copilot_does_not_count(github_api: GitHubApiFake) -> None:
    """Only Copilot's own logins are Copilot's: two reviews by people named after it leave the
    whole budget."""
    people = [
        {"id": 11, "user": {"login": "copilot-fan", "type": "User"}, "state": "COMMENTED"},
        {"id": 12, "user": {"login": "my-copilot", "type": "User"}, "state": "APPROVED"},
    ]
    _route(github_api, people)
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, "1 of 2" in result.output) == (0, [_REQUEST], True)


@pytest.mark.parametrize(
    ("budget_file", "reviews", "timeline", "exit_code", "requests", "says"),
    [
        pytest.param(
            "board = 5\nrelease_copilot_passes = 3\n",
            _TWO_PASSES,
            _TWO_PASSES_TIMELINE,
            0,
            [_REQUEST],
            "3 of 3",
            id="three-passes",
        ),
        pytest.param(
            "board = 5\nrelease_copilot_passes = 1\n",
            _ONE_PASS,
            copilot_pass(FIRST_REVIEW_ID),
            1,
            [],
            "1 of 1",
            id="one-pass",
        ),
    ],
)
def test_the_command_holds_to_the_budget_the_file_sets(
    github_api: GitHubApiFake,
    roadmap_store: InMemoryRoadmapStore,
    budget_file: str,
    reviews: list[Any],
    timeline: list[Any],
    exit_code: int,
    requests: list[list[str]],
    says: str,
) -> None:
    """The budget is `release_copilot_passes` as `.github/roadmap.toml` sets it, neither the
    default nor any other key's value."""
    roadmap_store.seed_file(".github/roadmap.toml", budget_file)
    _route(github_api, reviews, timeline)
    gh = _Gh(_pull_request())
    result = _run(gh)
    assert (result.exit_code, gh.requests, says in result.output) == (exit_code, requests, True)


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
@pytest.mark.parametrize(
    ("merged", "says"),
    [pytest.param(True, "is merged", id="merged"), pytest.param(False, "is closed", id="closed")],
)
def test_a_release_pull_request_that_is_not_open_is_refused(
    github_api: GitHubApiFake, merged: bool, says: str
) -> None:
    """The previous release's pull request, named by its number, gets no pass: a pass on it
    would spend Copilot's tokens on a release already merged or abandoned."""
    gh = _Gh(_pull_request(state="closed", merged=merged))
    result = _run(gh)
    assert (
        result.exit_code,
        gh.requests,
        github_api.requested,
        f"PR #7 {says}" in result.output,
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
    gh = _Gh(_pull_request(), edit=(1, "", "gh: Could not request reviewer (HTTP 422)"))
    result = _run(gh)
    assert (result.exit_code, gh.requests, "HTTP 422" in result.output) == (1, [_REQUEST], True)


@pytest.mark.usefixtures("budget_roadmap")
@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        pytest.param("", "", id="silent"),
        pytest.param("", "   \n", id="blank-stderr"),
        pytest.param("  \t\n", "", id="blank-stdout"),
    ],
)
def test_a_silent_refused_request_names_its_exit_code(
    github_api: GitHubApiFake, stdout: str, stderr: str
) -> None:
    """gh that fails saying nothing still gives a reason, never an empty one."""
    _route(github_api, [])
    gh = _Gh(_pull_request(), edit=(1, stdout, stderr))
    result = _run(gh)
    with _gh_patched(gh), pytest.raises(GitHubOperationError) as raised:
        request_copilot_pass("dan-petty", "devops-cli", 7)
    assert (
        result.exit_code,
        "failed: exit code 1" in result.output,
        raised.value.details["error"],
    ) == (1, True, "exit code 1")


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
        f"gh api {_PULL}" in result.output,
        f"{_REPO}/pulls/7/reviews" in result.output,
    ) == (0, [], [], [], True, True, True)


def test_dry_run_without_a_number_plans_the_branchs_pull_request(
    github_api: GitHubApiFake, roadmap_store_repos: list[str], roadmap_store: InMemoryRoadmapStore
) -> None:
    """Without a number the pull request is the current branch's, which a dry run names with a
    placeholder rather than reading it, through the commands a real run sends."""
    gh = _Gh(_pull_request())
    with _gh_patched(gh):
        result = CliRunner().invoke(app, ["copilot-pass", "--repo", _REPO, "--dry-run"])
    view = f"gh pr view '<branch>' --json number --jq .number -R {_REPO}"
    rest = f"gh api 'repos/{_REPO}/pulls?head=dan-petty:<branch>&state=open' --jq '.[0].number'"
    assert (
        result.exit_code,
        gh.calls,
        github_api.requested,
        roadmap_store_repos,
        view in result.output,
        rest in result.output,
        "gh pr edit '<number>' --add-reviewer @copilot" in result.output,
    ) == (0, [], [], [], True, True, True)


def test_the_plan_names_the_commands_that_find_the_branchs_pull_request() -> None:
    """The plan's first two requests are the commands `resolve_branch_pr_number` runs when the
    REST read names no pull request, so the plan cannot drift from the real path."""
    sent: list[list[str]] = []

    def gh(args: list[str], **_: object) -> MagicMock:
        sent.append(list(args))
        return MagicMock(returncode=0, stdout="null" if len(sent) == 1 else "7", stderr="")

    with patch("devops_cli.github.pr_monitor.run_gh", side_effect=gh):
        resolve_branch_pr_number("<branch>", owner="dan-petty", repo="devops-cli")
    planned = [list(request.argv) for request in plan_copilot_pass(_REPO, None)[:2]]
    assert planned == sent


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
    reviews = [copilot_review(FIRST_REVIEW_ID + n) for n in range(submitted)]
    passes = count_copilot_passes(reviews, running=running, budget=budget)
    assert (passes, passes.used, passes.spent) == (
        CopilotPasses(submitted=submitted, running=running, budget=budget),
        used,
        spent,
    )


def test_a_review_counts_by_copilots_rest_or_graphql_login_and_by_no_other() -> None:
    reviews = [
        {"user": REVIEWS_COPILOT},
        {"author": {"login": "copilot-pull-request-reviewer"}},
        {"user": {"login": "copilot-pull-request-reviewer-fan", "type": "User"}},
        {"user": {"login": "copilot-swe-agent[bot]", "type": "Bot"}},
        {"user": {"login": "Copilot", "type": "Bot"}},
        {"user": None},
        "not a review",
    ]
    assert count_copilot_passes(reviews, running=False, budget=2).submitted == 2

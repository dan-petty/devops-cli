"""The check-results comment of a pull request: its text, and its one comment per pull request
(#3199).

The text is built from the check runs GitHub returns. The comment is posted through the GitHub
session, which `github_api` fakes at the HTTP edge.
"""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.check_verdict import CheckBucket, PRCheckItem
from devops_cli.github.pr_evidence import (
    EvidenceAction,
    build_pr_evidence_comment,
    publish_pr_evidence,
)
from devops_cli.github.session import get_github_session
from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    pull_request_payload,
    route_pull_request,
)

_REPO = "owner/repo"
_SHA = "a" * 40
_MARKER = "<!-- devops-cli:pr-evidence -->"
_LOGIN = "devops-bot"


def _item(name: str, state: str, bucket: CheckBucket, link: str = "") -> PRCheckItem:
    return PRCheckItem(name=name, state=state, bucket=bucket, link=link)


def _passing(name: str = "Tests", link: str = "https://example.com/run/1") -> PRCheckItem:
    return _item(name, "success", CheckBucket.PASS, link)


def test_comment_names_the_head_commit_and_lists_each_check_with_its_link() -> None:
    comment = build_pr_evidence_comment(
        [
            _passing("Tests", "https://example.com/run/1"),
            _item("Lint", "failure", CheckBucket.FAIL, "https://example.com/run/2"),
        ],
        head_sha=_SHA,
        title="feat(pr): add a thing",
    )

    assert comment.splitlines()[0] == _MARKER
    assert f"`{_SHA}`" in comment
    assert "| Tests | success | [run](https://example.com/run/1) |" in comment
    assert "| Lint | failure | [run](https://example.com/run/2) |" in comment


def test_comment_escapes_a_pipe_in_a_check_name() -> None:
    comment = build_pr_evidence_comment(
        [_passing("Build | linux")], head_sha=_SHA, title="feat(pr): add a thing"
    )

    assert "| Build \\| linux | success |" in comment


def test_comment_shows_a_dash_for_a_check_with_no_link() -> None:
    comment = build_pr_evidence_comment(
        [_passing("Tests", "")], head_sha=_SHA, title="feat(pr): add a thing"
    )

    assert "| Tests | success | - |" in comment


def test_comment_names_each_skipped_check_on_its_own_line() -> None:
    comment = build_pr_evidence_comment(
        [
            _passing(),
            _item("Docs", "skipped", CheckBucket.SKIPPING),
            _item("Release", "neutral", CheckBucket.SKIPPING),
        ],
        head_sha=_SHA,
        title="feat(pr): add a thing",
    )

    lines = comment.splitlines()
    assert "Skipped check: Docs" in lines
    assert "Skipped check: Release" in lines


def test_a_fix_links_its_passing_fail_to_pass_run() -> None:
    comment = build_pr_evidence_comment(
        [_passing(), _passing("Fail-to-Pass Check", "https://example.com/run/9")],
        head_sha=_SHA,
        title="fix(pr): repair a thing",
    )

    assert "Fail-to-pass run: https://example.com/run/9" in comment.splitlines()


def test_a_feature_has_no_fail_to_pass_section() -> None:
    comment = build_pr_evidence_comment(
        [_passing(), _passing("Fail-to-Pass Check", "https://example.com/run/9")],
        head_sha=_SHA,
        title="feat(pr): add a thing",
    )

    assert "Fail-to-pass run" not in comment


def test_a_fix_with_no_fail_to_pass_run_has_no_link() -> None:
    comment = build_pr_evidence_comment(
        [_passing()], head_sha=_SHA, title="fix(pr): repair a thing"
    )

    assert "Fail-to-pass run" not in comment


def test_a_fix_with_a_failed_fail_to_pass_run_has_no_link() -> None:
    comment = build_pr_evidence_comment(
        [_item("Fail-to-Pass Check", "failure", CheckBucket.FAIL, "https://example.com/run/9")],
        head_sha=_SHA,
        title="fix(pr): repair a thing",
    )

    assert "Fail-to-pass run" not in comment


def test_comment_ends_with_each_attribution_paragraph() -> None:
    comment = build_pr_evidence_comment(
        [_passing()],
        head_sha=_SHA,
        title="feat(pr): add a thing",
        attribution=("First line.", "Second line."),
    )

    assert comment.endswith("First line.\n\nSecond line.\n")


def test_comment_has_no_attribution_by_default() -> None:
    comment = build_pr_evidence_comment([_passing()], head_sha=_SHA, title="feat(pr): add a thing")

    assert comment.endswith("|\n")


# ── Posting: one comment per pull request ──────────────────────────────────────


def _check_run(name: str, conclusion: str, number: int = 1) -> dict[str, Any]:
    return {
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "html_url": f"https://example.com/run/{number}",
    }


def _comment(comment_id: int, body: str, login: str = _LOGIN) -> dict[str, Any]:
    return {"id": comment_id, "body": body, "user": {"login": login}}


class _Pull:
    """Pull request 42 of `owner/repo`, its check runs and its comments, over the fake API."""

    def __init__(self, api: GitHubApiFake, *, title: str = "feat(pr): add a thing") -> None:
        self.api = api
        route_pull_request(api, _REPO, 42, pull_request_payload(title=title, head_sha=_SHA))
        api.route("GET", "/user", github_json({"login": _LOGIN}))
        self.checks(_check_run("Tests", "success"), _check_run("Docs", "skipped", 2))
        self.comments()
        api.route(
            "POST", f"/repos/{_REPO}/issues/42/comments", github_json({"id": 900}, status=201)
        )
        api.route("PATCH", f"/repos/{_REPO}/issues/comments/7", github_json({"id": 7}))

    def checks(self, *runs: dict[str, Any]) -> None:
        self.api.route(
            "GET",
            f"/repos/{_REPO}/commits/{_SHA}/check-runs?per_page=100",
            github_json({"total_count": len(runs), "check_runs": list(runs)}),
        )

    def comments(self, *comments: dict[str, Any]) -> None:
        self.api.route(
            "GET", f"/repos/{_REPO}/issues/42/comments?per_page=100", github_json(list(comments))
        )

    def writes(self) -> list[tuple[str, str, str]]:
        return [
            (request.method, request.url.path, json.loads(request.content)["body"])
            for request in self.api.sent
            if request.method in {"POST", "PATCH"}
        ]


@pytest.fixture
def pull(github_api: GitHubApiFake) -> _Pull:
    return _Pull(github_api)


def test_publish_posts_one_comment_when_none_carries_the_marker(pull: _Pull) -> None:
    pull.comments(_comment(1, "Looks good."), _comment(2, "Please rebase.", "someone"))

    outcome = publish_pr_evidence(get_github_session(), _REPO, 42)

    writes = pull.writes()
    assert [(method, path) for method, path, _ in writes] == [
        ("POST", "/repos/owner/repo/issues/42/comments")
    ]
    assert (outcome.action, outcome.body) == (EvidenceAction.CREATED, writes[0][2])
    assert "| Tests | success |" in outcome.body


def test_publish_updates_the_marked_comment_and_posts_no_second_one(pull: _Pull) -> None:
    pull.comments(_comment(3, "Looks good."), _comment(7, f"{_MARKER}\nold text"))

    outcome = publish_pr_evidence(get_github_session(), _REPO, 42)

    assert [(method, path) for method, path, _ in pull.writes()] == [
        ("PATCH", "/repos/owner/repo/issues/comments/7")
    ]
    assert outcome.action == EvidenceAction.UPDATED


def test_publish_ignores_a_marker_in_the_comment_of_another_author(pull: _Pull) -> None:
    pull.comments(_comment(7, f"{_MARKER}\nforged", "someone-else"))

    publish_pr_evidence(get_github_session(), _REPO, 42)

    assert [method for method, _, _ in pull.writes()] == ["POST"]


def test_publish_ignores_a_marker_that_is_not_the_first_line(pull: _Pull) -> None:
    pull.comments(_comment(7, f"I quote {_MARKER} here"))

    publish_pr_evidence(get_github_session(), _REPO, 42)

    assert [method for method, _, _ in pull.writes()] == ["POST"]


def test_publish_reads_every_page_of_the_comments(pull: _Pull, github_api: GitHubApiFake) -> None:
    first = github_json([_comment(1, "Looks good.")])
    first.headers["link"] = (
        '<https://api.github.com/repositories/1/issues/42/comments?per_page=100&page=2>; rel="next"'
    )
    github_api.route("GET", f"/repos/{_REPO}/issues/42/comments?per_page=100", first)
    github_api.route(
        "GET",
        "/repositories/1/issues/42/comments?per_page=100&page=2",
        github_json([_comment(7, f"{_MARKER}\nold text")]),
    )

    publish_pr_evidence(get_github_session(), _REPO, 42)

    assert [method for method, _, _ in pull.writes()] == ["PATCH"]


def test_publish_posts_nothing_when_the_checks_cannot_be_read(
    pull: _Pull, github_api: GitHubApiFake
) -> None:
    github_api.route(
        "GET",
        f"/repos/{_REPO}/commits/{_SHA}/check-runs?per_page=100",
        github_json({"message": "Server Error"}, status=500),
    )

    with pytest.raises(GitHubOperationError) as failure:
        publish_pr_evidence(get_github_session(), _REPO, 42)

    assert (failure.value.error_code, pull.writes()) == ("GITHUB_UNREAD", [])


def test_publish_posts_nothing_when_the_connection_fails(
    pull: _Pull, github_api: GitHubApiFake
) -> None:
    github_api.route("GET", f"/repos/{_REPO}/issues/42/comments?per_page=100", httpx2.ConnectError)

    with pytest.raises(GitHubOperationError) as failure:
        publish_pr_evidence(get_github_session(), _REPO, 42)

    assert (failure.value.error_code, pull.writes()) == ("GITHUB_UNREAD", [])

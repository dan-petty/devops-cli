"""`devops pr evidence` posts the check results of a pull request as one comment (#3199).

The command layer owns the arguments, the output and the exit code. The text of the comment and
the one-comment rule are tested in `tests/github/test_pr_evidence.py`. GitHub is faked at the HTTP
edge.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    pull_request_payload,
    route_pull_request,
)

_REPO = "owner/repo"
_SHA = "a" * 40
_MARKER = "<!-- devops-cli:pr-evidence -->"


@pytest.fixture
def pull(github_api: GitHubApiFake) -> GitHubApiFake:
    """Pull request 42 with a passing and a skipped check, and no comment."""
    route_pull_request(
        github_api, _REPO, 42, pull_request_payload(title="feat(pr): add a thing", head_sha=_SHA)
    )
    github_api.route("GET", "/user", github_json({"login": "devops-bot"}))
    runs = [
        {"name": "Tests", "status": "completed", "conclusion": "success", "html_url": "u/1"},
        {"name": "Docs", "status": "completed", "conclusion": "skipped", "html_url": "u/2"},
    ]
    github_api.route(
        "GET",
        f"/repos/{_REPO}/commits/{_SHA}/check-runs?per_page=100",
        github_json({"total_count": 2, "check_runs": runs}),
    )
    github_api.route("GET", f"/repos/{_REPO}/issues/42/comments?per_page=100", github_json([]))
    github_api.route("POST", f"/repos/{_REPO}/issues/42/comments", github_json({}, status=201))
    return github_api


def _writes(api: GitHubApiFake) -> list[str]:
    return [str(request.method) for request in api.sent if request.method in {"POST", "PATCH"}]


def test_evidence_posts_the_comment_and_says_so(
    cli: Callable[..., Any], pull: GitHubApiFake
) -> None:
    result = cli("pr", "evidence", "42", "--repo", _REPO)

    posted = [json.loads(r.content)["body"] for r in pull.sent if r.method == "POST"]
    assert (result.exit_code, len(posted)) == (0, 1)
    assert posted[0].startswith(_MARKER)
    assert "Created the check-results comment on PR #42" in " ".join(result.output.split())


def test_evidence_ends_the_comment_with_each_attribution_paragraph(
    cli: Callable[..., Any], pull: GitHubApiFake
) -> None:
    cli("pr", "evidence", "42", "--repo", _REPO, "--attribution", "One.", "--attribution", "Two.")

    posted = [json.loads(r.content)["body"] for r in pull.sent if r.method == "POST"]
    assert posted[0].endswith("One.\n\nTwo.\n")


def test_evidence_refuses_free_text_and_sends_no_request(
    cli: Callable[..., Any], pull: GitHubApiFake
) -> None:
    result = cli("pr", "evidence", "42", "--repo", _REPO, "--body", "3 passed")

    assert (result.exit_code, pull.sent) == (2, [])


def test_evidence_exits_with_an_error_and_posts_nothing_when_a_read_fails(
    cli: Callable[..., Any], pull: GitHubApiFake
) -> None:
    pull.route(
        "GET",
        f"/repos/{_REPO}/commits/{_SHA}/check-runs?per_page=100",
        github_json({"message": "Server Error"}, status=500),
    )

    result = cli("pr", "evidence", "42", "--repo", _REPO)

    assert (result.exit_code, _writes(pull)) == (1, [])


def test_evidence_dry_run_prints_the_plan_and_sends_no_request(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    result = cli("pr", "evidence", "42", "--repo", _REPO, "--dry-run")

    assert (result.exit_code, github_api.sent) == (0, [])
    for expected in (
        "GET repos/owner/repo/pulls/42",
        "GET repos/owner/repo/commits/<head-sha>/check-runs",
        "GET repos/owner/repo/issues/42/comments",
        "PATCH repos/owner/repo/issues/comments/<comment-id>",
        "POST repos/owner/repo/issues/42/comments",
    ):
        assert expected in result.output

"""Tests for the read-only issue calls of the GitHub client that the stage planner uses (#3238):
one issue or pull request, the end of its comments, the pull request that closed it, and the search
of open items. The session runs over the fake of GitHub's REST API."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import pytest

from devops_cli.exceptions.git import GitHubNotFoundError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session
from tests.support.fakes.github import github_json, quota_headers

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

_REPO = "octocat/Hello-World"
_ISSUE = f"/repos/{_REPO}/issues/7"
_SHA = "a" * 40


def _client() -> Any:
    return get_github_session().client


def _comments_path(page: int) -> str:
    return f"{_ISSUE}/comments?per_page=100&page={page}"


def _comments(numbers: range) -> Any:
    return github_json(
        [{"body": f"comment {n}", "created_at": "2026-11-02T10:00:00Z"} for n in numbers]
    )


def test_an_issue_is_read_with_its_state_title_labels_and_body(github_api: GitHubApiFake) -> None:
    github_api.route(
        "GET",
        _ISSUE,
        github_json(
            {
                "number": 7,
                "title": "feat: a thing",
                "state": "closed",
                "state_reason": "completed",
                "body": "The body.",
                "comments": 4,
                "labels": [{"name": "type/feature"}, {"name": "status/ready"}],
            }
        ),
    )

    issue = _client().get_issue(_REPO, 7)

    assert (
        issue.number,
        issue.title,
        issue.state,
        issue.state_reason,
        issue.body,
        issue.comments,
        issue.label_names,
        issue.is_pull_request,
        issue.merged_at,
    ) == (
        7,
        "feat: a thing",
        "closed",
        "completed",
        "The body.",
        4,
        ["type/feature", "status/ready"],
        False,
        None,
    )


def test_a_pull_request_read_as_an_issue_says_when_it_merged(github_api: GitHubApiFake) -> None:
    github_api.route(
        "GET",
        _ISSUE,
        github_json(
            {
                "number": 7,
                "title": "feat: a pull",
                "state": "closed",
                "body": None,
                "pull_request": {"merged_at": "2026-11-01T09:00:00Z"},
            }
        ),
    )

    issue = _client().get_issue(_REPO, 7)

    assert (issue.is_pull_request, issue.merged_at, issue.body, issue.label_names) == (
        True,
        "2026-11-01T09:00:00Z",
        None,
        [],
    )


def test_an_issue_that_does_not_exist_raises_the_not_found_error(
    github_api: GitHubApiFake,
) -> None:
    with pytest.raises(GitHubNotFoundError, match="issues/7"):
        _client().get_issue(_REPO, 7)


def test_the_last_comments_come_from_the_last_page(github_api: GitHubApiFake) -> None:
    github_api.route("GET", _comments_path(3), _comments(range(201, 251)))

    found = _client().get_last_comments(_REPO, 7, total=250, count=3)

    assert (found, github_api.requested) == (
        ["comment 248", "comment 249", "comment 250"],
        [f"GET https://api.github.com{_comments_path(3)}"],
    )


def test_a_short_last_page_is_completed_from_the_page_before(github_api: GitHubApiFake) -> None:
    github_api.route("GET", _comments_path(2), _comments(range(101, 102)))
    github_api.route("GET", _comments_path(1), _comments(range(1, 101)))

    found = _client().get_last_comments(_REPO, 7, total=101, count=3)

    assert found == ["comment 99", "comment 100", "comment 101"]


def test_an_issue_with_no_comment_makes_no_request(github_api: GitHubApiFake) -> None:
    found = _client().get_last_comments(_REPO, 7, total=0, count=3)

    assert (found, github_api.requested) == ([], [])


def _events_path() -> str:
    return f"{_ISSUE}/events?per_page=100"


def _commit_pulls_path(sha: str) -> str:
    return f"/repos/{_REPO}/commits/{sha}/pulls?per_page=100"


def test_the_pull_request_that_closed_an_issue_is_the_merged_one_of_the_closing_commit(
    github_api: GitHubApiFake,
) -> None:
    github_api.route(
        "GET",
        _events_path(),
        github_json(
            [
                {"event": "labeled", "commit_id": None},
                {"event": "closed", "commit_id": "b" * 40},
                {"event": "reopened", "commit_id": None},
                {"event": "closed", "commit_id": _SHA},
            ]
        ),
    )
    github_api.route(
        "GET",
        _commit_pulls_path(_SHA),
        github_json(
            [
                {"number": 11, "merged_at": None, "head": {"sha": "c" * 40}},
                {"number": 12, "merged_at": "2026-11-01T09:00:00Z", "head": {"sha": "d" * 40}},
            ]
        ),
    )

    assert _client().get_closing_pull(_REPO, 7) == 12


@pytest.mark.parametrize(
    "events",
    [
        [{"event": "closed", "commit_id": None}],
        [{"event": "labeled", "commit_id": None}],
        [],
    ],
    ids=["closed_by_hand", "never_closed", "no_event"],
)
def test_an_issue_closed_with_no_commit_has_no_closing_pull_request(
    github_api: GitHubApiFake, events: list[dict[str, Any]]
) -> None:
    github_api.route("GET", _events_path(), github_json(events))

    assert (_client().get_closing_pull(_REPO, 7), len(github_api.requested)) == (None, 1)


def test_a_closing_commit_whose_pull_request_did_not_merge_gives_none(
    github_api: GitHubApiFake,
) -> None:
    github_api.route("GET", _events_path(), github_json([{"event": "closed", "commit_id": _SHA}]))
    github_api.route(
        "GET",
        _commit_pulls_path(_SHA),
        github_json([{"number": 11, "merged_at": None, "head": {"sha": "c" * 40}}]),
    )

    assert _client().get_closing_pull(_REPO, 7) is None


def _search_path(query: str, limit: int) -> str:
    return f"/search/issues?{urlencode({'q': query, 'per_page': limit})}"


@pytest.fixture
def search_quota(github_api: GitHubApiFake) -> GitHubApiFake:
    get_github_rate_limiter().update_quota(
        "search", remaining=30, limit=30, reset_epoch=time.time() + 60.0
    )
    return github_api


def test_the_search_for_open_items_names_the_repository_and_the_state(
    search_quota: GitHubApiFake,
) -> None:
    path = _search_path(f"redaction point repo:{_REPO} is:open", 10)
    search_quota.route(
        "GET",
        path,
        github_json(
            {
                "total_count": 2,
                "incomplete_results": False,
                "items": [
                    {"number": 2740, "title": "feat: redact", "state": "open"},
                    {
                        "number": 3189,
                        "title": "fix: gate",
                        "state": "open",
                        "pull_request": {"url": "https://example.com/pull/3189"},
                    },
                ],
            },
            headers=quota_headers(29, resource="search", limit=30),
        ),
    )

    found = _client().search_open_items(_REPO, "redaction point", limit=10)

    assert [(item.number, item.title, item.is_pull_request) for item in found] == [
        (2740, "feat: redact", False),
        (3189, "fix: gate", True),
    ]


def test_the_search_terms_hold_no_qualifier(search_quota: GitHubApiFake) -> None:
    """A colon would let the model name `repo:` of another repository, so the client takes every
    colon and quote out of the terms before it searches."""
    path = _search_path(f"repo other/private is closed repo:{_REPO} is:open", 10)
    search_quota.route(
        "GET",
        path,
        github_json(
            {"total_count": 0, "incomplete_results": False, "items": []},
            headers=quota_headers(29, resource="search", limit=30),
        ),
    )

    found = _client().search_open_items(_REPO, 'repo:other/private "is:closed"', limit=10)

    assert (found, search_quota.requested) == (
        [],
        [f"GET https://api.github.com{path}"],
    )

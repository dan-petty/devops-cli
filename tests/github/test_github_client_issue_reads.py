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
        [
            {
                "body": f"comment {n}",
                "created_at": "2026-11-02T10:00:00Z",
                "author_association": "COLLABORATOR",
                "user": {"login": "a-colleague"},
            }
            for n in numbers
        ]
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


ANOTHER_ISSUE = [
    pytest.param({"number": 12}, id="another-number"),
    pytest.param(
        {"number": 7, "repository_url": "https://api.github.com/repos/example/other"},
        id="another-repository",
    ),
    pytest.param(
        {"number": 7, "html_url": "https://github.com/example/other/issues/7"},
        id="another-repository-in-the-page-url",
    ),
]


@pytest.mark.parametrize("named", ANOTHER_ISSUE)
def test_an_answer_that_names_another_issue_raises_the_error_of_no_issue(
    github_api: GitHubApiFake, named: dict[str, object]
) -> None:
    """The session follows the redirect of a transferred issue, so the answer is the issue at its
    new place (#7337). The client gives no such answer as the issue that it was asked for."""
    github_api.route(
        "GET", _ISSUE, github_json({"title": "moved", "state": "closed", "body": "Other.", **named})
    )

    with pytest.raises(GitHubNotFoundError) as refused:
        _client().get_issue(_REPO, 7)

    assert (type(refused.value).__name__, refused.value.error_code, str(refused.value)) == (
        "GitHubNotAnIssueError",
        "GITHUB_NOT_AN_ISSUE",
        f"#7 is not an issue of {_REPO}.",
    )


NO_ISSUE_STATUSES = [
    pytest.param(github_json({"message": "This issue was deleted"}, status=410), id="deleted-410"),
    pytest.param(github_json(None, status=301), id="redirect-not-followed-301"),
]


@pytest.mark.parametrize("answer", NO_ISSUE_STATUSES)
def test_a_status_that_says_that_the_issue_left_raises_the_error_of_no_issue(
    github_api: GitHubApiFake, answer: Any
) -> None:
    """GitHub answers 410 for a deleted issue, and a redirect that the session does not follow
    ends with 301 (#7337). Each is no issue of the repository, as a 404 is."""
    github_api.route("GET", _ISSUE, answer)

    with pytest.raises(GitHubNotFoundError) as refused:
        _client().get_issue(_REPO, 7)

    assert (type(refused.value).__name__, refused.value.error_code, str(refused.value)) == (
        "GitHubNotAnIssueError",
        "GITHUB_NOT_AN_ISSUE",
        f"#7 is not an issue of {_REPO}.",
    )


def _renamed_answer() -> Any:
    return github_json(
        {
            "number": 7,
            "title": "feat: a thing",
            "state": "open",
            "repository_url": "https://api.github.com/repos/octocat/Hello-Again",
        }
    )


def test_an_answer_under_the_old_name_of_a_renamed_repository_is_the_issue(
    github_api: GitHubApiFake,
) -> None:
    """GitHub redirects each route of a renamed repository, so the answer holds the requested
    number and the new name of the same repository. The client reads the name of the repository
    one time and takes each such answer."""
    github_api.route("GET", _ISSUE, _renamed_answer())
    github_api.route("GET", f"/repos/{_REPO}", github_json({"full_name": "octocat/Hello-Again"}))
    client = _client()

    read = [client.get_issue(_REPO, 7).number, client.get_issue(_REPO, 7).number]

    assert read == [7, 7]
    assert [sent for sent in github_api.requested if sent.endswith(f"/repos/{_REPO}")] == [
        f"GET https://api.github.com/repos/{_REPO}"
    ]


def test_an_answer_with_the_number_and_the_name_of_another_repository_is_refused(
    github_api: GitHubApiFake,
) -> None:
    """A transferred issue can keep its number. The repository of the client keeps its name, so
    the answer is the issue at another place."""
    github_api.route("GET", _ISSUE, _renamed_answer())
    github_api.route("GET", f"/repos/{_REPO}", github_json({"full_name": _REPO}))

    with pytest.raises(GitHubNotFoundError) as refused:
        _client().get_issue(_REPO, 7)

    assert refused.value.error_code == "GITHUB_NOT_AN_ISSUE"


def test_the_last_comments_come_from_the_last_page(github_api: GitHubApiFake) -> None:
    github_api.route("GET", _comments_path(3), _comments(range(201, 251)))

    found = _client().get_last_comments(_REPO, 7, total=250, count=3)

    assert ([comment.body for comment in found], github_api.requested) == (
        [f"comment {n}" for n in range(201, 251)],
        [f"GET https://api.github.com{_comments_path(3)}"],
    )


def test_a_short_last_page_is_completed_from_the_page_before(github_api: GitHubApiFake) -> None:
    github_api.route("GET", _comments_path(2), _comments(range(101, 102)))
    github_api.route("GET", _comments_path(1), _comments(range(1, 101)))

    found = _client().get_last_comments(_REPO, 7, total=101, count=3)

    assert [comment.body for comment in found] == [f"comment {n}" for n in range(1, 102)]


def test_a_comment_is_read_with_the_relation_and_the_login_of_its_author(
    github_api: GitHubApiFake,
) -> None:
    github_api.route(
        "GET",
        _comments_path(1),
        github_json(
            [
                {
                    "body": "first",
                    "author_association": "COLLABORATOR",
                    "user": {"login": "a-colleague"},
                },
                {"body": "second", "author_association": "NONE", "user": None},
            ]
        ),
    )

    found = _client().get_last_comments(_REPO, 7, total=2, count=3)

    assert [(c.body, c.author_association, c.author_login) for c in found] == [
        ("first", "COLLABORATOR", "a-colleague"),
        ("second", "NONE", None),
    ]


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

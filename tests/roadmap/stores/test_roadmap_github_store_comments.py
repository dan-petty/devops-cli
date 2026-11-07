"""The comments that the GitHub roadmap store reads from one issue or from the whole repository
(#1335).
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from typing import Any

from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from tests.support.fakes.github import (
    API,
    GitHubApiFake,
    github_json,
    next_page,
)
from tests.support.roadmap_github_store import REPO, over_github, recorded, recorded_store

# ── Comments ──────────────────────────────────────────────────────────────────


def test_comments_on_reads_every_comment_of_the_issue_oldest_first_with_its_time() -> None:
    store, runner = recorded_store({"issues/844/comments": recorded("issue-844-comments.json")})
    (comment,) = store.comments_on(844)
    assert (
        comment.body.startswith("**Placement (2026-10-02):** moved from v0.2.28"),
        comment.created_at,
        runner.calls[0][0],
    ) == (
        True,
        datetime(2026, 10, 2, 3, 26, 48, tzinfo=UTC),
        [f"{API}/repos/{REPO}/issues/844/comments?per_page=100"],
    )


def test_a_comment_carries_its_authors_login_and_association() -> None:
    """The model of refine reads the replies of trusted authors only (#3502): a comment gives
    the login that GitHub holds in its `user` and the association that it states."""
    store, _ = recorded_store(
        {
            "issues/844/comments": [
                {
                    "body": "A reply",
                    "created_at": "2026-10-02T03:26:48Z",
                    "author_association": "CONTRIBUTOR",
                    "user": {"login": "devops-cli-service[bot]"},
                },
                {"body": "An old reply", "created_at": "2026-10-02T03:27:48Z"},
            ]
        }
    )

    assert [(c.author_login, c.author_association) for c in store.comments_on(844)] == [
        ("devops-cli-service[bot]", "CONTRIBUTOR"),
        (None, None),
    ]


def _repository_comment(
    created_at: str, login: str, association: str, *, page: str = "issues"
) -> dict[str, Any]:
    """A comment as the listing of the whole repository gives it: `page` is `issues` for a
    comment on an issue and `pull` for one on a pull request, and `issue_url` is the same for
    both, as GitHub gives it."""
    return {
        "body": "An answer",
        "created_at": created_at,
        "author_association": association,
        "user": {"login": login},
        "issue_url": f"{API}/repos/{REPO}/issues/844",
        "html_url": f"https://github.com/{REPO}/{page}/844#issuecomment-1",
    }


COMMENTS_LISTING = f"/repos/{REPO}/issues/comments?sort=created&direction=desc"


def test_comments_since_reads_the_repository_comments_newest_first_from_the_time(
    github_api: GitHubApiFake,
) -> None:
    listing = f"{COMMENTS_LISTING}&since=2026-11-05T12:00:00Z&per_page=100"
    github_api.route(
        "GET",
        listing,
        github_json(
            [
                _repository_comment(
                    "2026-11-05T13:00:00Z", "devops-cli-service[bot]", "CONTRIBUTOR"
                ),
                _repository_comment("2026-11-05T12:30:00Z", "alice", "OWNER"),
            ]
        ),
    )
    store, runner = over_github()

    found = list(store.comments_since(datetime(2026, 11, 5, 12, tzinfo=UTC)))

    assert [(c.author_login, c.author_association, c.created_at) for c in found] == [
        ("devops-cli-service[bot]", "CONTRIBUTOR", datetime(2026, 11, 5, 13, tzinfo=UTC)),
        ("alice", "OWNER", datetime(2026, 11, 5, 12, 30, tzinfo=UTC)),
    ]
    assert (github_api.requested, runner.calls) == ([f"GET {API}{listing}"], [])


def test_comments_since_tells_a_comment_on_a_pull_request_from_one_on_an_issue(
    github_api: GitHubApiFake,
) -> None:
    listing = f"{COMMENTS_LISTING}&per_page=100"
    github_api.route(
        "GET",
        listing,
        github_json(
            [
                _repository_comment("2026-11-05T13:00:00Z", "alice", "OWNER", page="pull"),
                _repository_comment("2026-11-05T12:30:00Z", "alice", "OWNER"),
            ]
        ),
    )
    store, _ = over_github()

    found = list(store.comments_since(None))

    assert [c.on_pull_request for c in found] == [True, False]


def test_comments_since_with_no_time_sends_no_since_parameter(github_api: GitHubApiFake) -> None:
    listing = f"{COMMENTS_LISTING}&per_page=100"
    github_api.route("GET", listing, github_json([]))
    store, _ = over_github()

    assert list(store.comments_since(None)) == []
    assert github_api.requested == [f"GET {API}{listing}"]


def test_comments_since_sends_no_request_for_a_page_the_caller_does_not_read(
    github_api: GitHubApiFake,
) -> None:
    listing = f"{COMMENTS_LISTING}&per_page=100"
    second = f"{COMMENTS_LISTING}&per_page=100&page=2"
    github_api.route(
        "GET",
        listing,
        github_json(
            [_repository_comment("2026-11-05T13:00:00Z", "alice", "OWNER")],
            headers=next_page(second),
        ),
    )
    github_api.route(
        "GET", second, github_json([_repository_comment("2026-11-05T12:00:00Z", "bob", "OWNER")])
    )
    store, _ = over_github()

    first = next(store.comments_since(None))

    assert (first.author_login, len(github_api.sent)) == ("alice", 1)


def test_comments_since_sends_one_request_for_the_first_page_of_comments(
    github_api: GitHubApiFake,
) -> None:
    """A caller that takes one page of comments and no more sends no request for the next page
    that the first one links, as the round of the Service does (#2754)."""
    listing = f"{COMMENTS_LISTING}&per_page=100"
    second = f"{COMMENTS_LISTING}&per_page=100&page=2"
    page = [
        _repository_comment("2026-11-05T13:00:00Z", "devops-cli-service[bot]", "CONTRIBUTOR")
    ] * DEFAULT_GH_REST_PER_PAGE
    github_api.route("GET", listing, github_json(page, headers=next_page(second)))
    github_api.route("GET", second, github_json([]))
    store, _ = over_github()

    taken = list(itertools.islice(store.comments_since(None), DEFAULT_GH_REST_PER_PAGE))

    assert (len(taken), github_api.requested) == (DEFAULT_GH_REST_PER_PAGE, [f"GET {API}{listing}"])

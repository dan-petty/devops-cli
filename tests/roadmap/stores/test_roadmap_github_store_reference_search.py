"""The reads of the reference step that the GitHub roadmap store sends (#4672): the code search
and the repository search through the GitHub session, the facts of a repository in one GraphQL
read, and the file of another repository through the contents API.

The searches run over `GitHubApiFake`, the HTTP edge of the session, so the test sees the request
that the session sends and the quota that it paces on. The gh commands are answered by a recorded
runner.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import pytest

from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.stores.store import CodeSearchHit, ReferenceFacts
from tests.support.fakes.github import (
    API,
    GitHubApiFake,
    github_json,
    next_page,
    quota_headers,
)
from tests.support.roadmap_github_store import over_github, recorded_store

PUSHED = "2026-11-20T10:00:00Z"
HEAD = "a" * 40


def _graphql(repository: dict[str, Any] | None) -> dict[str, Any]:
    return {"data": {"repository": repository}}


def _named(full_name: str, *, private: bool = False) -> dict[str, Any]:
    return {"full_name": full_name, "private": private}


def _repository(**changes: Any) -> dict[str, Any]:
    return {
        "nameWithOwner": "example/agent",
        "url": "https://github.com/example/agent",
        "isPrivate": False,
        "description": "An agent.",
        "isArchived": False,
        "isFork": False,
        "pushedAt": PUSHED,
        "stargazerCount": 250,
        "licenseInfo": {"spdxId": "MIT"},
        "defaultBranchRef": {"target": {"oid": HEAD}},
        "tests": {"__typename": "Tree"},
        "test": None,
        **changes,
    }


@pytest.fixture
def search_quota(github_api: GitHubApiFake) -> GitHubApiFake:
    """A known quota of the two search resources, so the pacing asks GitHub nothing."""
    for resource, limit in (("code_search", 10), ("search", 30)):
        get_github_rate_limiter().update_quota(
            resource, remaining=limit, limit=limit, reset_epoch=time.time() + 60.0
        )
    return github_api


def test_the_two_searches_send_one_request_each_and_leave_out_a_private_file(
    search_quota: GitHubApiFake,
) -> None:
    code = f"/search/code?{urlencode({'q': 'pydantic_ai', 'per_page': 2})}"
    repositories = f"/search/repositories?{urlencode({'q': 'pydantic-ai', 'per_page': 2})}"
    search_quota.route(
        "GET",
        code,
        github_json(
            {
                "total_count": 3,
                "incomplete_results": False,
                "items": [
                    {"path": "src/agent.py", "repository": _named("example/agent")},
                    {"path": "key.py", "repository": _named("example/closed", private=True)},
                    {"path": "more.py", "repository": _named("example/more")},
                ],
            },
            headers=quota_headers(9, resource="code_search", limit=10),
        ),
    )
    search_quota.route(
        "GET",
        repositories,
        github_json(
            {
                "total_count": 1,
                "incomplete_results": False,
                "items": [
                    {
                        "full_name": "example/agent",
                        "html_url": "https://github.com/example/agent",
                        "private": False,
                        "description": None,
                        "license": {"spdx_id": "MIT"},
                        "archived": True,
                        "fork": True,
                        "pushed_at": PUSHED,
                        "stargazers_count": 250,
                    }
                ],
            },
            headers=quota_headers(29, resource="search", limit=30),
        ),
    )
    store, runner = over_github()

    found = (
        store.search_code("pydantic_ai", limit=2),
        store.search_repositories("pydantic-ai", limit=2),
    )

    assert (found, search_quota.requested, runner.calls) == (
        (
            [
                CodeSearchHit(repository="example/agent", path="src/agent.py"),
            ],
            [
                ReferenceFacts(
                    full_name="example/agent",
                    url="https://github.com/example/agent",
                    private=False,
                    license="MIT",
                    archived=True,
                    fork=True,
                    pushed_at=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
                    stars=250,
                )
            ],
        ),
        [f"GET {API}{code}", f"GET {API}{repositories}"],
        [],
    )


def test_one_search_is_one_request_when_a_short_page_links_a_next_page(
    search_quota: GitHubApiFake,
) -> None:
    """GitHub can answer a code search with a page that holds fewer files than it asked for and
    that links a next page. The step counts one search, so the store reads one page."""
    code = f"/search/code?{urlencode({'q': 'pydantic_ai', 'per_page': 5})}"
    repositories = f"/search/repositories?{urlencode({'q': 'pydantic-ai', 'per_page': 5})}"
    more = {"total_count": 9, "incomplete_results": False}
    search_quota.route(
        "GET",
        code,
        github_json(
            {**more, "items": [{"path": "src/agent.py", "repository": _named("example/agent")}]},
            headers={
                **quota_headers(9, resource="code_search", limit=10),
                **next_page(f"{code}&page=2"),
            },
        ),
    )
    search_quota.route(
        "GET",
        repositories,
        github_json(
            {**more, "items": []},
            headers={
                **quota_headers(29, resource="search", limit=30),
                **next_page(f"{repositories}&page=2"),
            },
        ),
    )
    store, _ = over_github()

    found = (
        store.search_code("pydantic_ai", limit=5),
        store.search_repositories("pydantic-ai", limit=5),
    )

    assert (found, search_quota.requested) == (
        ([CodeSearchHit(repository="example/agent", path="src/agent.py")], []),
        [f"GET {API}{code}", f"GET {API}{repositories}"],
    )


def test_a_search_answer_that_holds_no_list_of_results_raises_the_read_error(
    search_quota: GitHubApiFake,
) -> None:
    code = f"/search/code?{urlencode({'q': 'pydantic_ai', 'per_page': 5})}"
    search_quota.route(
        "GET",
        code,
        github_json({"message": "ok"}, headers=quota_headers(9, resource="code_search")),
    )
    store, _ = over_github()

    with pytest.raises(GitHubOperationError, match="code search"):
        store.search_code("pydantic_ai", limit=5)


def test_a_search_with_no_limit_sends_no_request(search_quota: GitHubApiFake) -> None:
    store, _ = over_github()

    assert (store.search_code("x", limit=0), search_quota.requested) == ([], [])


def test_reference_facts_read_the_gates_the_head_commit_and_the_tests_in_one_read() -> None:
    store, runner = recorded_store({"graphql": _graphql(_repository())})

    facts = store.reference_facts("example/agent")

    (args, _), *others = runner.calls
    assert (facts, args[:2], args[-4:], others) == (
        ReferenceFacts(
            full_name="example/agent",
            url="https://github.com/example/agent",
            private=False,
            description="An agent.",
            license="MIT",
            pushed_at=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
            stars=250,
            head_sha=HEAD,
            has_tests=True,
        ),
        ["api", "graphql"],
        ["-f", "owner=example", "-f", "name=agent"],
        [],
    )


def test_reference_facts_of_a_repository_with_no_license_no_branch_and_no_tests() -> None:
    bare = _repository(licenseInfo=None, defaultBranchRef=None, tests=None, description=None)
    store, _ = recorded_store({"graphql": _graphql(bare)})

    facts = store.reference_facts("example/agent")

    assert facts is not None
    assert (facts.license, facts.head_sha, facts.has_tests, facts.description) == (
        None,
        None,
        False,
        "",
    )


def test_reference_facts_of_a_missing_repository_are_none_and_a_failed_read_raises() -> None:
    missing, _ = recorded_store({"graphql": (1, '{"data": {"repository": null}}')})
    broken, _ = recorded_store({"graphql": (1, "gh: HTTP 502")})

    assert missing.reference_facts("example/none") is None
    with pytest.raises(GitHubOperationError, match="reference facts of example/agent"):
        broken.reference_facts("example/agent")


def test_reference_facts_refuse_a_name_that_is_no_repository_name_before_any_request() -> None:
    store, runner = recorded_store({})

    with pytest.raises(GitHubOperationError, match="is not a repository name"):
        store.reference_facts("../secrets")
    assert runner.calls == []


def test_a_file_of_another_repository_is_read_at_the_commit_through_the_contents_api() -> None:
    store, runner = recorded_store({"contents/": "import pydantic_ai\n"})

    text = store.repository_file("src/agent.py", ref=HEAD, repository="example/agent")

    assert (text, runner.calls[0][0][-1]) == (
        "import pydantic_ai\n",
        f"repos/example/agent/contents/src/agent.py?ref={HEAD}",
    )


def test_a_file_that_another_repository_does_not_hold_raises_the_not_found_error() -> None:
    store, runner = recorded_store({"contents/": (1, "gh: Not Found (HTTP 404)")})

    with pytest.raises(GitHubFileNotFoundError, match=r"example/agent has no gone\.py"):
        store.repository_file("gone.py", ref=HEAD, repository="example/agent")
    with pytest.raises(GitHubOperationError, match="is not a repository name"):
        store.repository_file("gone.py", ref=HEAD, repository="../other")
    assert len(runner.calls) == 1

"""The reference step over the GitHub roadmap store (#4672): its two searches go to GitHub on the
paced session, `GET /search/code` and `GET /search/repositories`, and its other reads go through
gh.

`GitHubApiFake` answers the session at the HTTP edge and records its requests, and a recorded
runner answers the gh commands.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import pytest

from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.references.providers import repositories_query
from devops_cli.roadmap.references.step import ReferenceRequest, open_reference_step
from tests.support.fakes.github import API, GitHubApiFake, github_json, quota_headers
from tests.support.roadmap_github_store import over_github

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
HEAD = "a" * 40
PUSHED = "2026-11-20T10:00:00Z"
FILE = "# An agent\n\nimport pydantic_ai\n\nagent = pydantic_ai.Agent()\n"


@pytest.fixture
def search_quota(github_api: GitHubApiFake) -> GitHubApiFake:
    """A known quota of the two search resources, so the pacing asks GitHub nothing."""
    for resource, limit in (("code_search", 10), ("search", 30)):
        get_github_rate_limiter().update_quota(
            resource, remaining=limit, limit=limit, reset_epoch=time.time() + 60.0
        )
    return github_api


def _found(items: list[dict[str, Any]], resource: str, limit: int) -> Any:
    return github_json(
        {"total_count": len(items), "incomplete_results": False, "items": items},
        headers=quota_headers(limit - 1, resource=resource, limit=limit),
    )


def test_the_step_of_a_public_repository_sends_only_the_two_github_searches_on_the_session(
    search_quota: GitHubApiFake,
) -> None:
    code = f"/search/code?{urlencode({'q': 'pydantic_ai', 'per_page': 5})}"
    query = repositories_query(["example/agent"])
    repositories = f"/search/repositories?{urlencode({'q': query, 'per_page': 15})}"
    search_quota.route(
        "GET",
        code,
        _found(
            [
                {
                    "path": "src/agent.py",
                    "repository": {"full_name": "example/agent", "private": False},
                }
            ],
            "code_search",
            10,
        ),
    )
    search_quota.route(
        "GET",
        repositories,
        _found(
            [
                {
                    "full_name": "example/agent",
                    "html_url": "https://github.com/example/agent",
                    "private": False,
                    "license": {"spdx_id": "MIT"},
                    "pushed_at": PUSHED,
                    "stargazers_count": 250,
                }
            ],
            "search",
            30,
        ),
    )
    facts = {
        "nameWithOwner": "example/agent",
        "url": "https://github.com/example/agent",
        "isPrivate": False,
        "pushedAt": PUSHED,
        "stargazerCount": 250,
        "licenseInfo": {"spdxId": "MIT"},
        "defaultBranchRef": {"target": {"oid": HEAD}},
    }
    store, runner = over_github({"graphql": {"data": {"repository": facts}}, "contents/": FILE})
    request = ReferenceRequest(
        number=7, title="Run an agent", text="Use `pydantic_ai`.", repo="example/roadmap", now=NOW
    )

    with open_reference_step(store, mode="on", private=False) as step:
        providers = [provider.name for provider in step.providers]
        found = step.run(store, request)

    to_github = [sent for sent in search_quota.requested if sent.startswith(f"GET {API}/")]
    assert (providers, to_github, found.urls, [args[-1] for args, _ in runner.calls][-1]) == (
        ["github-code", "github-repository"],
        [f"GET {API}{code}", f"GET {API}{repositories}"],
        (f"https://github.com/example/agent/blob/{HEAD}/src/agent.py#L3-L5",),
        f"repos/example/agent/contents/src/agent.py?ref={HEAD}",
    )

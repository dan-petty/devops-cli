"""How a failed read, a rate limit or a listing of the wrong shape ends a read of the GitHub
roadmap store (#1335).
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.roadmap.stores.github_store import (
    GitHubRoadmapStore,
)
from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    quota_headers,
)
from tests.support.roadmap_github_store import LISTING_MILESTONES, REPO, over_github, recorded_store


def test_a_listing_github_fails_raises_the_sessions_unread_error_naming_it(
    github_api: GitHubApiFake,
) -> None:
    """A listing GitHub answers with a 502 through the session's retries raises the session's
    unread error, naming the listing and the status; no gh command runs (#983)."""
    github_api.route("GET", f"/{LISTING_MILESTONES}", github_json({"message": "x"}, status=502))
    store, runner = over_github()
    with pytest.raises(GitHubUnreadError) as raised:
        store.milestones()
    details = raised.value.details
    assert (details["path"], details["status"], runner.calls) == (
        f"/{LISTING_MILESTONES}",
        502,
        [],
    )


def test_a_rate_limited_listing_raises_rate_limit_error(github_api: GitHubApiFake) -> None:
    """A listing GitHub refuses for a spent quota raises the rate limit, which stops an intake
    round."""
    github_api.route(
        "GET",
        f"/{LISTING_MILESTONES}",
        github_json({"message": "rate"}, status=403, headers=quota_headers(0, reset_in=30.0)),
    )
    store, _ = over_github()
    with pytest.raises(GitHubRateLimitError) as raised:
        store.milestones()
    assert raised.value.error_code == "GITHUB_RATE_LIMIT_UNKNOWN"


def test_a_failed_gh_read_raises_and_names_the_read() -> None:
    store, _ = recorded_store({"contents/notes.md": (1, "HTTP 502: Bad Gateway")})
    with pytest.raises(GitHubOperationError, match=r"Could not read notes\.md"):
        store.repository_file("notes.md")


@pytest.mark.parametrize(
    ("said", "error"),
    [
        pytest.param("gh: Too Many Requests (HTTP 429)", GitHubRateLimitError, id="429"),
        pytest.param(
            "You have exceeded a secondary rate limit.", GitHubRateLimitError, id="secondary"
        ),
        pytest.param("gh: Bad credentials (HTTP 401)", GitHubUnauthenticatedError, id="401"),
    ],
)
def test_a_failed_read_raises_the_class_the_gh_classifier_names(
    said: str, error: type[GitHubOperationError]
) -> None:
    """A failed gh read raises what `classify_gh_failure` makes of gh's output (#983), not only
    the rate limits the store once matched itself, with gh's exit status as an int."""
    store, _ = recorded_store({"contents/notes.md": (1, said)})
    with pytest.raises(GitHubOperationError) as raised:
        store.repository_file("notes.md")
    assert (type(raised.value), raised.value.details["exit_code"]) == (error, 1)


_PARTIAL_GRAPHQL_ANSWER = (
    '{{"data": {{"repository": {{"issues": {{"nodes": [{{"number": 705, "title": "{title}"}}]}}}}}},'
    ' "errors": [{{"type": "FORBIDDEN", "message": "Resource not accessible by integration"}}]}}'
)


@pytest.mark.parametrize(
    "title",
    [
        "correct secondary-limit backoff and retry-after handling in run_gh",
        "verify read:project scope",
        "HTTP 401 Bad credentials",
        "not logged in",
        "unknown owner type",
    ],
)
def test_a_failed_read_classifies_gh_s_stderr_never_the_titles_on_stdout(title: str) -> None:
    """gh copies GitHub's partial answer, item titles included, to stdout and writes only
    `gh: <message>` to stderr; a title that reads like a rate limit, a scope or a refused login
    is GitHub's data, so the read fails as a failed read (#983). `RecordedGh` writes one text to
    both streams, so this runner writes each its own."""

    def gh(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        body = _PARTIAL_GRAPHQL_ANSWER.format(title=title)
        return subprocess.CompletedProcess(
            args, 1, body, "gh: Resource not accessible by integration"
        )

    store = GitHubRoadmapStore(REPO, runner=gh)
    with pytest.raises(GitHubOperationError) as raised:
        store.repository_file("notes.md")
    assert (type(raised.value), "Could not read notes.md" in raised.value.message) == (
        GitHubOperationError,
        True,
    )


def test_a_listing_entry_that_is_not_the_shape_the_store_reads_raises() -> None:
    store, _ = recorded_store({"milestones?state=all": [{"number": 1}]})
    with pytest.raises(GitHubOperationError, match="malformed milestones"):
        store.milestones()


def test_an_error_object_where_a_listing_belongs_raises() -> None:
    store, _ = recorded_store({"issues?state=all": {"message": "Not Found"}})
    with pytest.raises(GitHubUnreadError, match="not a JSON array"):
        store.candidates()

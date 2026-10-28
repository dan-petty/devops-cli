"""The metrics devops-cli sends about its requests to GitHub (#814).

The rate limiter paces every attempt of a gh command and of the GitHub session, records every
wait before a refused request is sent again, and charges the points each GraphQL answer reports.
Each of these sends its metric, so a dashboard shows the requests, the throttles and the GraphQL
cost.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.github.rate_limiter import get_github_rate_limiter, run_gh
from devops_cli.github.session import get_github_session
from devops_cli.telemetry.instruments import (
    GITHUB_GRAPHQL_POINTS_TOTAL,
    GITHUB_REQUESTS_TOTAL,
    GITHUB_THROTTLE_WAIT,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.telemetry_capture import Captured

_REPO_READ = ["api", "repos/octo/repo"]
_GRAPHQL_READ = ["api", "graphql", "-f", "query={ viewer { login } }"]


@pytest.fixture
def fresh_quotas(clock: ClockFake) -> None:
    """The pinned identity's `core` and `graphql` quotas, fresh, so pacing reads no quota."""
    limiter = get_github_rate_limiter()
    for resource in ("core", "graphql"):
        limiter.update_quota(resource, remaining=5000, limit=5000, reset_epoch=time.time() + 3600)


def _histogram_points(captured: Captured, name: str) -> list[tuple[dict[str, Any], int, float]]:
    """Each data point of a histogram, as (attributes, count, sum)."""
    found = []
    for metric in captured.metrics:
        if metric["name"] != name:
            continue
        for point in metric["exponentialHistogram"]["dataPoints"]:
            attrs = {a["key"]: next(iter(a["value"].values())) for a in point["attributes"]}
            found.append((attrs, int(point["count"]), point["sum"]))
    return found


@pytest.mark.usefixtures("fresh_quotas")
def test_a_refused_and_retried_gh_command_counts_two_requests_and_one_wait(
    process_fake: ProcessFake, captured: Captured
) -> None:
    """Each attempt is a request, and the wait before the retry is one throttle observation."""
    replies = [
        subprocess.CompletedProcess(
            [], 1, stdout="", stderr="API rate limit exceeded for user ID 1. Retry-After: 7"
        ),
        subprocess.CompletedProcess([], 0, stdout='{"id": 1}', stderr=""),
    ]
    process_fake.answer(["gh", *_REPO_READ], ProcessAnswer(side_effect=lambda _: replies.pop(0)))

    result = run_gh(_REPO_READ, max_retries=2)

    assert (
        result.returncode,
        captured.points(GITHUB_REQUESTS_TOTAL.name),
        _histogram_points(captured, GITHUB_THROTTLE_WAIT.name),
    ) == (0, [({"resource": "core"}, 2.0)], [({"resource": "core"}, 1, 7.0)])


@pytest.mark.usefixtures("fresh_quotas")
def test_a_graphql_answer_counts_its_request_and_the_points_it_reports(
    process_fake: ProcessFake, captured: Captured
) -> None:
    """A GraphQL request is counted on its own resource, and its points come from `rateLimit`."""
    reset_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    answer = {
        "data": {
            "viewer": {"login": "octocat"},
            "rateLimit": {"cost": 3, "remaining": 4997, "limit": 5000, "resetAt": reset_at},
        }
    }
    process_fake.answer(["gh", *_GRAPHQL_READ], ProcessAnswer(stdout=json.dumps(answer)))

    run_gh(_GRAPHQL_READ)

    assert (
        captured.points(GITHUB_REQUESTS_TOTAL.name),
        captured.points(GITHUB_GRAPHQL_POINTS_TOTAL.name),
        _histogram_points(captured, GITHUB_THROTTLE_WAIT.name),
    ) == ([({"resource": "graphql"}, 1.0)], [({}, 3.0)], [])


def test_a_session_request_refused_once_counts_two_requests_and_its_wait(
    github_api: GitHubApiFake, captured: Captured
) -> None:
    """The GitHub session's attempts and retry wait are counted as a gh command's are."""
    github_api.route(
        "GET",
        "/user",
        github_json({"message": "slow down"}, status=429, headers={"retry-after": "1"}),
        github_json({"login": "octocat"}),
    )

    get_github_session().rest("GET", "/user")

    assert (
        captured.points(GITHUB_REQUESTS_TOTAL.name),
        _histogram_points(captured, GITHUB_THROTTLE_WAIT.name),
    ) == ([({"resource": "core"}, 2.0)], [({"resource": "core"}, 1, 1.0)])

"""The metrics devops-cli sends about its requests to GitHub (#814).

The rate limiter paces every attempt of a gh command and of the GitHub session, records every
wait before a refused request is sent again, and charges the points each GraphQL answer reports.
Each of these sends its metric, so a dashboard shows the requests, the throttles and the GraphQL
cost. Each request also names its method, and the repository and the job row whose work sent it
(#2475), so an alert on the roadmap Service's writes finds the repository that spent them.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.github.rate_limiter import get_github_rate_limiter, run_gh
from devops_cli.github.request_scope import request_scope
from devops_cli.github.session import get_github_session
from devops_cli.telemetry.instruments import (
    GITHUB_GRAPHQL_POINTS_TOTAL,
    GITHUB_REQUESTS_TOTAL,
    GITHUB_THROTTLE_WAIT,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.process import ProcessAnswer, ProcessFake

_REPO_READ = ["api", "repos/octo/repo"]
_GRAPHQL_READ = ["api", "graphql", "-f", "query={ viewer { login } }"]
_COMMENT = ["api", "-X", "POST", "repos/octo/repo/issues/7/comments", "-f", "body=Hello"]
# The labels of a request that no Service worker and no job row sent.
_UNSCOPED = {"repo": "other", "row": "other"}


@pytest.fixture
def fresh_quotas(clock: ClockFake) -> None:
    """The pinned identity's `core` and `graphql` quotas, fresh, so pacing reads no quota."""
    limiter = get_github_rate_limiter()
    for resource in ("core", "graphql"):
        limiter.update_quota(resource, remaining=5000, limit=5000, reset_epoch=time.time() + 3600)


def _histogram_points(otlp: FakeCollector, name: str) -> list[tuple[dict[str, Any], int, float]]:
    """Each data point of a histogram, as (attributes, count, sum)."""
    found = []
    for metric in otlp.metrics:
        if metric["name"] != name:
            continue
        for point in metric["exponentialHistogram"]["dataPoints"]:
            attrs = {a["key"]: next(iter(a["value"].values())) for a in point["attributes"]}
            found.append((attrs, int(point["count"]), point["sum"]))
    return found


@pytest.mark.usefixtures("fresh_quotas")
def test_a_refused_and_retried_gh_command_counts_two_requests_and_one_wait(
    process_fake: ProcessFake, otlp: FakeCollector
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
        otlp.points(GITHUB_REQUESTS_TOTAL.name),
        _histogram_points(otlp, GITHUB_THROTTLE_WAIT.name),
    ) == (
        0,
        [({"resource": "core", "method": "GET", **_UNSCOPED}, 2.0)],
        [({"resource": "core"}, 1, 7.0)],
    )


@pytest.mark.usefixtures("fresh_quotas")
def test_a_graphql_answer_counts_its_request_and_the_points_it_reports(
    process_fake: ProcessFake, otlp: FakeCollector
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
        otlp.points(GITHUB_REQUESTS_TOTAL.name),
        otlp.points(GITHUB_GRAPHQL_POINTS_TOTAL.name),
        _histogram_points(otlp, GITHUB_THROTTLE_WAIT.name),
    ) == ([({"resource": "graphql", "method": "POST", **_UNSCOPED}, 1.0)], [({}, 3.0)], [])


def test_a_session_request_refused_once_counts_two_requests_and_its_wait(
    github_api: GitHubApiFake, otlp: FakeCollector
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
        otlp.points(GITHUB_REQUESTS_TOTAL.name),
        _histogram_points(otlp, GITHUB_THROTTLE_WAIT.name),
    ) == (
        [({"resource": "core", "method": "GET", **_UNSCOPED}, 2.0)],
        [({"resource": "core"}, 1, 1.0)],
    )


@pytest.mark.usefixtures("fresh_quotas")
def test_a_write_of_a_job_row_counts_its_method_repository_and_row(
    process_fake: ProcessFake, otlp: FakeCollector
) -> None:
    """A comment that a job row writes for the repository of a Service worker counts under its
    method, the repository and the row. A row's scope keeps the repository of the worker's."""
    process_fake.answer(["gh", *_COMMENT], ProcessAnswer(stdout='{"id": 1}'))

    with request_scope(repo="octo/repo"), request_scope(row="refine"):
        run_gh(_COMMENT)
    run_gh(_COMMENT)

    assert otlp.points(GITHUB_REQUESTS_TOTAL.name) == [
        ({"resource": "core", "method": "POST", "repo": "octo/repo", "row": "refine"}, 1.0),
        ({"resource": "core", "method": "POST", **_UNSCOPED}, 1.0),
    ]


@pytest.mark.usefixtures("fresh_quotas")
@pytest.mark.parametrize(
    ("command", "method"),
    [(["issue", "comment", "7", "--body", "Hello"], "POST"), (["issue", "list"], "GET")],
    ids=["write", "read"],
)
def test_a_gh_command_other_than_gh_api_counts_as_post_when_it_writes_and_get_when_it_reads(
    process_fake: ProcessFake, otlp: FakeCollector, command: list[str], method: str
) -> None:
    """gh chooses the requests of its own commands, so the method of such a command is the one
    its write or read classification gives."""
    process_fake.answer(["gh", *command], ProcessAnswer(stdout="[]"))

    run_gh(command)

    assert [labels["method"] for labels, _ in otlp.points(GITHUB_REQUESTS_TOTAL.name)] == [method]


def test_a_session_request_counts_the_scope_of_the_thread_that_sent_it(
    github_api: GitHubApiFake, otlp: FakeCollector
) -> None:
    """The session paces each request in a thread of its portal, and the request still counts
    under the repository and the row of the thread that sent it."""
    github_api.route("PATCH", "/repos/octo/repo/issues/7", github_json({"number": 7}))

    with request_scope(repo="octo/repo", row="intake"):
        get_github_session().rest("PATCH", "/repos/octo/repo/issues/7", body={"title": "T"})

    assert otlp.points(GITHUB_REQUESTS_TOTAL.name) == [
        ({"resource": "core", "method": "PATCH", "repo": "octo/repo", "row": "intake"}, 1.0)
    ]

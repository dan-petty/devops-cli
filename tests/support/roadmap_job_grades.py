"""Recorded Loki replies of the job grade report, and the streams of the result lines, for the
tests of `devops roadmap eval grades` (#5165, #5556).

`tests/fixtures/roadmap/job_grades/replies.json` holds one vector reply for each planned query,
under the key `<measure>@<window>`. `serve_grade_replies` answers each request that the report
sends to `/loki/api/v1/query` with the reply of its query, and an empty vector for a query that
the file does not hold. The counts in the file are a hand count that the tests repeat.

The streams have the labels that Loki gave the pods of the namespace `devops` on 2026-11-13.
`written_records` gives the records that `log_job_result` logs, so a test writes a line in the
JSON form of the Service (`JsonLogFormatter`) or in the plain form of a Job pod (the message).

A test that also reads the verdicts of the bot pull requests (#5968) cannot ask for `web` and
`github_api` together, so `route_grade_replies` gives the same replies on the fake GitHub API, and
`pull_node` gives one pull request of the GraphQL search with its label events.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

import httpx2

from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.job_grade_report import GradeWindow, plan_grade_queries
from devops_cli.roadmap.job_result import LINE_PREFIX, RoadmapJob, log_job_result
from tests.support.paths import FIXTURES

if TYPE_CHECKING:
    import pytest

    from devops_cli.github.repo_ref import RepoRef
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.http import WebFake

GRADE_REPLIES: Final = FIXTURES / "roadmap" / "job_grades" / "replies.json"
LOKI_URL: Final = "http://example.com:3100"
QUERY_PATH: Final = "/loki/api/v1/query"
GRADES_REPO: Final = "example/app"
# A time in the past, so the quota that the fake GitHub API holds is still ahead of the clock.
VERDICT_NOW: Final = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

_POD: Final = {"cluster": "example", "namespace": "devops", "flags": "F"}
# The Service logs JSON on stdout.
SERVICE_STREAM: Final = {
    **_POD,
    "app_kubernetes_io_name": "roadmap-service",
    "container": "service",
    "job": "devops/service",
    "stream": "stdout",
}
# A fix-plan Job logs the plain line on stderr (#5363).
FIX_PLAN_STREAM: Final = {
    **_POD,
    "app_kubernetes_io_name": "roadmap-fix-plan-validation",
    "container": "fix-plan",
    "job": "devops/fix-plan",
    "stream": "stderr",
}
# A stage Job logs the plain line on stderr, and its plan report on stdout (#4559).
STAGE_STREAM: Final = {
    **_POD,
    "app_kubernetes_io_name": "devops-cli-job",
    "container": "stage",
    "job": "devops/stage",
    "stream": "stderr",
}
STAGE_REPORT_STREAM: Final = {**STAGE_STREAM, "stream": "stdout"}
# A runner pod has the name label of a stage Job, and logs the output of a coding agent.
RUNNER_STREAM: Final = {
    **_POD,
    "app_kubernetes_io_name": "devops-cli-job",
    "container": "runner",
    "job": "devops/runner",
    "stream": "stdout",
}


def written_records(
    caplog: pytest.LogCaptureFixture, *attempts: tuple[RoadmapJob, str]
) -> list[logging.LogRecord]:
    """The record that `log_job_result` logs for each attempt, a job and its result, on item 7 of
    `GRADES_REPO`, with the counts of a short attempt."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.job_result"):
        for job, result in attempts:
            log_job_result(job, GRADES_REPO, 7, result, counts={"tokens": 1000, "seconds": 60})
    return [record for record in caplog.records if record.getMessage().startswith(LINE_PREFIX)]


def _vector(result: list[dict[str, Any]]) -> dict[str, Any]:
    return {"status": "success", "data": {"resultType": "vector", "result": result}}


def serve_grade_replies(
    web: WebFake, *, window: GradeWindow = GradeWindow.D7, repo: RepoRef | None = None
) -> None:
    """Answer the instant queries of the report with the recorded replies of `window`."""
    replies: dict[str, list[dict[str, Any]]] = json.loads(GRADE_REPLIES.read_text("utf-8"))
    keys = {query.expr: query.key for query in plan_grade_queries(window, repo)}

    def answer(request: httpx2.Request) -> httpx2.Response | None:
        if request.url.path != QUERY_PATH:
            return None
        key = keys.get(request.url.params.get("query", ""))
        if key is None:
            return httpx2.Response(400, text="parse error: the fake knows no such query")
        return httpx2.Response(200, json=_vector(replies.get(key, [])))

    web.serve(answer)


def route_grade_replies(
    api: GitHubApiFake, *, window: GradeWindow = GradeWindow.D7, repo: RepoRef | None = None
) -> None:
    """Answer the instant queries of the report on the fake GitHub API, which answers each URL
    that a test routes, with the recorded replies of `window`."""
    replies: dict[str, list[dict[str, Any]]] = json.loads(GRADE_REPLIES.read_text("utf-8"))
    endpoint = f"{LOKI_URL}{QUERY_PATH}"
    for query in plan_grade_queries(window, repo):
        url = httpx2.URL(endpoint, params={"query": query.expr})
        api.route("GET", str(url), httpx2.Response(200, json=_vector(replies.get(query.key, []))))


def hold_graphql_quota() -> None:
    """A fresh GraphQL quota whose reset is ahead of the clock, so the pacing of the search of
    the verdicts runs no `gh api rate_limit`."""
    get_github_rate_limiter().update_quota(
        "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )


def pull_node(
    number: int, title: str, labels: Iterable[str], repo: str = GRADES_REPO
) -> dict[str, Any]:
    """One pull request of the GraphQL search of the verdicts, with a label event for each of
    `labels`, in order."""
    return {
        "number": number,
        "title": title,
        "repository": {"nameWithOwner": repo},
        "timelineItems": {"nodes": [{"label": {"name": name}} for name in labels]},
    }

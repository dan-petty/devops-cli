"""Recorded Loki replies of the job grade report, and the streams of the result lines, for the
tests of `devops roadmap eval grades` (#5165, #5556).

`tests/fixtures/roadmap/job_grades/replies.json` holds one vector reply for each planned query,
under the key `<measure>@<window>`. `serve_grade_replies` answers each request that the report
sends to `/loki/api/v1/query` with the reply of its query, and an empty vector for a query that
the file does not hold. The counts in the file are a hand count that the tests repeat.

The streams have the labels that Loki gave the pods of the namespace `devops` on 2026-11-13.
`written_records` gives the records that `log_job_result` logs, so a test writes a line in the
JSON form of the Service (`JsonLogFormatter`) or in the plain form of a Job pod (the message).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Final

import httpx2

from devops_cli.roadmap.job_grade_report import GradeWindow, plan_grade_queries
from devops_cli.roadmap.job_result import LINE_PREFIX, RoadmapJob, log_job_result
from tests.support.paths import FIXTURES

if TYPE_CHECKING:
    import pytest

    from devops_cli.github.repo_ref import RepoRef
    from tests.support.fakes.http import WebFake

GRADE_REPLIES: Final = FIXTURES / "roadmap" / "job_grades" / "replies.json"
LOKI_URL: Final = "http://example.com:3100"
QUERY_PATH: Final = "/loki/api/v1/query"
GRADES_REPO: Final = "example/app"

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

"""Recorded Loki replies of the job grade report, for the tests of `devops roadmap eval grades`
(#5165).

`tests/fixtures/roadmap/job_grades/replies.json` holds one vector reply for each planned query,
under the key `<measure>@<window>`. `serve_grade_replies` answers each request that the report
sends to `/loki/api/v1/query` with the reply of its query, and an empty vector for a query that
the file does not hold. The counts in the file are a hand count that the tests repeat.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

import httpx2

from devops_cli.roadmap.job_grade_report import GradeWindow, plan_grade_queries
from tests.support.paths import FIXTURES

if TYPE_CHECKING:
    from devops_cli.github.repo_ref import RepoRef
    from tests.support.fakes.http import WebFake

GRADE_REPLIES: Final = FIXTURES / "roadmap" / "job_grades" / "replies.json"
LOKI_URL: Final = "http://example.com:3100"
QUERY_PATH: Final = "/loki/api/v1/query"


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

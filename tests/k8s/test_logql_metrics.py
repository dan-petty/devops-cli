"""The Loki metric queries of `devops roadmap eval grades` under the read retry policy (#5532).

`query_loki_metrics` builds its client through the HTTP entry point, so the `web` fixture answers
each attempt below it, and the `clock` fixture records each wait.
"""

from __future__ import annotations

import httpx2
import pytest

from devops_cli.exceptions import ServiceRequestError
from devops_cli.exceptions.k8s import KubernetesLoggingError
from devops_cli.k8s.logql import query_loki_metrics
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake

_LOKI = "http://loki.example.com:3100"
_VECTOR = {
    "status": "success",
    "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1700000000, "7"]}]},
}


def test_a_metric_query_answers_after_a_503(web: WebFake, clock: ClockFake) -> None:
    """Loki that starts again answers the second attempt."""
    answers = iter([httpx2.Response(503)])
    web.serve(lambda request: next(answers, httpx2.Response(200, json=_VECTOR)))

    [result] = query_loki_metrics(['count_over_time({app="x"}[1h])'], _LOKI)

    assert ([series.value for series in result.series], len(web.sent)) == (["7"], 2)


def test_a_loki_that_stays_down_raises_one_service_error(web: WebFake, clock: ClockFake) -> None:
    """After 4 attempts the error names Loki, the status and the attempts."""
    web.serve(lambda request: httpx2.Response(503, text="Service Unavailable"))

    with pytest.raises(ServiceRequestError) as raised:
        query_loki_metrics(['count_over_time({app="x"}[1h])'], _LOKI)

    assert (raised.value.status_code, raised.value.attempts, len(web.sent)) == (503, 4, 4)
    assert raised.value.message.startswith("Loki failed after 4 attempts in ")


def test_a_refused_query_is_sent_once_and_names_the_reply(web: WebFake, clock: ClockFake) -> None:
    """Loki refuses a query with a line of plain text, which the error holds."""
    web.serve(lambda request: httpx2.Response(400, text="parse error at line 1"))

    with pytest.raises(ServiceRequestError) as raised:
        query_loki_metrics(["count_over_time(bad"], _LOKI)

    assert (raised.value.status_code, len(web.sent), clock.waits) == (400, 1, [])
    assert "HTTP 400 Bad Request: parse error at line 1." in raised.value.message


def test_a_loki_that_refuses_the_connection_names_its_setting(
    web: WebFake, clock: ClockFake
) -> None:
    """A network error has no status, and the hint names `loki.url`."""

    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused", request=request)

    web.serve(refuse)

    with pytest.raises(ServiceRequestError) as raised:
        query_loki_metrics(['count_over_time({app="x"}[1h])'], _LOKI)

    assert (raised.value.status_code, len(web.sent), "loki.url" in raised.value.message) == (
        None,
        4,
        True,
    )


def test_a_metric_query_at_a_time_sends_that_time_and_a_query_now_sends_none(
    web: WebFake, clock: ClockFake
) -> None:
    """The project review reads a past window at its end (#4692)."""
    web.serve(lambda request: httpx2.Response(200, json=_VECTOR))

    query_loki_metrics(['count_over_time({app="x"}[1h])'], _LOKI, at="2026-11-11T14:51:23Z")
    query_loki_metrics(['count_over_time({app="x"}[1h])'], _LOKI)

    assert [request.url.params.get("time") for request in web.sent] == [
        "2026-11-11T14:51:23Z",
        None,
    ]


@pytest.mark.parametrize(
    "answer",
    [
        httpx2.Response(200, headers={"content-type": "text/html"}, text="<html>Sign in</html>"),
        httpx2.Response(200, headers={"content-type": "application/json"}, text="<html>"),
    ],
)
def test_an_answer_that_is_not_json_raises_a_project_error_that_names_the_setting(
    web: WebFake, clock: ClockFake, answer: httpx2.Response
) -> None:
    """A `loki.url` that points at Grafana or at a sign-in page answers 200 with HTML (#4692)."""
    web.serve(lambda request: answer)

    with pytest.raises(KubernetesLoggingError) as raised:
        query_loki_metrics(['count_over_time({app="x"}[1h])'], _LOKI)

    assert "loki.url" in str(raised.value)

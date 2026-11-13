"""The Loki metric queries of `devops roadmap eval grades` under the read retry policy (#5532).

`query_loki_metrics` builds its client through the HTTP entry point, so the `web` fixture answers
each attempt below it, and the `clock` fixture records each wait.
"""

from __future__ import annotations

import httpx2
import pytest

from devops_cli.exceptions import ServiceRequestError
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

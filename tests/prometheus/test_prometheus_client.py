"""The Prometheus client and the checks before a request, over the HTTP fake.

`PrometheusClient` builds its httpx2 client through the HTTP entry point, so the `web` fixture
answers each request below it. The fake vets each host at the client's egress level, as the real
connect does. A test reads the request that reached the fake, never a patched client.
"""

from __future__ import annotations

import httpx2
import pytest

from devops_cli.exceptions import SSRFBlockedError
from devops_cli.http.egress import EgressLevel
from devops_cli.prometheus.client import (
    MAX_PROMQL_LENGTH,
    DurationTooLongError,
    PrometheusClient,
    PrometheusContentTypeError,
    expression_problem,
    parse_duration,
)
from tests.support.fakes.http import WebFake

BASE = "http://prometheus.example.com:9090"
VECTOR = {
    "status": "success",
    "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1700000000, "3.5"]}]},
}


def _serve(web: WebFake, path: str, response: httpx2.Response) -> None:
    """Answer each request to `path` with `response`."""
    web.serve(lambda request: response if request.url.path == path else None)


def _client() -> PrometheusClient:
    return PrometheusClient(BASE, EgressLevel.LOOPBACK)


def test_an_instant_query_sends_the_expression_and_returns_the_answer(web: WebFake) -> None:
    """The instant query is one GET of the query endpoint, and the JSON answer comes back whole."""
    _serve(web, "/api/v1/query", httpx2.Response(200, json=VECTOR))

    with _client() as prometheus:
        answer = prometheus.query("up")

    assert (answer, [dict(request.url.params) for request in web.sent]) == (
        VECTOR,
        [{"query": "up"}],
    )


def test_an_instant_query_at_a_time_sends_that_time(web: WebFake) -> None:
    """A named time becomes the `time` parameter; without one the parameter is absent."""
    _serve(web, "/api/v1/query", httpx2.Response(200, json=VECTOR))

    with _client() as prometheus:
        prometheus.query("up", at="2026-11-01T00:00:00Z")
        prometheus.query("up")

    assert [dict(request.url.params) for request in web.sent] == [
        {"query": "up", "time": "2026-11-01T00:00:00Z"},
        {"query": "up"},
    ]


def test_a_range_query_sends_the_window_and_the_step(web: WebFake) -> None:
    """The range query is one GET of the range endpoint with the start, the end and the step."""
    matrix = {"status": "success", "data": {"resultType": "matrix", "result": []}}
    _serve(web, "/api/v1/query_range", httpx2.Response(200, json=matrix))

    with _client() as prometheus:
        answer = prometheus.query_range("up", start="100", end="200", step="30s")

    assert (answer, [dict(request.url.params) for request in web.sent]) == (
        matrix,
        [{"query": "up", "start": "100", "end": "200", "step": "30s"}],
    )


def test_a_server_that_answers_with_html_raises_the_content_type_it_sent(web: WebFake) -> None:
    """A page that is not JSON is no answer: the error names the content type."""
    _serve(web, "/api/v1/query", httpx2.Response(200, html="<html></html>"))

    with pytest.raises(PrometheusContentTypeError) as raised, _client() as prometheus:
        prometheus.query("up")

    assert "text/html" in str(raised.value)


def test_a_failed_status_raises_before_the_body_is_read(web: WebFake) -> None:
    """A 500 is an `httpx2.HTTPStatusError`, so the caller cannot take its body for an answer."""
    _serve(web, "/api/v1/query", httpx2.Response(500, json=VECTOR))

    with pytest.raises(httpx2.HTTPStatusError) as raised, _client() as prometheus:
        prometheus.query("up")

    assert raised.value.response.status_code == 500


def test_an_address_the_level_refuses_is_refused_before_a_request(web: WebFake) -> None:
    """A private address at the loopback level raises the refusal, and no request is recorded."""
    prometheus = PrometheusClient("http://10.0.0.1:9090", EgressLevel.LOOPBACK)

    with pytest.raises(SSRFBlockedError, match="egress level refuses"), prometheus:
        prometheus.query("up")

    assert web.recorded == []


def test_the_rules_of_an_empty_answer_are_an_empty_document(web: WebFake) -> None:
    """A rules answer with no body is `{}`, so a caller finds no group."""
    _serve(web, "/api/v1/rules", httpx2.Response(200))

    with _client() as prometheus:
        assert prometheus.rules() == {}


def test_the_rules_and_the_targets_are_read_from_their_endpoints(web: WebFake) -> None:
    """The rules come from the rules endpoint and the scrape targets from the targets endpoint."""
    rules = {"data": {"groups": [{"name": "node", "rules": []}]}}
    targets = {"data": {"activeTargets": [{"health": "up"}]}}
    _serve(web, "/api/v1/rules", httpx2.Response(200, json=rules))
    _serve(web, "/api/v1/targets", httpx2.Response(200, json=targets))

    with _client() as prometheus:
        answers = (prometheus.rules(), prometheus.targets())

    assert answers == (rules, targets)


def test_a_json_answer_that_is_not_an_object_is_an_empty_document(web: WebFake) -> None:
    """A list at the top level is not a Prometheus answer, so it reads as an empty document."""
    _serve(web, "/api/v1/targets", httpx2.Response(200, json=[1, 2]))

    with _client() as prometheus:
        assert prometheus.targets() == {}


def test_a_client_outside_its_with_block_cannot_send() -> None:
    """The client opens its connection pool in `with`; a call outside it fails at once."""
    with pytest.raises(RuntimeError, match="outside its `with` block"):
        _client().query("up")


def test_a_valid_expression_has_no_problem() -> None:
    """A well-formed PromQL expression may be sent."""
    assert expression_problem('sum by (job) (rate(http_requests_total{code=~"5.."}[5m]))') is None


def test_an_expression_over_the_limit_is_named_with_the_limit() -> None:
    """The problem of a long expression states the limit."""
    problem = expression_problem("a" * (MAX_PROMQL_LENGTH + 1))

    assert problem is not None
    assert str(MAX_PROMQL_LENGTH) in problem


def test_an_expression_of_exactly_the_limit_is_sent() -> None:
    """The limit is the longest expression that may be sent, not the first that is refused."""
    assert expression_problem("a" * MAX_PROMQL_LENGTH) is None


def test_a_malformed_expression_is_refused_with_the_error_found() -> None:
    """An unclosed range bracket is found before any request."""
    problem = expression_problem("rate(x[5m")

    assert problem is not None
    assert "Invalid PromQL" in problem


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("10s", 10.0),
        ("5m", 300.0),
        ("2h", 7200.0),
        ("1d", 86400.0),
        ("365d", 31_536_000.0),
        ("90", 90.0),
        ("", 0.0),
        ("invalid", 0.0),
    ],
)
def test_a_relative_duration_is_read_as_seconds(text: str, seconds: float) -> None:
    """A unit letter scales the number; a plain number is seconds; nothing readable is 0."""
    assert parse_duration(text) == seconds


def test_a_duration_over_a_year_is_refused() -> None:
    """The limit is 365 days."""
    with pytest.raises(DurationTooLongError, match="365 days"):
        parse_duration("400d")

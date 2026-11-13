"""The retry policy of the reads of a cluster service, and the one error line (#5532).

A client takes the policy through `http_client(level, retries=SERVICE_READ_RETRY)`. The `web`
fixture answers each attempt below the retry transport, and the `clock` fixture records each wait
and moves the clock seam, which the time bound reads.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx2
import pytest

from devops_cli.config.defaults import DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS
from devops_cli.exceptions import ServiceRequestError, SSRFBlockedError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.http.retry import SERVICE_READ_RETRY, service_error
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake

_URL = "https://prometheus.example.com/api/v1/query"
_VECTOR = {"status": "success", "data": {"resultType": "vector", "result": []}}


def _client() -> httpx2.Client:
    return http_client(EgressLevel.PUBLIC, retries=SERVICE_READ_RETRY)


def _answer_in_turn(web: WebFake, *answers: httpx2.Response | httpx2.TransportError) -> None:
    """Answer each request with the next of `answers`, and the last one after them."""
    queue: Iterator[httpx2.Response | httpx2.TransportError] = iter(answers)
    last = answers[-1]

    def answer(request: httpx2.Request) -> httpx2.Response:
        reply = next(queue, last)
        if isinstance(reply, httpx2.TransportError):
            reply.request = request
            raise reply
        return httpx2.Response(reply.status_code, headers=reply.headers, content=reply.content)

    web.serve(answer)


# =============================================================================
# What the policy sends again
# =============================================================================


@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_a_get_is_sent_again_after_a_transient_status(
    web: WebFake, clock: ClockFake, status: int
) -> None:
    """A status of a service that is not ready, or that limits the rate, gets one more attempt."""
    _answer_in_turn(web, httpx2.Response(status), httpx2.Response(200, json=_VECTOR))

    response = _client().get(_URL)

    assert (response.json(), len(web.sent), len(clock.waits)) == (_VECTOR, 2, 1)


@pytest.mark.parametrize(
    "error",
    [
        httpx2.ConnectError("Connection refused"),
        httpx2.ConnectTimeout("timed out"),
        httpx2.ReadError("Connection reset by peer"),
        httpx2.ReadTimeout("The read operation timed out"),
        httpx2.RemoteProtocolError("Server disconnected without sending a response."),
    ],
    ids=["connect", "connect-timeout", "read", "read-timeout", "disconnected"],
)
def test_a_get_is_sent_again_after_a_failed_connect_or_read(
    web: WebFake, clock: ClockFake, error: httpx2.TransportError
) -> None:
    """A pod that starts again refuses or drops the connection for some seconds."""
    _answer_in_turn(web, error, httpx2.Response(200, json=_VECTOR))

    response = _client().get(_URL)

    assert (response.status_code, len(web.sent)) == (200, 2)


def test_two_503_replies_then_an_answer_take_three_attempts(web: WebFake, clock: ClockFake) -> None:
    """The case of #5532: Prometheus answers some seconds after its pod started again."""
    _answer_in_turn(
        web, httpx2.Response(503), httpx2.Response(503), httpx2.Response(200, json=_VECTOR)
    )

    response = _client().get(_URL)

    assert (response.json(), len(web.sent), len(clock.waits)) == (_VECTOR, 3, 2)


def test_the_last_reply_comes_back_when_the_attempts_end(web: WebFake, clock: ClockFake) -> None:
    """After 4 attempts the caller gets the last reply, as one attempt gives it, and can read it."""
    web.respond("GET", _URL, 503, {"status": "error", "error": "not ready"})

    response = _client().get(_URL)

    assert (response.status_code, response.json()["error"], len(web.sent)) == (
        503,
        "not ready",
        4,
    )


def test_the_waits_back_off_with_jitter(web: WebFake, clock: ClockFake) -> None:
    """The waits double from 1 s, and each adds up to 1 s of jitter."""
    web.answer(_URL, 503)

    _client().get(_URL)

    first, second, third = clock.waits
    assert (1.0 <= first <= 2.0, 2.0 <= second <= 3.0, 4.0 <= third <= 5.0) == (True, True, True)


def test_the_last_network_error_is_raised_when_the_attempts_end(
    web: WebFake, clock: ClockFake
) -> None:
    """A service that stays silent raises the error of the last attempt."""
    web.refuse(_URL)

    with pytest.raises(httpx2.ConnectError, match="Connection refused"):
        _client().get(_URL)

    assert (len(web.sent), len(clock.waits)) == (4, 3)


@pytest.mark.parametrize("status", [400, 401, 404, 422, 500])
def test_a_status_that_is_not_transient_is_sent_once(
    web: WebFake, clock: ClockFake, status: int
) -> None:
    """A refused request, or an internal error of the server, does not change on a second try."""
    web.answer(_URL, status)

    response = _client().get(_URL)

    assert (response.status_code, len(web.sent), clock.waits) == (status, 1, [])


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_a_request_that_is_not_idempotent_is_sent_once(
    web: WebFake, clock: ClockFake, method: str
) -> None:
    """The server can have applied a write before it failed, so a write is never sent again."""
    web.answer(_URL, 503)

    response = _client().request(method, _URL)

    assert (response.status_code, len(web.sent), clock.waits) == (503, 1, [])


def test_an_address_that_the_level_refuses_is_not_sent_again(
    web: WebFake, clock: ClockFake
) -> None:
    """An egress refusal is not an httpx2 error, so the policy raises it at once."""
    client = http_client(EgressLevel.LOOPBACK, retries=SERVICE_READ_RETRY)

    with pytest.raises(SSRFBlockedError, match="egress level refuses"):
        client.get("http://10.0.0.1:9090/api/v1/query")

    assert (web.recorded, clock.waits) == ([], [])


# =============================================================================
# Retry-After and the time bound
# =============================================================================


def test_a_retry_after_header_sets_the_wait(web: WebFake, clock: ClockFake) -> None:
    """A wait is at least the delay that the service asks for."""
    _answer_in_turn(
        web,
        httpx2.Response(429, headers={"Retry-After": "6"}),
        httpx2.Response(200, json=_VECTOR),
    )

    response = _client().get(_URL)

    assert (response.status_code, clock.waits) == (200, [6.0])


def test_a_retry_after_past_the_time_bound_gives_the_reply_at_once(
    web: WebFake, clock: ClockFake
) -> None:
    """A wait that would end after the time bound is not made."""
    web.answer(_URL, 503, headers={"Retry-After": "30"})

    response = _client().get(_URL)

    assert (response.status_code, len(web.sent), clock.waits) == (503, 1, [])


def test_slow_attempts_end_at_the_time_bound(web: WebFake, clock: ClockFake) -> None:
    """No attempt starts 20 s or more after the first, whatever is left of the attempts."""

    def slow_timeout(request: httpx2.Request) -> httpx2.Response:
        clock.shift(10.0)
        raise httpx2.ConnectTimeout("timed out", request=request)

    web.serve(slow_timeout)

    with pytest.raises(httpx2.ConnectTimeout, match="timed out"):
        _client().get(_URL)

    assert len(web.sent) == 2


def test_the_time_bound_is_shorter_than_the_shortest_command_timeout() -> None:
    """A command that an MCP tool runs ends with the error line before the tool times out."""
    assert SERVICE_READ_RETRY.budget_seconds < DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS


# =============================================================================
# The pool
# =============================================================================


def test_a_pooled_client_with_a_retry_option_is_not_one_without(web: WebFake) -> None:
    """Two callers of one origin get the transport that each asked for."""
    plain = http_client(EgressLevel.PUBLIC, key="origin")
    retrying = http_client(EgressLevel.PUBLIC, key="origin", retries=SERVICE_READ_RETRY)

    assert (
        plain is retrying,
        retrying is http_client(EgressLevel.PUBLIC, key="origin", retries=SERVICE_READ_RETRY),
    ) == (False, True)


# =============================================================================
# The one error line
# =============================================================================


def _status_error(client: httpx2.Client) -> httpx2.HTTPStatusError:
    with pytest.raises(httpx2.HTTPStatusError) as raised:
        client.get(_URL).raise_for_status()
    return raised.value


def test_a_service_that_stays_down_is_one_line_with_the_attempts_and_the_time(
    web: WebFake, clock: ClockFake
) -> None:
    """The line names the service, the status, the attempts, the time of the waits and a hint."""
    web.answer(_URL, 503)

    error = service_error("Prometheus", _status_error(_client()), setting="prometheus.url")

    assert isinstance(error, ServiceRequestError)
    assert (error.exit_code, error.status_code, error.attempts, "\n" in error.message) == (
        1,
        503,
        4,
        False,
    )
    assert error.message == (
        f"Prometheus failed after 4 attempts in {sum(clock.waits):.1f} s: "
        "HTTP 503 Service Unavailable. The service is not ready: try again, or examine its pod."
    )


def test_a_network_error_names_its_class_and_the_setting(web: WebFake, clock: ClockFake) -> None:
    """A service that does not answer has no status, and the hint names its address setting."""
    web.refuse(_URL)

    with pytest.raises(httpx2.ConnectError) as raised:
        _client().get(_URL)
    error = service_error("Loki", raised.value, setting="loki.url")

    assert error.status_code is None
    assert error.message.startswith("Loki failed after 4 attempts in ")
    assert error.message.endswith(
        ": ConnectError: Connection refused. The service did not answer: make sure that loki.url"
        " is correct and that its pod runs, then try again."
    )


def test_a_refused_query_names_the_error_of_the_reply(web: WebFake, clock: ClockFake) -> None:
    """The `errorType` and `error` fields of a Prometheus error reply are the detail (#5487)."""
    web.respond(
        "GET",
        _URL,
        400,
        {"status": "error", "errorType": "bad_data", "error": "1:9: parse error: unexpected <by>"},
    )

    error = service_error("Prometheus", _status_error(_client()))

    assert error.message == (
        "Prometheus failed after 1 attempt in 0.0 s: HTTP 400 Bad Request: bad_data: 1:9: parse"
        " error: unexpected <by>. The service refused the request: correct the request, then try"
        " again."
    )


def test_a_message_field_and_a_plain_text_reply_are_the_detail(
    web: WebFake, clock: ClockFake
) -> None:
    """Grafana gives `message` in its JSON error, and Loki gives a line of plain text."""
    web.respond("GET", _URL, 404, {"message": "Dashboard not found"})
    grafana = service_error("Grafana", _status_error(_client()))
    web.answer(
        _URL,
        400,
        method="GET",
        headers={"content-type": "text/plain; charset=utf-8"},
        body="parse error at line 1\n",
    )
    loki = service_error("Loki", _status_error(_client()))

    assert (
        ": HTTP 404 Not Found: Dashboard not found. " in grafana.message,
        ": HTTP 400 Bad Request: parse error at line 1. " in loki.message,
    ) == (True, True)


def test_a_rate_limit_hint_asks_to_wait(web: WebFake, clock: ClockFake) -> None:
    """A 429 that stays after the attempts asks the person to wait."""
    web.answer(_URL, 429)

    error = service_error("Grafana", _status_error(_client()))

    assert error.message.endswith("The service limits the rate of requests: wait, then try again.")


def test_an_error_of_a_client_with_no_policy_counts_one_attempt(web: WebFake) -> None:
    """A request that went through no policy has no record of its attempts."""
    web.answer(_URL, 503)

    error = service_error("Grafana", _status_error(http_client(EgressLevel.PUBLIC)))

    assert error.message.startswith("Grafana failed after 1 attempt in 0.0 s: HTTP 503")

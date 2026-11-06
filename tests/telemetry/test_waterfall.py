"""Tests of the Tempo trace query of `devops_cli.telemetry.waterfall`.

Tempo is reached through the HTTP entry point at the loopback egress level. The `web` fixture
answers its requests and the `dns` fixture answers its host lookups. Which address a client dials,
and the TLS handshake with the host name, are the transport's work: `tests/http/test_http_egress.py`
holds them.
"""

from __future__ import annotations

import json

import httpx2
import pytest

from devops_cli.telemetry.waterfall import query_tempo_trace
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake
from tests.support.fakes.http import WebFake
from tests.support.paths import FIXTURES

_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
_TEMPO_URL = "http://example.com:3200"
_QUERY_URL = f"{_TEMPO_URL}/api/v2/traces/{_TRACE_ID}"


def test_the_tempo_query_goes_to_the_configured_host_without_its_credentials(
    dns: DnsFake, web: WebFake
) -> None:
    """Tempo is queried at its configured host name, which the Host header carries. The userinfo
    of the URL never reaches the Host header."""
    payload = json.loads(
        (FIXTURES / "traces" / "tempo-otlp-trace.json").read_text(encoding="utf-8")
    )
    web.respond(
        "GET", f"https://user:secret@example.com:3200/api/v2/traces/{_TRACE_ID}", 200, payload
    )

    spans = query_tempo_trace(_TRACE_ID, tempo_url="https://user:secret@example.com:3200")

    assert (
        [span["traceId"] for span in spans],
        [request.headers["host"] for request in web.recorded],
        [lookup.port for lookup in dns.lookups_of("example.com")],
    ) == ([_TRACE_ID, _TRACE_ID], ["example.com:3200"], [3200])


def test_the_tempo_timeout_bounds_the_connect(web: WebFake) -> None:
    """A Tempo query's `timeout` bounds the connect too, not only the read."""
    web.respond("GET", _QUERY_URL, 200, {"trace": {}})

    query_tempo_trace(_TRACE_ID, _TEMPO_URL, 7.0)

    assert web.sent[0].extensions["timeout"]["connect"] == 7.0


@pytest.mark.parametrize("flag", ["false", "true"])
def test_tempo_admits_loopback_and_public_answers_only(
    monkeypatch: pytest.MonkeyPatch, dns: DnsFake, web: WebFake, flag: str
) -> None:
    """Verify Tempo's loopback-level client refuses RFC 1918 and link-local answers, flag or not."""
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", flag)
    answers = [
        "169.254.169.254",
        "10.0.0.1",
        "172.16.0.1",
        "169.254.1.2",
        "127.0.0.1",
        PUBLIC_ADDRESS,
    ]
    dns.script("example.com", *[[answer] for answer in answers])
    web.respond("GET", _QUERY_URL, 200, {"trace": {}})

    for _ in answers:
        query_tempo_trace(_TRACE_ID, tempo_url=_TEMPO_URL)

    assert (len(dns.lookups_of("example.com")), web.requested) == (len(answers), [_QUERY_URL] * 2)


def test_query_tempo_trace_security_validation(web: WebFake) -> None:
    """Verify query_tempo_trace rejects invalid hex, path traversal, and disallowed URLs."""
    # Invalid trace IDs: path traversal, non-hex, empty
    assert query_tempo_trace("../../admin") == []
    assert query_tempo_trace("not-a-hex-id!") == []
    assert query_tempo_trace("") == []

    # Invalid Tempo URLs: invalid scheme, cloud metadata, private addresses
    assert query_tempo_trace(_TRACE_ID, tempo_url="ftp://example.com") == []
    assert query_tempo_trace(_TRACE_ID, tempo_url="http://169.254.169.254") == []
    assert query_tempo_trace(_TRACE_ID, tempo_url="http://10.0.0.1:3200") == []
    assert query_tempo_trace(_TRACE_ID, tempo_url="http://192.168.1.1:3200") == []
    assert query_tempo_trace(_TRACE_ID, tempo_url="http://172.16.0.1:3200") == []
    assert [request.url.host for request in web.sent if request.url.host != "example.com"] == []


def test_a_host_that_resolves_to_cloud_metadata_gets_no_request(dns: DnsFake, web: WebFake) -> None:
    """Verify query_tempo_trace rejects hosts resolving to link-local metadata addresses."""
    dns.add("example.com", "169.254.169.254")

    assert (query_tempo_trace(_TRACE_ID, tempo_url=_TEMPO_URL), web.sent) == ([], [])


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(None, id="error-status"),
        pytest.param(httpx2.ConnectError("Connection refused"), id="connection-refused"),
        pytest.param(httpx2.ReadTimeout("The read operation timed out"), id="read-timeout"),
    ],
)
def test_query_tempo_trace_returns_no_spans_on_an_error_status_or_a_network_failure(
    web: WebFake, failure: httpx2.TransportError | None
) -> None:
    """Verify query_tempo_trace returns an empty list on HTTP non-200 and on request errors."""
    if failure is None:
        web.respond("GET", _QUERY_URL, 500, {})
    else:
        web.fail(_QUERY_URL, failure)

    assert (query_tempo_trace(_TRACE_ID, tempo_url=_TEMPO_URL), len(web.sent)) == ([], 1)

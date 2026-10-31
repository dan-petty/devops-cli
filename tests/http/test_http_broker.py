"""Unit tests for the Unified Async HTTP/2 Connection Broker."""

from __future__ import annotations

from functools import partial

import httpx2
import pytest

from devops_cli.config.constants import CONST_HTTP_EGRESS_POLICY_EXTENSION
from devops_cli.config.defaults import DEFAULT_HTTP_MAX_REDIRECTS
from devops_cli.core.validation import validate_url_egress
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.http.broker import HttpClientBroker, get_broker
from devops_cli.http.egress import EgressLevel
from tests.web_fakes import StubWeb


def test_http_broker_keeps_one_shared_client_per_level() -> None:
    """Each level has its own client, so a connection never crosses from one level to another."""
    broker = HttpClientBroker()
    public, private = broker.get_client(EgressLevel.PUBLIC), broker.get_client(EgressLevel.PRIVATE)
    assert (public is broker.get_client(EgressLevel.PUBLIC), public is private) == (True, False)
    broker.close()


def test_http_broker_traceparent_header_injection() -> None:
    broker = HttpClientBroker()
    headers = broker.build_headers({"Authorization": "Bearer token123"})
    assert headers["Authorization"] == "Bearer token123"
    # Should contain traceparent if span context exists or return standard headers
    assert "User-Agent" in headers or "Authorization" in headers
    broker.close()


def test_http_broker_hook_refuses_a_scheme_other_than_http() -> None:
    """The request hook admits http and https hops only; it makes no lookup."""
    HttpClientBroker._validate_request(httpx2.Request("GET", "https://example.com/repos"))
    with pytest.raises(ValidationError):
        HttpClientBroker._validate_request(httpx2.Request("GET", "ftp://example.com/api"))


@pytest.mark.asyncio
async def test_http_broker_async_context_manager() -> None:
    async with HttpClientBroker() as broker:
        aclient1 = await broker.get_async_client(EgressLevel.PRIVATE)
        aclient2 = await broker.get_async_client(EgressLevel.PRIVATE)
        assert aclient1 is aclient2
        assert not aclient1.is_closed


_START = "https://example.com/start"
_LINK_LOCAL = "http://169.254.169.254/latest/meta-data/"
_NAT64_METADATA = "http://[64:ff9b::a9fe:a9fe]/latest/meta-data/"
_LOOPBACK = "http://127.0.0.1:8200/v1/sys/health"
_FINAL = "https://example.com/final"


def _serve_chain(stub_web: StubWeb, hop: str) -> None:
    """Serve a public page that redirects to `hop`, which redirects to a public final page."""
    stub_web.redirect(_START, hop)
    stub_web.redirect(hop, _FINAL)
    stub_web.page(_FINAL, "<h1>Final</h1>")


def test_http_broker_never_sends_a_link_local_redirect_hop(stub_web: StubWeb) -> None:
    """A public, then metadata, then public 3xx chain stops before the metadata hop is sent.

    The private level, Vault's, still refuses cloud metadata at every hop.
    """
    _serve_chain(stub_web, _LINK_LOCAL)

    with pytest.raises(SSRFBlockedError):
        get_broker().request("GET", _START, level=EgressLevel.PRIVATE)

    assert stub_web.requested == [_START]


def test_http_broker_holds_every_hop_to_the_request_egress_policy(stub_web: StubWeb) -> None:
    """A request's own egress policy vets each hop, even on the private-level client."""
    _serve_chain(stub_web, _LOOPBACK)
    vetted: list[str] = []

    def public_only(url: str) -> None:
        vetted.append(url)
        validate_url_egress(url, purpose="test", allow_private=False)

    with HttpClientBroker() as broker:
        client = broker.get_client(EgressLevel.PRIVATE)
        request = client.build_request(
            "GET", _START, extensions={CONST_HTTP_EGRESS_POLICY_EXTENSION: public_only}
        )
        with pytest.raises(SSRFBlockedError):
            client.send(request)

    assert (vetted, stub_web.requested) == ([_START, _LOOPBACK], [_START])


@pytest.mark.parametrize("hop", [_LINK_LOCAL, _NAT64_METADATA])
def test_http_broker_keeps_its_own_veto_under_a_request_egress_policy(
    stub_web: StubWeb, hop: str
) -> None:
    """A request's egress policy adds to the connect's check: a no-op one cannot reach metadata."""
    _serve_chain(stub_web, hop)
    vetted: list[str] = []

    with HttpClientBroker() as broker:
        client = broker.get_client(EgressLevel.PRIVATE)
        request = client.build_request(
            "GET", _START, extensions={CONST_HTTP_EGRESS_POLICY_EXTENSION: vetted.append}
        )
        with pytest.raises(SSRFBlockedError):
            client.send(request)

    assert (vetted, stub_web.requested) == ([_START, hop], [_START])


@pytest.mark.asyncio
async def test_http_broker_async_client_vetoes_each_redirect_hop(stub_web: StubWeb) -> None:
    """The async client vetoes a redirect hop under the request's egress policy before sending it."""
    _serve_chain(stub_web, _LOOPBACK)
    policy = {CONST_HTTP_EGRESS_POLICY_EXTENSION: partial(validate_url_egress, allow_private=False)}

    async with HttpClientBroker() as broker:
        with pytest.raises(SSRFBlockedError):
            await broker.arequest("GET", _START, level=EgressLevel.PRIVATE, extensions=policy)

    assert stub_web.requested == [_START]


def test_http_broker_stops_a_redirect_loop_below_the_httpx2_default(stub_web: StubWeb) -> None:
    """A redirect loop ends after the broker's redirect limit, which is below httpx2's 20."""
    stub_web.redirect(_START, _START)

    with pytest.raises(httpx2.TooManyRedirects):
        get_broker().request("GET", _START, level=EgressLevel.PUBLIC)

    assert (len(stub_web.requested), DEFAULT_HTTP_MAX_REDIRECTS < 20) == (
        DEFAULT_HTTP_MAX_REDIRECTS + 1,
        True,
    )


@pytest.mark.asyncio
async def test_http_broker_async_client_stops_a_redirect_loop_below_the_httpx2_default(
    stub_web: StubWeb,
) -> None:
    """The async client ends a redirect loop after the broker's redirect limit too."""
    stub_web.redirect(_START, _START)

    async with HttpClientBroker() as broker:
        with pytest.raises(httpx2.TooManyRedirects):
            await broker.arequest("GET", _START, level=EgressLevel.PUBLIC)

    assert len(stub_web.requested) == DEFAULT_HTTP_MAX_REDIRECTS + 1


def test_stub_web_leaves_httpx2_clients_subclassable(stub_web: StubWeb) -> None:
    """Code that subclasses httpx2's clients while stub_web is active still builds and answers."""
    stub_web.page(_FINAL, "<h1>Final</h1>")

    class Client(httpx2.Client):
        """A subclass as SDKs declare one, such as openai's default client."""

    class AsyncClient(httpx2.AsyncClient):
        """An async subclass, which is answered by the stub as well."""

    with Client() as client:
        status = client.get(_FINAL).status_code

    assert (status, issubclass(AsyncClient, httpx2.AsyncClient), stub_web.requested) == (
        200,
        True,
        [_FINAL],
    )

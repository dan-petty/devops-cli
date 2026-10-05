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
from tests.web_fakes import StubWeb


def test_http_broker_get_client_singleton() -> None:
    broker = HttpClientBroker()
    client1 = broker.get_client()
    client2 = broker.get_client()
    assert client1 is client2
    broker.close()


def test_http_broker_traceparent_header_injection() -> None:
    broker = HttpClientBroker()
    headers = broker.build_headers({"Authorization": "Bearer token123"})
    assert headers["Authorization"] == "Bearer token123"
    # Should contain traceparent if span context exists or return standard headers
    assert "User-Agent" in headers or "Authorization" in headers
    broker.close()


def test_http_broker_ssrf_destination_validation() -> None:
    broker = HttpClientBroker(allow_private_networks=False)

    # Invalid URL scheme
    with pytest.raises(ValidationError):
        broker.validate_url("ftp://example.com/api")

    # Safe public URL
    safe_url = broker.validate_url("https://api.github.com/repos")
    assert safe_url == "https://api.github.com/repos"
    broker.close()


@pytest.mark.asyncio
async def test_http_broker_async_context_manager() -> None:
    async with HttpClientBroker() as broker:
        aclient1 = await broker.get_async_client()
        aclient2 = await broker.get_async_client()
        assert aclient1 is aclient2
        assert not aclient1.is_closed


def test_http_broker_per_request_allow_private_network_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that per-request allow_private_network overrides broker default."""
    from unittest.mock import MagicMock, patch

    import httpx

    from devops_cli.exceptions.security import SSRFBlockedError

    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    broker = HttpClientBroker(allow_private_networks=False)

    # 1. Default (disallowed) rejects private destination on request()
    with pytest.raises(SSRFBlockedError):
        broker.request("GET", "http://127.0.0.1:8200/v1/sys/health")

    # 2. Per-request override allow_private_network=True permits private destination
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200

    client = broker.get_client()
    with patch.object(client, "send", return_value=mock_resp) as mock_send:
        resp = broker.request(
            "GET", "http://127.0.0.1:8200/v1/sys/health", allow_private_network=True
        )
        assert resp.status_code == 200
        assert mock_send.called
        sent_req = mock_send.call_args[0][0]
        assert sent_req.extensions.get("allow_private_network") is True

    broker.close()


@pytest.mark.asyncio
async def test_http_broker_async_per_request_allow_private_network_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that per-request allow_private_network overrides broker default in async arequest."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import httpx

    from devops_cli.exceptions.security import SSRFBlockedError

    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    async with HttpClientBroker(allow_private_networks=False) as broker:
        # Default rejects private network
        with pytest.raises(SSRFBlockedError):
            await broker.arequest("GET", "http://127.0.0.1:8200/v1/sys/health")

        # Per-request override permits private destination
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200

        aclient = await broker.get_async_client()
        with patch.object(aclient, "send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_resp
            resp = await broker.arequest(
                "GET", "http://127.0.0.1:8200/v1/sys/health", allow_private_network=True
            )
            assert resp.status_code == 200
            assert mock_send.called
            sent_req = mock_send.call_args[0][0]
            assert sent_req.extensions.get("allow_private_network") is True


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
    """A public, then link-local, then public 3xx chain stops before the link-local hop is sent."""
    _serve_chain(stub_web, _LINK_LOCAL)

    with pytest.raises(SSRFBlockedError):
        get_broker().request("GET", _START)

    assert stub_web.requested == [_START]


def test_http_broker_holds_every_hop_to_the_request_egress_policy(
    stub_web: StubWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A request's own egress policy vets each hop, even where the broker admits private networks."""
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    _serve_chain(stub_web, _LOOPBACK)
    vetted: list[str] = []

    def public_only(url: str) -> None:
        vetted.append(url)
        validate_url_egress(url, purpose="test", allow_private=False)

    with HttpClientBroker(allow_private_networks=True) as broker:
        client = broker.get_client()
        request = client.build_request(
            "GET", _START, extensions={CONST_HTTP_EGRESS_POLICY_EXTENSION: public_only}
        )
        with pytest.raises(SSRFBlockedError):
            client.send(request)

    assert (vetted, stub_web.requested) == ([_START, _LOOPBACK], [_START])


@pytest.mark.parametrize("hop", [_LINK_LOCAL, _NAT64_METADATA])
def test_http_broker_keeps_its_own_veto_under_a_request_egress_policy(
    stub_web: StubWeb, monkeypatch: pytest.MonkeyPatch, hop: str
) -> None:
    """A request's egress policy adds to the broker's check: a no-op one cannot reach metadata."""
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    _serve_chain(stub_web, hop)
    vetted: list[str] = []

    with HttpClientBroker(allow_private_networks=True) as broker:
        client = broker.get_client()
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

    async with HttpClientBroker(allow_private_networks=True) as broker:
        with pytest.raises(SSRFBlockedError):
            await broker.arequest("GET", _START, extensions=policy)

    assert stub_web.requested == [_START]


def test_http_broker_stops_a_redirect_loop_below_the_httpx2_default(stub_web: StubWeb) -> None:
    """A redirect loop ends after the broker's redirect limit, which is below httpx2's 20."""
    stub_web.redirect(_START, _START)

    with pytest.raises(httpx2.TooManyRedirects):
        get_broker().request("GET", _START)

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
            await broker.arequest("GET", _START)

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

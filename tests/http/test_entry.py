"""Tests of the HTTP entry point (`devops_cli.http.entry`) and its transport hook (#1314)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx2
import pytest

from devops_cli.ai.retries import create_retry_transport
from devops_cli.config.constants import (
    CONST_HTTP_EGRESS_POLICY_EXTENSION,
    CONST_TRACEPARENT_HEADER,
)
from devops_cli.config.defaults import DEFAULT_HTTP_MAX_REDIRECTS
from devops_cli.exceptions import InvalidURLError
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.http.client import user_agent
from devops_cli.http.egress import EgressLevel, vet_addresses
from devops_cli.http.entry import (
    async_http_client,
    aveto_request,
    http_client,
    install_transport,
    remove_transport,
    request_headers,
    veto_request,
)
from devops_cli.http.pool import close_shared_clients
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake

_START = "https://example.com/start"
_LINK_LOCAL = "http://169.254.169.254/latest/meta-data/"
_NAT64_METADATA = "http://[64:ff9b::a9fe:a9fe]/latest/meta-data/"
_LOOPBACK = "http://127.0.0.1:8200/v1/sys/health"
_FINAL = "https://example.com/final"
_HOOKS = {"request": [veto_request]}


def _serve_chain(web: WebFake, hop: str) -> None:
    """Serve a public page that redirects to `hop`, which redirects to a public final page."""
    web.redirect(_START, hop)
    web.redirect(hop, _FINAL)
    web.page(_FINAL, "<h1>Final</h1>")


# =============================================================================
# Pooled and unpooled clients
# =============================================================================


def test_a_key_and_a_level_name_one_pooled_client() -> None:
    """Each level has its own client, so a connection never crosses from one level to another."""
    public = http_client(EgressLevel.PUBLIC, key="profile")
    private = http_client(EgressLevel.PRIVATE, key="profile")

    assert (
        public is http_client(EgressLevel.PUBLIC, key="profile"),
        public is private,
        public is http_client(EgressLevel.PUBLIC, key="other"),
    ) == (True, False, False)


def test_an_unpooled_client_is_a_new_one_each_time() -> None:
    """Without a key the caller owns the client and closes it."""
    first, second = http_client(EgressLevel.PUBLIC), http_client(EgressLevel.PUBLIC)
    assert first is not second
    first.close()
    second.close()


@pytest.mark.parametrize("option", [{"timeout": 1.0}, {"read_timeout": 1.0}, {"http2": True}])
def test_a_pooled_client_refuses_an_option_that_the_pool_fixes(option: dict[str, Any]) -> None:
    """A pooled client has one timeout, protocol and transport for every caller."""
    with pytest.raises(TypeError, match="pooled client fixes"):
        http_client(EgressLevel.PUBLIC, key="profile", **option)
    with pytest.raises(TypeError, match="pooled client fixes"):
        async_http_client(EgressLevel.PUBLIC, key="profile", **option)


def test_a_pooled_async_client_is_shared_per_key() -> None:
    """The async pool shares a client per key and level too."""
    assert async_http_client(EgressLevel.PUBLIC, key="profile") is async_http_client(
        EgressLevel.PUBLIC, key="profile"
    )


# =============================================================================
# The transport hook
# =============================================================================


def test_a_client_takes_its_transport_from_the_installed_hook(web: WebFake) -> None:
    """Every client the entry point builds, pooled or not, sync or async, is answered by the fake."""
    web.page(_FINAL, "<h1>Final</h1>")

    async def get_async() -> int:
        async with async_http_client(EgressLevel.PUBLIC) as client:
            return (await client.get(_FINAL)).status_code

    with http_client(EgressLevel.PUBLIC) as unpooled:
        unpooled_status = unpooled.get(_FINAL).status_code
    pooled_status = http_client(EgressLevel.PUBLIC, key="profile").get(_FINAL).status_code

    assert (unpooled_status, pooled_status, asyncio.run(get_async()), web.requested) == (
        200,
        200,
        200,
        [_FINAL] * 3,
    )


def test_the_hook_gives_the_factory_the_level_of_the_client(web: WebFake) -> None:
    """The fake vets a request at the level of the client that sent it."""
    web.page(_LOOPBACK, "{}")

    with pytest.raises(SSRFBlockedError) as raised:
        http_client(EgressLevel.PUBLIC).get(_LOOPBACK)
    private_status = http_client(EgressLevel.PRIVATE).get(_LOOPBACK).status_code

    assert (raised.value.error_code, private_status, web.requested) == (
        "SSRF_BLOCKED",
        200,
        [_LOOPBACK],
    )


def test_installing_and_removing_a_transport_close_the_pooled_clients(web: WebFake) -> None:
    """A pooled client built earlier would keep the old transport, so each swap closes it first."""
    before = http_client(EgressLevel.PUBLIC, key="profile")
    install_transport(WebFake().transport)
    after_install = http_client(EgressLevel.PUBLIC, key="profile")
    remove_transport()
    after_remove = http_client(EgressLevel.PUBLIC, key="profile")

    assert (
        before.is_closed,
        after_install.is_closed,
        after_remove is not after_install,
        after_install is not before,
    ) == (True, True, True, True)


def test_a_removed_transport_gives_the_real_egress_transport_back(
    web: WebFake, refusing_port: int
) -> None:
    """After the fake goes, a client dials, so a port with nothing listening refuses it."""
    url = f"http://127.0.0.1:{refusing_port}/"
    web.page(url, "faked")
    faked = http_client(EgressLevel.LOOPBACK).get(url).text

    remove_transport()
    with pytest.raises(httpx2.ConnectError) as raised:
        http_client(EgressLevel.LOOPBACK, read_timeout=0.2).get(url)

    assert (faked, str(raised.value.request.url)) == ("faked", url)


def test_an_installed_transport_of_the_wrong_kind_is_a_type_error() -> None:
    """A sync-only transport cannot serve an async client, and the error names both."""

    class SyncOnly(httpx2.BaseTransport):
        def handle_request(self, request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200)

    install_transport(lambda level: SyncOnly())
    try:
        with pytest.raises(TypeError, match="SyncOnly, not a AsyncBaseTransport"):
            async_http_client(EgressLevel.PUBLIC)
        with http_client(EgressLevel.PUBLIC) as client:
            assert client.get(_FINAL).status_code == 200
    finally:
        remove_transport()


def test_the_pool_keeps_its_public_reset(web: WebFake) -> None:
    """`close_shared_clients` still closes every pooled client."""
    client = http_client(EgressLevel.PUBLIC, key="profile")
    close_shared_clients()
    assert client.is_closed


def test_a_retrying_client_wraps_the_installed_transport(web: WebFake, clock: ClockFake) -> None:
    """The retry transport sits on the seam's transport: the fake sees every attempt."""
    web.answer(_FINAL, 503)

    with pytest.raises(httpx2.HTTPStatusError) as raised:
        http_client(EgressLevel.PUBLIC, retries=3).get(_FINAL)

    assert (raised.value.response.status_code, web.requested, len(clock.waits)) == (
        503,
        [_FINAL] * 3,
        2,
    )


def test_a_retry_transport_has_no_default_transport_to_wrap() -> None:
    """A default would dial with no egress check, so the caller passes the transport."""
    no_arguments: dict[str, Any] = {}
    with pytest.raises(TypeError, match="wrapped"):
        create_retry_transport(**no_arguments)


# =============================================================================
# Headers and the request veto
# =============================================================================


def test_request_headers_name_the_release_and_keep_the_callers_headers() -> None:
    """The caller's headers stay, a User-Agent of the caller wins, and the release is the default."""
    assert (
        request_headers({"Authorization": "Bearer token123"}),
        request_headers({"User-Agent": "probe"})["User-Agent"],
    ) == ({"Authorization": "Bearer token123", "User-Agent": user_agent()}, "probe")


def test_request_headers_carry_the_traceparent_of_the_active_span(tracer: Any) -> None:
    """A request sent inside a span continues its trace."""
    with tracer.span("operation"):
        headers = request_headers()
        expected = tracer.current_trace_id

    assert headers[CONST_TRACEPARENT_HEADER].split("-")[1] == expected


def test_the_veto_refuses_a_scheme_other_than_http() -> None:
    """The hook admits http and https hops only; it makes no lookup."""
    veto_request(httpx2.Request("GET", "https://example.com/repos"))
    with pytest.raises(InvalidURLError) as raised:
        veto_request(httpx2.Request("GET", "ftp://example.com/api"))
    assert raised.value.error_code == "INVALID_URL"


def test_the_veto_of_a_scheme_says_which_problem_it_is(web: WebFake) -> None:
    """A client with the veto refuses a file URL before it sends anything."""
    with http_client(EgressLevel.PUBLIC, event_hooks=_HOOKS) as client:
        with pytest.raises(InvalidURLError) as raised:
            client.send(client.build_request("GET", "file:///etc/passwd"))

    assert (str(raised.value), web.requested) == (
        "Invalid URL: Only http and https URLs may be requested",
        [],
    )


async def test_the_async_veto_refuses_like_the_sync_one() -> None:
    """The async hook gives the same refusal."""
    with pytest.raises(InvalidURLError) as raised:
        await aveto_request(httpx2.Request("GET", "ftp://example.com/api"))
    assert raised.value.error_code == "INVALID_URL"


def test_a_redirect_to_metadata_is_never_sent(web: WebFake) -> None:
    """A public, then metadata, then public 3xx chain stops before the metadata hop is sent.

    The private level, Vault's, still refuses cloud metadata at every hop.
    """
    _serve_chain(web, _LINK_LOCAL)

    with pytest.raises(SSRFBlockedError) as raised:
        http_client(EgressLevel.PRIVATE, follow_redirects=True).get(_START)
    assert raised.value.error_code == "SSRF_BLOCKED"

    assert web.requested == [_START]


def test_every_hop_is_held_to_the_request_egress_policy(web: WebFake) -> None:
    """A request's own egress policy vets each hop, even on the private-level client."""
    _serve_chain(web, _LOOPBACK)
    vetted: list[str] = []

    def public_only(url: str) -> None:
        vetted.append(url)
        parsed = httpx2.URL(url)
        vet_addresses(parsed.host, parsed.origin.port, EgressLevel.PUBLIC)

    with http_client(EgressLevel.PRIVATE, follow_redirects=True, event_hooks=_HOOKS) as client:
        request = client.build_request(
            "GET", _START, extensions={CONST_HTTP_EGRESS_POLICY_EXTENSION: public_only}
        )
        with pytest.raises(SSRFBlockedError) as raised:
            client.send(request)
    assert raised.value.error_code == "SSRF_BLOCKED"

    assert (vetted, web.requested) == ([_START, _LOOPBACK], [_START])


@pytest.mark.parametrize("hop", [_LINK_LOCAL, _NAT64_METADATA])
def test_the_veto_keeps_its_own_check_under_a_request_egress_policy(web: WebFake, hop: str) -> None:
    """A request's egress policy adds to the connect's check: a no-op one cannot reach metadata."""
    _serve_chain(web, hop)
    vetted: list[str] = []

    with http_client(EgressLevel.PRIVATE, follow_redirects=True, event_hooks=_HOOKS) as client:
        request = client.build_request(
            "GET", _START, extensions={CONST_HTTP_EGRESS_POLICY_EXTENSION: vetted.append}
        )
        with pytest.raises(SSRFBlockedError) as raised:
            client.send(request)
    assert raised.value.error_code == "SSRF_BLOCKED"

    assert (vetted, web.requested) == ([_START, hop], [_START])


async def test_an_async_client_vetoes_each_redirect_hop(web: WebFake) -> None:
    """The async client vetoes a redirect hop under the request's egress policy before sending it."""
    _serve_chain(web, _LOOPBACK)

    def public_only(url: str) -> None:
        parsed = httpx2.URL(url)
        vet_addresses(parsed.host, parsed.origin.port, EgressLevel.PUBLIC)

    policy = {CONST_HTTP_EGRESS_POLICY_EXTENSION: public_only}

    async with async_http_client(
        EgressLevel.PRIVATE, follow_redirects=True, event_hooks={"request": [aveto_request]}
    ) as client:
        with pytest.raises(SSRFBlockedError) as raised:
            await client.get(_START, extensions=policy)
    assert raised.value.error_code == "SSRF_BLOCKED"

    assert web.requested == [_START]


def test_a_redirect_loop_ends_at_the_redirect_limit_below_the_httpx2_default(
    web: WebFake,
) -> None:
    """A redirect loop ends after the configured redirect limit, which is below httpx2's 20."""
    web.redirect(_START, _START)

    with http_client(
        EgressLevel.PUBLIC, follow_redirects=True, max_redirects=DEFAULT_HTTP_MAX_REDIRECTS
    ) as client:
        with pytest.raises(httpx2.TooManyRedirects) as raised:
            client.get(_START)

    assert (str(raised.value.request.url), len(web.requested), DEFAULT_HTTP_MAX_REDIRECTS < 20) == (
        _START,
        DEFAULT_HTTP_MAX_REDIRECTS + 1,
        True,
    )


async def test_an_async_redirect_loop_ends_at_the_redirect_limit(web: WebFake) -> None:
    """The async client ends a redirect loop after the configured limit too."""
    web.redirect(_START, _START)

    async with async_http_client(
        EgressLevel.PUBLIC, follow_redirects=True, max_redirects=DEFAULT_HTTP_MAX_REDIRECTS
    ) as client:
        with pytest.raises(httpx2.TooManyRedirects) as raised:
            await client.get(_START)

    assert (str(raised.value.request.url), len(web.requested)) == (
        _START,
        DEFAULT_HTTP_MAX_REDIRECTS + 1,
    )

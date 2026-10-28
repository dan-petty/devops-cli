"""The connect-time egress policy: the vetting backends, the client factory and their seams.

Each test stubs `socket.getaddrinfo` and httpcore2's dial (`tests/web_fakes.py`), so it sees the
lookups a client made and the address it dialled, with no socket opened and no DNS query made.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import socket
import ssl
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpcore2
import httpx2
import pytest

from devops_cli.ai.benchmark.embedding_runner import EmbeddingBenchmarkRunner
from devops_cli.ai.benchmark.runner import BenchmarkRunner
from devops_cli.ai.client import LLMClient
from devops_cli.ai.common_tools import firecrawl_search
from devops_cli.ai.gateway import GatewayRouter, fetch_model_info
from devops_cli.ai.library.docs_ingester import DocsIngester
from devops_cli.ai.providers import create_pydantic_ai_provider
from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model
from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.spend.pricing import PricingRegistry
from devops_cli.argo.fleet import sync_single_target
from devops_cli.argo.gitops import trigger_argocd_sync
from devops_cli.argo.rollouts import evaluate_rollout_gate
from devops_cli.cloudflare.client import CloudflareClient
from devops_cli.commands import ai_gateway, argo, grafana, prometheus
from devops_cli.commands.install_tools import _download
from devops_cli.config.defaults import (
    DEFAULT_HTTP_MAX_CONNECTIONS,
    DEFAULT_HTTP_MAX_KEEPALIVE_CONNECTIONS,
)
from devops_cli.config.settings import AIConfig, Settings, load_settings
from devops_cli.core.process import reset_process_runner, set_process_runner
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.http.broker import HttpClientBroker
from devops_cli.http.client import new_async_http_client, new_http_client
from devops_cli.http.egress import (
    AsyncVettingBackend,
    EgressLevel,
    VettingBackend,
    avet_addresses,
    configured_level,
    vet_addresses,
)
from devops_cli.http.pool import close_shared_clients, get_shared_async_client, get_shared_client
from devops_cli.k8s import service_http
from devops_cli.k8s.credentials import (
    get_or_mint_argocd_token,
    get_or_mint_grafana_auth,
    sync_k8s_credentials,
)
from devops_cli.k8s.logql import execute_loki_query, parse_logql_query
from devops_cli.k8s.service_proxy import ProxyTarget
from devops_cli.sandbox.metrics import scrape_prometheus_metrics
from devops_cli.sandbox.probe import probe_http, probe_tcp
from devops_cli.security.vault_broker import VaultSecretBroker
from devops_cli.security.vault_lease import _post
from devops_cli.security.vulnerability_lookup import (
    CloudflareRadarClient,
    OSVClient,
    ShodanInternetDBClient,
)
from devops_cli.telemetry.memory_profiler import _exercise_http_pool
from devops_cli.telemetry.service_status import fetch_statuspage_summary
from devops_cli.telemetry.waterfall import query_tempo_trace
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.web_fakes import (
    PUBLIC_ADDRESS,
    http_response,
    rebinding,
    record_connects,
    scripted_resolver,
)

PUBLIC, LOOPBACK, PRIVATE = EgressLevel.PUBLIC, EgressLevel.LOOPBACK, EgressLevel.PRIVATE
_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"


@pytest.fixture(scope="module", autouse=True)
def model_modules_imported() -> None:
    """Import the modules a pydantic-ai model request loads, once, before the first test.

    Their first import takes over 1 s. Without this, that cost lands in the call phase of the
    first row that builds a model, and not in the behavior that the row checks.
    """
    for module in ("pydantic_ai.models.ollama", "devops_cli.ai.agents.agent"):
        importlib.import_module(module)


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    """Shared clients are process-wide; a test must not inherit another's connections."""
    close_shared_clients()
    yield
    close_shared_clients()


def _admitted_levels(host: str) -> set[EgressLevel]:
    """The levels whose check lets a client dial `host`."""
    admitted: set[EgressLevel] = set()
    for level in EgressLevel:
        try:
            vet_addresses(host, 443, level)
        except SSRFBlockedError:
            continue
        admitted.add(level)
    return admitted


# =============================================================================
# Classification: what each level admits
# =============================================================================

_METADATA_HOSTS = (
    "169.254.169.254",
    "2852039166",
    "0xa9fea9fe",
    "0xa9.0xfe.0xa9.0xfe",
    "64:ff9b::a9fe:a9fe",
    "2002:a9fe:a9fe::",
    "2001::5601:5601",
    "::ffff:169.254.169.254",
    "fd00:ec2::254",
    "fd20:ce::254",
    "169.254.170.2",
    "168.63.129.16",
    "metadata.google.internal",
    "metadata.",
)


@pytest.mark.parametrize("host", _METADATA_HOSTS)
def test_every_spelling_of_cloud_metadata_is_refused_at_every_level_before_a_dial(
    monkeypatch: pytest.MonkeyPatch, host: str
) -> None:
    """Old vs new: integer, hex, NAT64, 6to4, Teredo, mapped and named metadata never reach a dial.

    Before #898 the integer and hex spellings resolved inside the dial itself, after every check.
    """
    recorder = record_connects(monkeypatch, [])
    refused = []
    for level in EgressLevel:
        with pytest.raises(SSRFBlockedError):
            VettingBackend(level).connect_tcp(host, 80)
        refused.append(level)

    assert (refused, recorder.dialled) == (list(EgressLevel), [])


@pytest.mark.parametrize("level", list(EgressLevel))
def test_the_ideographic_dot_spelling_of_metadata_is_refused(
    monkeypatch: pytest.MonkeyPatch, level: EgressLevel
) -> None:
    """httpx2 reads `169。254。169。254` as 169.254.169.254, and the connect refuses it."""
    recorder = record_connects(monkeypatch, [])

    with new_http_client(level=level) as client, pytest.raises(SSRFBlockedError):
        client.get("http://169。254。169。254/latest/meta-data/")

    assert recorder.dialled == []


@pytest.mark.parametrize(
    "answer", ["169.254.169.254", "fd00:ec2::254", "fd20:ce::254", "64:ff9b::a9fe:a9fe"]
)
def test_a_name_answering_metadata_is_refused_at_every_level(
    monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    """Old vs new: before #898 a name answering metadata passed `validate_url(allow_private=True)`."""
    scripted_resolver(monkeypatch, {"example.com": [[answer]]})
    recorder = record_connects(monkeypatch, [])

    assert (_admitted_levels("example.com"), recorder.dialled) == (set(), [])


@pytest.mark.parametrize(
    ("answer", "admitted"),
    [
        (PUBLIC_ADDRESS, {PUBLIC, LOOPBACK, PRIVATE}),
        ("127.0.0.1", {LOOPBACK, PRIVATE}),
        ("::1", {LOOPBACK, PRIVATE}),
        ("10.0.0.1", {PRIVATE}),
        ("172.16.0.1", {PRIVATE}),
        ("100.64.0.1", {PRIVATE}),
        ("fc00::1", {PRIVATE}),
    ],
    ids=["public", "loopback", "loopback-v6", "rfc1918-10", "rfc1918-172", "cgnat", "ula"],
)
def test_each_level_admits_only_its_address_classes(
    monkeypatch: pytest.MonkeyPatch, answer: str, admitted: set[EgressLevel]
) -> None:
    """Loopback, RFC 1918, CGNAT and unique-local answers are admitted only where the level allows."""
    scripted_resolver(monkeypatch, {"example.com": [[answer]]})

    assert _admitted_levels("example.com") == admitted


def test_link_local_host_gateways_are_admitted_only_at_the_private_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the link-local answer proposed on #898, which the owner confirms before merge.

    Rootless Podman reaches its host at 169.254.1.2, a link-local address the documented
    `host.docker.internal` setups name. It is refused at the public and loopback levels and
    admitted at the private level; the metadata link-local addresses stay refused there.
    """
    scripted_resolver(
        monkeypatch,
        {
            "example.com": [["169.254.1.2"]],
            "example.org": [["169.254.169.254"]],
            "example.net": [["169.254.170.2"]],
            "example.edu": [["fd00:ec2::254"]],
        },
    )

    assert [
        _admitted_levels(host)
        for host in ("example.com", "example.org", "example.net", "example.edu")
    ] == [{PRIVATE}, set(), set(), set()]


def test_one_unsafe_answer_refuses_the_name_with_no_dial(monkeypatch: pytest.MonkeyPatch) -> None:
    """A name answering a public and a private address together is refused before any dial."""
    scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS, "10.0.0.1"]]})
    recorder = record_connects(monkeypatch, [])

    with pytest.raises(SSRFBlockedError) as caught:
        VettingBackend(PUBLIC).connect_tcp("example.com", 443)

    assert (caught.value.details["address"], recorder.dialled) == ("10.0.0.1", [])


def test_an_ip_literal_is_classified_without_a_dns_query() -> None:
    """A literal resolves numerically: the session guard, which fails every DNS query, lets it by."""
    assert (vet_addresses(PUBLIC_ADDRESS, 443, PUBLIC), _admitted_levels("127.0.0.1")) == (
        [PUBLIC_ADDRESS],
        {LOOPBACK, PRIVATE},
    )


@pytest.mark.unreachable("fe80::1%eth0", "fe80::1%25eth0")
def test_a_scoped_ipv6_address_fails_closed_at_every_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zone in the URL, or a scope id in an answer, is never dialled at any level."""
    recorder = record_connects(monkeypatch, [])
    for level in EgressLevel:
        with (
            new_http_client(level=level) as client,
            pytest.raises((SSRFBlockedError, httpx2.ConnectError)),
        ):
            client.get("http://[fe80::1%25eth0]/")

    def scoped(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("fe80::1", port, 0, 2))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", scoped)

    assert (_admitted_levels("example.com"), recorder.dialled) == (set(), [])


@pytest.mark.unreachable("example.com")
def test_a_failed_lookup_surfaces_as_httpx2_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The backend re-raises the resolver's OSError as httpcore2.ConnectError, which httpx2 maps."""
    recorder = record_connects(monkeypatch, [])

    with new_http_client(level=PUBLIC) as client, pytest.raises(httpx2.ConnectError):
        client.get("https://example.com/")

    assert recorder.dialled == []


def test_each_vetted_address_is_dialled_in_turn_and_the_last_error_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Like `socket.create_connection`, a refused address moves the dial on to the next answer."""
    addresses = ["93.184.215.14", "93.184.215.15", "93.184.215.16"]
    scripted_resolver(monkeypatch, {"example.com": [addresses]})
    dialled: list[str] = []

    class Refusing(httpcore2.NetworkBackend):
        """Refuses every address in `refused`; answers any other."""

        def __init__(self, refused: set[str]) -> None:
            self.refused = refused

        def connect_tcp(
            self, host: str, port: int, *args: Any, **kwargs: Any
        ) -> httpcore2.NetworkStream:
            dialled.append(host)
            if host in self.refused:
                raise httpcore2.ConnectError(f"refused by {host}")
            return httpcore2.MockStream([])

    VettingBackend(PUBLIC, inner=Refusing(set(addresses[:2]))).connect_tcp("example.com", 443)
    with pytest.raises(httpcore2.ConnectError, match=r"refused by 93\.184\.215\.16"):
        VettingBackend(PUBLIC, inner=Refusing(set(addresses))).connect_tcp("example.com", 443)

    assert dialled == addresses + addresses


def test_unix_sockets_and_sleep_are_delegated_to_the_inner_backend() -> None:
    """Only TCP connects are vetted: a Unix socket is not network egress."""
    inner = httpcore2.MockBackend([b"ok"])

    stream = VettingBackend(PRIVATE, inner=inner).connect_unix_socket("/run/example.sock")
    VettingBackend(PRIVATE, inner=inner).sleep(0)

    assert stream.read(2) == b"ok"


# =============================================================================
# The factory and its pinned seam
# =============================================================================


def test_the_factory_swaps_httpx2s_pool_for_a_vetting_httpcore2_pool() -> None:
    """Pinned seam: an httpx2 upgrade that moves `_pool` fails here instead of skipping the check."""
    context = ssl.create_default_context()
    sync_client = new_http_client(level=LOOPBACK, http2=True, verify=context)
    async_client = new_async_http_client(level=PRIVATE)
    sync_pool, async_pool = sync_client._transport._pool, async_client._transport._pool

    assert (
        type(sync_pool),
        type(sync_pool._network_backend),
        sync_pool._network_backend.level,
        sync_pool._ssl_context is context,
        sync_pool._http2,
        (sync_pool._max_connections, sync_pool._max_keepalive_connections),
        type(async_pool),
        type(async_pool._network_backend),
        async_pool._network_backend.level,
    ) == (
        httpcore2.ConnectionPool,
        VettingBackend,
        LOOPBACK,
        True,
        True,
        (DEFAULT_HTTP_MAX_CONNECTIONS, DEFAULT_HTTP_MAX_KEEPALIVE_CONNECTIONS),
        httpcore2.AsyncConnectionPool,
        AsyncVettingBackend,
        PRIVATE,
    )
    sync_client.close()


@pytest.mark.usefixtures("public_dns")
def test_tls_and_the_host_header_keep_the_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dial goes to the vetted address; SNI, the certificate check and Host use the name."""
    recorder = record_connects(monkeypatch, [http_response(200, "ok")])

    with new_http_client(level=PUBLIC) as client:
        response = client.get("https://example.com/")
    ((server_hostname, context),) = recorder.tls

    assert (
        recorder.dialled,
        server_hostname,
        context.check_hostname,
        context.verify_mode,
        recorder.requested_hosts,
        str(response.url),
    ) == (
        [(PUBLIC_ADDRESS, 443)],
        "example.com",
        True,
        ssl.CERT_REQUIRED,
        ["example.com"],
        "https://example.com/",
    )


@pytest.mark.usefixtures("public_dns")
def test_environment_proxies_are_ignored_and_the_destination_dialled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the proxy answer proposed on #898: a vetted client never hands its request to a proxy.

    A proxy would become the peer the backend vets in place of the destination.
    """
    for variable in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(variable, "http://192.0.2.10:3128")
    recorder = record_connects(monkeypatch, [http_response(200, "ok")])

    with new_http_client(level=PUBLIC) as client:
        status = client.get("https://example.com/").status_code

    assert (status, recorder.dialled, recorder.tls[0][0]) == (
        200,
        [(PUBLIC_ADDRESS, 443)],
        "example.com",
    )


@pytest.mark.usefixtures("public_dns")
def test_a_client_without_retries_returns_error_statuses_and_dials_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry wrapping is opt-in: a plain factory client keeps httpx2's 4xx, 5xx and error semantics."""
    record_connects(monkeypatch, [http_response(404), http_response(503)])
    with new_http_client(level=PUBLIC) as client:
        statuses = [
            client.get("http://example.com/").status_code,
            client.get("http://example.org/").status_code,
        ]
    attempts: list[str] = []

    def refuse(self: Any, host: str, port: int, *args: Any, **kwargs: Any) -> Any:
        attempts.append(host)
        raise httpcore2.ConnectError("Connection refused")

    monkeypatch.setattr(httpcore2.SyncBackend, "connect_tcp", refuse)
    with new_http_client(level=PUBLIC) as client, pytest.raises(httpx2.ConnectError):
        client.get("http://example.net/")

    assert (statuses, attempts) == ([404, 503], [PUBLIC_ADDRESS])


def test_a_refusal_is_attempted_once_under_the_retry_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSRFBlockedError is not an httpx2 TransportError, so tenacity never retries it."""
    resolver = scripted_resolver(monkeypatch, {"example.com": [["10.0.0.1"]]})
    recorder = record_connects(monkeypatch, [])

    with new_http_client(level=PUBLIC, retries=5) as client, pytest.raises(SSRFBlockedError):
        client.get("https://example.com/")

    assert (resolver.lookups["example.com"], recorder.dialled) == (1, [])


def test_a_redirect_to_a_name_answering_metadata_is_refused_at_hop_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second hop's name is resolved at its own connect; nothing is left pooled for it."""
    scripted_resolver(
        monkeypatch,
        {"example.com": [[PUBLIC_ADDRESS]], "example.org": [["169.254.169.254"]]},
    )
    recorder = record_connects(
        monkeypatch, [http_response(302, headers={"Location": "https://example.org/"})]
    )
    metadata_origin = httpcore2.Origin(b"https", b"example.org", 443)

    with new_http_client(level=PRIVATE, follow_redirects=True) as client:
        with pytest.raises(SSRFBlockedError):
            client.get("https://example.com/")
        pooled = client._transport._pool.connections

    assert (
        recorder.dialled,
        any(connection.can_handle_request(metadata_origin) for connection in pooled),
    ) == ([(PUBLIC_ADDRESS, 443)], False)


# =============================================================================
# Async
# =============================================================================


async def test_the_async_lookup_runs_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """A resolver that blocks for 0.5 s leaves a concurrent task running throughout."""

    def slow_lookup(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        time.sleep(0.5)
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_ADDRESS, port))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", slow_lookup)
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.05)
            ticks += 1

    ticker = asyncio.create_task(tick())
    addresses = await avet_addresses("example.com", 443, PUBLIC, timeout=5.0)
    ticker.cancel()

    assert (addresses, ticks >= 3) == ([PUBLIC_ADDRESS], True)


async def test_a_slow_async_lookup_times_out_as_a_connect_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The connect timeout bounds the lookup, as it bounded anyio's own resolve-and-connect."""

    def slow_lookup(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        time.sleep(0.3)
        return []

    monkeypatch.setattr(socket, "getaddrinfo", slow_lookup)

    with pytest.raises(httpcore2.ConnectTimeout):
        await avet_addresses("example.com", 443, PUBLIC, timeout=0.05)


async def test_the_async_client_dials_only_vetted_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The async backend admits the public answer and refuses the private one, with no dial."""
    scripted_resolver(
        monkeypatch, {"example.com": [[PUBLIC_ADDRESS]], "example.org": [["10.0.0.1"]]}
    )
    recorder = record_connects(monkeypatch, [http_response(200, "ok")])

    async with new_async_http_client(level=PUBLIC) as client:
        status = (await client.get("https://example.com/")).status_code
        with pytest.raises(SSRFBlockedError):
            await client.get("https://example.org/")

    assert (status, recorder.dialled, recorder.tls[0][0]) == (
        200,
        [(PUBLIC_ADDRESS, 443)],
        "example.com",
    )


@pytest.mark.unreachable("example.org")
async def test_the_async_backend_fails_closed_and_tries_each_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed async lookup is a ConnectError; refused addresses move the dial on, then raise."""
    addresses = ["93.184.215.14", "93.184.215.15"]
    scripted_resolver(monkeypatch, {"example.com": [addresses]})
    dialled: list[str] = []

    class Refusing(httpcore2.AsyncNetworkBackend):
        """Refuses every address."""

        async def connect_tcp(
            self, host: str, port: int, *args: Any, **kwargs: Any
        ) -> httpcore2.AsyncNetworkStream:
            dialled.append(host)
            raise httpcore2.ConnectError(f"refused by {host}")

    with pytest.raises(httpcore2.ConnectError, match=r"refused by 93\.184\.215\.15"):
        await AsyncVettingBackend(PUBLIC, inner=Refusing()).connect_tcp("example.com", 443)
    with pytest.raises(httpcore2.ConnectError):
        await AsyncVettingBackend(PUBLIC).connect_tcp("example.org", 443)

    assert dialled == addresses


async def test_async_unix_sockets_and_sleep_are_delegated() -> None:
    """Only TCP connects are vetted by the async backend too."""
    inner = httpcore2.AsyncMockBackend([b"ok"])
    backend = AsyncVettingBackend(PRIVATE, inner=inner)

    stream = await backend.connect_unix_socket("/run/example.sock")
    await backend.sleep(0)

    assert await stream.read(2) == b"ok"


def test_a_lookup_with_no_answer_is_a_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty answer is no address to dial, never an empty list that dials nothing silently."""
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [])

    with pytest.raises(httpcore2.ConnectError, match="No address"):
        vet_addresses("example.com", 443, PUBLIC)


async def test_the_broker_async_hook_makes_no_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hook checks the policy and the scheme; the address is the connect's to check."""
    lookups: list[Any] = []

    def recording(*args: Any, **kwargs: Any) -> list[Any]:
        lookups.append(args)
        return []

    monkeypatch.setattr(socket, "getaddrinfo", recording)
    await HttpClientBroker()._async_validate_request(httpx2.Request("GET", "https://example.com/"))

    assert lookups == []


# =============================================================================
# Isolation and the configured level
# =============================================================================


def test_a_private_level_connection_is_never_reused_by_a_public_level_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The broker keeps a client, so a pool, per level, and the shared pool keys carry the level."""
    scripted_resolver(monkeypatch, {"example.com": [["10.0.0.1"]]})
    recorder = record_connects(monkeypatch, [http_response(200, "private")])

    with HttpClientBroker() as broker:
        private_status = broker.request("GET", "http://example.com/", level=PRIVATE).status_code
        with pytest.raises(SSRFBlockedError):
            broker.request("GET", "http://example.com/", level=PUBLIC)

    assert (
        private_status,
        recorder.dialled,
        get_shared_client("profile", PUBLIC) is get_shared_client("profile", PRIVATE),
        get_shared_async_client("profile", PUBLIC) is get_shared_async_client("profile", PRIVATE),
    ) == (200, [("10.0.0.1", 80)], False, False)


def test_the_configured_level_is_read_from_the_settings_when_a_client_is_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK reaches the level through `ai.allow_private_network`.

    It is read each time a client is built, so a change after import takes effect.
    """
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
    without_flag = configured_level()
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    with_flag = configured_level()

    assert (
        without_flag,
        with_flag,
        configured_level(AIConfig(allow_private_network=False)),
        configured_level(AIConfig(allow_private_network=True)),
    ) == (LOOPBACK, PRIVATE, LOOPBACK, PRIVATE)


def test_an_ai_client_raises_when_its_client_cannot_be_built(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Fail closed: an error building the client is raised, with no fallback client in its place.

    httpx2 loads the CA bundle `SSL_CERT_FILE` names when it builds the TLS context, so a missing
    bundle fails the build for real.
    """
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "missing-ca-bundle.pem"))
    client = LLMClient(AIConfig(provider="openai", api_key="sk-test"))

    with pytest.raises(FileNotFoundError):
        client._create_http_client()
    with pytest.raises(FileNotFoundError):
        client._shared_client()


# =============================================================================
# The level each caller's client gets
# =============================================================================


def _call_ignoring_errors(call: Callable[[], Any]) -> None:
    """Run a caller up to its connect; whatever it makes of the stopped connect is not the point."""
    try:
        call()
    except Exception:
        return


def _k8s_proxy_call() -> None:
    target = ProxyTarget(
        url="https://example.com:6443/api/v1/namespaces/monitoring/services/prometheus:9090/proxy/x",
        headers={},
        ssl_context=ssl.create_default_context(),
    )
    with patch.object(service_http, "resolve_proxy_target", return_value=target):
        service_http.get_json("k8s://monitoring/prometheus:9090", "x")


def _ai_shared_call(flag: bool) -> Callable[[], Any]:
    config = AIConfig(
        provider="openai",
        api_key="sk-test",
        api_base_url="https://example.com/v1",
        max_retries=0,
        allow_private_network=flag,
    )
    return lambda: LLMClient(config)._shared_client().get("https://example.com/v1/models")


def _ai_config(flag: bool, **fields: Any) -> AIConfig:
    """An AI configuration with one attempt per request, so a stopped connect is not retried."""
    return AIConfig(allow_private_network=flag, max_retries=1, **fields)


def _ollama_config(flag: bool, **fields: Any) -> AIConfig:
    return _ai_config(flag, provider="ollama", ollama_urls=["http://example.com:11434"], **fields)


def _gateway_config(flag: bool, **fields: Any) -> AIConfig:
    return _ai_config(flag, provider="gateway", gateway_url="https://example.com/v1", **fields)


_GATEWAY_SERVICE = {
    "spec": {"type": "NodePort", "ports": [{"name": "http", "port": 4000, "nodePort": 30400}]}
}


def _gateway_connect_call() -> None:
    """`devops ai gateway connect`, with kubectl answering a gateway NodePort on example.com."""
    kubectl = ProcessFake()
    kubectl.answer(
        lambda call: "service" in call.argv, ProcessAnswer(stdout=json.dumps(_GATEWAY_SERVICE))
    )
    kubectl.answer(
        lambda call: "config" in call.argv, ProcessAnswer(stdout="https://example.com:6443")
    )
    set_process_runner(kubectl)
    try:
        ai_gateway.connect_cmd(timeout=1.0)
    finally:
        reset_process_runner()


def _pool_load_call() -> None:
    """`devops ai gateway load`, which gives `prometheus_query` its level."""
    with patch.dict(os.environ, {"DEVOPS_CLI_PROMETHEUS_URL": "http://example.com:9090"}):
        ai_gateway.load_cmd(window="30m", output_format="json")


def _ollama_model_call(flag: bool) -> Callable[[], Any]:
    """One request of the pydantic-ai Ollama model that the bridge resolves."""
    settings = Settings(ai=_ollama_config(flag))

    def call() -> None:
        model = resolve_pydantic_ai_model("ollama:qwen3-coder:30b", settings=settings)
        asyncio.run(model.client.with_options(max_retries=0).models.list())

    return call


def _provider_call(flag: bool) -> Callable[[], Any]:
    """One request of a pydantic-ai provider on a configured base URL."""

    def call() -> None:
        provider = create_pydantic_ai_provider(
            "openai",
            base_url="https://example.com/v1",
            api_key="sk-test",
            allow_private_network=flag,
        )
        asyncio.run(provider.client.with_options(max_retries=0).models.list())

    return call


def _benchmark_chat_call(flag: bool) -> Callable[[], Any]:
    """A request of the AI client that the chat benchmark builds for a `--servers` URL."""
    settings = Settings(ai=_ollama_config(flag).model_copy(update={"max_retries": 0}))

    def call() -> None:
        runner = BenchmarkRunner(models=["qwen3-coder:30b"], tasks=[], settings=settings)
        client = runner._client_for_model("qwen3-coder:30b", "http://example.com:11434")
        client._shared_client().get("http://example.com:11434/api/tags")

    return call


_UNKNOWN_EMBEDDING_MODEL = "probe-embedding"
"""A model with no known dimension: a failed probe caches no dimension, so each run probes again."""


_PROBING_TASKS = {"embedding": {"model": _UNKNOWN_EMBEDDING_MODEL}}


def _dimension_probe_call(config: AIConfig, **engine_options: Any) -> Callable[[], Any]:
    """The dimension of a new engine for a model with no known dimension: the engine probes it."""
    return lambda: EmbeddingsEngine(config, valkey_client=None, **engine_options).dimension


def _benchmark_embedding_call(flag: bool) -> Callable[[], Any]:
    """The run of one model of the embedding benchmark on a server."""
    settings = Settings(ai=_ollama_config(flag))

    def call() -> None:
        runner = EmbeddingBenchmarkRunner(
            models=[_UNKNOWN_EMBEDDING_MODEL], settings=settings, is_dry_run=False
        )
        runner.evaluate_model(
            _UNKNOWN_EMBEDDING_MODEL, [], ["probe"], server_url="http://example.com:11434"
        )

    return call


def _ai_service_calls(flag: bool, tmp_path: Path) -> dict[str, Callable[[], Any]]:
    """Each AI service caller #2422 moves, invoked against example.com or its fixed API host."""
    return {
        "gateway model info": lambda: fetch_model_info("https://example.com/v1", flag),
        "gateway probe": lambda: GatewayRouter(
            _ai_config(flag, gateway_url="https://example.com/v1"),
            state_file=tmp_path / "gateway.json",
        ).probe_gateway(),
        "backend probe": lambda: GatewayRouter(
            _ai_config(flag), state_file=tmp_path / "gateway.json"
        ).probe_backend("ollama", backend_url="http://example.com:11434"),
        "gateway connect probe": _gateway_connect_call,
        "pool load query": _pool_load_call,
        "embeddings ollama": lambda: EmbeddingsEngine(
            _ollama_config(flag), valkey_client=None
        ).embed_texts(["probe"]),
        "embeddings openai": lambda: EmbeddingsEngine(
            _gateway_config(flag), api_key="sk-test", valkey_client=None
        ).embed_texts(["probe"]),
        "embedding probe ollama": _dimension_probe_call(_ollama_config(flag, tasks=_PROBING_TASKS)),
        "embedding probe openai": _dimension_probe_call(
            _gateway_config(flag, tasks=_PROBING_TASKS), api_key="sk-test"
        ),
        "pricing source": lambda: PricingRegistry(data_dir=tmp_path).update_from_remote(
            source_url="https://example.com/prices.json", timeout=1.0
        ),
        "pricing registry": lambda: PricingRegistry(data_dir=tmp_path).update_from_remote(
            timeout=1.0
        ),
        "docs crawler": lambda: DocsIngester().ingest_remote_docs(
            "https://example.com/docs", output_dir=tmp_path / "docs"
        ),
        "ollama model": _ollama_model_call(flag),
        "pydantic-ai provider": _provider_call(flag),
        "benchmark chat": _benchmark_chat_call(flag),
        "benchmark embedding": _benchmark_embedding_call(flag),
    }


_GRAFANA_URL = "http://example.com:3000"
_PROMETHEUS_URL = "http://example.com:9090"
_ARGOCD_URL = "http://example.com:8080"
_LOKI_URL = "http://example.com:3100"


def _with_env(env: dict[str, str], call: Callable[[], Any]) -> Callable[[], Any]:
    """`call`, run with the settings and the secrets of `env` in the environment."""

    def run() -> Any:
        with patch.dict(os.environ, env):
            return call()

    return run


def _grafana_env(**secret: str) -> dict[str, str]:
    """`grafana.url` and one Grafana secret, as `DEVOPS_CLI_GRAFANA_<NAME>` variables."""
    named = {f"DEVOPS_CLI_GRAFANA_{name.upper()}": value for name, value in secret.items()}
    return {"DEVOPS_CLI_GRAFANA_URL": _GRAFANA_URL, **named}


def _argocd_env(**secret: str) -> dict[str, str]:
    """`argocd.url` and one Argo CD secret, as `DEVOPS_CLI_ARGOCD_<NAME>` variables."""
    named = {f"DEVOPS_CLI_ARGOCD_{name.upper()}": value for name, value in secret.items()}
    return {"DEVOPS_CLI_ARGOCD_URL": _ARGOCD_URL, **named}


def _k8s_service_calls() -> dict[str, Callable[[], Any]]:
    """Each Grafana, Prometheus, Argo CD and Loki caller #2424 moves, invoked against example.com.

    The token check runs in the credential sync, whose read of the Argo CD admin password gets
    the empty answer of `process_fake`.
    """
    prometheus_env = {"DEVOPS_CLI_PROMETHEUS_URL": _PROMETHEUS_URL}
    return {
        "grafana command": _with_env(_grafana_env(token="glsa-test"), grafana.datasources),
        "prometheus command": _with_env(prometheus_env, lambda: prometheus.query("up")),
        "argo cd command": _with_env(
            _argocd_env(token="argocd-test"), lambda: argo.cd_apps_sync("web")
        ),
        "argo cd fleet": _with_env(
            _argocd_env(token="argocd-test"), lambda: sync_single_target("web", "edge")
        ),
        "argo cd gitops": _with_env(
            _argocd_env(token="argocd-test"), lambda: trigger_argocd_sync("web")
        ),
        "rollout metric gate": _with_env(
            prometheus_env, lambda: evaluate_rollout_gate("web", auto_abort=False, dry_run=True)
        ),
        "argo cd token mint": _with_env(
            _argocd_env(password="admin-pw"), lambda: get_or_mint_argocd_token(load_settings())
        ),
        "grafana token mint": _with_env(
            _grafana_env(password="admin-pw"), lambda: get_or_mint_grafana_auth(load_settings())
        ),
        "stack token check": _with_env(
            {"DEVOPS_CLI_GRAFANA_TOKEN": "glsa-test"},
            lambda: sync_k8s_credentials(stack="infra", grafana_url=_GRAFANA_URL),
        ),
        "loki": lambda: execute_loki_query(parse_logql_query('{app="web"}'), loki_url=_LOKI_URL),
    }


def _caller_calls(flag: bool, tmp_path: Path) -> dict[str, Callable[[], Any]]:
    """Each caller that a change moved to the factory, against example.com or its fixed API host."""
    return {
        "tool download": lambda: _download("https://example.com/tool.tar.gz"),
        "vault": lambda: VaultSecretBroker("http://example.com:8200", "token").get_status(),
        "vault lease": lambda: _post("http://example.com:8200", "sys/leases/renew", {}, {}),
        "tempo": lambda: query_tempo_trace(_TRACE_ID, tempo_url="http://example.com:3200"),
        "probe http": lambda: probe_http("http://example.com/healthz"),
        "probe tcp": lambda: probe_tcp("example.com", 80),
        "metrics scrape": lambda: scrape_prometheus_metrics("http://example.com:9100/metrics"),
        "k8s direct": lambda: service_http.get_json("http://example.com:9090", "api/v1/query"),
        "k8s proxy": _k8s_proxy_call,
        "ai shared client": _ai_shared_call(flag),
        "firecrawl": lambda: firecrawl_search("devops", api_key="fc-test"),
        "statuspage": lambda: fetch_statuspage_summary("https://example.com/api/v2/summary.json"),
        **_ai_service_calls(flag, tmp_path),
        **_k8s_service_calls(),
        **_public_api_calls(),
    }


def _ai_service_levels(flag: bool) -> dict[str, EgressLevel]:
    """The level table of #2422. Configured is loopback, or private with the flag."""
    configured = PRIVATE if flag else LOOPBACK
    return {
        "gateway model info": configured,
        "gateway probe": configured,
        "backend probe": configured,
        "gateway connect probe": PRIVATE,
        "pool load query": configured,
        "embeddings ollama": configured,
        "embeddings openai": configured,
        "embedding probe ollama": configured,
        "embedding probe openai": configured,
        "pricing source": configured,
        "pricing registry": PUBLIC,
        "docs crawler": PUBLIC,
        "ollama model": configured,
        "pydantic-ai provider": configured,
        "benchmark chat": configured,
        "benchmark embedding": configured,
    }


def _k8s_service_levels(flag: bool) -> dict[str, EgressLevel]:
    """The level table of #2424. Configured is loopback, or private with the flag."""
    configured = PRIVATE if flag else LOOPBACK
    return {
        "grafana command": configured,
        "prometheus command": configured,
        "argo cd command": configured,
        "argo cd fleet": configured,
        "argo cd gitops": configured,
        "rollout metric gate": configured,
        "argo cd token mint": configured,
        "grafana token mint": configured,
        "stack token check": configured,
        "loki": PRIVATE,
    }


def _expected_levels(flag: bool) -> dict[str, EgressLevel]:
    """The level table of each change that moved callers to the factory, for those callers."""
    return {
        "tool download": PUBLIC,
        "vault": PRIVATE,
        "vault lease": PRIVATE,
        "tempo": LOOPBACK,
        "probe http": PRIVATE,
        "probe tcp": PRIVATE,
        "metrics scrape": LOOPBACK,
        "k8s direct": PRIVATE,
        "k8s proxy": PRIVATE,
        "ai shared client": PRIVATE if flag else LOOPBACK,
        "firecrawl": PUBLIC,
        "statuspage": PUBLIC,
        **_ai_service_levels(flag),
        **_k8s_service_levels(flag),
        **_public_api_levels(),
    }


_PUBLIC_API_HOSTS = ("api.osv.dev", "internetdb.shodan.io", "api.cloudflare.com")


def _public_api_calls() -> dict[str, Callable[[], Any]]:
    """Each client of a fixed public API that #2430 moves, invoked against its API host.

    InternetDB and Radar send a request only for a target they ask about
    (`classify_network_target`): a public address, and a domain that is neither an example nor
    local.
    """
    return {
        "osv": lambda: OSVClient().query_package("requests", version="2.0.0", ecosystem="PyPI"),
        "shodan internetdb": lambda: ShodanInternetDBClient().check_ip(PUBLIC_ADDRESS),
        "cloudflare radar": lambda: CloudflareRadarClient(
            token="cf-test", valkey_client=None
        ).check_domain("service-domain.org"),
        "cloudflare api": lambda: CloudflareClient(token="cf-test").verify_token(),
    }


def _public_api_levels() -> dict[str, EgressLevel]:
    """The level table of #2430: public, whatever `ai.allow_private_network` says."""
    return dict.fromkeys(_public_api_calls(), PUBLIC)


_CALLER_HOSTS = (
    "example.com",
    "api.firecrawl.dev",
    "raw.githubusercontent.com",
    *_PUBLIC_API_HOSTS,
)

_LEVEL_BY_DIALS = {(False, False): PUBLIC, (True, False): LOOPBACK, (True, True): PRIVATE}
"""A level, by whether a loopback answer and an RFC 1918 answer reached the dial."""


@pytest.mark.usefixtures("keyring_store", "process_fake")
@pytest.mark.parametrize("flag", [False, True], ids=["without-flag", "with-flag"])
@pytest.mark.parametrize("caller", list(_expected_levels(False)))
def test_each_caller_dials_at_its_level(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caller: str, flag: bool
) -> None:
    """Every caller dials what the level the table gives it admits, with and without the flag.

    The caller runs twice, its host answering 127.0.0.1 and then 10.0.0.1: a public-level client
    dials neither, a loopback-level one only the first, a private-level one both. Only the URLs
    that come from configuration follow the flag; the tool downloads, the documentation crawler,
    the default pricing registry and the clients of fixed public APIs (OSV, Shodan InternetDB,
    Cloudflare Radar and the Cloudflare API) do not widen with it. A caller host name never
    reaches the dial: a client that hands the socket the name lets it resolve the name again
    after the check (#2422, #2424). Only dials to the answer or a caller host count: the test
    configuration's telemetry exporter may dial its collector from a background thread meanwhile.
    """
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", str(flag).lower())
    call = _caller_calls(flag, tmp_path)[caller]
    dials: list[bool] = []
    named: list[str] = []
    for address in ("127.0.0.1", "10.0.0.1"):
        scripted_resolver(monkeypatch, {host: [[address]] for host in _CALLER_HOSTS})
        recorder = record_connects(monkeypatch, [])
        _call_ignoring_errors(call)
        dials.append(address in [host for host, _ in recorder.dialled])
        named += [host for host, _ in recorder.dialled if host in _CALLER_HOSTS]
        close_shared_clients()

    assert (_LEVEL_BY_DIALS.get((dials[0], dials[1])), named) == (
        _expected_levels(flag)[caller],
        [],
    )


_METADATA_ADDRESS = "169.254.169.254"


@pytest.mark.usefixtures("keyring_store")
@pytest.mark.parametrize("caller", list(_ai_service_levels(False)))
def test_each_ai_service_caller_dials_the_address_it_checked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caller: str
) -> None:
    """Old vs new (#2422): a host that answers cloud metadata after two lookups is never reached.

    Before, the caller checked the host name before the request, at most twice, and httpx2
    resolved it again at the socket, so a rebinding DNS server reached an address no check saw.
    Now the connect resolves the name once and dials the address it checked; a later connect
    resolves again and refuses the metadata answer. Neither the name nor the metadata address
    reaches the socket. The engines that the embedding benchmark builds read the Valkey password
    from the keyring, which `keyring_store` fakes.
    """
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
    scripted_resolver(
        monkeypatch, {host: rebinding(2, _METADATA_ADDRESS) for host in _CALLER_HOSTS}
    )
    recorder = record_connects(monkeypatch, [])

    _call_ignoring_errors(_ai_service_calls(False, tmp_path)[caller])

    unvetted = {*_CALLER_HOSTS, _METADATA_ADDRESS}
    assert [host for host, _ in recorder.dialled if host in unvetted] == []


@pytest.mark.usefixtures("keyring_store", "process_fake")
@pytest.mark.parametrize("caller", list(_k8s_service_calls()))
def test_each_k8s_service_caller_dials_the_address_it_checked(
    monkeypatch: pytest.MonkeyPatch, caller: str
) -> None:
    """Old vs new (#2424): a host that answers cloud metadata after its first lookup is not reached.

    Before, the caller checked the host name before the request, and httpx2 resolved it again at
    the socket, so a rebinding DNS server reached an address that no check saw. Now the connect
    resolves the name once and dials the address that it checked; a later connect resolves again
    and refuses the metadata answer. Neither the name nor the metadata address reaches the socket.
    """
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
    scripted_resolver(monkeypatch, {"example.com": rebinding(1, _METADATA_ADDRESS)})
    recorder = record_connects(monkeypatch, [])

    _call_ignoring_errors(_k8s_service_calls()[caller])

    unvetted = {"example.com", _METADATA_ADDRESS}
    assert [host for host, _ in recorder.dialled if host in unvetted] == []


@pytest.mark.parametrize(
    ("call", "port"),
    [
        (_k8s_service_calls()["loki"], 3100),
        (lambda: service_http.get_json("http://example.com:9090", "api/v1/query"), 9090),
    ],
    ids=["loki", "k8s direct"],
)
def test_loki_and_a_direct_service_url_look_up_their_host_once(
    monkeypatch: pytest.MonkeyPatch, call: Callable[[], Any], port: int
) -> None:
    """Old vs new (#2424): one request makes one lookup, at the connect, and dials its answer.

    Before, `validate_url_egress` resolved the public name in a check before the request, and the
    connect resolved it a second time.
    """
    resolver = scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
    recorder = record_connects(monkeypatch, [])

    _call_ignoring_errors(call)

    assert (resolver.lookups["example.com"], recorder.dialled) == (1, [(PUBLIC_ADDRESS, port)])


def test_a_loki_url_that_is_not_http_fails_with_no_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """httpx2 refuses the scheme before the connect, so no check of its own runs before it."""
    resolver = scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})

    with pytest.raises(httpx2.UnsupportedProtocol):
        execute_loki_query(parse_logql_query('{app="web"}'), loki_url="ftp://example.com:3100")

    assert resolver.lookups["example.com"] == 0


def test_the_memory_profiler_exercises_its_pool_without_a_lookup_or_a_dial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The profiler's requests go to an in-memory ASGI app, so its host is never resolved or dialled.

    Only its target port counts: the test configuration's telemetry exporter may dial its collector
    from a background thread meanwhile.
    """
    resolver = scripted_resolver(monkeypatch, {"localhost": [["127.0.0.1"]]})
    recorder = record_connects(monkeypatch, [])

    asyncio.run(_exercise_http_pool(2))

    assert (resolver.lookups, [port for _, port in recorder.dialled if port == 8080]) == (
        {"localhost": 0},
        [],
    )

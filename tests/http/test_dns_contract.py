"""Contract suite for the DNS resolver seam (`devops_cli.http.egress`) and `FakeResolver` (#3752).

Each contract case runs against the fake (`dns` fixture) and against the real resolver. The real
side resolves only `localhost`, IP literals and a name the floor refuses with the error of an
unknown name, so no case makes a DNS query. The cases after the contract check what the egress
checks do with the resolver they are given.
"""

from __future__ import annotations

import ipaddress
import socket
import threading
from typing import Any

import httpcore2
import pytest

from devops_cli.exceptions import SSRFBlockedError
from devops_cli.http import egress
from devops_cli.http.egress import EgressLevel, Resolver, SystemResolver
from tests.support.fakes.dns import PUBLIC_ADDRESS, FakeResolver, installed_dns

UNKNOWN_NAME = "unknown.example.com"
STALLED_NAME = "slow.example.com"
MODES = ["fake", "real"]


def _resolver(request: pytest.FixtureRequest, mode: str) -> Resolver:
    if mode == "fake":
        fake: FakeResolver = request.getfixturevalue("dns")
        fake.stall(STALLED_NAME)
        return fake
    return SystemResolver()


def _addresses(answers: Any) -> list[str]:
    return sorted({str(answer[4][0]) for answer in answers})


@pytest.mark.parametrize("mode", MODES)
def test_a_loopback_name_answers_loopback_addresses_with_the_port(
    request: pytest.FixtureRequest, mode: str
) -> None:
    """`localhost` resolves to loopback addresses only, each answer carrying the port."""
    answers = _resolver(request, mode).lookup("localhost", 8080)

    assert (
        bool(answers),
        all(ipaddress.ip_address(address).is_loopback for address in _addresses(answers)),
        {answer[4][1] for answer in answers},
    ) == (True, True, {8080})


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("literal", ["192.0.2.7", "2001:db8::1"])
def test_an_ip_literal_answers_itself(
    request: pytest.FixtureRequest, mode: str, literal: str
) -> None:
    """A name that is an IP literal needs no lookup and answers that address."""
    answers = _resolver(request, mode).lookup(literal, 443)

    assert (_addresses(answers), {answer[4][1] for answer in answers}) == ([literal], {443})


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.unreachable(UNKNOWN_NAME)
def test_an_unknown_name_fails_with_a_gaierror(request: pytest.FixtureRequest, mode: str) -> None:
    """A name that no one answers raises the `socket.gaierror` of `socket.getaddrinfo`."""
    resolver = _resolver(request, mode)

    with pytest.raises(socket.gaierror) as raised:
        resolver.lookup(UNKNOWN_NAME, 443)

    assert raised.value.errno == socket.EAI_NONAME


@pytest.mark.parametrize("mode", MODES)
async def test_the_async_lookup_answers_as_the_sync_lookup_does(
    request: pytest.FixtureRequest, mode: str
) -> None:
    """The async lookup of a loopback name and of an IP literal gives the sync lookup's
    addresses."""
    resolver = _resolver(request, mode)

    assert [
        _addresses(await resolver.alookup(host, 443, 5.0)) for host in ("localhost", "192.0.2.7")
    ] == [_addresses(resolver.lookup(host, 443)) for host in ("localhost", "192.0.2.7")]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.unreachable(UNKNOWN_NAME)
async def test_an_async_lookup_of_an_unknown_name_fails_with_a_gaierror(
    request: pytest.FixtureRequest, mode: str
) -> None:
    """The async lookup raises the same `socket.gaierror` as the sync lookup."""
    resolver = _resolver(request, mode)

    with pytest.raises(socket.gaierror) as raised:
        await resolver.alookup(UNKNOWN_NAME, 443, 5.0)

    assert raised.value.errno == socket.EAI_NONAME


@pytest.mark.parametrize("mode", MODES)
async def test_an_async_lookup_that_outlasts_its_timeout_raises_timeout_error(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """A lookup that cannot finish within the timeout raises `TimeoutError`. The fake stalls the
    name. The real side blocks `socket.getaddrinfo`, the stdlib edge below `anyio`, until the
    test ends."""
    resolver = _resolver(request, mode)
    release = threading.Event()
    if mode == "real":
        monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: release.wait(30) and [])
    try:
        with pytest.raises(TimeoutError) as raised:
            await resolver.alookup(STALLED_NAME, 443, 0.05)
    finally:
        release.set()

    assert type(raised.value) is TimeoutError


def test_the_fake_answers_every_name_with_one_public_address_on_demand(dns: FakeResolver) -> None:
    """`answer_every_name` is the `public_dns` of the fake: any name gets the public address."""
    address = dns.answer_every_name()

    assert (
        address,
        _addresses(dns.lookup("anything.example.com", 443)),
        _addresses(dns.lookup("other.example.org", 80)),
    ) == (PUBLIC_ADDRESS, [PUBLIC_ADDRESS], [PUBLIC_ADDRESS])


def test_the_fake_scripts_the_answers_of_a_name_per_lookup_and_repeats_the_last(
    dns: FakeResolver,
) -> None:
    """A rebinding name answers a public address first and a private one after."""
    dns.script("rebind.example.com", [PUBLIC_ADDRESS], ["10.0.0.1"])

    seen = [_addresses(dns.lookup("rebind.example.com", 443)) for _ in range(3)]

    assert (seen, [lookup.host for lookup in dns.lookups]) == (
        [[PUBLIC_ADDRESS], ["10.0.0.1"], ["10.0.0.1"]],
        ["rebind.example.com"] * 3,
    )


def test_the_fake_records_each_lookup_with_its_port_and_timeout(dns: FakeResolver) -> None:
    """The fake keeps the host, port, kind and timeout of every lookup, sync or async."""
    dns.map("api.example.com", PUBLIC_ADDRESS)

    dns.lookup("api.example.com", 443)

    assert [(lookup.host, lookup.port, lookup.timeout) for lookup in dns.lookups] == [
        ("api.example.com", 443, None)
    ]


def test_vet_addresses_resolves_through_the_installed_resolver(dns: FakeResolver) -> None:
    """The egress check asks the installed resolver, not `socket.getaddrinfo`."""
    dns.map("api.example.com", PUBLIC_ADDRESS)

    assert egress.vet_addresses("api.example.com", 443, EgressLevel.PUBLIC) == [PUBLIC_ADDRESS]


def test_vet_addresses_refuses_a_name_that_rebinds_to_a_private_address(dns: FakeResolver) -> None:
    """The second lookup of a rebinding name answers a private address, which a client at the
    public level refuses."""
    dns.script("rebind.example.com", [PUBLIC_ADDRESS], ["10.0.0.1"])
    first = egress.vet_addresses("rebind.example.com", 443, EgressLevel.PUBLIC)

    with pytest.raises(SSRFBlockedError) as raised:
        egress.vet_addresses("rebind.example.com", 443, EgressLevel.PUBLIC)

    assert (first, raised.value.details["address"]) == ([PUBLIC_ADDRESS], "10.0.0.1")


def test_vet_addresses_reports_an_unknown_name_as_a_connect_error(dns: FakeResolver) -> None:
    """A name that fails to resolve raises `httpcore2.ConnectError`, as it did with the stdlib."""
    with pytest.raises(httpcore2.ConnectError) as raised:
        egress.vet_addresses(UNKNOWN_NAME, 443, EgressLevel.PUBLIC)

    assert (type(raised.value), [lookup.host for lookup in dns.lookups]) == (
        httpcore2.ConnectError,
        [UNKNOWN_NAME],
    )


async def test_avet_addresses_resolves_through_the_installed_resolver_within_the_timeout(
    dns: FakeResolver,
) -> None:
    """The async check passes its timeout to the installed resolver."""
    dns.map("api.example.com", PUBLIC_ADDRESS)

    addresses = await egress.avet_addresses("api.example.com", 443, EgressLevel.PUBLIC, 2.5)

    assert (addresses, [(lookup.host, lookup.timeout) for lookup in dns.lookups]) == (
        [PUBLIC_ADDRESS],
        [("api.example.com", 2.5)],
    )


async def test_avet_addresses_reports_a_stalled_lookup_as_a_connect_timeout(
    dns: FakeResolver,
) -> None:
    """A lookup that outlasts the timeout raises `httpcore2.ConnectTimeout`."""
    dns.stall(STALLED_NAME)

    with pytest.raises(httpcore2.ConnectTimeout) as raised:
        await egress.avet_addresses(STALLED_NAME, 443, EgressLevel.PUBLIC, 1.0)

    assert type(raised.value) is httpcore2.ConnectTimeout


def test_the_hook_returns_the_resolver_it_replaces_and_a_reset_restores_the_real_one() -> None:
    """`set_resolver` installs a resolver and gives back the previous one; `reset_resolver` puts
    the system resolver back."""
    fake = FakeResolver()
    previous = egress.set_resolver(fake)
    try:
        installed = egress.get_resolver()
    finally:
        egress.reset_resolver()

    assert installed is fake
    assert type(previous) is SystemResolver
    assert type(egress.get_resolver()) is SystemResolver


@pytest.mark.unreachable(UNKNOWN_NAME)
def test_the_dns_fixture_removes_the_fake_and_restores_the_stdlib_lookup_at_teardown() -> None:
    """After the fixture's context ends, the real resolver and the stdlib lookup are back."""
    stdlib_before = socket.getaddrinfo
    with installed_dns() as fake:
        fake.map("api.example.com", PUBLIC_ADDRESS)
        during = (egress.get_resolver() is fake, socket.getaddrinfo is stdlib_before)

    assert during == (True, False)
    assert type(egress.get_resolver()) is SystemResolver
    assert socket.getaddrinfo is stdlib_before


@pytest.mark.unreachable(UNKNOWN_NAME)
def test_the_dns_fixture_answers_the_stdlib_lookup_from_the_same_fake(dns: FakeResolver) -> None:
    """Code that calls `socket.getaddrinfo` itself gets the fake's answer for a mapped name, the
    stdlib's for a numeric host, and the `gaierror` of an unknown name."""
    dns.map("api.example.com", PUBLIC_ADDRESS)

    mapped = socket.getaddrinfo("api.example.com", 443, type=socket.SOCK_STREAM)
    numeric = socket.getaddrinfo("192.0.2.7", 443, flags=socket.AI_NUMERICHOST)
    with pytest.raises(socket.gaierror) as raised:
        socket.getaddrinfo(UNKNOWN_NAME, 443)

    assert (
        _addresses(mapped),
        _addresses(numeric),
        raised.value.errno,
        [lookup.host for lookup in dns.lookups],
    ) == ([PUBLIC_ADDRESS], ["192.0.2.7"], socket.EAI_NONAME, ["api.example.com", UNKNOWN_NAME])

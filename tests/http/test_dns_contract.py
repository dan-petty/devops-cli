"""Contract suite for the DNS resolver seam (`devops_cli.http.egress`) and `DnsFake` (#3752).

Each contract case runs against the fake (`dns` fixture) and against `SystemResolver`, the real
lookup. The real side resolves only `localhost` and IP literals, which the hermetic floor lets
through, and a name the floor refuses, which fails the way an unknown name fails. The cases after
the contract hold the fake alone: scripted answers, the record of lookups and the stdlib fallback.
"""

from __future__ import annotations

import ipaddress
import socket
import threading
from typing import Any

import pytest

from devops_cli.http.egress import Resolver, SystemResolver
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake, Lookup

_MODES = ["fake", "real"]


def _resolver(request: pytest.FixtureRequest, mode: str) -> Resolver:
    """The fake behind the `dns` fixture, or the real lookup."""
    if mode == "fake":
        fake: DnsFake = request.getfixturevalue("dns")
        return fake
    return SystemResolver()


@pytest.mark.parametrize("mode", _MODES)
def test_a_loopback_name_resolves_to_loopback_stream_addresses(
    request: pytest.FixtureRequest, mode: str
) -> None:
    """`localhost` answers at least one stream address, each on loopback with the port asked."""
    answers = _resolver(request, mode).resolve("localhost", 8080)

    assert answers
    assert all(
        answer[1] == socket.SOCK_STREAM
        and ipaddress.ip_address(answer[4][0]).is_loopback
        and answer[4][1] == 8080
        for answer in answers
    )


@pytest.mark.parametrize("mode", _MODES)
def test_an_ip_literal_resolves_to_itself(request: pytest.FixtureRequest, mode: str) -> None:
    """An IP literal answers its own address and the port asked, with no name to look up."""
    answers = _resolver(request, mode).resolve("192.0.2.7", 443)

    assert [(answer[0], answer[4]) for answer in answers] == [(socket.AF_INET, ("192.0.2.7", 443))]


@pytest.mark.parametrize("mode", _MODES)
@pytest.mark.unreachable("unknown.example.com")
def test_an_unknown_name_fails_with_a_name_not_known_error(
    request: pytest.FixtureRequest, mode: str
) -> None:
    """A name that no one maps raises `socket.gaierror` with the code `EAI_NONAME`."""
    resolver = _resolver(request, mode)

    with pytest.raises(socket.gaierror) as raised:
        resolver.resolve("unknown.example.com", 443)

    assert raised.value.errno == socket.EAI_NONAME


@pytest.mark.parametrize("mode", _MODES)
async def test_an_async_loopback_name_resolves_to_loopback_addresses(
    request: pytest.FixtureRequest, mode: str
) -> None:
    """The async lookup of `localhost` answers the same family, address and port as the sync one.

    `anyio.getaddrinfo` cuts an IPv6 socket address to its address and port, so the cases compare
    those three and not the whole tuple.
    """
    resolver = _resolver(request, mode)

    answers = await resolver.aresolve("localhost", 8080, timeout=5.0)

    assert [(a[0], *a[4][:2]) for a in answers] == [
        (a[0], *a[4][:2]) for a in resolver.resolve("localhost", 8080)
    ]


@pytest.mark.parametrize("mode", _MODES)
async def test_an_async_ip_literal_resolves_to_itself(
    request: pytest.FixtureRequest, mode: str
) -> None:
    """The async lookup of an IP literal answers its own address."""
    answers = await _resolver(request, mode).aresolve("2001:db8::7", 443, timeout=5.0)

    assert [answer[4][:2] for answer in answers] == [("2001:db8::7", 443)]


@pytest.mark.parametrize("mode", _MODES)
@pytest.mark.unreachable("unknown.example.com")
async def test_an_async_unknown_name_fails_with_a_name_not_known_error(
    request: pytest.FixtureRequest, mode: str
) -> None:
    """The async lookup of an unknown name raises the same `socket.gaierror`."""
    resolver = _resolver(request, mode)

    with pytest.raises(socket.gaierror) as raised:
        await resolver.aresolve("unknown.example.com", 443, timeout=5.0)

    assert raised.value.errno == socket.EAI_NONAME


@pytest.mark.parametrize("mode", _MODES)
async def test_an_async_lookup_that_runs_past_its_timeout_raises_timeout_error(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """A lookup that takes longer than its timeout raises `TimeoutError`. The real side has no slow
    name to ask for, so the stdlib lookup under it blocks until the case ends."""
    release = threading.Event()
    if mode == "fake":
        request.getfixturevalue("dns").stall("localhost")
    else:

        def slow_lookup(*args: Any, **kwargs: Any) -> list[Any]:
            release.wait(timeout=2.0)
            return []

        monkeypatch.setattr(socket, "getaddrinfo", slow_lookup)

    try:
        with pytest.raises(TimeoutError) as raised:
            await _resolver(request, mode).aresolve("localhost", 80, timeout=0.05)
        assert raised.type is TimeoutError
    finally:
        release.set()


def test_a_name_answers_the_addresses_it_is_mapped_to_with_the_port_asked(dns: DnsFake) -> None:
    """A mapped name answers each address in order, IPv6 as a four-field address."""
    dns.add("Service.Example.com.", "192.0.2.1", "2001:db8::1")

    answers = dns.resolve("service.example.com", 8443)

    assert [(answer[0], answer[4]) for answer in answers] == [
        (socket.AF_INET, ("192.0.2.1", 8443)),
        (socket.AF_INET6, ("2001:db8::1", 8443, 0, 0)),
    ]


def test_a_scripted_name_answers_per_lookup_and_the_last_answer_repeats(dns: DnsFake) -> None:
    """A rebinding name answers a public address twice, then a private one for every lookup."""
    dns.script("rebind.example.com", [PUBLIC_ADDRESS], [PUBLIC_ADDRESS], ["10.0.0.1"])

    answered = [dns.resolve("rebind.example.com", 443)[0][4][0] for _ in range(5)]

    assert answered == [PUBLIC_ADDRESS, PUBLIC_ADDRESS, "10.0.0.1", "10.0.0.1", "10.0.0.1"]


def test_every_name_can_answer_one_public_address(dns: DnsFake) -> None:
    """After `answer_every_name`, a name that no one mapped answers the public address."""
    dns.answer_every_name()

    assert dns.resolve("anything.example.com", 80)[0][4] == (PUBLIC_ADDRESS, 80)


def test_a_stalled_name_times_out_in_the_sync_lookup_too(dns: DnsFake) -> None:
    """A sync lookup cannot wait, so a stalled name raises `TimeoutError` at once."""
    dns.stall("slow.example.com")

    with pytest.raises(TimeoutError, match=r"slow\.example\.com"):
        dns.resolve("slow.example.com", 443)


def test_the_fake_records_each_lookup_in_order(dns: DnsFake) -> None:
    """The record holds the lower-case name and the port of every lookup, address literals too."""
    dns.add("a.example.com", "192.0.2.1")
    dns.add("b.example.com", "192.0.2.2")

    dns.resolve("B.example.com", 80)
    dns.resolve("a.example.com", 443)
    dns.resolve("192.0.2.9", 22)

    assert (dns.lookups, dns.lookups_of("a.example.com")) == (
        [Lookup("b.example.com", 80), Lookup("a.example.com", 443), Lookup("192.0.2.9", 22)],
        [Lookup("a.example.com", 443)],
    )


def test_a_name_with_no_address_answers_an_empty_list(dns: DnsFake) -> None:
    """A mapped name with no address is an empty answer, not an unknown name."""
    dns.add("empty.example.com")

    assert dns.resolve("empty.example.com", 443) == []


def test_the_stdlib_lookup_answers_from_the_fake_and_records_only_names(dns: DnsFake) -> None:
    """`socket.getaddrinfo` serves a mapped name from the fake. A numeric-host call reads a
    literal through the stdlib and is not a lookup."""
    dns.add("service.example.com", "192.0.2.5")

    by_name = socket.getaddrinfo("service.example.com", 443, type=socket.SOCK_STREAM)
    literal = socket.getaddrinfo("192.0.2.6", 443, flags=socket.AI_NUMERICHOST)

    assert (
        [answer[4] for answer in by_name],
        literal[0][4],
        dns.lookups,
    ) == ([("192.0.2.5", 443)], ("192.0.2.6", 443), [Lookup("service.example.com", 443)])


@pytest.mark.unreachable("unknown.example.com")
def test_the_stdlib_lookup_of_an_unknown_name_fails_like_the_seam(dns: DnsFake) -> None:
    """A name that the fake does not map raises `gaierror` through `socket.getaddrinfo` too."""
    with pytest.raises(socket.gaierror) as raised:
        socket.getaddrinfo("unknown.example.com", 443)

    assert raised.value.errno == socket.EAI_NONAME

"""The resolver seam under `vet_addresses` and `avet_addresses` (#3752).

The seam's contract is `tests/core/test_dns_contract.py`. These tests hold what the vetting
functions do with the seam's answers and failures, with `DnsFake` behind the `dns` fixture.
"""

from __future__ import annotations

import socket

import httpcore2
import pytest

from devops_cli.exceptions import SSRFBlockedError
from devops_cli.http.egress import (
    EgressLevel,
    Resolver,
    avet_addresses,
    get_resolver,
    install_resolver,
    reset_resolver,
    vet_addresses,
)
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake

PUBLIC = EgressLevel.PUBLIC


def test_the_real_resolver_is_active_until_one_is_installed() -> None:
    """With no resolver installed, the seam hands out `SystemResolver`."""
    assert type(get_resolver()).__name__ == "SystemResolver"


def test_installing_a_resolver_returns_the_previous_one_and_a_reset_restores_the_real_one() -> None:
    """The hook swaps the resolver, hands back what it replaced, and a reset restores the real one."""
    first, second = DnsFake(), DnsFake()

    replaced_real = install_resolver(first)
    replaced_first = install_resolver(second)
    active = get_resolver()
    reset_resolver()

    assert (
        type(replaced_real).__name__,
        replaced_first,
        active,
        type(get_resolver()).__name__,
    ) == ("SystemResolver", first, second, "SystemResolver")


def test_the_fake_is_a_resolver(dns: DnsFake) -> None:
    """The fake has the shape of the Protocol, so the type check holds the two together."""
    resolver: Resolver = dns

    assert resolver is get_resolver()


def test_vet_addresses_resolves_through_the_installed_resolver_and_returns_the_answers(
    dns: DnsFake,
) -> None:
    """A name that only the fake knows resolves, once, for the port that the dial uses."""
    dns.add("service.example.com", PUBLIC_ADDRESS, "93.184.215.15")

    addresses = vet_addresses("service.example.com", 8443, PUBLIC)

    assert (addresses, [(look.host, look.port) for look in dns.lookups]) == (
        [PUBLIC_ADDRESS, "93.184.215.15"],
        [("service.example.com", 8443)],
    )


def test_vet_addresses_refuses_a_name_that_answers_a_private_address(dns: DnsFake) -> None:
    """The classification is unchanged: one private answer refuses the name at the public level."""
    dns.add("internal.example.com", PUBLIC_ADDRESS, "10.0.0.1")

    with pytest.raises(SSRFBlockedError) as raised:
        vet_addresses("internal.example.com", 443, PUBLIC)

    assert raised.value.details["address"] == "10.0.0.1"


def test_vet_addresses_reports_each_answer_of_a_rebinding_name(dns: DnsFake) -> None:
    """A name that answers a public address and then a private one is vetted on each lookup."""
    dns.script("rebind.example.com", [PUBLIC_ADDRESS], ["10.0.0.1"])

    first = vet_addresses("rebind.example.com", 443, PUBLIC)
    with pytest.raises(SSRFBlockedError) as raised:
        vet_addresses("rebind.example.com", 443, PUBLIC)

    assert (first, raised.value.details["address"]) == ([PUBLIC_ADDRESS], "10.0.0.1")


def test_vet_addresses_reports_an_unknown_name_as_a_connect_error(dns: DnsFake) -> None:
    """The resolver's `gaierror` surfaces as `httpcore2.ConnectError`, which httpx2 maps."""
    with pytest.raises(httpcore2.ConnectError) as raised:
        vet_addresses("unknown.example.com", 443, PUBLIC)

    assert type(raised.value.__cause__) is socket.gaierror


async def test_avet_addresses_resolves_through_the_installed_resolver(dns: DnsFake) -> None:
    """The async check asks the same resolver, with the connect timeout."""
    dns.add("service.example.com", PUBLIC_ADDRESS)

    addresses = await avet_addresses("service.example.com", 443, PUBLIC, timeout=5.0)

    assert (addresses, [(look.host, look.port) for look in dns.lookups]) == (
        [PUBLIC_ADDRESS],
        [("service.example.com", 443)],
    )


async def test_avet_addresses_reports_a_stalled_name_as_a_connect_timeout(dns: DnsFake) -> None:
    """A lookup that runs past the connect timeout is `httpcore2.ConnectTimeout`."""
    dns.stall("slow.example.com")

    with pytest.raises(httpcore2.ConnectTimeout, match="timed out"):
        await avet_addresses("slow.example.com", 443, PUBLIC, timeout=0.05)


async def test_avet_addresses_reports_an_unknown_name_as_a_connect_error(dns: DnsFake) -> None:
    """The async resolver's `gaierror` is a `ConnectError` too, never mistaken for a timeout."""
    with pytest.raises(httpcore2.ConnectError) as raised:
        await avet_addresses("unknown.example.com", 443, PUBLIC, timeout=5.0)

    assert type(raised.value.__cause__) is socket.gaierror

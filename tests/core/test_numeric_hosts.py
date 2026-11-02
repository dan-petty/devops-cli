"""Tests for how the address checks read a numeric host (#2152)."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

import pytest

from devops_cli.core.validation import (
    is_cloud_metadata_host,
    is_cloud_metadata_ip,
    is_loopback_host,
    is_loopback_or_private_host,
    is_private_ip,
    parse_numeric_ip,
)


@pytest.mark.parametrize(
    ("host", "address"),
    [
        ("0177.0.0.1", "127.0.0.1"),
        ("127.1", "127.0.0.1"),
        ("127.0.1", "127.0.0.1"),
        ("2130706433", "127.0.0.1"),
        ("0x7f.1", "127.0.0.1"),
        ("0x7f000001", "127.0.0.1"),
        ("017700000001", "127.0.0.1"),
        ("fe80::1%eth0", "fe80::1%eth0"),
    ],
)
def test_a_legacy_numeric_host_gives_its_address(host: str, address: str) -> None:
    """The octal, one-part, two-part, three-part and hex spellings and an IPv6 zone ID give the
    address that a resolver dials (#2152)."""
    assert parse_numeric_ip(host) == ipaddress.ip_address(address)


@pytest.mark.parametrize(
    "host",
    ["08.0.0.1", "1.2.3.4 x", "256.1.1.1", "example.com", "x" * 300, "é" * 70],
)
def test_a_host_that_is_not_numeric_gives_no_address(host: str) -> None:
    """A bad octal part, trailing text, a part out of range, a name and a label that the C
    library cannot encode give no address (#2152)."""
    assert parse_numeric_ip(host) is None


@pytest.mark.parametrize("host", ["0177.0.0.1", "127.0.1"])
def test_an_octal_or_three_part_loopback_host_is_refused(host: str) -> None:
    """The octal and three-part spellings of 127.0.0.1 are loopback and are refused (#2152)."""
    assert (is_loopback_host(host), is_loopback_or_private_host(host)) == (True, True)


def test_a_link_local_host_with_a_zone_id_is_refused() -> None:
    """`fe80::1%eth0` is link-local, so the metadata and private checks refuse it (#2152)."""
    assert (
        is_cloud_metadata_host("fe80::1%eth0"),
        is_loopback_or_private_host("fe80::1%eth0"),
    ) == (True, True)


def test_a_metadata_address_with_a_zone_id_is_a_metadata_address() -> None:
    """The classifier drops the zone ID before it compares, so `fd00:ec2::254%eth0` is the
    metadata address of AWS (#2152)."""
    assert is_cloud_metadata_ip("fd00:ec2::254%eth0") is True


@pytest.mark.parametrize("value", ["not-an-ip", ""])
def test_a_value_that_does_not_parse_is_private(value: str) -> None:
    """`is_private_ip` treats a value that does not parse as private, so the check fails closed
    (#2152)."""
    assert is_private_ip(value) is True


@pytest.mark.parametrize(
    ("host", "address"),
    [
        ("0b11.1", None),
        ("0o17.1", None),
        ("+1.2.3.4", None),
        ("1_0.0.0.1", None),
        ("٣.0.0.1", None),
        ("127.0.0.1 ", None),
        ("127。0。0。1", "127.0.0.1"),
    ],
)
def test_a_host_reads_as_the_resolver_reads_it(host: str, address: str | None) -> None:
    """A spelling that only Python reads as a number is a name to a resolver, so it gives no
    address. Ideographic full stops are dots to a resolver, so that spelling gives the address
    (#2152)."""
    expected = None if address is None else ipaddress.ip_address(address)
    assert parse_numeric_ip(host) == expected


def test_a_legacy_host_is_read_by_the_resolver_with_no_dns_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host that is not an address literal goes to `getaddrinfo` one time, with
    `AI_NUMERICHOST`, so the C library reads it and no DNS query is made (#2152)."""
    real_getaddrinfo = socket.getaddrinfo
    calls: list[tuple[object, int]] = []

    def recorder(host: object, *args: Any, **kwargs: Any) -> Any:
        calls.append((host, kwargs.get("flags", 0) & socket.AI_NUMERICHOST))
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", recorder)
    results = (parse_numeric_ip("0177.0.0.1"), parse_numeric_ip("example.com"))

    assert (results, calls) == (
        (ipaddress.ip_address("127.0.0.1"), None),
        [("0177.0.0.1", socket.AI_NUMERICHOST), ("example.com", socket.AI_NUMERICHOST)],
    )

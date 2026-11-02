"""The class of an IP address in a network reference: public, documentation or local (#1174)."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

import pytest

from devops_cli.security.reference_extractor import (
    is_example_ip,
    is_example_or_invalid_network_target,
    is_private_or_local_ip,
    is_public_ip,
    network_target_address,
)


@pytest.mark.parametrize(
    ("address", "public"),
    [
        ("8.8.8.8", True),
        ("1.1.1.1", True),
        ("127.0.0.1", False),
        ("192.168.1.1", False),
        ("10.0.0.1", False),
        ("172.16.0.1", False),
        ("invalid-ip", False),
    ],
)
def test_only_a_global_address_is_public(address: str, public: bool) -> None:
    """Loopback, private space and a string that is not an address are not public."""
    assert is_public_ip(address) is public


# Each address and the one class it is in. Documentation space is RFC 5737, RFC 3849, RFC 9637,
# RFC 2544 and RFC 5180. Public is global, not reserved and not multicast; everything else
# specified is local, including `64:ff9b::a00:1` (the NAT64 form of 10.0.0.1), `4000::1` and
# `5f00::1`, which the stdlib reads as global but reserved, and `fec0::1`, deprecated site-local
# space it reads as global. An IPv4-mapped address is in the class of the IPv4 address it carries.
_ADDRESS_CLASSES: list[tuple[str, str]] = [
    *(
        (address, "public")
        for address in ("8.8.8.8", "2606:4700::1", "192.0.0.9", "2001:1::1", "2001:4:112::1")
    ),
    *(
        (address, "documentation")
        for address in (
            "192.0.2.1",
            "198.18.0.1",
            "2001:db8::1",
            "2001:2::1",
            "3fff::1",
            "::ffff:192.0.2.1",
        )
    ),
    *(
        (address, "local")
        for address in (
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "100.64.0.1",
            "192.0.0.1",
            "192.88.99.1",
            "240.0.0.1",
            "255.255.255.255",
            "224.0.0.1",
            "ff02::1",
            "100::1",
            "2001::1",
            "2002:a00:1::1",
            "64:ff9b::a00:1",
            "4000::1",
            "5f00::1",
            "fec0::1",
            "::ffff:192.88.99.2",
        )
    ),
    ("::", "unspecified"),
]


@pytest.mark.parametrize(("address", "address_class"), _ADDRESS_CLASSES)
def test_every_specified_address_is_in_exactly_one_class(address: str, address_class: str) -> None:
    """Public, documentation and local partition the specified addresses; an unspecified one is
    in none of them. An address in no class used to fall through `check_threat_intel` to a
    Cloudflare Radar lookup, as multicast did (#1174)."""
    assert (is_public_ip(address), is_example_ip(address), is_private_or_local_ip(address)) == (
        address_class == "public",
        address_class == "documentation",
        address_class == "local",
    )


@pytest.mark.parametrize("address", ["192.88.99.2", "fec0::1"])
def test_the_stdlib_still_reads_each_non_global_network_as_global(address: str) -> None:
    """Each entry of `CONST_NON_GLOBAL_NETWORKS_STDLIB_READS_GLOBAL` exists only while this holds.

    IANA lists 192.88.99.2/32 as not globally reachable (RFC 6751), and the rest of
    192.88.99.0/24 as deprecated (RFC 7526). Site-local fec0::/10 was IPv6's private space until
    RFC 3879 deprecated it, and IANA lists it as reserved by the IETF. When a case fails, CPython
    has followed IANA: delete that network from the constant, and the constant with its last
    entry.
    """
    assert ipaddress.ip_address(address).is_global is True


@pytest.mark.parametrize(
    ("target", "address_class"),
    [
        ("8.8.8.8.", "public"),
        ("192.0.2.1,", "documentation"),
        ("100.64.0.1.", "local"),
        ("224.0.0.1,", "local"),
        ("10.0.0.1)", "local"),
        ("fec0::1.", "local"),
    ],
)
def test_an_address_is_classed_without_the_punctuation_prose_leaves_after_it(
    target: str, address_class: str
) -> None:
    """The classes read a target as `is_example_or_invalid_network_target` reads it, without the
    `.,;)>]"'` prose leaves after it. A trailing dot is never part of an address literal, so
    `100.64.0.1.` is local; it used to be in no class and went to Cloudflare Radar (#1174)."""
    assert (is_public_ip(target), is_example_ip(target), is_private_or_local_ip(target)) == (
        address_class == "public",
        address_class == "documentation",
        address_class == "local",
    )


@pytest.mark.parametrize(
    ("target", "address"),
    [
        ("100.64.0.1.", "100.64.0.1"),
        ("224.0.0.1,", "224.0.0.1"),
        ("http://100.64.0.1./v1", "100.64.0.1"),
        ("100.64.0.1:443", "100.64.0.1"),
        ("[::1]:8080", "::1"),
        ("::ffff:192.88.99.1", "192.88.99.1"),
        ("2130706433", "127.0.0.1"),
        ("127.1", "127.0.0.1"),
        ("0x7f.0.0.1", "127.0.0.1"),
        ("0177.0.0.1", "127.0.0.1"),
        ("127.0.1", "127.0.0.1"),
        ("http://0177.0.0.1/", "127.0.0.1"),
        ("http://127.0.1/", "127.0.0.1"),
        ("example.com", None),
        ("localhost", None),
        ("555-0100", None),
    ],
)
def test_a_network_target_names_the_address_a_resolver_would_dial(
    target: str, address: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A URL or `host:port` names its host, prose punctuation is not part of it, and the legacy
    numeric spellings `inet_aton` reads (`2130706433`, `127.1`, `0x7f.0.0.1`) name the address a
    resolver dials. A name names no address, and no DNS query is made: only a call with
    `AI_NUMERICHOST` reaches the resolver (#1174, #2152)."""
    real_getaddrinfo = socket.getaddrinfo

    def _numeric_only(host: object, *args: Any, **kwargs: Any) -> Any:
        if not kwargs.get("flags", 0) & socket.AI_NUMERICHOST:
            raise AssertionError("no lookup may be made")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", _numeric_only)
    expected = None if address is None else ipaddress.ip_address(address)
    assert network_target_address(target) == expected


@pytest.mark.parametrize(
    "address",
    [
        "192.0.2.1",  # TEST-NET-1
        "192.0.2.254",
        "198.51.100.1",  # TEST-NET-2
        "198.51.100.50",
        "203.0.113.1",  # TEST-NET-3
        "203.0.113.254",
        "2001:db8::1",
        "2001:db8:85a3::8a2e:370:7334",
        "2001:db8:ffff:ffff:ffff:ffff:ffff:ffff",
        "3fff::1",
        "3fff:fff:ffff:ffff:ffff:ffff:ffff:ffff",
        "198.18.0.1",
        "198.19.255.254",
        "2001:2::1",
    ],
)
def test_a_documentation_or_benchmarking_address_is_an_example_target(address: str) -> None:
    """Documentation (RFC 5737, RFC 3849, RFC 9637) and benchmarking (RFC 2544, RFC 5180)
    addresses are examples."""
    assert is_example_or_invalid_network_target(address) is True


@pytest.mark.parametrize(
    "address", ["100.64.0.1", "100.127.255.254", "100::1", "8.8.8.8", "1.1.1.1", "93.184.216.34"]
)
def test_shared_discard_and_public_addresses_are_not_example_targets(address: str) -> None:
    """Shared address space (RFC 6598), the discard prefix (RFC 6666) and public addresses are
    not examples."""
    assert is_example_or_invalid_network_target(address) is False

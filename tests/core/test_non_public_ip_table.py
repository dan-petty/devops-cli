"""Table test of `is_non_public_ip` over the IANA special-purpose registries (#2184).

The classifier takes its answer from `ipaddress` (`is_global`, `is_multicast`) and adds the rules
that `ipaddress` lacks. Each row below names one registry block or one transition form. A row
fails if a change to the code or to a Python release changes the answer.
"""

from __future__ import annotations

import ipaddress

import pytest

from devops_cli.config.constants import CONST_PRIVATE_NETWORKS
from devops_cli.core.validation import is_non_public_ip

# IANA IPv4 special-purpose registry: the network address, a middle address and the last address
# of each block that is not globally reachable.
_NON_PUBLIC_V4 = [
    "0.0.0.1",
    "0.255.255.255",
    "10.0.0.0",
    "10.1.2.3",
    "10.255.255.255",
    "100.64.0.0",
    "100.100.100.200",
    "100.127.255.255",
    "127.0.0.1",
    "127.255.255.255",
    "169.254.0.0",
    "169.254.169.254",
    "172.16.0.0",
    "172.31.255.255",
    "192.0.0.0",
    "192.0.0.8",
    "192.0.0.192",
    "192.0.0.255",
    "192.0.2.0",
    "192.0.2.255",
    "192.168.0.0",
    "192.168.255.255",
    "198.18.0.0",
    "198.19.255.255",
    "198.51.100.0",
    "198.51.100.255",
    "203.0.113.0",
    "203.0.113.255",
    "224.0.0.1",
    "239.255.255.255",
    "240.0.0.0",
    "255.255.255.255",
    # IANA marks these two globally reachable and `is_global` is True for them, but the code
    # refuses the whole block 192.0.0.0/24 (RFC 6890).
    "192.0.0.9",
    "192.0.0.10",
]

# IANA IPv6 special-purpose registry, plus multicast.
_NON_PUBLIC_V6 = [
    "::",
    "::1",
    "100::",
    "100::1",
    "2001::1",
    "2001:2::1",
    "2001:10::1",
    "2001:db8::1",
    "2002::1",
    "3fff::1",
    "64:ff9b:1::1",
    "fc00::1",
    "fd00:ec2::254",
    "fe80::1",
    "ff02::1",
    "ff00::",
]

# Blocks that IANA marks as globally reachable: the code accepts them.
_PUBLIC = [
    "1.1.1.1",
    "8.8.8.8",
    "192.31.196.1",
    "192.52.193.1",
    "192.88.99.1",
    "192.175.48.1",
    "2001:1::1",
    "2001:3::1",
    "2001:4:112::1",
    "2001:20::1",
    "2001:30::1",
    "2606:4700::1",
    "2620:4f:8000::1",
]

# The NAT64 (RFC 6052, RFC 8215), Teredo, 6to4, IPv4-mapped, IPv4-compatible (RFC 4291) and ISATAP
# (RFC 5214) forms of an address. `ipaddress` calls the NAT64, compatible and ISATAP forms of a
# private address global, so these rows hold the rules that the code adds.
_TRANSITION_NON_PUBLIC = [
    "64:ff9b::c000:201",  # NAT64 of 192.0.2.1: `is_global` is True for it
    "64:ff9b::a00:1",  # NAT64 of 10.0.0.1
    "64:ff9b::7f00:1",  # NAT64 of 127.0.0.1
    "64:ff9b::a9fe:a9fe",  # NAT64 of the cloud metadata address
    "64:ff9b:1::a00:1",  # RFC 8215 form of 10.0.0.1
    "2001:0:a9fe:a9fe::",  # Teredo of a client that the mask inverts
    "2002:a9fe:a9fe::",  # 6to4 of 169.254.169.254
    "::ffff:10.0.0.1",  # IPv4-mapped 10.0.0.1
    "::ffff:127.0.0.1",  # IPv4-mapped 127.0.0.1
    "::a00:1",  # IPv4-compatible 10.0.0.1: `is_global` is True for it
    "::127.0.0.1",  # IPv4-compatible loopback
    "2606:4700::5efe:a00:1",  # ISATAP of 10.0.0.1: `is_global` is True for it
    "2606:4700::200:5efe:a00:1",  # ISATAP with the universal-local bit set
]
_TRANSITION_PUBLIC = [
    "64:ff9b::808:808",  # NAT64 of 8.8.8.8
    "::ffff:8.8.8.8",  # IPv4-mapped 8.8.8.8
    "::808:808",  # IPv4-compatible 8.8.8.8
    "2606:4700::5efe:808:808",  # ISATAP of 8.8.8.8
]


@pytest.mark.parametrize("address", _NON_PUBLIC_V4 + _NON_PUBLIC_V6 + _TRANSITION_NON_PUBLIC)
def test_a_non_public_address_is_refused(address: str) -> None:
    """Each block of the registries and each transition form of a private address is refused."""
    assert is_non_public_ip(ipaddress.ip_address(address)) is True


@pytest.mark.parametrize("address", _PUBLIC + _TRANSITION_PUBLIC)
def test_a_public_address_is_accepted(address: str) -> None:
    """A globally reachable block and the transition form of a public address pass."""
    assert is_non_public_ip(ipaddress.ip_address(address)) is False


# `is_global` is True for these blocks, so the table cannot test them against `ipaddress`.
_GLOBAL_BUT_REFUSED = {ipaddress.ip_network("224.0.0.0/4"), ipaddress.ip_network("ff00::/8")}


@pytest.mark.parametrize("block", CONST_PRIVATE_NETWORKS, ids=str)
def test_a_listed_block_agrees_with_ipaddress(
    block: ipaddress.IPv4Network | ipaddress.IPv6Network,
) -> None:
    """The block list stays in line with `ipaddress`: both ends of a block are non-global, or the
    block is a multicast block that the code refuses with `is_multicast`."""
    assert is_non_public_ip(block) is True
    if block in _GLOBAL_BUT_REFUSED:
        assert block.network_address.is_multicast
        return
    assert not block.network_address.is_global
    assert not block.broadcast_address.is_global


@pytest.mark.parametrize(
    ("network", "expected"),
    [
        ("8.0.0.0/5", True),  # holds 10.0.0.0/8
        ("64::/16", True),  # holds 64:ff9b::/96
        ("2606:4700::/48", False),
        ("1.1.1.0/24", False),
    ],
)
def test_a_range_is_non_public_when_it_holds_a_block(network: str, expected: bool) -> None:
    """`is_global` of a network tests its two ends only, so a range needs the block list."""
    assert is_non_public_ip(ipaddress.ip_network(network)) is expected

"""Hypothesis property-based tests for sandbox policy boundaries and deny-class oracles.

Validates deterministic containment, prefix-length oracle, path traversal,
benign multi-dot handling, NUL-byte rejection, and unified metadata denials.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

from hypothesis import Phase, example, given, settings
from hypothesis import strategies as st

from devops_cli.ai.models.ollama import _is_cloud_metadata_host as _ollama_is_metadata
from devops_cli.core.paths import (
    safe_resolve_subpath,
    validate_no_path_traversal,
    validate_path_parameter,
)
from devops_cli.core.validation import (
    is_cloud_metadata_host,
    is_loopback_or_private_host,
    is_non_public_ip,
    validate_url,
)
from devops_cli.exceptions import (
    SecurityError,
    SSRFBlockedError,
)
from devops_cli.http.egress import EgressLevel, vet_addresses
from devops_cli.sandbox.models import (
    _parse_whitelist_entry,
    _resolve_local_host,
    _resolve_public_host,
    _validate_local_whitelist_item,
)

# Standard derandomized settings profile for deterministic CI property runs
_DERANDOMIZED = settings(
    phases=[Phase.explicit, Phase.generate],
    derandomize=True,
    max_examples=50,
)


class CustomSubpathError(Exception):
    """Custom error class for safe_resolve_subpath testing."""


def _check_raises(func: Any, *args: Any, expected_exc: type[Exception], **kwargs: Any) -> bool:
    """Helper verifying that func raises expected_exc."""
    try:
        func(*args, **kwargs)
        return False
    except expected_exc:
        return True


# =============================================================================
# 1. Path Traversal & NUL-Byte Property Tests
# =============================================================================

_TRAVERSAL_PREFIXES = ("../", "..\\", "%2e%2e/", "%2e%2e\\", "%2E%2E/", "%2E%2E\\")
_TRAVERSAL_SEGMENTS = ("/../", "\\..\\", "/%2e%2e/", "\\%2e%2e\\", "/%2E%2E/", "\\%2E%2E\\")


@_DERANDOMIZED
@given(
    base=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=10),
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=10),
    prefix_sep=st.sampled_from(_TRAVERSAL_PREFIXES),
    segment_sep=st.sampled_from(_TRAVERSAL_SEGMENTS),
)
@example(base="foo", suffix="bar", prefix_sep="../", segment_sep="/../")
@example(base="etc", suffix="passwd", prefix_sep="%2e%2e/", segment_sep="/%2e%2e/")
def test_property_path_traversal_segments_are_denied(
    base: str, suffix: str, prefix_sep: str, segment_sep: str
) -> None:
    """Property: Any path with explicit directory traversal segments is rejected."""
    traversal_paths = [
        f"{prefix_sep}{suffix}",
        f"{base}{segment_sep}{suffix}",
        f"{base}/..",
        "..",
    ]
    for p in traversal_paths:
        traversal_blocked = _check_raises(
            validate_no_path_traversal, p, expected_exc=(SecurityError, ValueError)
        )
        param_blocked = _check_raises(
            validate_path_parameter,
            "file_path",
            p,
            allow_absolute=False,
            expected_exc=SecurityError,
        )
        assert (traversal_blocked, param_blocked) == (True, True)


@_DERANDOMIZED
@given(
    left=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=10),
    right=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=10),
    ext=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=4),
)
@example(left="notes", right="txt", ext="md")
@example(left="v1", right="2", ext="diff")
@example(left="a", right="b", ext="c")
def test_property_benign_multidot_paths_permitted(left: str, right: str, ext: str) -> None:
    """Property: Benign filenames containing '..' as an internal substring are permitted."""
    benign_paths = [
        f"{left}..{right}",
        f"{left}..{right}.{ext}",
        f"sub/{left}..{right}",
        f"sub/{left}..{right}/{ext}",
    ]
    for p in benign_paths:
        val_no_trav = validate_no_path_traversal(p, label="test")
        validate_path_parameter("file_path", p, allow_absolute=False)
        assert val_no_trav == Path(p)


@_DERANDOMIZED
@given(
    head=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=0, max_size=8),
    tail=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=0, max_size=8),
)
@example(head="a", tail="b")
@example(head="", tail="test")
def test_property_nul_bytes_in_subpath_raise_error_cls(head: str, tail: str) -> None:
    """Property: Embedded NUL bytes in safe_resolve_subpath raise error_cls, never raw ValueError."""
    path_with_nul = f"{head}\x00{tail}"
    raises_custom = _check_raises(
        safe_resolve_subpath,
        Path("/tmp/sandbox"),
        path_with_nul,
        error_cls=CustomSubpathError,
        expected_exc=CustomSubpathError,
    )
    assert raises_custom is True


@_DERANDOMIZED
@given(
    path_suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_/-", min_size=1, max_size=15)
)
@example(path_suffix="etc/passwd")
@example(path_suffix=".ssh/id_rsa")
def test_property_absolute_tilde_and_file_schemes_denied_when_not_allowed(path_suffix: str) -> None:
    """Property: Absolute paths, tilde, and file:// URIs are denied when allow_absolute=False."""
    disallowed_forms = [
        f"/{path_suffix}",
        f"~/{path_suffix}",
        f"~{path_suffix}",
        f"file:///{path_suffix}",
        f"file://{path_suffix}",
    ]
    for target in disallowed_forms:
        blocked = _check_raises(
            validate_path_parameter,
            "target",
            target,
            allow_absolute=False,
            expected_exc=SecurityError,
        )
        assert blocked is True


# =============================================================================
# 2. IPv6 Prefix-Length & CIDR Oracle Tests
# =============================================================================


@_DERANDOMIZED
@given(ip=st.ip_addresses())
def test_property_resolve_hosts_emit_correct_prefix_lengths(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> None:
    """Property: _resolve_public_host and _resolve_local_host emit /128 for IPv6 and /32 for IPv4."""
    from unittest.mock import patch

    ip_str = str(ip)
    expected_prefix = "128" if isinstance(ip, ipaddress.IPv6Address) else "32"
    expected_cidr = f"{ip_str}/{expected_prefix}"
    mock_addr = [(2, 1, 6, "", (ip_str, 80))]

    net = ipaddress.ip_network(ip_str, strict=False)
    is_public = not is_non_public_ip(net)

    with patch("socket.getaddrinfo", return_value=mock_addr):
        if is_public:
            blocks_direct = _resolve_public_host(ip_str)
            blocks_dns = _resolve_public_host("example.com")
            assert (blocks_direct, blocks_dns) == ([expected_cidr], [expected_cidr])
        elif (ip.is_private or ip.is_loopback) and not is_cloud_metadata_host(
            ip, resolve_dns=False
        ):
            blocks_direct = _resolve_local_host(ip_str)
            blocks_dns = _resolve_local_host("service.internal")
            assert (blocks_direct, blocks_dns) == ([expected_cidr], [expected_cidr])


@_DERANDOMIZED
@given(
    ip=st.ip_addresses(v=6),
    port=st.integers(min_value=1, max_value=65535),
    prefix_len=st.integers(min_value=0, max_value=128),
)
@example(ip=ipaddress.IPv6Address("fd00:ec2::254"), port=8080, prefix_len=128)
@example(ip=ipaddress.IPv6Address("::1"), port=11434, prefix_len=128)
@example(ip=ipaddress.IPv6Address("2001:db8::1"), port=443, prefix_len=64)
def test_property_parse_whitelist_entry_reads_ipv6_hosts_and_ports_oracle(
    ip: ipaddress.IPv6Address, port: int, prefix_len: int
) -> None:
    """Property: whitelist entries keep the full IPv6 address or CIDR, and the port they state."""
    ip_str = str(ip)
    cidr_str = f"{ip_str}/{prefix_len}"
    expected_cidr = str(ipaddress.ip_network(cidr_str, strict=False))

    # Oracle invariant: the host is never truncated to its first segment (e.g. 'fd00'), and an
    # entry without a port gets 443
    assert (
        _parse_whitelist_entry(ip_str),
        _parse_whitelist_entry(cidr_str),
        _parse_whitelist_entry(f"[{ip_str}]:{port}"),
        _parse_whitelist_entry(f"[{ip_str}]"),
        _parse_whitelist_entry(f"http://[{ip_str}]:{port}/api/v1"),
    ) == (
        (ip_str, 443),
        (expected_cidr, 443),
        (ip_str, port),
        (ip_str, 443),
        (ip_str, port),
    )


# =============================================================================
# 3. Cloud Metadata & Link-Local Containment Oracle Across All Six Sites
# =============================================================================

_METADATA_ORACLE_TARGETS = (
    "169.254.169.254",
    "169.254.169.254.",
    "169.254.1.1",
    "fd00:ec2::254",
    "[fd00:ec2::254]",
    "metadata.google.internal",
    "metadata.google.internal.",
    "metadata",
    "metadata.",
    "fe80::1",
    "[fe80::1]",
    "2852039166",
    "0xa9fea9fe",
    "64:ff9b::a9fe:a9fe",
    "168.63.129.16",
    "fd20:ce::254",
    "metadata.goog",
)


@_DERANDOMIZED
@given(target=st.sampled_from(_METADATA_ORACLE_TARGETS))
def test_property_cloud_metadata_superset_containment_at_all_six_sites(target: str) -> None:
    """Property: Unified cloud metadata superset is rejected with 1.0 containment at every site.

    The sandbox probe and Jaeger no longer keep checks of their own: both dial through the
    connect-time policy (`devops_cli.http.egress`), which refuses every target here at the loopback
    level Jaeger uses. The probe's private level admits the link-local host gateways among them,
    as `test_link_local_host_gateways_are_admitted_only_at_the_private_level` pins.
    """
    clean_host = target.strip("[]").rstrip(".")
    url_target = (
        f"[{clean_host}]" if ":" in clean_host and not clean_host.startswith("[") else target
    )

    # 1. Canonical is_cloud_metadata_host predicate
    pred_meta = is_cloud_metadata_host(target, resolve_dns=False)

    # 2. core/validation.py: is_loopback_or_private_host
    pred_priv = is_loopback_or_private_host(target, resolve_dns=False)

    # 3. core/validation.py: validate_url
    url_str = f"http://{url_target}/latest/meta-data/"
    val_url_blocked = _check_raises(
        validate_url, url_str, allow_private=True, expected_exc=SSRFBlockedError
    )

    # 4. http/egress.py: the connect-time policy, at the loopback level
    connect_blocked = _check_raises(
        vet_addresses, clean_host, 80, EgressLevel.LOOPBACK, expected_exc=SSRFBlockedError
    )

    # 5. sandbox/models.py: local whitelist and local host
    whitelist_blocked = _check_raises(
        _validate_local_whitelist_item, f"http://{url_target}:80", expected_exc=ValueError
    )
    models_host_blocked = _check_raises(_resolve_local_host, target, expected_exc=ValueError)

    # 7. ai/models/ollama.py: _is_cloud_metadata_host
    ollama_blocked = _ollama_is_metadata(target)

    assert (
        pred_meta,
        pred_priv,
        val_url_blocked,
        connect_blocked,
        whitelist_blocked,
        models_host_blocked,
        ollama_blocked,
    ) == (True, True, True, True, True, True, True)

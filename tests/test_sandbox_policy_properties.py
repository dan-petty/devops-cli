"""Hypothesis property-based tests for sandbox policy boundaries and deny-class oracles.

Validates deterministic containment, prefix-length oracle, path traversal,
benign multi-dot handling, NUL-byte rejection, and unified metadata denials.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
from devops_cli.sandbox.models import (
    _extract_host_or_ip,
    _resolve_local_host,
    _resolve_public_host,
    _validate_local_whitelist_item,
)
from devops_cli.sandbox.probe import _resolve_safe_socket_addr
from devops_cli.telemetry.waterfall import _resolve_safe_jaeger_target

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
def test_property_extract_host_or_ip_parses_ipv6_oracle(
    ip: ipaddress.IPv6Address, port: int, prefix_len: int
) -> None:
    """Property: _extract_host_or_ip extracts full IPv6 addresses, CIDRs, bracketed and URL forms."""
    ip_str = str(ip)
    cidr_str = f"{ip_str}/{prefix_len}"
    bracketed_port = f"[{ip_str}]:{port}"
    bracketed_no_port = f"[{ip_str}]"
    http_url = f"http://[{ip_str}]:{port}/api/v1"

    parsed_bare = _extract_host_or_ip(ip_str)
    parsed_cidr = _extract_host_or_ip(cidr_str)
    parsed_bracketed_port = _extract_host_or_ip(bracketed_port)
    parsed_bracketed = _extract_host_or_ip(bracketed_no_port)
    parsed_url = _extract_host_or_ip(http_url)

    expected_cidr = str(ipaddress.ip_network(cidr_str, strict=False))

    # Oracle invariant: parsed host must never be truncated to first segment (e.g. 'fd00')
    assert (
        parsed_bare,
        parsed_cidr,
        parsed_bracketed_port,
        parsed_bracketed,
        parsed_url,
    ) == (
        ip_str,
        expected_cidr,
        ip_str,
        ip_str,
        ip_str,
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
    """Property: Unified cloud metadata superset is rejected with 1.0 containment across all six sites."""
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

    # 4. sandbox/probe.py: _resolve_safe_socket_addr
    probe_blocked, _ = _resolve_safe_socket_addr(clean_host, 80)

    # 5. sandbox/models.py: local whitelist and local host
    whitelist_blocked = _check_raises(
        _validate_local_whitelist_item, f"http://{url_target}:80", expected_exc=ValueError
    )
    models_host_blocked = _check_raises(_resolve_local_host, target, expected_exc=ValueError)

    # 6. telemetry/waterfall.py: _resolve_safe_jaeger_target
    parsed_endpoint = urlparse(f"http://{url_target}:14268")
    jaeger_blocked, _ = _resolve_safe_jaeger_target(parsed_endpoint)

    # 7. ai/models/ollama.py: _is_cloud_metadata_host
    ollama_blocked = _ollama_is_metadata(target)

    assert (
        pred_meta,
        pred_priv,
        val_url_blocked,
        probe_blocked,
        whitelist_blocked,
        models_host_blocked,
        jaeger_blocked,
        ollama_blocked,
    ) == (True, True, True, True, True, True, True, True)

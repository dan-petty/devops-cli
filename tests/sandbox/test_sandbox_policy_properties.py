"""Hypothesis property-based tests for sandbox policy boundaries and deny-class oracles.

Validates deterministic containment, prefix-length oracle, path traversal,
benign multi-dot handling, NUL-byte rejection, and unified metadata denials.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, Phase, assume, example, given, settings
from hypothesis import strategies as st

from devops_cli.core.paths import (
    safe_resolve_subpath,
    validate_no_path_traversal,
    validate_path_parameter,
)
from devops_cli.core.validation import (
    is_cloud_metadata_host,
    is_loopback_or_private_host,
    is_non_public_ip,
)
from devops_cli.exceptions import (
    SecurityError,
    SSRFBlockedError,
)
from devops_cli.http.egress import EgressLevel, vet_addresses
from devops_cli.sandbox.models import SandboxNetworkConfig, SandboxNetworkMode
from tests.support.fakes.dns import DnsFake

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


def _whitelist_rules(mode: SandboxNetworkMode, entries: list[str]) -> list[dict[str, Any]]:
    """The egress rules the NetworkPolicy of a whitelist holds after its kube-dns rule."""
    field = "public_whitelist" if mode == SandboxNetworkMode.PUBLIC_WHITELIST else "local_whitelist"
    config = SandboxNetworkConfig(mode=mode, **{field: entries})
    return config.to_k8s_network_policy()["spec"]["egress"][1:]


def _tcp_rule(cidr: str, port: int) -> dict[str, Any]:
    """The egress rule that opens one TCP port on one address block."""
    return {"to": [{"ipBlock": {"cidr": cidr}}], "ports": [{"protocol": "TCP", "port": port}]}


# =============================================================================
# 1. Path Traversal & NUL-Byte Property Tests
# =============================================================================

_TRAVERSAL_PREFIXES = ("../", "..\\", "%2e%2e/", "%2e%2e\\", "%2E%2E/", "%2E%2E\\")
_TRAVERSAL_SEGMENTS = (
    "/../",
    "\\..\\",
    "/%2e%2e/",
    "\\%2e%2e\\",
    "/%2E%2E/",
    "\\%2E%2E\\",
)


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
def test_property_nul_bytes_in_subpath_raise_error_cls(
    tmp_path_factory: pytest.TempPathFactory, head: str, tail: str
) -> None:
    """Property: Embedded NUL bytes in safe_resolve_subpath raise error_cls, never raw ValueError."""
    path_with_nul = f"{head}\x00{tail}"
    raises_custom = _check_raises(
        safe_resolve_subpath,
        tmp_path_factory.getbasetemp(),
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
def test_property_absolute_tilde_and_file_schemes_denied_when_not_allowed(
    path_suffix: str,
) -> None:
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


# The `dns` fixture lives across the examples of one test, and each example scripts its own names.
@settings(_DERANDOMIZED, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(ip=st.ip_addresses())
def test_property_resolve_hosts_emit_correct_prefix_lengths(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    dns: DnsFake,
) -> None:
    """Property: a whitelist emits /128 for an IPv6 address and /32 for an IPv4 address.

    A loopback address emits nothing: NetworkPolicy never polices a pod's loopback (#1174).
    """
    ip_str = str(ip)
    expected_prefix = "128" if isinstance(ip, ipaddress.IPv6Address) else "32"
    expected_cidr = f"{ip_str}/{expected_prefix}"

    net = ipaddress.ip_network(ip_str, strict=False)
    is_public = not is_non_public_ip(net)

    if ip.is_loopback:
        assert _whitelist_rules(SandboxNetworkMode.LOCAL_WHITELIST, [ip_str]) == []
        return
    if is_public:
        dns.script("example.com", [ip_str])
        rules = _whitelist_rules(SandboxNetworkMode.PUBLIC_WHITELIST, [ip_str, "example.com"])
        assert rules == [_tcp_rule(expected_cidr, 443)] * 2
    elif ip.is_private and not is_cloud_metadata_host(ip):
        dns.script("service.internal", [ip_str])
        entries = [ip_str, "service.internal"]
        rules = _whitelist_rules(SandboxNetworkMode.LOCAL_WHITELIST, entries)
        assert rules == [_tcp_rule(expected_cidr, 443)] * 2


@_DERANDOMIZED
@given(
    ip=st.ip_addresses(v=6, network="2000::/3"),
    port=st.integers(min_value=1, max_value=65535),
)
@example(ip=ipaddress.IPv6Address("2606:4700::1111"), port=8080)
def test_property_public_whitelist_keeps_ipv6_hosts_and_ports_oracle(
    ip: ipaddress.IPv6Address, port: int
) -> None:
    """Property: public whitelist entries keep the full IPv6 address and the port they state."""
    ip_str = str(ip)
    assume(not is_non_public_ip(ipaddress.ip_network(ip_str)))

    # Oracle invariant: the host is never truncated to its first segment (e.g. '2606'), and an
    # entry without a port gets 443
    rules = [
        _whitelist_rules(SandboxNetworkMode.PUBLIC_WHITELIST, [entry])
        for entry in (
            ip_str,
            f"[{ip_str}]:{port}",
            f"[{ip_str}]",
            f"http://[{ip_str}]:{port}/api/v1",
        )
    ]
    assert rules == [
        [_tcp_rule(f"{ip_str}/128", 443)],
        [_tcp_rule(f"{ip_str}/128", port)],
        [_tcp_rule(f"{ip_str}/128", 443)],
        [_tcp_rule(f"{ip_str}/128", port)],
    ]


@_DERANDOMIZED
@given(
    ip=st.ip_addresses(v=6, network="fc00::/7").filter(lambda ip: not is_cloud_metadata_host(ip)),
    port=st.integers(min_value=1, max_value=65535),
    prefix_len=st.integers(min_value=8, max_value=128),
)
@example(ip=ipaddress.IPv6Address("fd00::1234"), port=11434, prefix_len=128)
@example(ip=ipaddress.IPv6Address("fd00::1234"), port=443, prefix_len=64)
def test_property_local_whitelist_keeps_ipv6_hosts_cidrs_and_ports_oracle(
    ip: ipaddress.IPv6Address, port: int, prefix_len: int
) -> None:
    """Property: local whitelist entries keep the full IPv6 address or CIDR, and the port."""
    ip_str = str(ip)
    network = ipaddress.ip_network(f"{ip_str}/{prefix_len}", strict=False)
    assume(not is_cloud_metadata_host(network))

    rules = [
        _whitelist_rules(SandboxNetworkMode.LOCAL_WHITELIST, [entry])
        for entry in (
            ip_str,
            f"{ip_str}/{prefix_len}",
            f"[{ip_str}]:{port}",
            f"http://[{ip_str}]:{port}/api/v1",
        )
    ]
    assert rules == [
        [_tcp_rule(f"{ip_str}/128", 443)],
        [_tcp_rule(str(network), 443)],
        [_tcp_rule(f"{ip_str}/128", port)],
        [_tcp_rule(f"{ip_str}/128", port)],
    ]


def test_the_properties_run_under_the_ci_profile_so_a_loaded_host_cannot_fail_them() -> None:
    """Every run loads Hypothesis's `ci` profile through `addopts`, so the properties here have
    no deadline and no `too_slow` health check. With the default 200 ms deadline, a loaded host
    that made the five parses of one IPv6 example slow failed the oracle property with
    DeadlineExceeded (#2092)."""
    assert (
        settings.get_current_profile_name(),
        _DERANDOMIZED.deadline,
        HealthCheck.too_slow in _DERANDOMIZED.suppress_health_check,
    ) == ("ci", None, True)


def test_whitelist_entries_name_a_lowercase_host_without_userinfo_and_their_port(
    dns: DnsFake,
) -> None:
    """Whitelist entries fold the host to lowercase, drop userinfo, and open 443 by default."""
    address = "93.184.215.14"
    dns.script("example.com", [address])

    rules = _whitelist_rules(
        SandboxNetworkMode.PUBLIC_WHITELIST, ["Example.COM", "user@example.com:22"]
    )

    assert (rules, len(dns.lookups_of("example.com"))) == (
        [_tcp_rule(f"{address}/32", 443), _tcp_rule(f"{address}/32", 22)],
        2,
    )


@pytest.mark.parametrize(
    "mode", [SandboxNetworkMode.PUBLIC_WHITELIST, SandboxNetworkMode.LOCAL_WHITELIST]
)
@pytest.mark.parametrize(
    "entry",
    ["http://:8080", "https://", "http:///x", "example.com:", "example.com:/x"],
)
def test_a_whitelist_entry_that_names_no_host_or_port_is_refused(
    mode: SandboxNetworkMode, entry: str
) -> None:
    """An entry with no host, an empty port or a path but no scheme fails the config."""
    with pytest.raises(ValueError, match="Whitelist entry"):
        _whitelist_rules(mode, [entry])


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
def test_property_cloud_metadata_superset_containment_at_all_six_sites(
    target: str,
) -> None:
    """Property: Unified cloud metadata superset is rejected with 1.0 containment at every site.

    The sandbox probe, Tempo and the pydantic-ai Ollama model no longer keep checks of their own:
    each dials through the connect-time policy (`devops_cli.http.egress`), which refuses every
    target here at the loopback level Tempo uses. The probe's private level admits the link-local host gateways among them,
    as `test_link_local_host_gateways_are_admitted_only_at_the_private_level` pins.
    """
    clean_host = target.strip("[]").rstrip(".")
    url_target = (
        f"[{clean_host}]" if ":" in clean_host and not clean_host.startswith("[") else target
    )

    # 1. Canonical is_cloud_metadata_host predicate
    pred_meta = is_cloud_metadata_host(target)

    # 2. core/validation.py: is_loopback_or_private_host
    pred_priv = is_loopback_or_private_host(target)

    # 3. http/egress.py: the connect-time policy, at the loopback level
    connect_blocked = _check_raises(
        vet_addresses,
        clean_host,
        80,
        EgressLevel.LOOPBACK,
        expected_exc=SSRFBlockedError,
    )

    # 4. sandbox/models.py: local whitelist and local host
    whitelist_blocked = _check_raises(
        _whitelist_rules,
        SandboxNetworkMode.LOCAL_WHITELIST,
        [f"http://{url_target}:80"],
        expected_exc=ValueError,
    )
    unvalidated = SandboxNetworkConfig.model_construct(
        mode=SandboxNetworkMode.LOCAL_WHITELIST, local_whitelist=[target]
    )
    models_host_blocked = _check_raises(unvalidated.to_k8s_network_policy, expected_exc=ValueError)

    assert (
        pred_meta,
        pred_priv,
        connect_blocked,
        whitelist_blocked,
        models_host_blocked,
    ) == (True, True, True, True, True)

"""Tests for core validation utilities."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

import pytest
import typer

from devops_cli.core.validation import (
    is_non_public_ip,
    validate_dir,
    validate_file,
    validate_k8s_name,
    validate_path,
    validate_safe_key_path,
)
from devops_cli.exceptions import SSRFBlockedError


def test_is_non_public_ip() -> None:
    assert (
        is_non_public_ip(ipaddress.ip_address("127.0.0.1")),
        is_non_public_ip(ipaddress.ip_address("10.0.0.1")),
        is_non_public_ip(ipaddress.ip_address("192.168.1.1")),
        is_non_public_ip(ipaddress.ip_address("8.8.8.8")),
        is_non_public_ip(ipaddress.ip_address("::1")),
        is_non_public_ip(ipaddress.ip_address("fd00::1")),
        is_non_public_ip(ipaddress.ip_address("2606:4700::1")),
        is_non_public_ip(ipaddress.ip_network("192.168.1.0/24")),
        is_non_public_ip(ipaddress.ip_network("2606:4700::/32")),
        is_non_public_ip(ipaddress.ip_address("64:ff9b::a9fe:a9fe")),
        is_non_public_ip(ipaddress.ip_address("64:ff9b::7f00:1")),
        is_non_public_ip(ipaddress.ip_address("::127.0.0.1")),
        is_non_public_ip(ipaddress.ip_network("64:ff9b::a9fe:0/112")),
        is_non_public_ip(ipaddress.ip_network("64:ff9b::/96")),
        is_non_public_ip(ipaddress.ip_network("64:ff9b::/95")),
        is_non_public_ip(ipaddress.ip_address("64:ff9b::808:808")),
        is_non_public_ip(ipaddress.ip_network("64:ff9b::808:0/112")),
        is_non_public_ip(ipaddress.ip_address("::ffff:8.8.8.8")),
        is_non_public_ip(ipaddress.ip_address("64:ff9b:1::808:808")),
        is_non_public_ip(ipaddress.ip_address("2002:a9fe:a9fe::")),
        is_non_public_ip(ipaddress.ip_address("2001:0:a9fe:a9fe::")),
        is_non_public_ip(ipaddress.ip_address("::")),
    ) == (
        True,
        True,
        True,
        False,
        True,
        True,
        False,
        True,
        False,
        True,
        True,
        True,
        True,
        True,
        True,
        False,
        False,
        False,
        True,
        True,
        True,
        True,
    )


@pytest.mark.parametrize(
    ("cidr", "non_public"),
    [
        ("0.0.0.0/0", True),
        ("::/0", True),
        ("128.0.0.0/1", True),
        ("8.0.0.0/5", True),
        ("64:ff9b::/96", True),
        ("64:ff9b::800:0/101", True),
        ("::800:0/101", True),
        ("64::/16", True),
        ("2606:4700::/48", False),
        ("140.82.112.0/20", False),
    ],
)
def test_a_range_is_non_public_when_any_of_its_addresses_is(cidr: str, non_public: bool) -> None:
    """A range holding a non-public block is non-public even when both its ends are public.

    `8.0.0.0/5` holds 10.0.0.0/8; `64:ff9b::800:0/101` and `::800:0/101` are its NAT64 and
    IPv4-compatible images, holding that block's images; `64::/16` holds `64:ff9b::/96`.
    """
    assert is_non_public_ip(ipaddress.ip_network(cidr)) is non_public


def test_validate_path_and_dir_and_file(tmp_path: Path) -> None:
    d = tmp_path / "subdir"
    d.mkdir()
    f = d / "test.txt"
    f.write_text("hello", encoding="utf-8")

    assert validate_path(d) == d
    assert validate_dir(d) == d
    assert validate_file(f) == f

    with pytest.raises(typer.Exit) as raised:
        validate_dir(f)
    assert raised.value.exit_code is not None

    with pytest.raises(typer.Exit) as raised:
        validate_file(d)
    assert raised.value.exit_code is not None

    with pytest.raises(typer.Exit) as raised:
        validate_path(tmp_path / "nonexistent")
    assert raised.value.exit_code is not None


def test_validate_safe_key_path() -> None:
    p = Path("id_ed25519-test")
    assert validate_safe_key_path(p) == p

    with pytest.raises(ValueError, match="Invalid SSH key path"):
        validate_safe_key_path("../id_ed25519")

    with pytest.raises(ValueError, match="Invalid SSH key path"):
        validate_safe_key_path("")


def test_validate_k8s_name() -> None:
    assert validate_k8s_name("valid-name") == "valid-name"
    assert validate_k8s_name("kube-system", namespace=True) == "kube-system"

    with pytest.raises(typer.Exit) as raised:
        validate_k8s_name("INVALID_NAME!!")
    assert raised.value.exit_code is not None


def test_validate_path_parameterized(tmp_path: Path) -> None:
    d = tmp_path / "somedir"
    d.mkdir()
    f = d / "file.txt"
    f.write_text("data", encoding="utf-8")

    assert validate_path(d, kind="dir", label="Directory") == d
    assert validate_path(f, kind="file", label="File") == f
    assert validate_path("id_ed25519", kind="key", allow_traversal=False) == Path("id_ed25519")

    with pytest.raises(typer.Exit) as raised:
        validate_path("", label="Empty")
    assert raised.value.exit_code is not None

    with pytest.raises(typer.Exit) as raised:
        validate_path("../outside", allow_traversal=False)
    assert raised.value.exit_code is not None


def test_validation_edge_cases() -> None:
    """Verify validate_safe_directory_path and validate_session_id."""
    from devops_cli.core.validation import (
        validate_safe_directory_path,
        validate_session_id,
    )
    from devops_cli.exceptions import ValidationError

    # 1. validate_safe_directory_path
    assert validate_safe_directory_path("src/devops_cli") == Path("src/devops_cli")
    with pytest.raises(ValidationError) as raised:
        validate_safe_directory_path("")
    assert raised.value.error_code == "VALIDATION_ERROR"
    with pytest.raises(ValidationError) as raised:
        validate_safe_directory_path("path/../traversal")
    assert raised.value.error_code == "VALIDATION_ERROR"

    # 2. validate_session_id
    assert validate_session_id("valid-session_123") == "valid-session_123"
    with pytest.raises(ValidationError) as raised:
        validate_session_id("")
    assert raised.value.error_code == "VALIDATION_ERROR"
    with pytest.raises(ValidationError) as raised:
        validate_session_id("invalid session!!")
    assert raised.value.error_code == "VALIDATION_ERROR"
    with pytest.raises(ValidationError) as raised:
        validate_session_id("session/../traversal")
    assert raised.value.error_code == "VALIDATION_ERROR"

    from devops_cli.core.validation import validate_k8s_context_name

    assert (
        validate_k8s_context_name("arn:aws:eks:us-west-2:123456789012:cluster/my-cluster")
        == "arn:aws:eks:us-west-2:123456789012:cluster/my-cluster"
    )
    with pytest.raises(typer.Exit) as raised:
        validate_k8s_context_name("invalid context with spaces")
    assert raised.value.exit_code is not None
    with pytest.raises(typer.Exit) as raised:
        validate_k8s_context_name("invalid\ncontext")
    assert raised.value.exit_code is not None


def test_is_loopback_or_private_host() -> None:
    """Verify loopback and private host classification."""
    from devops_cli.core.validation import is_loopback_or_private_host

    assert is_loopback_or_private_host("127.0.0.1") is True
    assert is_loopback_or_private_host("::1") is True
    assert is_loopback_or_private_host("localhost") is True
    assert is_loopback_or_private_host("service.local") is True
    assert is_loopback_or_private_host("10.0.0.1") is True
    assert is_loopback_or_private_host("192.168.1.100") is True
    assert is_loopback_or_private_host("169.254.169.254") is True
    assert is_loopback_or_private_host("8.8.8.8") is False
    assert is_loopback_or_private_host("1.1.1.1") is False
    assert is_loopback_or_private_host("example.com") is False
    assert is_loopback_or_private_host("unresolvable.invalid") is True


def test_network_guard_blocks_external_socket_calls(
    unexpected_loopback_connects: list[str],
) -> None:
    """Verify that tests are prevented from making unmocked external socket connections."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(
            RuntimeError, match="External network call blocked during test execution"
        ):
            sock.connect(("192.0.2.1", 80))
    finally:
        sock.close()
        unexpected_loopback_connects.clear()


def test_network_guard_blocks_external_dns_lookups(
    unexpected_loopback_connects: list[str],
) -> None:
    """Verify that tests cannot resolve external hostnames, while loopback names still resolve."""
    import socket

    try:
        with pytest.raises(
            socket.gaierror, match="External DNS lookup blocked during test execution"
        ):
            socket.getaddrinfo("api.osv.dev", 443)
    finally:
        unexpected_loopback_connects.clear()
    assert socket.getaddrinfo("localhost", 80)
    assert socket.getaddrinfo("127.0.0.1", 80)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_network_guard_refuses_and_reports_loopback_services_the_test_did_not_bind(
    host: str, unexpected_loopback_connects: list[str]
) -> None:
    """A loopback port no socket in the test process binds refuses, even when a service answers,
    and the connect is reported, which fails the test that made it.

    The service binds and listens through the C socket type, as a port-forward in another process
    does: the kernel accepts connections on a port the guard never saw a test bind.
    """
    import _socket
    import errno
    import socket

    with socket.socket() as service, socket.socket() as client, socket.socket() as probe:
        _socket.socket.bind(service, ("127.0.0.1", 0))
        _socket.socket.listen(service)
        address = (host, service.getsockname()[1])
        try:
            with pytest.raises(ConnectionRefusedError) as refused:
                client.connect(address)
            outcome = (
                refused.value.errno,
                probe.connect_ex(address),
                list(unexpected_loopback_connects),
            )
        finally:
            unexpected_loopback_connects.clear()

    assert outcome == (
        errno.ECONNREFUSED,
        errno.ECONNREFUSED,
        [f"{host}:{address[1]} (MainThread)"] * 2,
    )


def test_network_guard_refuses_and_reports_a_port_once_the_test_closes_its_server(
    unexpected_loopback_connects: list[str],
) -> None:
    """A port is the test's only while its socket is open; whoever holds it next is refused.

    The service shares the port through SO_REUSEPORT and binds and listens through the C socket
    type, so it still answers there after the test closes its server, as a port-forward that binds
    the freed port in another process would.
    """
    import _socket
    import errno
    import socket

    with (
        socket.socket() as server,
        socket.socket() as service,
        socket.socket() as client,
        socket.socket() as probe,
    ):
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        service.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        server.bind(("127.0.0.1", 0))
        server.listen()
        _socket.socket.bind(service, server.getsockname())
        _socket.socket.listen(service)
        server.close()
        address = service.getsockname()
        try:
            with pytest.raises(ConnectionRefusedError) as raised:
                client.connect(address)
            assert raised.value is not None
            outcome = (probe.connect_ex(address), list(unexpected_loopback_connects))
        finally:
            unexpected_loopback_connects.clear()

    assert outcome == (errno.ECONNREFUSED, [f"127.0.0.1:{address[1]} (MainThread)"] * 2)


def test_a_refusing_port_is_refused_by_the_kernel_and_not_reported(
    refusing_port: int, unexpected_loopback_connects: list[str]
) -> None:
    """The test binds `refusing_port` and never listens on it, so the guard lets a connect through
    and the kernel refuses it, as a service that is down would, with nothing reported."""
    import errno
    import socket

    with socket.socket() as client, socket.socket() as probe:
        with pytest.raises(ConnectionRefusedError) as refused:
            client.connect(("127.0.0.1", refusing_port))
        outcome = (refused.value.errno, probe.connect_ex(("127.0.0.1", refusing_port)))

    assert (outcome, unexpected_loopback_connects) == (
        (errno.ECONNREFUSED, errno.ECONNREFUSED),
        [],
    )


def test_network_guard_lets_a_test_reach_a_server_it_started() -> None:
    """A server the test starts in-process stays reachable over loopback."""
    import socket

    with socket.socket() as server, socket.socket() as client, socket.socket() as probe:
        server.bind(("127.0.0.1", 0))
        server.listen()
        address = server.getsockname()
        client.connect(address)
        assert (client.getpeername(), probe.connect_ex(address)) == (address, 0)


def test_is_cloud_metadata_host_superset() -> None:
    """Verify is_cloud_metadata_host matches ollama superset (bare metadata, trailing dots, IPv6, ULA)."""
    from devops_cli.core.validation import is_cloud_metadata_host

    assert (
        is_cloud_metadata_host("169.254.169.254"),
        is_cloud_metadata_host("169.254.1.1"),
        is_cloud_metadata_host("fd00:ec2::254"),
        is_cloud_metadata_host("[fd00:ec2::254]"),
        is_cloud_metadata_host("metadata.google.internal"),
        is_cloud_metadata_host("metadata.google.internal."),
        is_cloud_metadata_host("metadata"),
        is_cloud_metadata_host("metadata."),
        is_cloud_metadata_host("metadata.goog"),
        is_cloud_metadata_host("metadata.goog."),
        is_cloud_metadata_host("fe80::1"),
        is_cloud_metadata_host("example.com"),
        is_cloud_metadata_host("8.8.8.8"),
        is_cloud_metadata_host("127.0.0.1"),
        is_cloud_metadata_host(ipaddress.ip_address("169.254.169.254")),
        is_cloud_metadata_host(ipaddress.ip_address("fd00:ec2::254")),
        is_cloud_metadata_host(ipaddress.ip_network("169.254.0.0/16")),
        is_cloud_metadata_host("64:ff9b::a9fe:a9fe"),
        is_cloud_metadata_host(ipaddress.ip_address("64:ff9b::a9fe:a9fe")),
        is_cloud_metadata_host("2852039166"),
        is_cloud_metadata_host("168.63.129.16"),
        is_cloud_metadata_host("fd20:ce::254"),
        is_cloud_metadata_host("64:ff9b::808:808"),
    ) == (
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        False,
        False,
        False,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        False,
    )


def _is_target_blocked(func: Any, arg: str, err_cls: type[Exception], **kwargs: Any) -> bool:
    """Helper to check if calling func(arg) raises err_cls."""
    try:
        func(arg, **kwargs)
        return False
    except err_cls:
        return True


def test_widened_metadata_denials_core_and_probe() -> None:
    """Verify core validation and sandbox probe deny unified metadata superset."""
    from devops_cli.core.validation import is_loopback_or_private_host
    from devops_cli.http.egress import EgressLevel, vet_addresses

    assert (
        is_loopback_or_private_host("metadata"),
        is_loopback_or_private_host("metadata."),
        is_loopback_or_private_host("fd00:ec2::254"),
        is_loopback_or_private_host("[fd00:ec2::254]"),
    ) == (True, True, True, True)

    connect_blocked = sum(
        1
        for host in ("metadata", "metadata.", "fd00:ec2::254")
        if _is_target_blocked(
            vet_addresses, host, SSRFBlockedError, port=80, level=EgressLevel.PRIVATE
        )
    )
    assert connect_blocked == 3


def test_widened_metadata_denials_models_and_the_connect() -> None:
    """Verify sandbox models and the connect-time policy deny the unified metadata superset.

    The telemetry waterfall and the pydantic-ai Ollama model dial through that policy.
    """
    from devops_cli.http.egress import EgressLevel, vet_addresses
    from devops_cli.sandbox.models import _resolve_local_host, _validate_local_whitelist_item

    endpoints = ("http://metadata:8080", "http://metadata.:8080", "http://[fd00:ec2::254]:8080")
    items_blocked = sum(
        1 for ep in endpoints if _is_target_blocked(_validate_local_whitelist_item, ep, ValueError)
    )
    hosts = ("metadata", "metadata.", "fd00:ec2::254")
    hosts_blocked = sum(
        1 for h in hosts if _is_target_blocked(_resolve_local_host, h, ValueError, port=443)
    )
    assert (items_blocked, hosts_blocked) == (len(endpoints), len(hosts))

    tempo_level_blocked = sum(
        1
        for host in hosts
        if _is_target_blocked(
            vet_addresses, host, SSRFBlockedError, port=3200, level=EgressLevel.LOOPBACK
        )
    )
    assert tempo_level_blocked == len(hosts)


def test_pydantic_ai_ssrf_classifier_contract() -> None:
    """Contract test verifying pydantic_ai._ssrf exports expected classification helpers and link-local networks."""
    from devops_cli.core.validation import _LINK_LOCAL_NETWORKS, is_cloud_metadata_ip, is_private_ip

    assert _LINK_LOCAL_NETWORKS == (
        ipaddress.IPv4Network("169.254.0.0/16"),
        ipaddress.IPv6Network("fe80::/10"),
    )
    assert (
        is_cloud_metadata_ip(ipaddress.ip_address("169.254.169.254")),
        is_cloud_metadata_ip(ipaddress.ip_address("fd00:ec2::254")),
        is_cloud_metadata_ip(ipaddress.ip_address("168.63.129.16")),
        is_cloud_metadata_ip(ipaddress.ip_address("64:ff9b::a9fe:a9fe")),
        is_cloud_metadata_ip(ipaddress.ip_address("8.8.8.8")),
        is_private_ip(ipaddress.ip_address("192.168.1.1")),
        is_private_ip(ipaddress.ip_address("64:ff9b::192.168.1.1")),
        is_private_ip(ipaddress.ip_address("8.8.8.8")),
    ) == (True, True, True, True, False, True, True, False)


def test_conftest_dns_guard_ai_numerichost(
    unexpected_loopback_connects: list[str],
) -> None:
    """Verify test DNS guard passes AI_NUMERICHOST calls positionally and via keyword."""
    import socket

    # Positionally passed AI_NUMERICHOST on numeric string
    res_pos = socket.getaddrinfo("127.0.0.1", 0, 0, 0, 0, socket.AI_NUMERICHOST)
    # Keyword passed AI_NUMERICHOST on numeric string
    res_kw = socket.getaddrinfo("127.0.0.1", 0, flags=socket.AI_NUMERICHOST)
    assert (bool(res_pos), bool(res_kw)) == (True, True)

    # External domain without AI_NUMERICHOST raises gaierror from guard
    try:
        with pytest.raises(socket.gaierror, match="External DNS lookup blocked"):
            socket.getaddrinfo("nonexistent.unmocked.domain", 80)
    finally:
        unexpected_loopback_connects.clear()


_PUBLIC_DNS_NAME_TABLE: tuple[tuple[str, bool], ...] = (
    ("grafana.corp", False),
    ("grafana.home.arpa", False),
    ("grafana.test", False),
    ("ollama.home", False),
    ("co.uk", False),
    ("1.2.0.192.in-addr.arpa", False),
    ("resolver.arpa", False),
    ("x.onion", False),
    ("localhost", False),
    ("192.0.2.1", False),
    ("a..b.example.com", False),
    ("example.com", True),
    ("EXAMPLE.COM.", True),
)


@pytest.mark.parametrize(("host", "expected"), _PUBLIC_DNS_NAME_TABLE)
def test_is_public_dns_name_table(host: str, expected: bool) -> None:
    """Verify is_public_dns_name classifies PSL suffixes, special-use roots, IPs, and malformed names (#887)."""
    from devops_cli.core.dns_names import is_public_dns_name

    assert is_public_dns_name(host) is expected


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("grafana.corp", True),
        ("x.alt", True),
        ("unresolvable.invalid", True),
        ("a..b.example.com", True),
        ("8.8.8.8", False),
    ],
)
def test_is_loopback_or_private_host_no_dns_table(host: str, expected: bool) -> None:
    """Verify is_loopback_or_private_host(h) uses PSL and IP checks (#887)."""
    from devops_cli.core.validation import is_loopback_or_private_host

    assert is_loopback_or_private_host(host) is expected


_ONE_ANSWER_HOSTS: tuple[str, ...] = (
    "grafana.corp",
    "grafana.home.arpa",
    "grafana.test",
    "ollama.home",
    "co.uk",
    "1.2.0.192.in-addr.arpa",
    "resolver.arpa",
    "x.onion",
    "localhost",
    "x.alt",
    "unresolvable.invalid",
    "a..b.example.com",
    "example.com",
    "EXAMPLE.COM.",
)


@pytest.mark.parametrize("host", _ONE_ANSWER_HOSTS)
def test_one_answer_everywhere_local_vs_public(
    host: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """is_public_dns_name, pricing._is_local_host, and is_loopback_or_private_host agree on every host (#887)."""
    from devops_cli.ai.spend.pricing import _is_local_host
    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.core.dns_names import is_public_dns_name
    from devops_cli.core.validation import is_loopback_or_private_host

    empty_cfg = tmp_path / "config.yaml"
    empty_cfg.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(empty_cfg))
    reset_settings_cache()

    not_public = not is_public_dns_name(host)
    assert (_is_local_host(host), is_loopback_or_private_host(host)) == (
        not_public,
        not_public,
    )


def test_shared_tld_extractor_no_writes_no_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Building the shared extractor and classifying a name writes nothing to HOME and opens no socket (#887)."""
    import socket

    from devops_cli.core.dns_names import get_tld_extractor, is_public_dns_name

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    get_tld_extractor.cache_clear()

    def fail_socket(*args: object, **kwargs: object) -> None:
        raise AssertionError("No socket may be opened")

    monkeypatch.setattr(socket, "create_connection", fail_socket)
    extractor = get_tld_extractor()
    extracted = extractor("example.com")
    assert (
        extracted.top_domain_under_public_suffix,
        is_public_dns_name("example.com"),
        is_public_dns_name("grafana.corp"),
        list(home_dir.iterdir()),
    ) == ("example.com", True, False, [])


def test_is_at_or_under_matches_whole_labels_and_equal_ip_literals() -> None:
    """A host is at or under a domain on whole DNS labels, and an IP literal matches only itself (#887)."""
    from devops_cli.core.dns_names import is_at_or_under

    assert (
        is_at_or_under("example.com", "example.com"),
        is_at_or_under("example.com", "com"),
        is_at_or_under("example.com", "ample.com"),
        is_at_or_under("192.0.2.1", "192.0.2.1"),
        is_at_or_under("192.0.2.1", "192.0.2.2"),
        is_at_or_under("192.0.2.1", "example.com"),
        is_at_or_under("example.com", "192.0.2.1"),
    ) == (True, True, False, True, False, False, False)


def test_settings_domain_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """k8s.domain / cloudflare.domain refuse invalid names while blank loads as None (#887)."""
    from pydantic import ValidationError as PydanticValidationError

    from devops_cli.config.settings import load_settings, reset_settings_cache

    cfg_path = tmp_path / "config.yaml"
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_path))

    cfg_path.write_text("k8s:\n  domain: '.'\n", encoding="utf-8")
    reset_settings_cache()
    with pytest.raises(PydanticValidationError, match=r"k8s\.domain"):
        load_settings()

    cfg_path.write_text("cloudflare:\n  domain: '.example.com'\n", encoding="utf-8")
    reset_settings_cache()
    with pytest.raises(PydanticValidationError, match=r"cloudflare\.domain"):
        load_settings()

    cfg_path.write_text("k8s:\n  domain: ''\ncloudflare:\n  domain: '  '\n", encoding="utf-8")
    reset_settings_cache()
    loaded_blank = load_settings()

    cfg_path.write_text("k8s:\n  domain: '  '\n", encoding="utf-8")
    reset_settings_cache()
    loaded_spaces = load_settings()

    assert (
        loaded_blank.k8s.domain,
        loaded_blank.cloudflare.domain,
        loaded_spaces.k8s.domain,
    ) == (None, None, None)


@pytest.mark.parametrize("root_spelling", ["@", " @ ", "\u3002", "\uff0e", "\uff61"])
def test_settings_domain_refuses_every_spelling_of_the_root_name(root_spelling: str) -> None:
    """dnspython reads `@` and the IDNA full stops as the root name, which no settings domain may be (#887)."""
    from pydantic import ValidationError as PydanticValidationError

    from devops_cli.config.settings import CloudflareConfig, KubernetesConfig

    with pytest.raises(PydanticValidationError, match=r"Invalid domain in k8s\.domain"):
        KubernetesConfig(domain=root_spelling)
    with pytest.raises(PydanticValidationError, match=r"Invalid domain in cloudflare\.domain"):
        CloudflareConfig(domain=root_spelling)

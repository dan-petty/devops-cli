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
    validate_service_url,
    validate_url,
    validate_version_str,
)


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
    ) == (True, True, True, False, True, True, False, True, False)


def test_validate_url_valid() -> None:
    assert validate_url("http://localhost:11434") == "http://localhost:11434"
    assert validate_url("https://api.openai.com/v1") == "https://api.openai.com/v1"


def test_validate_url_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid service URL scheme"):
        validate_url("ftp://example.com")

    with pytest.raises(ValueError, match="missing valid hostname"):
        validate_url("http://")


def test_validate_service_url_public_vs_private(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    # Loopback IP without allow
    with pytest.raises(ValueError, match="Refusing non-public"):
        validate_service_url("http://127.0.0.1:8080", "test-service", allow=False)

    # Allowed private network
    validate_service_url("http://127.0.0.1:8080", "test-service", allow=True)


def test_validate_path_and_dir_and_file(tmp_path: Path) -> None:
    d = tmp_path / "subdir"
    d.mkdir()
    f = d / "test.txt"
    f.write_text("hello", encoding="utf-8")

    assert validate_path(d) == d
    assert validate_dir(d) == d
    assert validate_file(f) == f

    with pytest.raises(typer.Exit):
        validate_dir(f)

    with pytest.raises(typer.Exit):
        validate_file(d)

    with pytest.raises(typer.Exit):
        validate_path(tmp_path / "nonexistent")


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

    with pytest.raises(typer.Exit):
        validate_k8s_name("INVALID_NAME!!")


def test_validate_path_parameterized(tmp_path: Path) -> None:
    d = tmp_path / "somedir"
    d.mkdir()
    f = d / "file.txt"
    f.write_text("data", encoding="utf-8")

    assert validate_path(d, kind="dir", label="Directory") == d
    assert validate_path(f, kind="file", label="File") == f
    assert validate_path("id_ed25519", kind="key", allow_traversal=False) == Path("id_ed25519")

    with pytest.raises(typer.Exit):
        validate_path("", label="Empty")

    with pytest.raises(typer.Exit):
        validate_path("../outside", allow_traversal=False)


def test_validate_version_str() -> None:
    assert validate_version_str("v1.28.0") == "1.28.0"
    assert validate_version_str("2.0.1-rc1") == "2.0.1-rc1"

    with pytest.raises(ValueError, match="Invalid tool version string"):
        validate_version_str("invalid..version!!")


def test_validate_ssrf_egress_and_dns_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify SSRF egress checks with public IP and DNS resolution."""
    from unittest.mock import patch

    from devops_cli.core.validation import _enforce_non_private_ssrf
    from devops_cli.exceptions import SSRFBlockedError

    # Public IP succeeds
    _enforce_non_private_ssrf("http://8.8.8.8:8080", "8.8.8.8", "http", 8080, "test")

    # Hostname resolving to private IP raises SSRFBlockedError
    mock_addrinfo = [(2, 1, 6, "", ("192.168.1.50", 8080))]
    with patch("socket.getaddrinfo", return_value=mock_addrinfo):
        with pytest.raises(SSRFBlockedError):
            _enforce_non_private_ssrf(
                "http://example.com:8080", "example.com", "http", 8080, "test"
            )

    # Hostname resolving to public IP succeeds
    mock_pub_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 80))]
    with patch("socket.getaddrinfo", return_value=mock_pub_addrinfo):
        _enforce_non_private_ssrf("http://example.com", "example.com", "http", 80, "test")


def test_validation_edge_cases() -> None:
    """Verify validate_safe_directory_path, validate_session_id, and empty version."""
    from unittest.mock import patch

    from devops_cli.core.validation import (
        _enforce_non_private_ssrf,
        validate_safe_directory_path,
        validate_session_id,
    )
    from devops_cli.exceptions import InvalidVersionError, SSRFBlockedError, ValidationError

    # 1. validate_safe_directory_path
    assert validate_safe_directory_path("src/devops_cli") == Path("src/devops_cli")
    with pytest.raises(ValidationError):
        validate_safe_directory_path("")
    with pytest.raises(ValidationError):
        validate_safe_directory_path("path/../traversal")

    # 2. validate_session_id
    assert validate_session_id("valid-session_123") == "valid-session_123"
    with pytest.raises(ValidationError):
        validate_session_id("")
    with pytest.raises(ValidationError):
        validate_session_id("invalid session!!")
    with pytest.raises(ValidationError):
        validate_session_id("session/../traversal")

    # 3. validate_version_str empty
    with pytest.raises(InvalidVersionError):
        validate_version_str("")

    # 4. _enforce_non_private_ssrf fails closed with unparseable IP or DNS failure
    mock_invalid_ip_addrinfo = [(2, 1, 6, "", ("invalid_ip_format", 80))]
    with patch("socket.getaddrinfo", return_value=mock_invalid_ip_addrinfo):
        with pytest.raises(SSRFBlockedError):
            _enforce_non_private_ssrf("http://example.com", "example.com", "http", 80, "service")

    import socket

    with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
        with pytest.raises(SSRFBlockedError):
            _enforce_non_private_ssrf("http://example.com", "example.com", "http", 80, "service")

    with patch("socket.getaddrinfo", side_effect=TimeoutError("DNS query timed out")):
        with pytest.raises(SSRFBlockedError):
            _enforce_non_private_ssrf("http://example.com", "example.com", "http", 80, "service")


def test_is_loopback_or_private_host() -> None:
    """Verify loopback and private host classification."""
    from unittest.mock import patch

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

    # DNS resolution mock
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 80))]):
        assert is_loopback_or_private_host("custom-internal-host.com") is True

    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]):
        assert is_loopback_or_private_host("example.com") is False

    import socket

    with patch("socket.getaddrinfo", side_effect=socket.gaierror):
        assert is_loopback_or_private_host("unresolvable.invalid") is False


def test_validate_url_egress() -> None:
    """Verify validate_url_egress helper with custom error classes and scheme enforcement."""
    from unittest.mock import patch

    from devops_cli.core.validation import validate_url_egress
    from devops_cli.exceptions import SSRFBlockedError

    class CustomContextError(Exception):
        pass

    # Valid public URL
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]):
        assert (
            validate_url_egress("http://example.com/manifest.yaml")
            == "http://example.com/manifest.yaml"
        )

    # Private IP blocked with default SSRFBlockedError
    with pytest.raises(SSRFBlockedError):
        validate_url_egress("http://127.0.0.1/manifest.yaml", allow_private=False)

    # Private IP allowed
    assert (
        validate_url_egress("http://127.0.0.1/manifest.yaml", allow_private=True)
        == "http://127.0.0.1/manifest.yaml"
    )

    # Cloud metadata service blocked even with allow_private=True
    from devops_cli.core.validation import validate_url

    with pytest.raises(SSRFBlockedError, match="prohibited"):
        validate_url("http://169.254.169.254/latest/meta-data", allow_private=True)

    # Custom error class
    with pytest.raises(CustomContextError, match="resolves to private or reserved IP"):
        validate_url_egress(
            "http://169.254.169.254/latest/meta-data",
            allow_private=False,
            error_cls=CustomContextError,
        )

    # Invalid scheme
    with pytest.raises(CustomContextError, match="scheme"):
        validate_url_egress(
            "ftp://example.com/manifest.yaml",
            schemes=("http", "https"),
            error_cls=CustomContextError,
        )

    # Unresolvable hostname must fail closed
    import socket

    initial_timeout = socket.getdefaulttimeout()
    with patch("socket.getaddrinfo", side_effect=socket.gaierror):
        with pytest.raises(SSRFBlockedError, match="DNS resolution failed"):
            validate_url_egress("http://example.com/manifest.yaml")
    # Verify global socket timeout was not mutated
    assert socket.getdefaulttimeout() == initial_timeout


def test_network_guard_blocks_external_socket_calls() -> None:
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


def test_network_guard_blocks_external_dns_lookups() -> None:
    """Verify that tests cannot resolve external hostnames, while loopback names still resolve."""
    import socket

    with pytest.raises(socket.gaierror, match="External DNS lookup blocked during test execution"):
        socket.getaddrinfo("api.osv.dev", 443)
    assert socket.getaddrinfo("localhost", 80)
    assert socket.getaddrinfo("127.0.0.1", 80)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_network_guard_refuses_loopback_services_the_test_did_not_start(host: str) -> None:
    """A loopback port the test process does not listen on refuses, even when a service answers.

    The service listens through the C socket type, as a port-forward in another process does: the
    kernel accepts connections on a port the guard never saw a test open.
    """
    import _socket
    import errno
    import socket

    with socket.socket() as service, socket.socket() as client, socket.socket() as probe:
        service.bind(("127.0.0.1", 0))
        _socket.socket.listen(service)
        address = (host, service.getsockname()[1])
        with pytest.raises(ConnectionRefusedError) as refused:
            client.connect(address)
        assert (refused.value.errno, probe.connect_ex(address)) == (
            errno.ECONNREFUSED,
            errno.ECONNREFUSED,
        )


def test_network_guard_refuses_a_port_once_the_test_closes_its_server() -> None:
    """A port is the test's only while its listener is open; whoever holds it next is refused.

    The service shares the port through SO_REUSEPORT and listens through the C socket type, so it
    still answers there after the test closes its server, as a port-forward that binds the freed
    port in another process would.
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
        service.bind(server.getsockname())
        _socket.socket.listen(service)
        server.close()
        address = service.getsockname()
        with pytest.raises(ConnectionRefusedError):
            client.connect(address)
        assert probe.connect_ex(address) == errno.ECONNREFUSED


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
        is_cloud_metadata_host("fe80::1"),
        is_cloud_metadata_host("example.com", resolve_dns=False),
        is_cloud_metadata_host("8.8.8.8"),
        is_cloud_metadata_host("127.0.0.1"),
        is_cloud_metadata_host(ipaddress.ip_address("169.254.169.254")),
        is_cloud_metadata_host(ipaddress.ip_address("fd00:ec2::254")),
        is_cloud_metadata_host(ipaddress.ip_network("169.254.0.0/16")),
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
        False,
        False,
        False,
        True,
        True,
        True,
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
    from devops_cli.core.validation import is_loopback_or_private_host, validate_url
    from devops_cli.exceptions import SSRFBlockedError
    from devops_cli.sandbox.probe import _resolve_safe_socket_addr

    assert (
        is_loopback_or_private_host("metadata", resolve_dns=False),
        is_loopback_or_private_host("metadata.", resolve_dns=False),
        is_loopback_or_private_host("fd00:ec2::254", resolve_dns=False),
        is_loopback_or_private_host("[fd00:ec2::254]", resolve_dns=False),
    ) == (True, True, True, True)

    targets = ("http://metadata/v1", "http://metadata./v1", "http://[fd00:ec2::254]/v1")
    blocked_count = sum(
        1
        for t in targets
        if _is_target_blocked(validate_url, t, SSRFBlockedError, allow_private=True)
    )
    assert blocked_count == len(targets)

    assert (
        _resolve_safe_socket_addr("metadata", 80)[0],
        _resolve_safe_socket_addr("metadata.", 80)[0],
        _resolve_safe_socket_addr("fd00:ec2::254", 80)[0],
    ) == (True, True, True)


def test_widened_metadata_denials_models_telemetry_ollama() -> None:
    """Verify sandbox models, telemetry waterfall, and ollama deny unified metadata superset."""
    from urllib.parse import urlparse

    from devops_cli.ai.models.ollama import _is_cloud_metadata_host as ollama_is_metadata
    from devops_cli.sandbox.models import _resolve_local_host, _validate_local_whitelist_item
    from devops_cli.telemetry.waterfall import _resolve_safe_jaeger_target

    endpoints = ("http://metadata:8080", "http://metadata.:8080", "http://[fd00:ec2::254]:8080")
    items_blocked = sum(
        1 for ep in endpoints if _is_target_blocked(_validate_local_whitelist_item, ep, ValueError)
    )
    hosts = ("metadata", "metadata.", "fd00:ec2::254")
    hosts_blocked = sum(1 for h in hosts if _is_target_blocked(_resolve_local_host, h, ValueError))
    assert (items_blocked, hosts_blocked) == (len(endpoints), len(hosts))

    assert (
        _resolve_safe_jaeger_target(urlparse("http://metadata:14268"))[0],
        _resolve_safe_jaeger_target(urlparse("http://metadata.:14268"))[0],
        _resolve_safe_jaeger_target(urlparse("http://[fd00:ec2::254]:14268"))[0],
    ) == (True, True, True)

    assert (
        ollama_is_metadata("metadata"),
        ollama_is_metadata("metadata."),
        ollama_is_metadata("fd00:ec2::254"),
    ) == (True, True, True)

"""Tests for core validation utilities."""

from __future__ import annotations

import ipaddress
from pathlib import Path

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
    assert is_non_public_ip(ipaddress.ip_address("127.0.0.1")) is True
    assert is_non_public_ip(ipaddress.ip_address("10.0.0.1")) is True
    assert is_non_public_ip(ipaddress.ip_address("192.168.1.1")) is True
    assert is_non_public_ip(ipaddress.ip_address("8.8.8.8")) is False


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
                "http://internal.service.corp:8080", "internal.service.corp", "http", 8080, "test"
            )

    # Hostname resolving to public IP succeeds
    mock_pub_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 80))]
    with patch("socket.getaddrinfo", return_value=mock_pub_addrinfo):
        _enforce_non_private_ssrf("http://example.com", "example.com", "http", 80, "test")

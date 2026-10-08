"""Tests for shared HTTP utilities and client configurations."""

from __future__ import annotations

import pytest

from devops_cli.http.client import new_http_client, request_timeout
from devops_cli.http.egress import EgressLevel
from devops_cli.http.validation import validate_service_url


def test_public_https_url_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import patch

    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    mock_addr = [(2, 1, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=mock_addr):
        validate_service_url("https://example.com", "Grafana")


def test_public_http_url_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import patch

    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    mock_addr = [(2, 1, 6, "", ("93.184.216.34", 8080))]
    with patch("socket.getaddrinfo", return_value=mock_addr):
        validate_service_url("http://example.com:8080", "ArgoCD")


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.5:3000",
        "http://10.0.0.1",
        "http://172.16.0.1:8080",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
        "http://[fe80::1]/admin",
        "http://[fc00::1]:8080",
    ],
)
def test_private_ip_rejected_by_default(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    with pytest.raises(ValueError, match=r"(Refusing non-public|Access to link-local)"):
        validate_service_url(url, "Grafana")


@pytest.mark.parametrize(
    "override",
    ["true", "1", "yes", "on"],
)
def test_private_ip_is_allowed_by_the_callers_flag_not_the_environment(
    override: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the environment never widens a check: the caller passes the configured flag.

    DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK sets `ai.allow_private_network`, which configured callers
    pass as `allow`; a check made with `allow=False` stays public-only whatever is exported.
    """
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", override)
    with pytest.raises(ValueError, match="Refusing non-public"):
        validate_service_url("http://192.168.1.5:3000", "Grafana")
    validate_service_url("http://192.168.1.5:3000", "Grafana", allow=True)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "not-a-url",
        "",
    ],
)
def test_invalid_scheme_rejected(url: str) -> None:
    with pytest.raises(ValueError, match=r"Invalid test URL scheme|missing valid hostname"):
        validate_service_url(url, "test")


def test_http_client_options() -> None:
    """Test request_timeout and new_http_client with varied timeout specifications."""
    t1 = request_timeout(read=30.0)
    assert t1.read == 30.0

    from devops_cli.config.defaults import DEFAULT_CONNECT_TIMEOUT_SECONDS
    from devops_cli.http.client import new_async_http_client

    c1 = new_http_client(level=EgressLevel.PUBLIC, read_timeout=15.0)
    assert c1.timeout.read == 15.0
    assert c1.timeout.connect == DEFAULT_CONNECT_TIMEOUT_SECONDS

    c2 = new_http_client(level=EgressLevel.PUBLIC, timeout=10.0)
    assert c2.timeout.read == 10.0
    assert c2.timeout.connect == DEFAULT_CONNECT_TIMEOUT_SECONDS

    c3 = new_http_client(level=EgressLevel.PUBLIC, timeout=t1)
    assert c3.timeout.read == 30.0
    assert c3.timeout.connect == DEFAULT_CONNECT_TIMEOUT_SECONDS

    ac1 = new_async_http_client(level=EgressLevel.PUBLIC, timeout=12.0)
    assert ac1.timeout.read == 12.0
    assert ac1.timeout.connect == DEFAULT_CONNECT_TIMEOUT_SECONDS


def test_http_client_invalid_timeout_type() -> None:
    """Verify HTTPTimeoutTypeError (and TypeError/ValidationError) is raised when unsupported timeout types are passed."""
    from devops_cli.exceptions.validation import ValidationError
    from devops_cli.http.client import HTTPTimeoutTypeError

    with pytest.raises(HTTPTimeoutTypeError, match="timeout must be") as exc_info1:
        new_http_client(level=EgressLevel.PUBLIC, timeout="invalid-string")  # type: ignore[arg-type]
    assert isinstance(exc_info1.value, TypeError)
    assert isinstance(exc_info1.value, ValidationError)

    with pytest.raises(HTTPTimeoutTypeError, match="read_timeout must be") as exc_info2:
        new_http_client(level=EgressLevel.PUBLIC, read_timeout="invalid-string")  # type: ignore[arg-type]
    assert isinstance(exc_info2.value, TypeError)
    assert isinstance(exc_info2.value, ValidationError)

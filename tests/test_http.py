"""Tests for shared HTTP utilities."""

from __future__ import annotations

import pytest

from devops_cli.http.validation import validate_service_url


def test_public_https_url_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    validate_service_url("https://grafana.example.com", "Grafana")


def test_public_http_url_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    validate_service_url("http://argocd.example.com:8080", "ArgoCD")


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
    with pytest.raises(ValueError, match="Refusing non-public"):
        validate_service_url(url, "Grafana")


@pytest.mark.parametrize(
    "override",
    ["true", "1", "yes", "on"],
)
def test_private_ip_allowed_when_env_set(override: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", override)
    validate_service_url("http://192.168.1.5:3000", "Grafana")


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
    with pytest.raises(ValueError):
        validate_service_url(url, "test")

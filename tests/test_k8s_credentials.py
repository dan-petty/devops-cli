"""Unit tests for automated Kubernetes stack credential synchronization (ArgoCD & Grafana)."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app as k8s_app
from devops_cli.k8s.credentials import (
    fetch_argocd_password,
    fetch_grafana_password,
    get_or_mint_argocd_token,
    get_or_mint_grafana_auth,
    mint_argocd_token,
    mint_grafana_token,
    sync_k8s_credentials,
    verify_argocd_token,
    verify_grafana_token,
)

runner = CliRunner()


@patch("devops_cli.k8s.credentials.run_subprocess")
@patch("devops_cli.k8s.credentials._keyring_set")
def test_fetch_argocd_password_success(mock_keyring: MagicMock, mock_subproc: MagicMock) -> None:
    secret_pw = "super-secret-argocd-pw"
    encoded = base64.b64encode(secret_pw.encode("utf-8")).decode("utf-8")
    import json

    payload = json.dumps({"data": {"password": encoded}})
    mock_subproc.return_value = MagicMock(returncode=0, stdout=payload, stderr="")

    pw = fetch_argocd_password(namespace="argocd", save_to_keyring=True)

    assert pw == secret_pw
    mock_keyring.assert_called_with("argocd_password", secret_pw)


@patch("devops_cli.k8s.credentials.run_subprocess")
def test_fetch_argocd_password_not_found(mock_subproc: MagicMock) -> None:
    mock_subproc.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="Error from server (NotFound): secrets not found",
    )

    pw = fetch_argocd_password(namespace="argocd", save_to_keyring=True)
    assert pw is None


@patch("devops_cli.k8s.credentials.run_subprocess")
@patch("devops_cli.k8s.credentials._keyring_set")
def test_fetch_grafana_password_success(mock_keyring: MagicMock, mock_subproc: MagicMock) -> None:
    secret_pw = "prom-grafana-pw-123"
    encoded = base64.b64encode(secret_pw.encode("utf-8")).decode("utf-8")
    import json

    payload = json.dumps({"data": {"admin-password": encoded}})
    mock_subproc.return_value = MagicMock(returncode=0, stdout=payload, stderr="")

    pw = fetch_grafana_password(namespaces=["monitoring"], save_to_keyring=True)

    assert pw == secret_pw
    mock_keyring.assert_called_with("grafana_password", secret_pw)


@patch("devops_cli.k8s.credentials.fetch_argocd_password")
@patch("devops_cli.config.settings._keyring_get")
def test_sync_k8s_credentials_summary(mock_keyring_get: MagicMock, mock_argocd: MagicMock) -> None:
    mock_argocd.return_value = "argo-pw"
    mock_keyring_get.return_value = "graf-pw"

    res = sync_k8s_credentials(stack="infra")

    assert (res.get("argocd"), res.get("grafana")) == (True, True)


def test_cli_k8s_sync_secrets_dry_run() -> None:
    res = runner.invoke(k8s_app, ["sync-secrets", "--dry-run"])
    assert (res.exit_code, "sync_secrets" in res.output or "argocd" in res.output) == (
        0,
        True,
    )


@patch("devops_cli.k8s.credentials._keyring_set")
@patch("httpx2.Client.post")
def test_mint_argocd_token_success(mock_post: MagicMock, mock_keyring: MagicMock) -> None:
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"token": "argo-jwt-123"})
    token = mint_argocd_token("http://example.com:8080", "admin-pass", save_to_keyring=True)
    assert (token, mock_keyring.called) == ("argo-jwt-123", True)
    mock_keyring.assert_called_with("argocd_token", "argo-jwt-123")


@patch("httpx2.Client.post")
def test_mint_argocd_token_failure(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(status_code=401, json=lambda: {})
    token_401 = mint_argocd_token("http://example.com:8080", "bad-pass")
    token_empty = mint_argocd_token("", "pass")
    assert (token_401, token_empty) == (None, None)


@patch("httpx2.Client.post")
def test_mint_tokens_url_validation(mock_post: MagicMock) -> None:
    """Ensure scheme-less service URLs fail with ConfigurationError and HTTPS is normalized."""
    from devops_cli.exceptions.config import ConfigurationError

    with pytest.raises(ConfigurationError) as exc_argo:
        mint_argocd_token("example.com", "admin-pass")
    service_calls_1 = [
        c[0][0] for c in mock_post.call_args_list if not c[0][0].endswith("/v1/traces")
    ]
    assert ("argocd.url" in str(exc_argo.value), len(service_calls_1)) == (True, 0)

    mock_post.reset_mock()
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"token": "argo-jwt-123"})
    mint_argocd_token("HTTPS://example.com:8080", "admin-pass", save_to_keyring=False)
    service_calls_2 = [
        c[0][0] for c in mock_post.call_args_list if not c[0][0].endswith("/v1/traces")
    ]
    assert (
        len(service_calls_2) > 0,
        service_calls_2[0].startswith("https://example.com:8080/"),
    ) == (True, True)

    mock_post.reset_mock()
    with pytest.raises(ConfigurationError) as exc_grafana:
        mint_grafana_token("example.com", "admin-pass")
    service_calls_3 = [
        c[0][0] for c in mock_post.call_args_list if not c[0][0].endswith("/v1/traces")
    ]
    assert ("grafana.url" in str(exc_grafana.value), len(service_calls_3)) == (True, 0)

    mock_post.reset_mock()

    def fake_post(url: str, **kwargs: object) -> MagicMock:
        if url.endswith("/api/serviceaccounts"):
            return MagicMock(status_code=201, json=lambda: {"id": 10})
        if "/tokens" in url:
            return MagicMock(status_code=200, json=lambda: {"key": "glsa-token-xyz"})
        return MagicMock(status_code=200, json=lambda: {})

    mock_post.side_effect = fake_post
    mint_grafana_token("HTTPS://example.com:3000", "admin-pass", save_to_keyring=False)
    service_calls_4 = [
        c[0][0] for c in mock_post.call_args_list if not c[0][0].endswith("/v1/traces")
    ]
    assert (
        len(service_calls_4) > 0,
        service_calls_4[0].startswith("https://example.com:3000/"),
    ) == (True, True)


@patch("devops_cli.k8s.credentials._keyring_set")
@patch("httpx2.Client.post")
def test_mint_grafana_token_sa_success(mock_post: MagicMock, mock_keyring: MagicMock) -> None:
    def fake_post(url: str, **kwargs: object) -> MagicMock:
        if url.endswith("/api/serviceaccounts"):
            return MagicMock(status_code=201, json=lambda: {"id": 10})
        if "/tokens" in url:
            return MagicMock(status_code=200, json=lambda: {"key": "glsa-token-xyz"})
        return MagicMock(status_code=404, json=lambda: {})

    mock_post.side_effect = fake_post
    token = mint_grafana_token("http://example.com:3000", "admin-pass", save_to_keyring=True)
    assert (token, mock_keyring.called) == ("glsa-token-xyz", True)
    mock_keyring.assert_called_with("grafana_token", "glsa-token-xyz")


@patch("devops_cli.k8s.credentials._keyring_set")
@patch("httpx2.Client.post")
def test_mint_grafana_token_sa_failure(mock_post: MagicMock, mock_keyring: MagicMock) -> None:
    mock_post.return_value = MagicMock(status_code=404, json=lambda: {})
    token = mint_grafana_token("http://example.com:3000", "admin-pass", save_to_keyring=True)
    assert (token, mock_keyring.called) == (None, False)


@patch("devops_cli.k8s.credentials._keyring_set")
@patch("httpx2.Client.delete")
@patch("httpx2.Client.get")
@patch("httpx2.Client.post")
def test_mint_grafana_token_revokes_prior_tokens(
    mock_post: MagicMock,
    mock_get: MagicMock,
    mock_delete: MagicMock,
    mock_keyring: MagicMock,
) -> None:
    def fake_post(url: str, **kwargs: object) -> MagicMock:
        if url.endswith("/api/serviceaccounts"):
            return MagicMock(status_code=201, json=lambda: {"id": 10})
        if "/tokens" in url:
            return MagicMock(status_code=200, json=lambda: {"key": "glsa-new-token"})
        return MagicMock(status_code=404, json=lambda: {})

    mock_post.side_effect = fake_post
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: [
            {"id": 1, "name": "devops-cli-old-1"},
            {"id": 2, "name": "devops-cli-old-2"},
        ],
    )
    mock_delete.return_value = MagicMock(status_code=200)

    token = mint_grafana_token("http://example.com:3000", "admin-pass", save_to_keyring=True)
    assert (token, mock_delete.call_count, mock_keyring.called) == (
        "glsa-new-token",
        2,
        True,
    )


@patch("devops_cli.k8s.credentials._keyring_set", side_effect=Exception("Keyring locked"))
@patch("httpx2.Client.post")
def test_mint_tokens_keyring_failure(mock_post: MagicMock, _mock_keyring: MagicMock) -> None:
    def fake_post(url: str, **kwargs: object) -> MagicMock:
        if url.endswith("/api/v1/session"):
            return MagicMock(status_code=200, json=lambda: {"token": "argo-tok"})
        if url.endswith("/api/serviceaccounts"):
            return MagicMock(status_code=201, json=lambda: {"id": 10})
        if "/tokens" in url:
            return MagicMock(status_code=200, json=lambda: {"key": "graf-tok"})
        return MagicMock(status_code=404, json=lambda: {})

    mock_post.side_effect = fake_post
    argo_tok = mint_argocd_token("http://example.com:8080", "admin-pass", save_to_keyring=True)
    graf_tok = mint_grafana_token("http://example.com:3000", "admin-pass", save_to_keyring=True)
    assert (argo_tok, graf_tok) == (None, None)


def test_get_or_mint_argocd_token() -> None:
    from devops_cli.config.settings import Settings

    settings_with_tok = Settings()
    with patch("devops_cli.config.settings.get_argocd_token", return_value="existing-tok"):
        res = get_or_mint_argocd_token(settings_with_tok)
        assert res == "existing-tok"

    settings_with_pw = Settings()
    settings_with_pw.argocd.url = "http://example.com:8080"
    with (
        patch("devops_cli.config.settings.get_argocd_token", return_value=None),
        patch("devops_cli.config.settings.get_argocd_password", return_value="argo-pw"),
        patch(
            "devops_cli.k8s.credentials.mint_argocd_token", return_value="minted-tok"
        ) as mock_mint,
    ):
        res = get_or_mint_argocd_token(settings_with_pw)
        assert (res, mock_mint.called) == ("minted-tok", True)


def test_get_or_mint_grafana_auth() -> None:
    from devops_cli.config.settings import Settings

    settings = Settings()
    with patch("devops_cli.config.settings.get_grafana_token", return_value="graf-tok"):
        tok, basic = get_or_mint_grafana_auth(settings)
        assert (tok, basic) == ("graf-tok", None)

    settings.grafana.url = "http://example.com:3000"
    with (
        patch("devops_cli.config.settings.get_grafana_token", return_value=None),
        patch("devops_cli.config.settings.get_grafana_password", return_value="admin-pw"),
        patch(
            "devops_cli.k8s.credentials.mint_grafana_token",
            return_value="minted-graf-tok",
        ),
    ):
        tok, basic = get_or_mint_grafana_auth(settings)
        assert (tok, basic) == ("minted-graf-tok", None)

    with (
        patch("devops_cli.config.settings.get_grafana_token", return_value=None),
        patch("devops_cli.config.settings.get_grafana_password", return_value="admin-pw"),
        patch("devops_cli.k8s.credentials.mint_grafana_token", return_value=None),
    ):
        tok, basic = get_or_mint_grafana_auth(settings)
        expected_b64 = base64.b64encode(b"admin:admin-pw").decode("utf-8")
        assert (tok, basic) == (None, f"Basic {expected_b64}")


@patch("devops_cli.k8s.credentials.fetch_argocd_password", return_value="argo-pw")
@patch("devops_cli.config.settings._keyring_get", return_value="graf-pw")
@patch("devops_cli.k8s.credentials.mint_argocd_token", return_value="argo-tok")
@patch("devops_cli.k8s.credentials.mint_grafana_token", return_value="graf-tok")
def test_sync_k8s_credentials_with_tokens(
    _mock_gtok: MagicMock,
    _mock_atok: MagicMock,
    _mock_gpw: MagicMock,
    _mock_apw: MagicMock,
) -> None:
    res = sync_k8s_credentials(
        stack="infra",
        argocd_url="http://example.com:8080",
        grafana_url="http://example.com:3000",
    )
    assert (
        res.get("argocd"),
        res.get("argocd_token"),
        res.get("grafana"),
        res.get("grafana_token"),
    ) == (True, True, True, True)


@patch("httpx2.Client.get")
def test_verify_tokens(mock_get: MagicMock) -> None:
    mock_get.return_value = MagicMock(status_code=200)
    argo_ok = verify_argocd_token("http://example.com:8080", "valid-argo-tok")
    graf_ok = verify_grafana_token("http://example.com:3000", "valid-graf-tok")

    mock_get.return_value = MagicMock(status_code=401)
    argo_fail = verify_argocd_token("http://example.com:8080", "invalid-argo-tok")
    graf_fail = verify_grafana_token("http://example.com:3000", "invalid-graf-tok")

    assert (argo_ok, graf_ok, argo_fail, graf_fail) == (True, True, False, False)


@patch("devops_cli.k8s.credentials.fetch_argocd_password", return_value="argo-pw")
@patch("devops_cli.config.settings._keyring_get", return_value="graf-pw")
@patch("devops_cli.k8s.credentials._resolve_existing_token")
@patch("devops_cli.k8s.credentials.verify_argocd_token", return_value=True)
@patch("devops_cli.k8s.credentials.verify_grafana_token", return_value=True)
@patch("devops_cli.k8s.credentials.mint_argocd_token")
@patch("devops_cli.k8s.credentials.mint_grafana_token")
def test_sync_k8s_credentials_reuses_existing_tokens(
    mock_mint_graf: MagicMock,
    mock_mint_argo: MagicMock,
    _mock_vg: MagicMock,
    _mock_va: MagicMock,
    mock_resolve: MagicMock,
    _mock_gpw: MagicMock,
    _mock_apw: MagicMock,
) -> None:
    mock_resolve.side_effect = lambda svc: f"existing-{svc}-tok"
    res = sync_k8s_credentials(
        stack="infra",
        argocd_url="http://example.com:8080",
        grafana_url="http://example.com:3000",
    )
    assert (
        res.get("argocd"),
        res.get("argocd_token"),
        res.get("grafana"),
        res.get("grafana_token"),
        mock_mint_argo.called,
        mock_mint_graf.called,
    ) == (True, True, True, True, False, False)

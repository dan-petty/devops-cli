"""Unit tests for automated Kubernetes stack credential synchronization (ArgoCD & Grafana)."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

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
        returncode=1, stdout="", stderr="Error from server (NotFound): secrets not found"
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
@patch("devops_cli.k8s.credentials.fetch_grafana_password")
def test_sync_k8s_credentials_summary(mock_grafana: MagicMock, mock_argocd: MagicMock) -> None:
    mock_argocd.return_value = "argo-pw"
    mock_grafana.return_value = "graf-pw"

    res = sync_k8s_credentials(stack="infra")

    assert (res.get("argocd"), res.get("grafana")) == (True, True)


def test_cli_k8s_sync_secrets_dry_run() -> None:
    res = runner.invoke(k8s_app, ["sync-secrets", "--dry-run"])
    assert (res.exit_code, "sync_secrets" in res.output or "argocd" in res.output) == (0, True)


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
def test_mint_grafana_token_legacy_fallback(mock_post: MagicMock, mock_keyring: MagicMock) -> None:
    def fake_post(url: str, **kwargs: object) -> MagicMock:
        if url.endswith("/api/serviceaccounts"):
            return MagicMock(status_code=404, json=lambda: {})
        if url.endswith("/api/auth/keys"):
            return MagicMock(status_code=200, json=lambda: {"key": "legacy-key-abc"})
        return MagicMock(status_code=404, json=lambda: {})

    mock_post.side_effect = fake_post
    token = mint_grafana_token("http://example.com:3000", "admin-pass", save_to_keyring=True)
    assert (token, mock_keyring.called) == ("legacy-key-abc", True)
    mock_keyring.assert_called_with("grafana_token", "legacy-key-abc")


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
        patch("devops_cli.k8s.credentials.mint_grafana_token", return_value="minted-graf-tok"),
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
@patch("devops_cli.k8s.credentials.fetch_grafana_password", return_value="graf-pw")
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

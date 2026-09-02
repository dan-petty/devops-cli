"""Unit tests for automated Kubernetes stack credential synchronization (ArgoCD & Grafana)."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app as k8s_app
from devops_cli.k8s.credentials import (
    fetch_argocd_password,
    fetch_grafana_password,
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

    assert res.get("argocd") is True
    assert res.get("grafana") is True


def test_cli_k8s_sync_secrets_dry_run() -> None:
    res = runner.invoke(k8s_app, ["sync-secrets", "--dry-run"])
    assert res.exit_code == 0
    assert "sync_secrets" in res.output or "argocd" in res.output

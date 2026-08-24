"""Unit tests for Kubernetes TLS secret subcommands (create-tls-secret and enable-tls)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.core.dry_run import set_dry_run
from devops_cli.crypto.tls_certificates import generate_server_certificate

runner = CliRunner()


def test_k8s_create_tls_secret_dry_run(tmp_path: Path) -> None:
    """devops k8s create-tls-secret --dry-run returns structured dry-run JSON."""
    set_dry_run(True)
    try:
        result = runner.invoke(
            app,
            [
                "create-tls-secret",
                "test-tls",
                "--namespace",
                "monitoring",
            ],
        )
        assert result.exit_code == 0
        assert "devops k8s create-tls-secret" in result.output
        assert "create_k8s_tls_secret" in result.output
    finally:
        set_dry_run(False)


def test_k8s_enable_tls_dry_run(tmp_path: Path) -> None:
    """devops k8s enable-tls --dry-run returns structured dry-run JSON with stack namespaces."""
    set_dry_run(True)
    try:
        result = runner.invoke(
            app,
            [
                "enable-tls",
                "--stack",
                "all",
                "--secret-name",
                "custom-tls",
            ],
        )
        assert result.exit_code == 0
        assert "devops k8s enable-tls" in result.output
        assert "enable_k8s_tls_stack" in result.output
    finally:
        set_dry_run(False)


@patch(
    "devops_cli.commands.k8s._run_cmd",
    return_value=MagicMock(returncode=0),
)
def test_k8s_create_tls_secret_live(mock_cmd: MagicMock, tmp_path: Path) -> None:
    """devops k8s create-tls-secret executes kubectl create secret tls."""
    cert_path, key_path, _ = generate_server_certificate(
        common_name="app.local",
        output_dir=tmp_path,
    )

    result = runner.invoke(
        app,
        [
            "create-tls-secret",
            "my-app-tls",
            "--namespace",
            "default",
            "--cert",
            str(cert_path),
            "--key",
            str(key_path),
        ],
    )
    assert result.exit_code == 0
    assert "Created TLS secret" in result.output
    assert mock_cmd.called


@patch(
    "devops_cli.commands.k8s._run_cmd",
    return_value=MagicMock(returncode=0),
)
def test_k8s_enable_tls_live(mock_cmd: MagicMock, tmp_path: Path) -> None:
    """devops k8s enable-tls generates bundle and creates secrets across namespaces."""
    result = runner.invoke(
        app,
        [
            "enable-tls",
            "--stack",
            "infra",
            "--tls-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Kubernetes TLS Secret Deployment" in result.output
    assert (tmp_path / "tls.crt").exists()
    assert (tmp_path / "tls.key").exists()

"""Unit tests for Kubernetes TLS secret subcommands (create-tls-secret and enable-tls)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.crypto.tls_certificates import generate_server_certificate
from devops_cli.dry_run import set_dry_run

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
        common_name="example.com",
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
    assert "Applied TLS secret" in result.output
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


def _kubectl_recorder(calls: list[tuple[list[str], str | None]], *, render_fails: bool) -> Any:
    """Stand in for kubectl: a client-side render of a TLS secret fails when asked to."""

    def kubectl(cmd: list[str], **kwargs: Any) -> MagicMock:
        calls.append((cmd, kwargs.get("input")))
        rendering = {"create", "secret", "tls"} <= set(cmd)
        if rendering and render_fails:
            return MagicMock(
                returncode=1, stdout="", stderr="error: tls: private key does not match"
            )
        return MagicMock(returncode=0, stdout="kind: Secret\n" if rendering else "", stderr="")

    return kubectl


@pytest.mark.parametrize(
    ("args", "exit_code"),
    [
        (["create-tls-secret", "my-app-tls"], 1),
        (["enable-tls", "--stack", "llm", "--secret-name", "my-app-tls", "--overwrite"], 0),
    ],
    ids=["create-tls-secret", "enable-tls-overwrite"],
)
def test_a_tls_secret_kubectl_rejects_leaves_the_live_one_in_place(
    tmp_path: Path, args: list[str], exit_code: int
) -> None:
    """A replacement kubectl refuses to build never costs the namespace its secret (#961).

    Both commands deleted the secret and then created the new one. A certificate and key that
    do not match make kubectl refuse the create, and ingresses then fell back to the default
    certificate. Nothing is deleted or applied unless the new secret builds.
    """
    (tmp_path / "tls.crt").write_text("certificate", encoding="utf-8")
    (tmp_path / "tls.key").write_text("rotated key", encoding="utf-8")
    files = (
        ["--cert", str(tmp_path / "tls.crt"), "--key", str(tmp_path / "tls.key")]
        if args[0] == "create-tls-secret"
        else ["--tls-dir", str(tmp_path)]
    )
    calls: list[tuple[list[str], str | None]] = []

    with patch(
        "devops_cli.commands.k8s.cluster_runtime._run_cmd",
        side_effect=_kubectl_recorder(calls, render_fails=True),
    ):
        result = runner.invoke(app, [*args, *files])

    changes = [cmd for cmd, _ in calls if {"delete", "apply"} & set(cmd)]
    assert (result.exit_code, changes, "private key does not match" in result.output) == (
        exit_code,
        [],
        True,
    )


def test_a_tls_secret_is_applied_over_the_live_one_from_its_render(tmp_path: Path) -> None:
    """The secret is rendered client-side, then applied in place of the one it replaces (#961)."""
    cert_path, key_path = tmp_path / "tls.crt", tmp_path / "tls.key"
    cert_path.write_text("certificate", encoding="utf-8")
    key_path.write_text("key", encoding="utf-8")
    calls: list[tuple[list[str], str | None]] = []

    with patch(
        "devops_cli.commands.k8s.cluster_runtime._run_cmd",
        side_effect=_kubectl_recorder(calls, render_fails=False),
    ):
        result = runner.invoke(
            app,
            ["create-tls-secret", "my-app-tls", "-n", "web"]
            + ["--cert", str(cert_path), "--key", str(key_path)],
        )

    assert (result.exit_code, calls[1:]) == (
        0,
        [
            (
                ["kubectl", "create", "secret", "tls", "my-app-tls"]
                + [f"--cert={cert_path}", f"--key={key_path}", "-n", "web"]
                + ["--dry-run=client", "-o", "yaml"],
                None,
            ),
            (["kubectl", "apply", "-f", "-", "-n", "web"], "kind: Secret\n"),
        ],
    )

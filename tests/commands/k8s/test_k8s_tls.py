"""Unit tests for Kubernetes TLS secret subcommands (create-tls-secret and enable-tls)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.crypto.tls_certificates import generate_server_certificate
from devops_cli.dry_run import set_dry_run
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

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
        assert "kubectl create secret tls test-tls" in result.output
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
        assert "kubectl create secret tls custom-tls" in result.output
    finally:
        set_dry_run(False)


def test_k8s_create_tls_secret_live(tmp_path: Path, process_fake: ProcessFake) -> None:
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
    assert process_fake.call_count > 0


def test_k8s_enable_tls_live(tmp_path: Path, process_fake: ProcessFake) -> None:
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


def _kubectl_renders_tls_secrets(process_fake: ProcessFake, *, render_fails: bool) -> None:
    """Script kubectl: a client-side render of a TLS secret fails when asked to."""

    def rendering(call: ProcessCall) -> bool:
        return {"create", "secret", "tls"} <= set(call.argv)

    if render_fails:
        process_fake.answer(
            rendering,
            ProcessAnswer(returncode=1, stderr="error: tls: private key does not match"),
        )
    else:
        process_fake.answer(rendering, ProcessAnswer(stdout="kind: Secret\n"))


@pytest.mark.parametrize(
    ("args", "exit_code"),
    [
        (["create-tls-secret", "my-app-tls"], 1),
        (["enable-tls", "--stack", "llm", "--secret-name", "my-app-tls", "--overwrite"], 0),
    ],
    ids=["create-tls-secret", "enable-tls-overwrite"],
)
def test_a_tls_secret_kubectl_rejects_leaves_the_live_one_in_place(
    tmp_path: Path, process_fake: ProcessFake, args: list[str], exit_code: int
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
    _kubectl_renders_tls_secrets(process_fake, render_fails=True)

    result = runner.invoke(app, [*args, *files])

    changes = [call.argv for call in process_fake.calls if {"delete", "apply"} & set(call.argv)]
    assert (result.exit_code, changes, "private key does not match" in result.output) == (
        exit_code,
        [],
        True,
    )


def test_a_tls_secret_is_applied_over_the_live_one_from_its_render(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """The secret is rendered client-side, then applied in place of the one it replaces (#961)."""
    cert_path, key_path = tmp_path / "tls.crt", tmp_path / "tls.key"
    cert_path.write_text("certificate", encoding="utf-8")
    key_path.write_text("key", encoding="utf-8")
    _kubectl_renders_tls_secrets(process_fake, render_fails=False)

    result = runner.invoke(
        app,
        ["create-tls-secret", "my-app-tls", "-n", "web"]
        + ["--cert", str(cert_path), "--key", str(key_path)],
    )

    assert (result.exit_code, [(call.argv, call.stdin) for call in process_fake.calls[1:]]) == (
        0,
        [
            (
                ("kubectl", "create", "secret", "tls", "my-app-tls")
                + (f"--cert={cert_path}", f"--key={key_path}", "-n", "web")
                + ("--dry-run=client", "-o", "yaml"),
                None,
            ),
            (("kubectl", "apply", "-f", "-", "-n", "web"), "kind: Secret\n"),
        ],
    )

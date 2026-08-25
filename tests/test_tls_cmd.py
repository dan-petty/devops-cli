"""Unit and CLI tests for devops tls subcommands."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.tls import app
from devops_cli.crypto.tls_certificates import generate_ca_certificate, generate_server_certificate
from devops_cli.models.tls import CertificateInfo

runner = CliRunner()


def test_tls_ca_command_live(tmp_path: Path) -> None:
    """devops tls ca creates a root CA in target directory."""
    result = runner.invoke(
        app, ["ca", "--output-dir", str(tmp_path), "--common-name", "CLI Root CA"]
    )
    assert result.exit_code == 0
    assert "Generated Root Certificate Authority" in result.output
    assert (tmp_path / "ca.crt").exists()
    assert (tmp_path / "ca.key").exists()


def test_tls_ca_command_dry_run(tmp_path: Path) -> None:
    """devops tls ca --dry-run prints json payload without creating files."""
    from devops_cli.dry_run import set_dry_run

    out_dir = tmp_path / "dry_run_ca"
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["ca", "--output-dir", str(out_dir)])
        assert result.exit_code == 0
        assert "devops tls ca" in result.output
        assert "generate_root_ca" in result.output
        assert not out_dir.exists()
    finally:
        set_dry_run(False)


def test_tls_cert_command_live(tmp_path: Path) -> None:
    """devops tls cert generates signed server certificate with SANs."""
    # First create CA
    generate_ca_certificate(output_dir=tmp_path)

    result = runner.invoke(
        app,
        [
            "cert",
            "--output-dir",
            str(tmp_path),
            "--common-name",
            "app.local",
            "--san",
            "app.local",
            "--san",
            "127.0.0.1",
        ],
    )
    assert result.exit_code == 0
    assert "Generated TLS Certificate" in result.output
    assert (tmp_path / "tls.crt").exists()
    assert (tmp_path / "tls.key").exists()
    assert (tmp_path / "fullchain.crt").exists()


def test_tls_homelab_command(tmp_path: Path) -> None:
    """devops tls homelab generates full certificate bundle."""
    result = runner.invoke(app, ["homelab", "--output-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Homelab TLS Certificate Bundle Generated" in result.output
    assert (tmp_path / "ca.crt").exists()
    assert (tmp_path / "tls.crt").exists()
    assert (tmp_path / "tls.key").exists()


def test_tls_inspect_and_verify_command(tmp_path: Path) -> None:
    """devops tls inspect and devops tls verify work on generated certificates."""
    ca_cert, ca_key = generate_ca_certificate(output_dir=tmp_path)
    srv_cert, _, _ = generate_server_certificate(
        common_name="service.local",
        ca_cert_path=ca_cert,
        ca_key_path=ca_key,
        output_dir=tmp_path,
    )

    # Test inspect
    inspect_res = runner.invoke(app, ["inspect", str(srv_cert)])
    assert inspect_res.exit_code == 0
    assert "Certificate Inspection" in inspect_res.output
    assert "service.local" in inspect_res.output

    # Test verify
    verify_res = runner.invoke(app, ["verify", str(srv_cert), "--ca-cert", str(ca_cert)])
    assert verify_res.exit_code == 0
    assert "Verified:" in verify_res.output


def test_tls_enable_k8s_dry_run(tmp_path: Path) -> None:
    """devops tls enable-k8s --dry-run prints plan without cluster calls."""
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        result = runner.invoke(app, ["enable-k8s", "--tls-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "devops tls enable-k8s" in result.output
        assert "apply_k8s_tls_secrets" in result.output
    finally:
        set_dry_run(False)


def test_tls_commands_mocked(tmp_path: Path) -> None:
    """Verify tls ca, cert, and inspect commands with mock crypto functions."""
    ca_cert = tmp_path / "ca.crt"
    ca_key = tmp_path / "ca.key"
    srv_cert = tmp_path / "srv.crt"
    srv_key = tmp_path / "srv.key"

    mock_info = CertificateInfo(
        subject={"CN": "example.com"},
        issuer={"CN": "Test CA"},
        not_before=datetime.now(UTC),
        not_after=datetime.now(UTC),
        sans_dns=["example.com"],
        serial_number="12345",
        signature_algorithm="sha256WithRSAEncryption",
        is_ca=False,
    )

    with (
        patch(
            "devops_cli.commands.tls.generate_ca_certificate",
            return_value=(ca_cert, ca_key),
        ),
        patch(
            "devops_cli.commands.tls.generate_server_certificate",
            return_value=(srv_cert, srv_key, srv_cert),
        ),
        patch("devops_cli.commands.tls.inspect_certificate", return_value=mock_info),
    ):
        res_ca = runner.invoke(app, ["ca", "--output-dir", str(tmp_path)])
        assert res_ca.exit_code == 0

        res_cert = runner.invoke(
            app,
            [
                "cert",
                "--common-name",
                "example.com",
                "--ca-cert",
                str(ca_cert),
                "--ca-key",
                str(ca_key),
                "--output-dir",
                str(tmp_path),
            ],
        )
        assert res_cert.exit_code == 0

        srv_cert.write_text(
            "-----BEGIN CERTIFICATE-----\n-----END CERTIFICATE-----", encoding="utf-8"
        )
        res_insp = runner.invoke(app, ["inspect", str(srv_cert)])
        assert res_insp.exit_code == 0

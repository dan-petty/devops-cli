"""Unit tests for X.509 TLS certificate and Root CA cryptographic operations."""

from __future__ import annotations

import stat
from pathlib import Path

from devops_cli.config.constants import (
    CONST_CA_CERT_NAME,
    CONST_CA_KEY_NAME,
)
from devops_cli.crypto.tls_certificates import (
    generate_ca_certificate,
    generate_homelab_tls_bundle,
    generate_server_certificate,
    inspect_certificate,
    verify_certificate,
)


def test_generate_ca_certificate(tmp_path: Path) -> None:
    """generate_ca_certificate creates a valid self-signed Root CA with restricted permissions."""
    ca_cert, ca_key = generate_ca_certificate(
        output_dir=tmp_path,
        common_name="Test Root CA",
        organization="Test Org",
        validity_days=30,
        key_size=2048,
    )

    assert ca_cert.exists()
    assert ca_key.exists()
    assert ca_cert.name == CONST_CA_CERT_NAME
    assert ca_key.name == CONST_CA_KEY_NAME

    # Check file permissions (key 0600, cert 0644)
    key_mode = stat.S_IMODE(ca_key.stat().st_mode)
    assert key_mode & 0o077 == 0  # no permissions for group/others (0600)

    # Inspect CA certificate
    info = inspect_certificate(ca_cert)
    assert info.is_ca is True
    assert info.is_expired is False
    assert info.days_remaining >= 29
    assert info.key_type == "RSA"
    assert info.key_size == 2048
    assert info.subject.get("commonName") == "Test Root CA"
    assert info.issuer.get("commonName") == "Test Root CA"


def test_generate_server_certificate_ca_signed(tmp_path: Path) -> None:
    """generate_server_certificate creates a leaf cert signed by CA with SANs."""
    ca_cert, ca_key = generate_ca_certificate(output_dir=tmp_path, validity_days=60)

    sans = ["*.homelab.local", "homelab.local", "192.168.1.50", "127.0.0.1", "::1"]
    srv_cert, srv_key, fullchain = generate_server_certificate(
        common_name="*.homelab.local",
        sans=sans,
        ca_cert_path=ca_cert,
        ca_key_path=ca_key,
        output_dir=tmp_path,
        validity_days=15,
    )

    assert srv_cert.exists()
    assert srv_key.exists()
    assert fullchain is not None and fullchain.exists()

    # Inspect leaf certificate
    info = inspect_certificate(srv_cert)
    assert info.is_ca is False
    assert info.is_expired is False
    assert "*.homelab.local" in info.sans_dns
    assert "homelab.local" in info.sans_dns
    assert "192.168.1.50" in info.sans_ip
    assert "127.0.0.1" in info.sans_ip
    assert "::1" in info.sans_ip

    # Verify cryptographic signature against CA
    assert verify_certificate(srv_cert, ca_cert) is True
    assert verify_certificate(fullchain, ca_cert) is True


def test_generate_server_certificate_self_signed(tmp_path: Path) -> None:
    """generate_server_certificate creates valid self-signed cert when CA is omitted."""
    srv_cert, srv_key, fullchain = generate_server_certificate(
        common_name="standalone.local",
        sans=["standalone.local", "127.0.0.1"],
        output_dir=tmp_path,
        validity_days=10,
    )

    assert srv_cert.exists()
    assert srv_key.exists()
    assert fullchain is None  # no fullchain when self-signed

    info = inspect_certificate(srv_cert)
    assert info.is_ca is False
    assert info.subject.get("commonName") == "standalone.local"
    assert info.issuer.get("commonName") == "standalone.local"


def test_generate_homelab_tls_bundle(tmp_path: Path) -> None:
    """generate_homelab_tls_bundle produces Root CA and wildcard cert covering stack services."""
    summary = generate_homelab_tls_bundle(
        output_dir=tmp_path,
        custom_domains=["custom.myhome.net"],
        custom_ips=["10.0.0.15"],
    )

    assert Path(summary.ca_cert_path).exists()
    assert Path(summary.ca_key_path).exists()
    assert Path(summary.server_cert_path).exists()
    assert Path(summary.server_key_path).exists()
    assert Path(summary.fullchain_path).exists()

    # Verify all expected services are included
    for svc in ["argocd", "grafana", "prometheus", "ollama", "open-webui", "qdrant", "jaeger"]:
        assert svc in summary.services_configured

    # Verify custom additions
    assert any(san == "custom.myhome.net" for san in summary.sans)
    assert any(san == "10.0.0.15" for san in summary.sans)

    # Cryptographically verify the server cert against the generated CA
    assert verify_certificate(summary.server_cert_path, summary.ca_cert_path) is True


def test_verify_certificate_tampered(tmp_path: Path) -> None:
    """verify_certificate returns False when checked against an unrelated CA."""
    ca_dir_1 = tmp_path / "ca1"
    ca_dir_2 = tmp_path / "ca2"

    ca_cert_1, ca_key_1 = generate_ca_certificate(output_dir=ca_dir_1, common_name="CA One")
    ca_cert_2, _ = generate_ca_certificate(output_dir=ca_dir_2, common_name="CA Two")

    srv_cert, _, _ = generate_server_certificate(
        common_name="app.local",
        ca_cert_path=ca_cert_1,
        ca_key_path=ca_key_1,
        output_dir=ca_dir_1,
    )

    # Valid against CA 1, invalid against CA 2
    assert verify_certificate(srv_cert, ca_cert_1) is True
    assert verify_certificate(srv_cert, ca_cert_2) is False


def test_inspect_and_verify_certificate_sources_and_ips(tmp_path: Path) -> None:
    """Verify inspect_certificate and verify_certificate with bytes, raw PEM strings, and IP SANs."""
    ca_cert, ca_key = generate_ca_certificate(output_dir=tmp_path, common_name="IP CA")
    srv_cert, _, _ = generate_server_certificate(
        common_name="service.local",
        sans=["service.local", "127.0.0.1", "10.0.0.1"],
        ca_cert_path=ca_cert,
        ca_key_path=ca_key,
        output_dir=tmp_path,
    )

    # 1. Inspect with bytes and path string
    cert_bytes = srv_cert.read_bytes()
    info_bytes = inspect_certificate(cert_bytes)
    assert "service.local" in info_bytes.sans_dns
    assert "127.0.0.1" in info_bytes.sans_ip
    assert info_bytes.is_ca is False
    assert info_bytes.is_expired is False
    assert info_bytes.days_remaining > 0

    info_str = inspect_certificate(str(srv_cert))
    assert info_str.serial_number == info_bytes.serial_number

    # 2. Inspect with raw PEM text string
    cert_pem_text = srv_cert.read_text(encoding="utf-8")
    info_pem = inspect_certificate(cert_pem_text)
    assert info_pem.fingerprint_sha256 == info_bytes.fingerprint_sha256

    # 3. Verify with bytes and string sources
    assert verify_certificate(cert_bytes, ca_cert.read_bytes()) is True
    assert verify_certificate(str(srv_cert), str(ca_cert)) is True
    assert verify_certificate(b"invalid pem bytes", ca_cert.read_bytes()) is False


def test_tls_edge_cases_and_cached_returns(tmp_path: Path) -> None:
    """Verify SAN deduplication, cached certificate returns, and verification edge cases."""
    # 1. Existing CA without overwrite
    ca_cert1, ca_key1 = generate_ca_certificate(output_dir=tmp_path, overwrite=False)
    ca_cert2, ca_key2 = generate_ca_certificate(output_dir=tmp_path, overwrite=False)
    assert ca_cert1 == ca_cert2
    assert ca_key1 == ca_key2

    # 2. Existing Server Cert without overwrite and with duplicate/empty SANs
    sans_with_dups = ["", "test.local", "test.local", "127.0.0.1", "127.0.0.1"]
    srv_cert1, srv_key1, chain1 = generate_server_certificate(
        common_name="test.local",
        sans=sans_with_dups,
        ca_cert_path=ca_cert1,
        ca_key_path=ca_key1,
        output_dir=tmp_path,
        overwrite=False,
    )
    srv_cert2, srv_key2, chain2 = generate_server_certificate(
        common_name="test.local",
        sans=sans_with_dups,
        ca_cert_path=ca_cert1,
        ca_key_path=ca_key1,
        output_dir=tmp_path,
        overwrite=False,
    )
    assert srv_cert1 == srv_cert2
    assert srv_key1 == srv_key2
    assert chain1 == chain2


def test_tls_output_dir_path_traversal_prevention() -> None:
    """Verify that path traversal in output_dir is prevented with ValidationError."""
    import pytest

    from devops_cli.exceptions import ValidationError

    with pytest.raises(ValidationError, match="Path traversal"):
        generate_ca_certificate(output_dir=Path("../../../../tmp/etc"))

    with pytest.raises(ValidationError, match="Path traversal"):
        generate_server_certificate(output_dir=Path("../../../../tmp/etc"))

    with pytest.raises(ValidationError, match="Path traversal"):
        generate_homelab_tls_bundle(output_dir=Path("../../../../tmp/etc"))


def test_tls_overwriting_insecure_permissions(tmp_path: Path) -> None:
    """Verify that regenerating TLS certs/keys resets file permissions to 0600 (key) / 0644 (cert)."""
    import os

    k_file = tmp_path / CONST_CA_KEY_NAME
    c_file = tmp_path / CONST_CA_CERT_NAME

    k_file.write_text("old_insecure_key")
    os.chmod(k_file, 0o666)
    c_file.write_text("old_cert")
    os.chmod(c_file, 0o666)

    generate_ca_certificate(output_dir=tmp_path, overwrite=True)

    priv_mode = os.stat(k_file).st_mode & 0o777
    pub_mode = os.stat(c_file).st_mode & 0o777
    assert priv_mode == 0o600
    assert pub_mode == 0o644

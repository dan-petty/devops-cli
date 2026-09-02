"""X.509 TLS Certificate and Root CA generation, inspection, and verification utilities."""

from __future__ import annotations

import datetime
import ipaddress
import os
from datetime import UTC
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID, NameOID

from devops_cli.config.constants import (
    CONST_CA_CERT_NAME,
    CONST_CA_KEY_NAME,
    CONST_FULLCHAIN_CERT_NAME,
    CONST_PERM_PRIVATE_KEY,
    CONST_PERM_PUBLIC_KEY,
    CONST_SERVER_CERT_NAME,
    CONST_SERVER_KEY_NAME,
)
from devops_cli.config.defaults import (
    DEFAULT_CA_VALIDITY_DAYS,
    DEFAULT_CERT_COMMON_NAME,
    DEFAULT_HOMELAB_DOMAINS,
    DEFAULT_HOMELAB_IPS,
    DEFAULT_TLS_COUNTRY,
    DEFAULT_TLS_DIR,
    DEFAULT_TLS_KEY_SIZE,
    DEFAULT_TLS_ORGANIZATION,
    DEFAULT_TLS_VALIDITY_DAYS,
)
from devops_cli.core.validation import validate_safe_directory_path, validate_safe_key_path
from devops_cli.models.tls import CertificateInfo, TLSEnablementSummary


def _write_restricted_file(
    file_path: Path,
    data: bytes,
    mode: int = CONST_PERM_PRIVATE_KEY,
) -> None:
    """Atomically write file with restricted POSIX permissions (e.g. 0600 or 0644)."""
    valid_path = validate_safe_key_path(file_path)
    valid_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(valid_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.chmod(valid_path, mode)


def _build_san_extension(sans: list[str]) -> x509.SubjectAlternativeName:
    """Construct SubjectAlternativeName extension supporting DNS names and IP addresses."""
    san_list: list[x509.GeneralName] = []
    seen: set[str] = set()

    for entry in sans:
        cleaned = entry.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)

        # Check if entry is an IP address
        try:
            ip_obj = ipaddress.ip_address(cleaned)
            san_list.append(x509.IPAddress(ip_obj))
            continue
        except ValueError:
            pass

        # Treat as DNS Name (including wildcards like *.homelab.local)
        san_list.append(x509.DNSName(cleaned))

    return x509.SubjectAlternativeName(san_list)


def generate_ca_certificate(
    output_dir: Path | None = None,
    common_name: str = f"{DEFAULT_TLS_ORGANIZATION} Root CA",
    organization: str = DEFAULT_TLS_ORGANIZATION,
    country: str = DEFAULT_TLS_COUNTRY,
    validity_days: int = DEFAULT_CA_VALIDITY_DAYS,
    key_size: int = DEFAULT_TLS_KEY_SIZE,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Generate a self-signed X.509 Root Certificate Authority (CA) key pair.

    Returns:
        tuple[Path, Path]: (ca_cert_path, ca_key_path)
    """
    out = validate_safe_directory_path(output_dir or DEFAULT_TLS_DIR)
    out.mkdir(parents=True, exist_ok=True)

    cert_path = out / CONST_CA_CERT_NAME
    key_path = out / CONST_CA_KEY_NAME

    if not overwrite and cert_path.exists() and key_path.exists():
        return cert_path, key_path

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    now = datetime.datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=validity_days))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=1),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    _write_restricted_file(key_path, key_pem, mode=CONST_PERM_PRIVATE_KEY)
    _write_restricted_file(cert_path, cert_pem, mode=CONST_PERM_PUBLIC_KEY)

    return cert_path, key_path


def generate_server_certificate(
    common_name: str = DEFAULT_CERT_COMMON_NAME,
    sans: list[str] | None = None,
    ca_cert_path: Path | None = None,
    ca_key_path: Path | None = None,
    output_dir: Path | None = None,
    validity_days: int = DEFAULT_TLS_VALIDITY_DAYS,
    key_size: int = DEFAULT_TLS_KEY_SIZE,
    organization: str = DEFAULT_TLS_ORGANIZATION,
    country: str = DEFAULT_TLS_COUNTRY,
    is_server: bool = True,
    is_client: bool = True,
    overwrite: bool = False,
) -> tuple[Path, Path, Path | None]:
    """Generate an X.509 Server/Client certificate signed by a CA or self-signed.

    Returns:
        tuple[Path, Path, Path | None]: (cert_path, key_path, fullchain_path)
    """
    out = validate_safe_directory_path(output_dir or DEFAULT_TLS_DIR)
    out.mkdir(parents=True, exist_ok=True)

    cert_path = out / CONST_SERVER_CERT_NAME
    key_path = out / CONST_SERVER_KEY_NAME
    fullchain_path = out / CONST_FULLCHAIN_CERT_NAME

    if not overwrite and cert_path.exists() and key_path.exists():
        fc = fullchain_path if fullchain_path.exists() else None
        return cert_path, key_path, fc

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    # Resolve SAN list (ensure common_name is in SANs if not wildcard)
    san_entries = list(sans or [])
    if common_name and common_name not in san_entries:
        san_entries.insert(0, common_name)

    now = datetime.datetime.now(UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=validity_days))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    )

    # Extended Key Usage (Server Auth & Client Auth)
    ekus: list[x509.ObjectIdentifier] = []
    if is_server:
        ekus.append(ExtendedKeyUsageOID.SERVER_AUTH)
    if is_client:
        ekus.append(ExtendedKeyUsageOID.CLIENT_AUTH)
    if ekus:
        builder = builder.add_extension(x509.ExtendedKeyUsage(ekus), critical=False)

    if san_entries:
        builder = builder.add_extension(_build_san_extension(san_entries), critical=False)

    builder = builder.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
        critical=False,
    )

    # Sign with CA if provided, else self-sign
    ca_cert: x509.Certificate | None = None
    if ca_cert_path and ca_key_path and ca_cert_path.exists() and ca_key_path.exists():
        ca_cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        builder = builder.issuer_name(ca_cert.subject)
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),  # type: ignore[arg-type]
            critical=False,
        )
        cert = builder.sign(ca_key, hashes.SHA256())  # type: ignore[arg-type]
    else:
        builder = builder.issuer_name(subject)
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(private_key.public_key()),
            critical=False,
        )
        cert = builder.sign(private_key, hashes.SHA256())

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    _write_restricted_file(key_path, key_pem, mode=CONST_PERM_PRIVATE_KEY)
    _write_restricted_file(cert_path, cert_pem, mode=CONST_PERM_PUBLIC_KEY)

    # Build fullchain if signed by CA
    fullchain_res: Path | None = None
    if ca_cert is not None and ca_cert_path:
        ca_pem = ca_cert_path.read_bytes()
        fullchain_pem = cert_pem + b"\n" + ca_pem
        _write_restricted_file(fullchain_path, fullchain_pem, mode=CONST_PERM_PUBLIC_KEY)
        fullchain_res = fullchain_path

    return cert_path, key_path, fullchain_res


def generate_homelab_tls_bundle(
    output_dir: Path | None = None,
    custom_domains: list[str] | None = None,
    custom_ips: list[str] | None = None,
    overwrite: bool = False,
) -> TLSEnablementSummary:
    """Generate complete Homelab TLS bundle (Root CA, Wildcard + Stack Services Cert).

    Includes SANs for:
    - Homelab domains (*.homelab.local, homelab.local, *.local, localhost)
    - Stack services (argocd, grafana, prometheus, ollama, webui, qdrant, jaeger, otel)
    - K8s cluster internal FQDNs (*.svc.cluster.local, etc.)
    - Local & Minikube IPs (127.0.0.1, ::1, 192.168.49.2)
    """
    out = validate_safe_directory_path(output_dir or DEFAULT_TLS_DIR)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Generate or load Root CA
    ca_cert, ca_key = generate_ca_certificate(
        output_dir=out,
        common_name="Homelab Root CA",
        organization="Homelab Infrastructure",
        validity_days=DEFAULT_CA_VALIDITY_DAYS,
        overwrite=overwrite,
    )

    # 2. Compile SAN list
    all_sans: list[str] = list(DEFAULT_HOMELAB_DOMAINS)
    all_sans.extend(DEFAULT_HOMELAB_IPS)

    # Add in-cluster Kubernetes DNS entries
    all_sans.extend(
        [
            "*.svc.cluster.local",
            "*.argocd.svc.cluster.local",
            "*.monitoring.svc.cluster.local",
            "*.llm.svc.cluster.local",
            "*.otel.svc.cluster.local",
            "argocd-server.argocd.svc.cluster.local",
            "grafana.monitoring.svc.cluster.local",
            "prometheus.monitoring.svc.cluster.local",
            "ollama.llm.svc.cluster.local",
            "open-webui.llm.svc.cluster.local",
            "qdrant.llm.svc.cluster.local",
        ]
    )

    if custom_domains:
        all_sans.extend(custom_domains)
    if custom_ips:
        all_sans.extend(custom_ips)

    # Deduplicate while preserving order
    dedup_sans = list(dict.fromkeys(all_sans))

    # 3. Generate server certificate signed by CA
    srv_cert, srv_key, fullchain = generate_server_certificate(
        common_name="*.homelab.local",
        sans=dedup_sans,
        ca_cert_path=ca_cert,
        ca_key_path=ca_key,
        output_dir=out,
        validity_days=DEFAULT_TLS_VALIDITY_DAYS,
        organization="Homelab Infrastructure",
        overwrite=overwrite,
    )

    return TLSEnablementSummary(
        ca_cert_path=str(ca_cert),
        ca_key_path=str(ca_key),
        server_cert_path=str(srv_cert),
        server_key_path=str(srv_key),
        fullchain_path=str(fullchain or srv_cert),
        sans=dedup_sans,
        services_configured=[
            "argocd",
            "grafana",
            "prometheus",
            "ollama",
            "open-webui",
            "qdrant",
            "jaeger",
            "otel",
        ],
    )


def _read_cert_bytes(source: Path | str | bytes) -> bytes:
    """Load raw PEM bytes from a Path, filesystem path string, or raw bytes."""
    if isinstance(source, bytes):
        return source
    p = Path(source)
    return p.read_bytes() if p.exists() else str(source).encode("utf-8")


def inspect_certificate(cert_source: Path | str | bytes) -> CertificateInfo:
    """Inspect and extract detailed metadata from an X.509 certificate."""
    data = _read_cert_bytes(cert_source)

    cert = x509.load_pem_x509_certificate(data)

    subject_dict: dict[str, str] = {attr.oid._name: str(attr.value) for attr in cert.subject}
    issuer_dict: dict[str, str] = {attr.oid._name: str(attr.value) for attr in cert.issuer}

    # Extract SANs
    sans_dns: list[str] = []
    sans_ip: list[str] = []
    try:
        san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        san_value = san_ext.value
        if isinstance(san_value, x509.SubjectAlternativeName):
            for name in san_value:
                if isinstance(name, x509.DNSName):
                    sans_dns.append(name.value)
                elif isinstance(name, x509.IPAddress):
                    sans_ip.append(str(name.value))
    except x509.ExtensionNotFound:
        pass

    # Basic Constraints
    is_ca = False
    try:
        bc_ext = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS)
        bc_val = bc_ext.value
        if isinstance(bc_val, x509.BasicConstraints):
            is_ca = bc_val.ca
    except x509.ExtensionNotFound:
        pass

    now = datetime.datetime.now(UTC)
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    is_expired = now > not_after or now < not_before
    days_remaining = max(0, (not_after - now).days) if not is_expired else 0

    fingerprint = cert.fingerprint(hashes.SHA256()).hex()

    # Public Key info
    pub_key = cert.public_key()
    key_type = "RSA" if isinstance(pub_key, rsa.RSAPublicKey) else pub_key.__class__.__name__
    key_size = getattr(pub_key, "key_size", 2048)

    return CertificateInfo(
        subject=subject_dict,
        issuer=issuer_dict,
        serial_number=hex(cert.serial_number),
        not_before=not_before,
        not_after=not_after,
        sans_dns=sans_dns,
        sans_ip=sans_ip,
        is_ca=is_ca,
        is_expired=is_expired,
        days_remaining=days_remaining,
        fingerprint_sha256=fingerprint,
        key_type=key_type,
        key_size=key_size,
        signature_algorithm=cert.signature_algorithm_oid._name,
    )


def verify_certificate(
    cert_source: Path | str | bytes,
    ca_source: Path | str | bytes,
) -> bool:
    """Cryptographically verify that a leaf certificate was signed by a CA certificate."""
    try:
        cert_data = _read_cert_bytes(cert_source)
        ca_data = _read_cert_bytes(ca_source)
        cert = x509.load_pem_x509_certificate(cert_data)
        ca_cert = x509.load_pem_x509_certificate(ca_data)

        # Check date validity
        now = datetime.datetime.now(UTC)
        if now < cert.not_valid_before_utc or now > cert.not_valid_after_utc:
            return False
        if now < ca_cert.not_valid_before_utc or now > ca_cert.not_valid_after_utc:
            return False

        # Verify signature using CA's public key
        ca_pub_key = ca_cert.public_key()
        if isinstance(ca_pub_key, rsa.RSAPublicKey):
            from cryptography.hazmat.primitives.asymmetric import padding

            ca_pub_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                cert.signature_hash_algorithm,  # type: ignore[arg-type]
            )
            return True
        return False
    except Exception:
        return False

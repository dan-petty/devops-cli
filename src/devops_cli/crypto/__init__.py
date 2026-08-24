"""Cryptographic utilities: SSH key management and X.509 TLS certificate generation."""

from __future__ import annotations

from devops_cli.crypto.ssh_keys import (
    find_newest_key,
    generate_ed25519_key,
    get_key_age_days,
    list_managed_keys,
    parse_key_date,
)
from devops_cli.crypto.tls_certificates import (
    generate_ca_certificate,
    generate_homelab_tls_bundle,
    generate_server_certificate,
    inspect_certificate,
    verify_certificate,
)

__all__ = [
    "find_newest_key",
    "generate_ca_certificate",
    "generate_ed25519_key",
    "generate_homelab_tls_bundle",
    "generate_server_certificate",
    "get_key_age_days",
    "inspect_certificate",
    "list_managed_keys",
    "parse_key_date",
    "verify_certificate",
]

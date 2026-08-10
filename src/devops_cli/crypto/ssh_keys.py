"""SSH key generation and management utilities."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

# Matches id_ed25519-2024JAN15  (YYYY + 3-letter month uppercase + 2-digit day)
_KEY_RE = re.compile(r"^id_ed25519-(\d{4}[A-Z]{3}\d{2})$")


def generate_ed25519_key(key_path: Path, comment: str = "") -> None:
    """Generate an Ed25519 SSH key pair.

    Private key is written to *key_path* (mode 0600).
    Public key is written to *key_path*.pub (mode 0644).
    """
    private_key = Ed25519PrivateKey.generate()

    private_bytes = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.OpenSSH,
        encryption_algorithm=NoEncryption(),
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(private_bytes)
    key_path.chmod(0o600)

    pub_raw = (
        private_key.public_key()
        .public_bytes(
            encoding=Encoding.OpenSSH,
            format=PublicFormat.OpenSSH,
        )
        .decode()
    )
    pub_line = f"{pub_raw} {comment}".strip() + "\n"
    pub_path = key_path.with_name(f"{key_path.name}.pub")
    pub_path.write_text(pub_line, encoding="utf-8")
    pub_path.chmod(0o644)


def parse_key_date(key_path: Path) -> date | None:
    """Parse the YYYYMMMDD date suffix from a managed key filename, or None."""
    m = _KEY_RE.match(key_path.name)
    if not m:
        return None
    date_str = m.group(1)  # e.g. "2024JAN15"
    # strptime %b requires title-case: "2024Jan15"
    normalized = date_str[:4] + date_str[4:7].capitalize() + date_str[7:]
    try:
        return datetime.strptime(normalized, "%Y%b%d").date()
    except ValueError:
        return None


def get_key_age_days(key_path: Path) -> int:
    """Return the key's age in days based on its filename date suffix."""
    key_date = parse_key_date(key_path)
    if key_date is None:
        raise ValueError(f"Cannot parse date from key name: {key_path.name}")
    return (date.today() - key_date).days


def find_newest_key(key_dir: Path) -> Path | None:
    """Return the newest managed SSH private key, or None."""
    keys = list_managed_keys(key_dir)
    if not keys:
        return None
    return max(keys, key=lambda p: parse_key_date(p) or date.min)


def list_managed_keys(key_dir: Path) -> list[Path]:
    """List all managed SSH private keys matching id_ed25519-YYYYMMMDD."""
    if not key_dir.exists():
        return []
    return [p for p in key_dir.iterdir() if p.is_file() and _KEY_RE.match(p.name)]

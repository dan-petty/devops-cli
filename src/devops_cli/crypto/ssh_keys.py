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

from devops_cli.config.constants import CONST_PERM_PRIVATE_KEY, CONST_PERM_PUBLIC_KEY
from devops_cli.models.ssh import ManagedSSHKey

# Matches id_ed25519-2024JAN15 or id_ed25519-2024JAN
_KEY_RE = re.compile(r"^id_ed25519-(\d{4}[A-Z]{3}(\d{2})?)$")


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
    # Write with restricted permissions atomically to avoid a world-readable window.
    import os as _os

    fd = _os.open(key_path, _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, CONST_PERM_PRIVATE_KEY)
    with _os.fdopen(fd, "wb") as file_handle:
        file_handle.write(private_bytes)

    pub_raw = (
        private_key.public_key()
        .public_bytes(
            encoding=Encoding.OpenSSH,
            format=PublicFormat.OpenSSH,
        )
        .decode()
    )
    clean_comment = re.sub(r"[\r\n\t\x00-\x1f]", " ", comment).strip()
    pub_line = f"{pub_raw} {clean_comment}".strip() + "\n"
    pub_path = key_path.with_name(f"{key_path.name}.pub")
    pub_fd = _os.open(pub_path, _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, CONST_PERM_PUBLIC_KEY)
    with _os.fdopen(pub_fd, "w", encoding="utf-8") as pub_fh:
        pub_fh.write(pub_line)


def parse_key_date(key_path: Path) -> date | None:
    """Parse the YYYYMMM[DD] date suffix from a managed key filename, or None."""
    match = _KEY_RE.match(key_path.name)
    if not match:
        return None
    date_str = match.group(1)  # e.g. "2024JAN15" or "2024JAN"
    # strptime %b requires title-case: "2024Jan15" / "2024Jan"
    normalized = date_str[:4] + date_str[4:7].capitalize() + date_str[7:]
    date_format = "%Y%b%d" if len(date_str) == 9 else "%Y%b"
    try:
        return datetime.strptime(normalized, date_format).date()
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
    return max(keys, key=lambda path: parse_key_date(path) or date.min)


def list_managed_keys(key_dir: Path) -> list[Path]:
    """List all managed SSH private keys matching id_ed25519-YYYYMMMDD."""
    if not key_dir.exists():
        return []
    return [path for path in key_dir.iterdir() if path.is_file() and _KEY_RE.match(path.name)]


def list_managed_keys_info(key_dir: Path) -> list[ManagedSSHKey]:
    """Return ManagedSSHKey objects for all managed keys, with date and age pre-computed."""
    today = date.today()
    result: list[ManagedSSHKey] = []
    for path in sorted(list_managed_keys(key_dir)):
        key_date = parse_key_date(path)
        age = (today - key_date).days if key_date is not None else None
        result.append(ManagedSSHKey(path=path, key_date=key_date, age_days=age))
    return result

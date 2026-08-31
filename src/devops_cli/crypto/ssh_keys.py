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
from devops_cli.core.validation import validate_safe_key_path
from devops_cli.exceptions import ValidationError
from devops_cli.models.ssh import ManagedSSHKey

# Matches [prefix-]id_ed25519-YYYYMMDD
_KEY_RE = re.compile(r"^(?:(?P<prefix>[a-zA-Z0-9_-]+)-)?id_ed25519-(?P<date>\d{8})$")


def get_ssh_key_prefix(workspace_path: Path | None = None) -> str:
    """Determine the SSH key prefix from config setting, devcontainer name, or basename pwd."""
    from devops_cli.config.settings import load_settings

    try:
        settings = load_settings()
        if settings.ssh.key_prefix:
            raw_prefix = settings.ssh.key_prefix.strip()
            sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_prefix).strip("-").lower()
            if sanitized:
                return sanitized
    except Exception:
        pass

    target_dir = (workspace_path or Path.cwd()).resolve()

    candidate_paths: list[Path] = [
        target_dir / ".devcontainer" / "devcontainer.json",
        target_dir / ".devcontainer.json",
        target_dir / "devcontainer.json",
    ]
    for parent in target_dir.parents:
        candidate_paths.append(parent / ".devcontainer" / "devcontainer.json")
        candidate_paths.append(parent / ".devcontainer.json")

    for dev_path in candidate_paths:
        if dev_path.is_file():
            try:
                import json

                text = dev_path.read_text(encoding="utf-8")
                cleaned = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
                data = json.loads(cleaned)
                if isinstance(data, dict) and data.get("name"):
                    raw_name = str(data["name"]).strip()
                    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_name).strip("-").lower()
                    if sanitized:
                        return sanitized
            except Exception:
                pass

    base_name = target_dir.name.strip()
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", base_name).strip("-").lower()
    return sanitized or "devops-cli"


def format_managed_key_filename(prefix: str | None = None, key_date: date | None = None) -> str:
    """Format a managed SSH key filename with prefix and YYYYMMDD date suffix."""
    d = key_date or date.today()
    date_str = d.strftime("%Y%m%d")
    active_prefix = prefix if prefix is not None else get_ssh_key_prefix()
    if active_prefix:
        return f"{active_prefix}-id_ed25519-{date_str}"
    return f"id_ed25519-{date_str}"


def generate_ed25519_key(key_path: Path, comment: str = "") -> None:
    """Generate an Ed25519 SSH key pair.

    Private key is written to *key_path* (mode 0600).
    Public key is written to *key_path*.pub (mode 0644).
    """
    key_path = validate_safe_key_path(key_path)

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
    _os.chmod(key_path, CONST_PERM_PRIVATE_KEY)

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
    _os.chmod(pub_path, CONST_PERM_PUBLIC_KEY)


def parse_key_date(key_path: Path) -> date | None:
    """Parse the YYYYMMDD date suffix from a managed key filename, or None."""
    match = _KEY_RE.match(key_path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group("date"), "%Y%m%d").date()
    except ValueError:
        return None


def get_key_age_days(key_path: Path) -> int:
    """Return the key's age in days based on its filename date suffix."""
    key_date = parse_key_date(key_path)
    if key_date is None:
        raise ValidationError(f"Cannot parse date from key name: {key_path.name}", field="key_name")
    return max(0, (date.today() - key_date).days)


def find_newest_key(key_dir: Path) -> Path | None:
    """Return the newest managed SSH private key, or None."""
    keys = list_managed_keys(key_dir)
    if not keys:
        return None
    return max(keys, key=lambda path: parse_key_date(path) or date.min)


def list_managed_keys(key_dir: Path) -> list[Path]:
    """List all managed SSH private keys matching id_ed25519-YYYYMMMDD."""
    expanded = key_dir.expanduser()
    if not expanded.exists():
        return []
    return [path for path in expanded.iterdir() if path.is_file() and _KEY_RE.match(path.name)]


def list_managed_keys_info(key_dir: Path) -> list[ManagedSSHKey]:
    """Return ManagedSSHKey objects for all managed keys, with date and age pre-computed."""
    today = date.today()
    result: list[ManagedSSHKey] = []
    for path in sorted(list_managed_keys(key_dir)):
        key_date = parse_key_date(path)
        age = (today - key_date).days if key_date is not None else None
        result.append(ManagedSSHKey(path=path, key_date=key_date, age_days=age))
    return result

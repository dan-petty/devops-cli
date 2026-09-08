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


def _sanitize_prefix(raw_prefix: str) -> str:
    """Sanitize raw string into a clean lowercase identifier prefix."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", raw_prefix.strip()).strip("-").lower()


def _extract_prefix_from_yaml(cfg_file: Path) -> str | None:
    """Extract and sanitize key_prefix from a YAML config file."""
    import yaml

    if not cfg_file.is_file():
        return None
    try:
        data = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return None
        ssh_conf = data.get("ssh", {})
        raw_prefix = None
        if isinstance(ssh_conf, dict) and ssh_conf.get("key_prefix"):
            raw_prefix = ssh_conf["key_prefix"]
        elif data.get("key_prefix"):
            raw_prefix = data["key_prefix"]
        return _sanitize_prefix(str(raw_prefix)) if raw_prefix else None
    except Exception:
        return None


def _resolve_prefix_from_project_config(target_dir: Path) -> str | None:
    """Inspect target directory and ancestors for project/devcontainer config.yaml with key_prefix."""
    import os

    env_cfg = os.environ.get("DEVOPS_CLI_CONFIG")
    if env_cfg:
        prefix = _extract_prefix_from_yaml(Path(env_cfg))
        if prefix:
            return prefix

    candidate_names = (
        "config.yaml",
        ".devcontainer/config.yaml",
        ".devops/config.yaml",
        ".devops.yaml",
        ".devcontainer/.devops.yaml",
    )
    for d in (target_dir, *target_dir.parents):
        for name in candidate_names:
            prefix = _extract_prefix_from_yaml(d / name)
            if prefix:
                return prefix
        if (d / ".git").exists() or (d / ".devcontainer").exists():
            break
    return None


def _resolve_prefix_from_devcontainer(target_dir: Path) -> str | None:
    """Extract and sanitize the 'name' field from devcontainer.json."""
    import json

    candidate_paths: list[Path] = [
        target_dir / ".devcontainer" / "devcontainer.json",
        target_dir / ".devcontainer.json",
        target_dir / "devcontainer.json",
    ]
    for parent in target_dir.parents:
        candidate_paths.append(parent / ".devcontainer" / "devcontainer.json")
        candidate_paths.append(parent / ".devcontainer.json")

    for dev_path in candidate_paths:
        if not dev_path.is_file():
            continue
        try:
            text = dev_path.read_text(encoding="utf-8")
            cleaned = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
            data = json.loads(cleaned)
            if isinstance(data, dict) and data.get("name"):
                sanitized = _sanitize_prefix(str(data["name"]))
                if sanitized:
                    return sanitized
        except Exception:
            continue
    return None


def _resolve_prefix_from_settings() -> str | None:
    """Extract configured ssh.key_prefix from active loaded settings."""
    from devops_cli.config.settings import load_settings

    try:
        settings = load_settings()
        if settings.ssh.key_prefix:
            sanitized = _sanitize_prefix(settings.ssh.key_prefix)
            if sanitized:
                return sanitized
    except Exception:
        pass
    return None


def get_ssh_key_prefix(workspace_path: Path | None = None) -> str:
    """Determine the SSH key prefix from env, devcontainer name, project config, or settings."""
    import os

    # 1. Environment variable override
    env_prefix = os.environ.get("DEVOPS_CLI_SSH_KEY_PREFIX")
    if env_prefix and env_prefix.strip():
        sanitized = _sanitize_prefix(env_prefix)
        if sanitized:
            return sanitized

    target_dir = (workspace_path or Path.cwd()).resolve()

    # 2. When a specific workspace_path is passed (external project), prioritize its local config/devcontainer
    if workspace_path is not None:
        proj_prefix = _resolve_prefix_from_project_config(target_dir)
        if proj_prefix:
            return proj_prefix

        dev_prefix = _resolve_prefix_from_devcontainer(target_dir)
        if dev_prefix:
            return dev_prefix

    # 3. Check loaded settings (respects load_settings mock and active project config)
    settings_prefix = _resolve_prefix_from_settings()
    if settings_prefix:
        return settings_prefix

    # 4. Devcontainer configuration in target directory hierarchy
    dev_prefix = _resolve_prefix_from_devcontainer(target_dir)
    if dev_prefix:
        return dev_prefix

    # 5. Target directory name fallback
    base_name = _sanitize_prefix(target_dir.name)
    return base_name or "devops-cli"


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
    pub_path = key_path.with_name(f"{key_path.name}.pub")

    if key_path.is_symlink() or key_path.parent.is_symlink():
        raise ValidationError(
            f"SSH key path '{key_path}' must not be a symlink to avoid arbitrary file overwrite",
            field="key_path",
        )
    if pub_path.is_symlink():
        raise ValidationError(
            f"SSH public key path '{pub_path}' must not be a symlink to avoid arbitrary file overwrite",
            field="key_path",
        )

    private_key = Ed25519PrivateKey.generate()

    private_bytes = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.OpenSSH,
        encryption_algorithm=NoEncryption(),
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    # Write with restricted permissions atomically to avoid a world-readable window.
    import os as _os

    flags = _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC | getattr(_os, "O_NOFOLLOW", 0)
    fd = _os.open(key_path, flags, CONST_PERM_PRIVATE_KEY)
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
    pub_fd = _os.open(pub_path, flags, CONST_PERM_PUBLIC_KEY)
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


def parse_key_prefix(key_path: Path) -> str | None:
    """Parse the optional prefix from a managed key filename, or None."""
    match = _KEY_RE.match(key_path.name)
    if not match:
        return None
    return match.group("prefix")


def find_newest_key(
    key_dir: Path,
    prefix: str | None = None,
    *,
    fallback_to_any: bool = True,
) -> Path | None:
    """Return the newest managed SSH private key (optionally filtered by prefix), or None."""
    keys = list_managed_keys(key_dir, prefix=prefix)
    if not keys and prefix is not None:
        variant = prefix.replace("_", "-") if "_" in prefix else prefix.replace("-", "_")
        keys = list_managed_keys(key_dir, prefix=variant)
    if not keys and prefix is not None:
        if fallback_to_any:
            keys = list_managed_keys(key_dir)
        else:
            keys = [p for p in list_managed_keys(key_dir) if parse_key_prefix(p) is None]
    if not keys:
        return None
    return max(keys, key=lambda path: parse_key_date(path) or date.min)


def list_managed_keys(key_dir: Path, prefix: str | None = None) -> list[Path]:
    """List all managed SSH private keys matching [prefix-]id_ed25519-YYYYMMDD."""
    expanded = key_dir.expanduser()
    if not expanded.is_dir():
        return []
    result: list[Path] = []
    for path in expanded.iterdir():
        if not path.is_file():
            continue
        m = _KEY_RE.match(path.name)
        if not m:
            continue
        if prefix is not None and m.group("prefix") != prefix:
            continue
        result.append(path)
    return result


def list_managed_keys_info(key_dir: Path, prefix: str | None = None) -> list[ManagedSSHKey]:
    """Return ManagedSSHKey objects for managed keys, with date and age pre-computed."""
    today = date.today()
    result: list[ManagedSSHKey] = []
    for path in sorted(list_managed_keys(key_dir, prefix=prefix)):
        key_date = parse_key_date(path)
        age = (today - key_date).days if key_date is not None else None
        result.append(ManagedSSHKey(path=path, key_date=key_date, age_days=age))
    return result

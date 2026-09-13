"""GitHub Actions repository secret synchronization with libsodium sealing."""

from __future__ import annotations

import json
import logging
from base64 import b64encode

from nacl import encoding, public
from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.settings import get_keyring_secret
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


class GitHubPublicKey(BaseModel):
    """GitHub Actions repository public key for libsodium encryption."""

    key_id: str
    key: str


class SecretSyncItem(BaseModel):
    """Result of an individual secret synchronization attempt."""

    name: str
    source: str
    status: str
    message: str = ""


class SecretSyncResult(BaseModel):
    """Summary of repository secret synchronization."""

    synced_secrets: list[str] = Field(default_factory=list)
    skipped_secrets: list[str] = Field(default_factory=list)
    failed_secrets: list[str] = Field(default_factory=list)
    missing_secrets: list[str] = Field(default_factory=list)
    items: list[SecretSyncItem] = Field(default_factory=list)
    dry_run: bool = False


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypt a secret string using the repository public key with libsodium sealed box."""
    clean_pk = public_key_b64.strip()
    try:
        pk_bytes = public.PublicKey(clean_pk.encode("utf-8"), encoding.Base64Encoder)
        sealed_box = public.SealedBox(pk_bytes)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return b64encode(encrypted).decode("utf-8")
    except Exception as exc:
        raise GitHubOperationError(
            f"Failed to encrypt secret with repository public key: {mask_secrets(str(exc)[:256])}",
            operation="encrypt_secret",
            details={"error": mask_secrets(str(exc)[:256])},
        ) from exc


def get_repository_public_key(repo: str) -> GitHubPublicKey:
    """Fetch the repository public key for Actions secrets encryption."""
    with trace_span("github.secrets.get_public_key", attributes={"repo": repo}):
        cmd = [CONST_GH_CLI, "api", f"repos/{repo}/actions/secrets/public-key"]
        res = run_subprocess(cmd, check=False, quiet=True)
        if res.returncode != 0 or not res.stdout.strip():
            err_msg = mask_secrets(res.stderr.strip()[:256]) or "Failed to retrieve public key"
            raise GitHubOperationError(
                f"Failed to get Actions public key for {repo}: {err_msg}",
                operation="get_repository_public_key",
                details={"repo": repo[:256], "error": err_msg},
            )

        try:
            data = json.loads(res.stdout)
            return GitHubPublicKey(
                key_id=str(data.get("key_id", "")),
                key=str(data.get("key", "")),
            )
        except (json.JSONDecodeError, KeyError) as exc:
            raise GitHubOperationError(
                f"Invalid public key response from GitHub API: {mask_secrets(str(exc)[:256])}",
                operation="get_repository_public_key",
                details={"repo": repo[:256], "error": mask_secrets(str(exc)[:256])},
            ) from exc


def list_repository_secrets(repo: str) -> list[str]:
    """List secret names configured in the repository (values are never exposed by GitHub)."""
    with trace_span("github.secrets.list", attributes={"repo": repo}):
        cmd = [CONST_GH_CLI, "api", f"repos/{repo}/actions/secrets"]
        res = run_subprocess(cmd, check=False, quiet=True)
        if res.returncode != 0 or not res.stdout.strip():
            logger.debug("Failed to list secrets for repository %s", repo)
            return []

        try:
            data = json.loads(res.stdout)
            raw_secrets = data.get("secrets", [])
            return [str(s.get("name", "")) for s in raw_secrets if s.get("name")]
        except Exception as exc:
            logger.warning("Error parsing repository secrets list: %s", exc)
            return []


def _resolve_secret_from_source(
    name: str,
    source: str,
    vault_path: str = "secret/devops",
) -> str | None:
    """Retrieve secret value from specified source store without exposing it in logs."""
    clean_source = source.strip().lower()
    if clean_source == "keyring":
        val = get_keyring_secret(name)
        return str(val) if val is not None else None

    if clean_source == "vault":
        from devops_cli.security.vault_broker import VaultSecretBroker

        broker = VaultSecretBroker()
        val = broker.get_secret(vault_path, key=name)
        return str(val) if val is not None else None

    raise GitHubOperationError(
        f"Unsupported secret source: '{source}'. Supported sources: 'keyring', 'vault'.",
        operation="resolve_secret_from_source",
        details={"source": source[:256]},
    )


def _upload_encrypted_secret(
    repo: str,
    secret_name: str,
    encrypted_value: str,
    key_id: str,
) -> bool:
    """Upload encrypted secret to GitHub Actions repository secrets via gh CLI."""
    cmd = [
        CONST_GH_CLI,
        "api",
        "-X",
        "PUT",
        f"repos/{repo}/actions/secrets/{secret_name}",
        "--input",
        "-",
    ]
    payload = json.dumps({"encrypted_value": encrypted_value, "key_id": key_id})
    res = run_subprocess(cmd, input=payload, check=False, quiet=True)
    if res.returncode != 0:
        logger.error("Failed to upload secret to repository %s", repo)
        return False
    return True


def sync_repository_secrets(
    repo: str,
    secret_names: list[str],
    source: str = "keyring",
    vault_path: str = "secret/devops",
    dry_run: bool = False,
) -> SecretSyncResult:
    """Synchronize secrets from source (OS Keyring or Vault) to GitHub repository secrets."""
    synced: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    missing: list[str] = []
    items: list[SecretSyncItem] = []

    unique_names = sorted(set(name.strip() for name in secret_names if name.strip()))
    if not unique_names:
        return SecretSyncResult(dry_run=dry_run)

    public_key: GitHubPublicKey | None = None
    if not dry_run:
        public_key = get_repository_public_key(repo)

    with trace_span(
        "github.secrets.sync",
        attributes={"repo": repo, "source": source, "dry_run": dry_run, "count": len(unique_names)},
    ):
        for name in unique_names:
            secret_value = _resolve_secret_from_source(name, source=source, vault_path=vault_path)
            if not secret_value:
                missing.append(name)
                items.append(
                    SecretSyncItem(
                        name=name,
                        source=source,
                        status="missing",
                        message=f"Secret not found in source '{source}'",
                    )
                )
                continue

            if dry_run:
                synced.append(name)
                items.append(
                    SecretSyncItem(
                        name=name,
                        source=source,
                        status="synced",
                        message="Would seal with libsodium and upload (dry-run)",
                    )
                )
                continue

            assert public_key is not None
            enc_val = encrypt_secret(public_key.key, secret_value)
            success = _upload_encrypted_secret(repo, name, enc_val, public_key.key_id)
            if success:
                synced.append(name)
                items.append(
                    SecretSyncItem(
                        name=name,
                        source=source,
                        status="synced",
                        message="Successfully sealed and uploaded to GitHub Actions",
                    )
                )
            else:
                failed.append(name)
                items.append(
                    SecretSyncItem(
                        name=name,
                        source=source,
                        status="failed",
                        message="GitHub API rejected secret upload",
                    )
                )

    return SecretSyncResult(
        synced_secrets=synced,
        skipped_secrets=skipped,
        failed_secrets=failed,
        missing_secrets=missing,
        items=items,
        dry_run=dry_run,
    )

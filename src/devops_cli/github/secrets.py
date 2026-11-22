"""GitHub Actions secret synchronization with libsodium sealing.

A secret belongs to the repository, or to one environment of the repository (#6781). The value
stays in memory between its source and the seal: no output, log record, span or error text holds
it.
"""

from __future__ import annotations

import json
import logging
from base64 import b64encode
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from devops_cli.dry_run.requests import PlannedRequest

from nacl import encoding, public
from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.os_keyring import get_keyring_secret
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.rate_limiter import run_gh
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


class GitHubPublicKey(BaseModel):
    """GitHub Actions public key of a repository or an environment, for libsodium encryption."""

    key_id: str
    key: str


class SecretSyncItem(BaseModel):
    """Result of an individual secret synchronization attempt."""

    name: str
    source: str
    status: str
    message: str = ""


class SecretSyncResult(BaseModel):
    """Summary of a secret synchronization into a repository or an environment."""

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
            f"Failed to encrypt secret with the Actions public key: {mask_secrets(str(exc)[:256])}",
            operation="encrypt_secret",
            details={"error": mask_secrets(str(exc)[:256])},
        ) from exc


def secrets_path(repo: str, environment: str | None = None) -> str:
    """The REST path of the Actions secrets of `repo`, or of its environment `environment`.

    GitHub asks for the environment name URL encoded, so a slash becomes `%2F`.
    """
    if environment is None:
        return f"repos/{repo}/actions/secrets"
    return f"repos/{repo}/environments/{quote(environment, safe='')}/secrets"


def _scope_label(repo: str, environment: str | None) -> str:
    """The scope of a secret as a message names it."""
    if environment is None:
        return repo
    return f"environment '{environment}' of {repo}"


def get_public_key_args(repo: str, environment: str | None = None) -> list[str]:
    """Arguments for fetching the Actions public key of the repository or the environment."""
    return ["api", f"{secrets_path(repo, environment)}/public-key"]


def get_repository_public_key(repo: str, environment: str | None = None) -> GitHubPublicKey:
    """Fetch the Actions public key of the repository, or of its environment `environment`."""
    attributes = {"repo": repo, "environment": environment or ""}
    with trace_span("github.secrets.get_public_key", attributes=attributes):
        cmd = [CONST_GH_CLI, *get_public_key_args(repo, environment)]
        res = run_gh(cmd, check=False, quiet=True)
        if res.returncode != 0 or not res.stdout.strip():
            err_msg = mask_secrets(res.stderr.strip()[:256]) or "Failed to retrieve public key"
            raise GitHubOperationError(
                f"Failed to get Actions public key for {_scope_label(repo, environment)}: "
                f"{err_msg}",
                operation="get_repository_public_key",
                details={
                    "repo": repo[:256],
                    "environment": (environment or "")[:256],
                    "error": err_msg,
                },
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


def list_secrets_args(repo: str) -> list[str]:
    """Arguments for listing repository Actions secrets."""
    return ["api", f"repos/{repo}/actions/secrets"]


def list_secrets_requests(repo: str) -> list[PlannedRequest]:
    """Planned requests for listing repository secrets."""
    from devops_cli.roadmap.request_plan import planned_gh

    args = list_secrets_args(repo)
    return [planned_gh(args, f"repos/{repo}/actions/secrets")]


def list_repository_secrets(repo: str) -> list[str]:
    """List secret names configured in the repository (values are never exposed by GitHub)."""
    with trace_span("github.secrets.list", attributes={"repo": repo}):
        cmd = [CONST_GH_CLI, *list_secrets_args(repo)]
        res = run_gh(cmd, check=False, quiet=True)
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


def is_vault_source(source: str) -> bool:
    """Report whether `source` names Vault, as `_resolve_secret_from_source` reads it."""
    return source.strip().lower() == "vault"


def _resolve_secret_from_source(
    name: str,
    source: str,
    vault_path: str = "secret/devops",
) -> str | None:
    """Retrieve secret value from specified source store without exposing it in logs.

    The Vault source reads Vault alone: a field Vault lacks is missing, never filled from the
    keyring, and a missing or rejected token raises `VaultAuthenticationError`.
    """
    clean_source = source.strip().lower()
    if clean_source == "keyring":
        val = get_keyring_secret(name)
        return str(val) if val is not None else None

    if is_vault_source(clean_source):
        from devops_cli.security.vault_broker import VaultSecretBroker

        val = VaultSecretBroker().read_secret(vault_path, key=name)
        return str(val) if val is not None else None

    raise GitHubOperationError(
        f"Unsupported secret source: '{source}'. Supported sources: 'keyring', 'vault'.",
        operation="resolve_secret_from_source",
        details={"source": source[:256]},
    )


def upload_secret_args(repo: str, secret_name: str, environment: str | None = None) -> list[str]:
    """Arguments for uploading an encrypted secret via gh api, with the body on stdin."""
    path = f"{secrets_path(repo, environment)}/{secret_name}"
    return ["api", "-X", "PUT", path, "--input", "-"]


def sync_secrets_requests(
    repo: str, secret_names: list[str], environment: str | None = None
) -> list[PlannedRequest]:
    """Planned requests for synchronizing secrets to the repository or the environment."""
    from devops_cli.roadmap.request_plan import planned_gh

    base = secrets_path(repo, environment)
    unique_names = sorted(set(name.strip() for name in secret_names if name.strip()))
    requests: list[PlannedRequest] = [
        planned_gh(get_public_key_args(repo, environment), f"{base}/public-key")
    ]
    for name in unique_names:
        args = upload_secret_args(repo, name, environment)
        payload = json.dumps({"encrypted_value": "<encrypted_secret>", "key_id": "<key_id>"})
        requests.append(planned_gh(args, f"{base}/{name}", stdin=payload))
    return requests


def _upload_encrypted_secret(
    repo: str,
    secret_name: str,
    encrypted_value: str,
    key_id: str,
    environment: str | None = None,
) -> bool:
    """Upload an encrypted secret to the repository or the environment via gh CLI."""
    cmd = [CONST_GH_CLI, *upload_secret_args(repo, secret_name, environment)]
    payload = json.dumps({"encrypted_value": encrypted_value, "key_id": key_id})
    res = run_gh(cmd, input=payload, check=False, quiet=True)
    if res.returncode != 0:
        logger.error("Failed to upload secret to %s", _scope_label(repo, environment))
        return False
    return True


def sync_repository_secrets(
    repo: str,
    secret_names: list[str],
    source: str = "keyring",
    vault_path: str = "secret/devops",
    dry_run: bool = False,
    environment: str | None = None,
    value: str | None = None,
) -> SecretSyncResult:
    """Synchronize secrets from a source to the Actions secrets of a repository or environment.

    Each value comes from `source` (the OS keyring or Vault) by the name of the secret. A caller
    that read the value of one secret from a file gives it as `value`: the source of the item is
    then `file`, and a value for more than one name raises `GitHubOperationError`. With
    `environment`, the public key and each secret are those of that environment of `repo`.

    A dry run reads the local keyring but never Vault, so it sends no request: each Vault secret
    is reported as one the run would read, seal and upload.
    """
    synced: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    missing: list[str] = []
    items: list[SecretSyncItem] = []

    unique_names = sorted(set(name.strip() for name in secret_names if name.strip()))
    if value is not None and len(unique_names) != 1:
        raise GitHubOperationError(
            f"A value from a file is the value of one secret, not of {len(unique_names)}.",
            operation="sync_repository_secrets",
            details={"count": len(unique_names)},
        )
    if not unique_names:
        return SecretSyncResult(dry_run=dry_run)
    if value is not None:
        source = "file"

    public_key: GitHubPublicKey | None = None
    scope_text = "GitHub Actions" if environment is None else f"environment '{environment}'"

    with trace_span(
        "github.secrets.sync",
        attributes={
            "repo": repo,
            "environment": environment or "",
            "source": source,
            "dry_run": dry_run,
            "count": len(unique_names),
        },
    ):
        for name in unique_names:
            if dry_run and is_vault_source(source):
                synced.append(name)
                items.append(
                    SecretSyncItem(
                        name=name,
                        source=source,
                        status="synced",
                        message=(
                            f"Would read from Vault at '{vault_path}', seal with libsodium and "
                            "upload (dry-run)"
                        ),
                    )
                )
                continue
            secret_value = (
                value
                if value is not None
                else _resolve_secret_from_source(name, source=source, vault_path=vault_path)
            )
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

            if public_key is None:
                public_key = get_repository_public_key(repo, environment)
            enc_val = encrypt_secret(public_key.key, secret_value)
            success = _upload_encrypted_secret(repo, name, enc_val, public_key.key_id, environment)
            if success:
                synced.append(name)
                items.append(
                    SecretSyncItem(
                        name=name,
                        source=source,
                        status="synced",
                        message=f"Successfully sealed and uploaded to {scope_text}",
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

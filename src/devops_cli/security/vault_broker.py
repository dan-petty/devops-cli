"""HashiCorp Vault KV secret broker, with an OS keyring fallback for `devops vault get`."""

from __future__ import annotations

import os
from typing import Any, Literal
from urllib.parse import urldefrag, urlsplit

import httpx2
from pydantic import BaseModel, ValidationError

from devops_cli.config.constants import (
    CONST_SECRET_PROVIDER_ENVIRONMENT,
    CONST_SECRET_PROVIDER_KEYRING,
    CONST_SECRET_PROVIDER_VAULT,
    CONST_VAULT_LOGIN_CREDENTIAL_ID,
    CONST_VAULT_LOGIN_KEYRING_KEY,
    CONST_VAULT_PATH_HEALTH,
    CONST_VAULT_TOKEN_CREDENTIAL_ID,
    CONST_VAULT_TOKEN_ENV_VARS,
    CONST_VAULT_TOKEN_REJECTED_STATUSES,
    CONST_VAULT_TOKEN_SOURCE_ARGUMENT,
    CONST_VAULT_TOKEN_SOURCE_NONE,
)
from devops_cli.config.defaults import DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS
from devops_cli.config.settings import get_keyring_secret, set_keyring_secret
from devops_cli.core.paths import validate_no_path_traversal
from devops_cli.exceptions.vault import (
    VaultAuthenticationError,
    VaultConfigurationError,
    VaultError,
    VaultKeyError,
    VaultOperationError,
    VaultUnreachableError,
)
from devops_cli.models.vault import (
    VaultSecretLookup,
    VaultStoredLogin,
    VaultSyncReport,
    VaultTokenSource,
)
from devops_cli.security.sanitizer import mask_uri_credentials
from devops_cli.security.secrets import SecretRef, resolve_secret
from devops_cli.security.vault_http import vault_request
from devops_cli.telemetry import trace_span

_SyncOutcome = Literal["synced", "skipped", "missing", "failed"]


class VaultStatus(BaseModel):
    """Vault cluster health and sealing status."""

    initialized: bool = False
    sealed: bool = True
    version: str = ""
    cluster_name: str = ""
    error_message: str | None = None

    @property
    def is_healthy(self) -> bool:
        """Return True if Vault is initialized and unsealed."""
        return self.initialized and not self.sealed


def parse_vault_uri(uri: str) -> tuple[str, str | None]:
    """Parse vault:// URI reference into secret path and optional key.

    Examples:
        vault://secret/data/devops/creds#github_token -> ('secret/data/devops/creds', 'github_token')
        secret/data/ci/database -> ('secret/data/ci/database', None)
    """
    cleaned, frag = urldefrag(uri.strip())
    key = frag.strip() or None

    validate_no_path_traversal(cleaned, error_cls=VaultConfigurationError, label="Vault URI")

    parsed = urlsplit(cleaned)
    if parsed.scheme.lower() == "vault":
        path = f"{parsed.netloc}{parsed.path}".lstrip("/")
        validate_no_path_traversal(path, error_cls=VaultConfigurationError, label="Vault URI")
        return path, key

    return cleaned, key


def _secret_fields(response: httpx2.Response, clean_path: str) -> dict[str, Any]:
    """Return the fields of a KV-v2 (or KV-v1) read, refusing a body that holds none."""
    try:
        payload = response.json()
    except ValueError as exc:
        raise VaultOperationError(
            f"Vault answered '{clean_path}' with a body that is not JSON."
        ) from exc
    raw_data = payload.get("data") if isinstance(payload, dict) else None
    fields = raw_data.get("data", raw_data) if isinstance(raw_data, dict) else None
    if not isinstance(fields, dict):
        raise VaultOperationError(f"Vault answered '{clean_path}' without secret data.")
    return fields


def _sync_field(name: str, value: Any) -> _SyncOutcome:
    """Store one Vault field in the OS keyring, never over the `vault login` record."""
    if name == CONST_VAULT_LOGIN_KEYRING_KEY:
        return "skipped"
    if value is None or value == "":
        return "missing"
    return "synced" if set_keyring_secret(name, str(value)) else "failed"


class VaultSecretBroker:
    """HashiCorp Vault KV broker.

    Its token is resolved once, at construction, in this order:

    1. the `vault_token` argument;
    2. the record `devops vault login` stored in the OS keyring, used only when the address and
       namespace stored with it are this broker's;
    3. `VAULT_TOKEN`;
    4. `DEVOPS_CLI_VAULT_TOKEN`.

    Keyring before environment is the order `build_default_resolver` gives every secret. Both
    lookups go through the shared resolver with references that carry no Vault path, so the
    audit trail records them and `VaultProvider` never builds a broker to answer them.
    `token_source` records where the token came from, and why a stored token was passed over;
    never the token.
    """

    def __init__(
        self,
        vault_addr: str | None = None,
        vault_token: str | None = None,
        vault_namespace: str | None = None,
    ) -> None:
        self.vault_addr = (
            vault_addr
            or os.getenv("VAULT_ADDR")
            or os.getenv("DEVOPS_CLI_VAULT_ADDR")
            or "http://127.0.0.1:8200"
        ).rstrip("/")
        parsed = urlsplit(self.vault_addr)
        if parsed.scheme not in ("http", "https"):
            raise VaultConfigurationError(
                f"Invalid Vault address scheme '{parsed.scheme}'; expected 'http' or 'https'"
            )
        if not parsed.netloc:
            raise VaultConfigurationError(f"Invalid Vault address host/netloc: '{self.vault_addr}'")
        validate_no_path_traversal(
            self.vault_addr,
            error_cls=VaultConfigurationError,
            label="Vault address",
        )

        self.vault_namespace = vault_namespace or os.getenv("VAULT_NAMESPACE") or None
        self.vault_token, self.token_source = self._resolve_token(vault_token)

    # -- token resolution -------------------------------------------------------------------

    def _resolve_token(self, vault_token: str | None) -> tuple[str | None, VaultTokenSource]:
        """Resolve the token in the documented order, recording its source."""
        if vault_token:
            return vault_token, VaultTokenSource(source=CONST_VAULT_TOKEN_SOURCE_ARGUMENT)
        stored_token, skipped = self._stored_login_token()
        if stored_token:
            return stored_token, VaultTokenSource(source=CONST_SECRET_PROVIDER_KEYRING)
        env_token = resolve_secret(
            SecretRef(name=CONST_VAULT_TOKEN_CREDENTIAL_ID, env_vars=CONST_VAULT_TOKEN_ENV_VARS)
        )
        source = CONST_SECRET_PROVIDER_ENVIRONMENT if env_token else CONST_VAULT_TOKEN_SOURCE_NONE
        return env_token, VaultTokenSource(source=source, stored_login_skipped=skipped)

    def _stored_login_token(self) -> tuple[str | None, str | None]:
        """Return the stored login's token when it is for this Vault, or why it is not used."""
        raw_record = resolve_secret(
            SecretRef(
                name=CONST_VAULT_LOGIN_CREDENTIAL_ID, keyring_key=CONST_VAULT_LOGIN_KEYRING_KEY
            )
        )
        if raw_record is None:
            return None, None
        try:
            login = VaultStoredLogin.model_validate_json(raw_record)
        except ValidationError:
            return None, "it is unreadable; run `devops vault login` again"
        if (login.vault_addr, login.namespace) != (self.vault_addr, self.vault_namespace):
            return None, f"issued for {login.issuer()}"
        return login.token, None

    def require_token(self) -> str:
        """Return the token, or raise `VaultAuthenticationError` naming where one comes from."""
        if self.vault_token:
            return self.vault_token
        skipped = self.token_source.stored_login_skipped
        reason = f" (the stored token was not used: {skipped})" if skipped else ""
        raise VaultAuthenticationError(
            f"Vault requires a token, but no usable token is available{reason}. "
            "Run `devops vault login`, or set VAULT_TOKEN or DEVOPS_CLI_VAULT_TOKEN.",
            vault_addr=self.vault_addr,
        )

    def status_error(self, status: int, path: str) -> VaultError:
        """Build the error for a refusing status: a rejected token, or any other refusal."""
        if status in CONST_VAULT_TOKEN_REJECTED_STATUSES:
            return VaultAuthenticationError(
                f"Vault rejected the token from the {self.token_source.source} (HTTP {status}). "
                f"It may have expired, been revoked, or have no policy for '{path}'. "
                "Run `devops vault login` to get a new token.",
                vault_addr=self.vault_addr,
                details={"status_code": status, "token_source": self.token_source.source},
            )
        return VaultOperationError(
            f"Vault answered HTTP {status} for '{path}'.",
            status_code=status,
            details={"path": path[:256]},
        )

    def _token_headers(self) -> dict[str, str]:
        """Build authenticated request headers, raising before any request without a token."""
        headers = {"Content-Type": "application/json", "X-Vault-Token": self.require_token()}
        if self.vault_namespace:
            headers["X-Vault-Namespace"] = self.vault_namespace
        return headers

    # -- reads -------------------------------------------------------------------------------

    def _read_fields(self, clean_path: str) -> dict[str, Any] | None:
        """Read the secret at `clean_path` from Vault alone; None when Vault has none there."""
        response = vault_request(
            "GET",
            self.vault_addr,
            clean_path,
            headers=self._token_headers(),
            timeout=DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS,
        )
        if response.status_code == httpx2.codes.NOT_FOUND:
            return None
        if not httpx2.codes.is_success(response.status_code):
            raise self.status_error(response.status_code, clean_path)
        return _secret_fields(response, clean_path)

    def read_secret(self, path: str, key: str | None = None) -> Any:
        """Read a secret, or one field of it, from Vault alone; None when Vault has no value.

        Raises `VaultAuthenticationError` before any request when no token is usable, and when
        Vault rejects the token; `VaultUnreachableError` when Vault does not answer; and
        `VaultOperationError` for any other refusal, a refused redirect among them.
        """
        clean_path, fragment_key = parse_vault_uri(path)
        effective_key = key or fragment_key
        with trace_span(
            "security.vault_broker.read_secret",
            attributes={"path": clean_path, "has_key": bool(effective_key)},
        ):
            fields = self._read_fields(clean_path)
        if fields is None or not effective_key:
            return fields
        return fields.get(effective_key)

    def get_secret(self, path: str, key: str | None = None) -> VaultSecretLookup:
        """Read a secret from Vault, falling back to the OS keyring only when Vault cannot answer.

        The keyring is read when no token is usable, when Vault has no value at the path, or
        when Vault is unreachable; never after Vault rejects the token, refuses a redirect, or
        answers with any other error, which are raised instead.
        """
        clean_path, fragment_key = parse_vault_uri(path)
        effective_key = key or fragment_key
        if not self.vault_token:
            skipped = self.token_source.stored_login_skipped
            reason = "Vault was not consulted: no usable token" + (
                f" (the stored token was not used: {skipped})" if skipped else ""
            )
            return self._keyring_fallback(clean_path, effective_key, [], reason)
        try:
            value = self.read_secret(clean_path, key=effective_key)
        except VaultUnreachableError as exc:
            return self._keyring_fallback(
                clean_path, effective_key, [CONST_SECRET_PROVIDER_VAULT], exc.message
            )
        if value is None:
            field = f" for '{effective_key}'" if effective_key else ""
            reason = f"Vault has no value at '{clean_path}'{field}"
            return self._keyring_fallback(
                clean_path, effective_key, [CONST_SECRET_PROVIDER_VAULT], reason
            )
        return VaultSecretLookup(
            value=value,
            source=CONST_SECRET_PROVIDER_VAULT,
            checked=[CONST_SECRET_PROVIDER_VAULT],
        )

    @staticmethod
    def _keyring_fallback(
        clean_path: str, effective_key: str | None, checked: list[str], reason: str
    ) -> VaultSecretLookup:
        """Answer from the OS keyring entry named after the key or the path's last segment."""
        value = get_keyring_secret(effective_key or clean_path.split("/")[-1])
        return VaultSecretLookup(
            value=value,
            source=CONST_SECRET_PROVIDER_KEYRING if value is not None else None,
            checked=[*checked, CONST_SECRET_PROVIDER_KEYRING],
            fallback_reason=reason,
        )

    # -- writes ------------------------------------------------------------------------------

    def set_secret(self, path: str, data: dict[str, Any]) -> None:
        """Store secret data in Vault's KV-v2 engine, raising as `read_secret` does on refusal."""
        clean_path, _ = parse_vault_uri(path)
        with trace_span("security.vault_broker.set_secret", attributes={"path": clean_path}):
            response = vault_request(
                "POST",
                self.vault_addr,
                clean_path,
                headers=self._token_headers(),
                payload={"data": data},
                timeout=DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS,
            )
        if not httpx2.codes.is_success(response.status_code):
            raise self.status_error(response.status_code, clean_path)

    def sync_to_keyring(self, path: str, keys: list[str] | None = None) -> VaultSyncReport:
        """Copy a Vault secret's fields into the OS keyring, reading Vault alone.

        A field named like the `devops vault login` record is skipped, so no secret can replace
        the stored login. Raises `VaultKeyError` when Vault has no secret at `path`.
        """
        clean_path, _ = parse_vault_uri(path)
        with trace_span("security.vault_broker.sync_to_keyring", attributes={"path": clean_path}):
            fields = self._read_fields(clean_path)
        if fields is None:
            raise VaultKeyError(f"Vault has no secret at '{clean_path}'.", secret_path=clean_path)
        report = VaultSyncReport()
        for name in keys or list(fields):
            getattr(report, _sync_field(name, fields.get(name))).append(name)
        return report

    # -- health ------------------------------------------------------------------------------

    def get_status(self) -> VaultStatus:
        """Inspect Vault health. `sys/health` is unauthenticated, so no token is ever sent."""
        with trace_span(
            "security.vault_broker.get_status",
            attributes={"vault_addr": mask_uri_credentials(self.vault_addr)},
        ):
            try:
                response = vault_request(
                    "GET",
                    self.vault_addr,
                    CONST_VAULT_PATH_HEALTH,
                    headers={"Content-Type": "application/json"},
                    timeout=DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS,
                )
                health = response.json()
            except (VaultError, ValueError) as exc:
                return VaultStatus(initialized=False, sealed=True, error_message=str(exc))
        if not isinstance(health, dict):
            return VaultStatus(
                error_message=f"Vault answered {CONST_VAULT_PATH_HEALTH} without a JSON object."
            )
        return VaultStatus(
            initialized=health.get("initialized", False),
            sealed=health.get("sealed", True),
            version=health.get("version", ""),
            cluster_name=health.get("cluster_name", ""),
        )

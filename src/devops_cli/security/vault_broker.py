"""Enterprise HashiCorp Vault and cloud KMS secret broker with OS Keyring fallback."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel

from devops_cli.config.defaults import DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS
from devops_cli.config.settings import get_keyring_secret, set_keyring_secret
from devops_cli.http.broker import get_broker
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


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
    cleaned = uri.strip()
    key: str | None = None

    if "#" in cleaned:
        cleaned, key = cleaned.split("#", 1)
        key = key.strip() or None

    if any(part == ".." for part in Path(cleaned).parts) or ".." in cleaned:
        raise ValueError(f"Path traversal detected in Vault URI: '{uri}'")

    if cleaned.startswith("vault://"):
        parsed = urlparse(cleaned)
        path = f"{parsed.netloc}{parsed.path}".lstrip("/")
        if any(part == ".." for part in Path(path).parts) or ".." in path:
            raise ValueError(f"Path traversal detected in Vault URI: '{uri}'")
        return path, key

    return cleaned, key


class VaultSecretBroker:
    """Unified HashiCorp Vault secret broker with transparent OS Keyring fallback."""

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
        parsed = urlparse(self.vault_addr)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Invalid Vault address scheme '{parsed.scheme}'; expected 'http' or 'https'"
            )
        if not parsed.netloc:
            raise ValueError(f"Invalid Vault address host/netloc: '{self.vault_addr}'")
        if ".." in self.vault_addr or ".." in parsed.path:
            raise ValueError(f"Path traversal detected in Vault address: '{self.vault_addr}'")

        self.vault_token = (
            vault_token or os.getenv("VAULT_TOKEN") or os.getenv("DEVOPS_CLI_VAULT_TOKEN")
        )
        self.vault_namespace = vault_namespace or os.getenv("VAULT_NAMESPACE")

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.vault_token:
            headers["X-Vault-Token"] = self.vault_token
        if self.vault_namespace:
            headers["X-Vault-Namespace"] = self.vault_namespace
        return headers

    def get_secret(self, path: str, key: str | None = None) -> Any:
        """Retrieve secret data from Vault KV-v2 engine, falling back to OS Keyring."""
        clean_path, fragment_key = parse_vault_uri(path)
        effective_key = key or fragment_key

        with trace_span(
            "security.vault_broker.get_secret",
            attributes={"path": clean_path, "has_key": bool(effective_key)},
        ):
            if self.vault_token:
                url = f"{self.vault_addr}/v1/{clean_path.lstrip('/')}"
                broker = get_broker()
                try:
                    resp = broker.request(
                        "GET",
                        url,
                        headers=self._get_headers(),
                        timeout=DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS,
                        allow_private_network=True,
                    )
                    if resp.status_code == 200:
                        payload = resp.json()
                        # KV-v2 data nesting: payload["data"]["data"]
                        raw_data = payload.get("data", {})
                        secret_data = raw_data.get("data", raw_data)
                        if effective_key:
                            return secret_data.get(effective_key)
                        return secret_data
                except Exception as exc:
                    logger.debug("Vault request failed for %s: %s", url, exc)

            # Seamless fallback to OS Keyring
            lookup_key = effective_key or clean_path.split("/")[-1]
            return get_keyring_secret(lookup_key)

    def set_secret(self, path: str, data: dict[str, Any]) -> bool:
        """Store secret data in Vault KV-v2 engine."""
        clean_path, _ = parse_vault_uri(path)
        url = f"{self.vault_addr}/v1/{clean_path.lstrip('/')}"
        payload = {"data": data}
        broker = get_broker()

        with trace_span("security.vault_broker.set_secret", attributes={"path": clean_path}):
            try:
                resp = broker.request(
                    "POST",
                    url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS,
                    allow_private_network=True,
                )
                return resp.status_code in (200, 204)
            except Exception as exc:
                logger.debug("Vault set_secret failed for %s: %s", url, exc)
                return False

    def get_status(self) -> VaultStatus:
        """Inspect Vault cluster health and initialization status."""
        url = f"{self.vault_addr}/v1/sys/health"
        broker = get_broker()

        with trace_span(
            "security.vault_broker.get_status", attributes={"vault_addr": self.vault_addr}
        ):
            try:
                resp = broker.request(
                    "GET",
                    url,
                    headers=self._get_headers(),
                    timeout=DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS,
                    allow_private_network=True,
                )
                data = resp.json()
                return VaultStatus(
                    initialized=data.get("initialized", False),
                    sealed=data.get("sealed", True),
                    version=data.get("version", ""),
                    cluster_name=data.get("cluster_name", ""),
                )
            except Exception as exc:
                return VaultStatus(
                    initialized=False,
                    sealed=True,
                    error_message=str(exc),
                )

    def sync_to_keyring(self, path: str, keys: list[str] | None = None) -> int:
        """Fetch secret dictionary from Vault and cache values into OS Keyring."""
        data = self.get_secret(path)
        if not isinstance(data, dict):
            return 0

        synced_count = 0
        target_keys = keys or list(data.keys())
        for k in target_keys:
            if k in data and data[k]:
                val = str(data[k])
                if set_keyring_secret(k, val):
                    synced_count += 1
        return synced_count

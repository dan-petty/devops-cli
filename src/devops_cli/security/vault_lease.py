"""Vault authentication methods and dynamic secret lease lifecycle management.

Long-running CI jobs and agent sessions outlive the default lease on a dynamic
credential. This module authenticates natively against Vault (AppRole or the in-cluster
Kubernetes ServiceAccount), tracks every issued lease, and renews proactively before
expiry so an operation never presents a credential that has already lapsed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_KUBERNETES_SA_TOKEN_PATH,
    CONST_VAULT_API_PREFIX,
    CONST_VAULT_PATH_APPROLE_LOGIN,
    CONST_VAULT_PATH_KUBERNETES_LOGIN,
    CONST_VAULT_PATH_LEASE_RENEW,
    CONST_VAULT_PATH_LEASE_REVOKE,
    CONST_VAULT_PATH_TOKEN_RENEW_SELF,
    CONST_VAULT_PATH_TRANSIT_DECRYPT,
    CONST_VAULT_PATH_TRANSIT_ENCRYPT,
)
from devops_cli.config.defaults import (
    DEFAULT_VAULT_LEASE_RENEW_INCREMENT_SECONDS,
    DEFAULT_VAULT_LEASE_RENEW_THRESHOLD,
    DEFAULT_VAULT_REQUEST_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.vault import VaultAuthenticationError, VaultLeaseError
from devops_cli.models.vault import VaultAuthResult, VaultLease, VaultLeaseReport

logger = logging.getLogger(__name__)


def _post(
    vault_addr: str,
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float = DEFAULT_VAULT_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Issue a Vault HTTP API POST through the shared, egress-validated broker."""
    from devops_cli.http.broker import get_broker

    url = f"{vault_addr.rstrip('/')}{CONST_VAULT_API_PREFIX}/{path.lstrip('/')}"
    response = get_broker().request(
        "POST",
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
        allow_private_network=True,
    )
    if response.status_code >= 400:
        raise VaultLeaseError(
            f"Vault API call to '{path}' failed with status {response.status_code}"
        )
    if not response.content:
        return {}
    parsed = response.json()
    return parsed if isinstance(parsed, dict) else {}


# =============================================================================
# Authentication
# =============================================================================


def _auth_headers(namespace: str | None) -> dict[str, str]:
    """Build unauthenticated request headers for a login call."""
    headers = {"Content-Type": "application/json"}
    if namespace:
        headers["X-Vault-Namespace"] = namespace
    return headers


def _project_auth(payload: dict[str, Any], method: str) -> VaultAuthResult:
    """Project a Vault login response into a typed authentication result."""
    auth = payload.get("auth") or {}
    if not isinstance(auth, dict) or not auth.get("client_token"):
        raise VaultAuthenticationError(f"Vault {method} login returned no client token")

    return VaultAuthResult(
        client_token=str(auth["client_token"]),
        accessor=str(auth.get("accessor", "") or ""),
        lease_duration=int(auth.get("lease_duration", 0) or 0),
        renewable=bool(auth.get("renewable", False)),
        method=method,
        policies=[str(p) for p in (auth.get("policies") or [])],
    )


def login_approle(
    vault_addr: str,
    role_id: str,
    secret_id: str,
    namespace: str | None = None,
) -> VaultAuthResult:
    """Authenticate with Vault using the AppRole method."""
    if not role_id or not secret_id:
        raise VaultAuthenticationError("AppRole login requires both a role_id and a secret_id")

    payload = _post(
        vault_addr,
        CONST_VAULT_PATH_APPROLE_LOGIN,
        {"role_id": role_id, "secret_id": secret_id},
        _auth_headers(namespace),
    )
    return _project_auth(payload, "approle")


def read_service_account_token(
    token_path: str = CONST_KUBERNETES_SA_TOKEN_PATH,
) -> str | None:
    """Read the projected in-cluster ServiceAccount token, if this process has one."""
    path = Path(token_path)
    try:
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8").strip() or None
    except OSError as exc:
        logger.debug("Could not read ServiceAccount token at %s: %s", token_path, exc)
        return None


def login_kubernetes(
    vault_addr: str,
    role: str,
    jwt: str | None = None,
    namespace: str | None = None,
    token_path: str = CONST_KUBERNETES_SA_TOKEN_PATH,
) -> VaultAuthResult:
    """Authenticate with Vault using the in-cluster Kubernetes ServiceAccount token."""
    service_account_token = jwt or read_service_account_token(token_path)
    if not service_account_token:
        raise VaultAuthenticationError(
            "Kubernetes login requires a ServiceAccount token; none was supplied and no "
            f"projected token was found at '{token_path}'"
        )
    if not role:
        raise VaultAuthenticationError("Kubernetes login requires a Vault role name")

    payload = _post(
        vault_addr,
        CONST_VAULT_PATH_KUBERNETES_LOGIN,
        {"role": role, "jwt": service_account_token},
        _auth_headers(namespace),
    )
    return _project_auth(payload, "kubernetes")


# =============================================================================
# Lease Lifecycle
# =============================================================================


@dataclass
class LeaseRegistry:
    """Tracks issued Vault leases and renews them before they lapse."""

    vault_addr: str
    token: str | None = None
    namespace: str | None = None
    renew_threshold: float = DEFAULT_VAULT_LEASE_RENEW_THRESHOLD
    renew_increment: int = DEFAULT_VAULT_LEASE_RENEW_INCREMENT_SECONDS

    def __post_init__(self) -> None:
        self._leases: dict[str, VaultLease] = {}

    def _headers(self) -> dict[str, str]:
        """Build authenticated Vault request headers."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Vault-Token"] = self.token
        if self.namespace:
            headers["X-Vault-Namespace"] = self.namespace
        return headers

    def track(
        self, lease_id: str, duration: int, renewable: bool, secret_path: str = ""
    ) -> VaultLease:
        """Register a newly issued lease for lifecycle management."""
        lease = VaultLease(
            lease_id=lease_id,
            duration_seconds=duration,
            renewable=renewable,
            secret_path=secret_path,
            issued_at=time.time(),
        )
        self._leases[lease_id] = lease
        return lease

    def track_auth(self, auth: VaultAuthResult, secret_path: str = "auth/token") -> VaultLease:
        """Register the lease backing an authentication token."""
        return self.track(
            auth.accessor or auth.client_token,
            auth.lease_duration,
            auth.renewable,
            secret_path,
        )

    def leases(self) -> list[VaultLease]:
        """Return every tracked lease."""
        return list(self._leases.values())

    def get(self, lease_id: str) -> VaultLease | None:
        """Return one tracked lease by id."""
        return self._leases.get(lease_id)

    def needs_renewal(self, lease: VaultLease, now: float | None = None) -> bool:
        """Report whether a lease has burned through enough of its TTL to renew."""
        if not lease.renewable or lease.duration_seconds <= 0:
            return False
        remaining = lease.remaining_seconds(now)
        return remaining <= lease.duration_seconds * self.renew_threshold

    def renew(self, lease_id: str, increment: int | None = None) -> VaultLease:
        """Renew a tracked lease, extending its lifetime."""
        lease = self._leases.get(lease_id)
        if lease is None:
            raise VaultLeaseError(f"Lease '{lease_id}' is not tracked", lease_id=lease_id)
        if not lease.renewable:
            raise VaultLeaseError(f"Lease '{lease_id}' is not renewable", lease_id=lease_id)

        payload = _post(
            self.vault_addr,
            CONST_VAULT_PATH_LEASE_RENEW,
            {"lease_id": lease_id, "increment": increment or self.renew_increment},
            self._headers(),
        )
        duration = int(payload.get("lease_duration", increment or self.renew_increment) or 0)
        renewed = lease.model_copy(
            update={
                "duration_seconds": duration,
                "issued_at": time.time(),
                "renewal_count": lease.renewal_count + 1,
            }
        )
        self._leases[lease_id] = renewed
        return renewed

    def renew_token(self, increment: int | None = None) -> int:
        """Renew the client token backing this registry, returning its new lifetime."""
        payload = _post(
            self.vault_addr,
            CONST_VAULT_PATH_TOKEN_RENEW_SELF,
            {"increment": increment or self.renew_increment},
            self._headers(),
        )
        auth = payload.get("auth") or {}
        return int(auth.get("lease_duration", 0) or 0) if isinstance(auth, dict) else 0

    def revoke(self, lease_id: str) -> bool:
        """Revoke a lease and stop tracking it."""
        try:
            _post(
                self.vault_addr,
                CONST_VAULT_PATH_LEASE_REVOKE,
                {"lease_id": lease_id},
                self._headers(),
            )
        except VaultLeaseError as exc:
            logger.debug("Lease %s revocation failed: %s", lease_id, exc)
            return False
        finally:
            self._leases.pop(lease_id, None)
        return True

    def revoke_all(self) -> int:
        """Revoke every tracked lease, returning how many were revoked."""
        return sum(1 for lease_id in list(self._leases) if self.revoke(lease_id))

    def renew_expiring(self, now: float | None = None) -> VaultLeaseReport:
        """Renew every tracked lease close to expiry, reporting the outcome.

        A single failed renewal does not abort the sweep: the remaining leases still get
        their chance, and the failure is reported rather than raised.
        """
        renewed: list[str] = []
        failed: list[str] = []
        skipped: list[str] = []

        for lease in self.leases():
            if not self.needs_renewal(lease, now):
                skipped.append(lease.lease_id)
                continue
            try:
                self.renew(lease.lease_id)
                renewed.append(lease.lease_id)
            except VaultLeaseError as exc:
                logger.debug("Proactive renewal failed for %s: %s", lease.lease_id, exc)
                failed.append(lease.lease_id)

        return VaultLeaseReport(
            renewed=renewed,
            failed=failed,
            skipped=skipped,
            tracked_count=len(self._leases),
        )


# =============================================================================
# Transit Envelope Encryption
# =============================================================================


def transit_encrypt(
    vault_addr: str,
    key_name: str,
    plaintext: str,
    token: str | None = None,
    namespace: str | None = None,
) -> str:
    """Encrypt a value with Vault's Transit engine, which never exposes the key.

    Used to wrap workstation credentials at rest so the encryption key remains inside
    Vault and the local machine only ever holds ciphertext.
    """
    import base64

    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Vault-Token"] = token
    if namespace:
        headers["X-Vault-Namespace"] = namespace

    encoded = base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
    payload = _post(
        vault_addr,
        f"{CONST_VAULT_PATH_TRANSIT_ENCRYPT}/{key_name}",
        {"plaintext": encoded},
        headers,
    )
    ciphertext = (payload.get("data") or {}).get("ciphertext")
    if not ciphertext:
        raise VaultLeaseError(f"Transit encryption with key '{key_name}' returned no ciphertext")
    return str(ciphertext)


def transit_decrypt(
    vault_addr: str,
    key_name: str,
    ciphertext: str,
    token: str | None = None,
    namespace: str | None = None,
) -> str:
    """Decrypt a Transit-encrypted value back to plaintext."""
    import base64

    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Vault-Token"] = token
    if namespace:
        headers["X-Vault-Namespace"] = namespace

    payload = _post(
        vault_addr,
        f"{CONST_VAULT_PATH_TRANSIT_DECRYPT}/{key_name}",
        {"ciphertext": ciphertext},
        headers,
    )
    encoded = (payload.get("data") or {}).get("plaintext")
    if not encoded:
        raise VaultLeaseError(f"Transit decryption with key '{key_name}' returned no plaintext")
    return base64.b64decode(str(encoded)).decode("utf-8")


__all__ = [
    "LeaseRegistry",
    "login_approle",
    "login_kubernetes",
    "read_service_account_token",
    "transit_decrypt",
    "transit_encrypt",
]

"""Pydantic models for Vault authentication and dynamic secret lease lifecycle."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class VaultAuthResult(BaseModel):
    """Outcome of a Vault login, carrying the issued client token and its lease."""

    client_token: str = Field(..., description="Issued Vault client token")
    accessor: str = Field(default="", description="Token accessor for audit correlation")
    lease_duration: int = Field(default=0, description="Token lifetime in seconds")
    renewable: bool = Field(default=False, description="Whether the token can be renewed")
    method: str = Field(default="", description="Authentication method that issued the token")
    policies: list[str] = Field(default_factory=list, description="Policies attached to the token")

    @field_serializer("client_token")
    def _mask_client_token(self, value: str) -> str:
        """Never serialize the raw token.

        This model is rendered into CLI output, JSON payloads, and trace spans; the token
        itself must not travel with it.
        """
        return "<masked-vault-token>" if value else ""


class VaultStoredLogin(BaseModel):
    """The record `devops vault login` keeps in the OS keyring: a token and the Vault it is for.

    The token is sent only to the address and namespace stored with it. Unlike
    `VaultAuthResult`, this model serializes the raw token, because the keyring is where it is
    kept; `repr=False` keeps it out of reprs and log lines.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    token: str = Field(..., min_length=1, repr=False, description="Issued Vault client token")
    vault_addr: str = Field(..., min_length=1, description="Vault address that issued the token")
    namespace: str | None = Field(default=None, description="Vault namespace, or None")

    def issuer(self) -> str:
        """Name the address, and namespace when there is one, the token was issued for."""
        if self.namespace:
            return f"{self.vault_addr} (namespace {self.namespace})"
        return self.vault_addr


class VaultTokenSource(BaseModel):
    """Where a broker's token came from, and why a stored login was passed over; never the token.

    `source` is `argument`, `keyring`, `environment`, or `none`. `stored_login_skipped` says why
    the token `devops vault login` stored was not used, when there was one.
    """

    model_config = ConfigDict(frozen=True)

    source: str
    stored_login_skipped: str | None = None

    def describe(self) -> str:
        """Render the source for a status row or an error message."""
        if self.stored_login_skipped:
            return f"{self.source} (stored token not used: {self.stored_login_skipped})"
        return self.source


class VaultSecretLookup(BaseModel):
    """The answer to a `vault get`: the value, the source that gave it, and what was checked."""

    value: Any = None
    source: str | None = Field(default=None, description="Source that answered, or None")
    checked: list[str] = Field(default_factory=list, description="Sources consulted, in order")
    fallback_reason: str | None = Field(
        default=None, description="Why the OS keyring was consulted instead of Vault"
    )


class VaultSyncReport(BaseModel):
    """Outcome of copying one Vault secret's fields into the OS keyring."""

    synced: list[str] = Field(default_factory=list, description="Fields stored in the keyring")
    skipped: list[str] = Field(
        default_factory=list, description="Fields never written: the `vault login` record's name"
    )
    missing: list[str] = Field(
        default_factory=list, description="Requested fields Vault has no value for"
    )
    failed: list[str] = Field(default_factory=list, description="Fields the keyring refused")


class VaultLease(BaseModel):
    """A tracked Vault lease and its renewal history."""

    lease_id: str = Field(..., description="Vault lease identifier")
    duration_seconds: int = Field(default=0, description="Lease lifetime granted by Vault")
    renewable: bool = Field(default=False, description="Whether Vault permits renewal")
    secret_path: str = Field(default="", description="Path the leased secret was read from")
    issued_at: float = Field(
        default_factory=time.time, description="Monotonic-safe issue timestamp"
    )
    renewal_count: int = Field(default=0, description="Number of successful renewals")

    def remaining_seconds(self, now: float | None = None) -> float:
        """Return the lease's remaining lifetime, floored at zero."""
        elapsed = (now if now is not None else time.time()) - self.issued_at
        return max(0.0, self.duration_seconds - elapsed)

    def is_expired(self, now: float | None = None) -> bool:
        """Report whether the lease has already lapsed."""
        return self.duration_seconds > 0 and self.remaining_seconds(now) <= 0


class VaultLeaseReport(BaseModel):
    """Outcome of a proactive lease renewal sweep."""

    renewed: list[str] = Field(default_factory=list, description="Leases successfully renewed")
    failed: list[str] = Field(default_factory=list, description="Leases whose renewal failed")
    skipped: list[str] = Field(
        default_factory=list, description="Leases still comfortably within their lifetime"
    )
    tracked_count: int = Field(default=0, description="Total leases under management")

    @property
    def all_renewed(self) -> bool:
        """Report whether every lease needing renewal was renewed."""
        return not self.failed

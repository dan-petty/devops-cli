"""Pydantic models for Vault authentication and dynamic secret lease lifecycle."""

from __future__ import annotations

import time

from pydantic import BaseModel, Field, field_serializer


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

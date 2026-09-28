"""Shared domain models for Cloudflare Zero Trust and DNS configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CloudflareTokenStatus(BaseModel):
    """Cloudflare API token verification result."""

    model_config = ConfigDict(frozen=True)

    id: str
    status: str


class CloudflareZone(BaseModel):
    """Cloudflare managed DNS zone."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    status: str
    paused: bool = False
    name_servers: list[str] = Field(default_factory=list)


class CloudflareDNSRecord(BaseModel):
    """Cloudflare DNS record specification."""

    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    name: str
    content: str
    proxiable: bool = False
    proxied: bool = False
    ttl: int = 1
    comment: str | None = None


class CloudflareTunnelIngressRule(BaseModel):
    """Cloudflare Zero Trust tunnel ingress rule."""

    model_config = ConfigDict(frozen=True)

    service: str
    hostname: str | None = None
    path: str | None = None


class CloudflareTunnelConfig(BaseModel):
    """Cloudflare Zero Trust tunnel configuration payload."""

    model_config = ConfigDict(frozen=True)

    tunnel_id: str
    version: int = 1
    ingress: list[CloudflareTunnelIngressRule] = Field(default_factory=list)


class CloudflareAccessApplication(BaseModel):
    """Cloudflare Zero Trust Access application specification."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    domain: str
    type: str = "self_hosted"
    session_duration: str = "24h"
    allowed_idps: list[str] = Field(default_factory=list)


class CloudflareAccessPolicy(BaseModel):
    """Cloudflare Zero Trust Access policy specification."""

    model_config = ConfigDict(frozen=True)

    id: str | None = None
    name: str
    decision: str = "allow"
    include: list[dict[str, str]] = Field(default_factory=list)


__all__ = [
    "CloudflareAccessApplication",
    "CloudflareAccessPolicy",
    "CloudflareDNSRecord",
    "CloudflareTokenStatus",
    "CloudflareTunnelConfig",
    "CloudflareTunnelIngressRule",
    "CloudflareZone",
]

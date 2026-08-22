"""Pydantic data models for X.509 TLS certificates and Kubernetes TLS secrets."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class CertificateInfo(BaseModel):
    """Structured inspection summary of an X.509 certificate."""

    model_config = ConfigDict(frozen=False)

    subject: dict[str, str] = Field(default_factory=dict)
    issuer: dict[str, str] = Field(default_factory=dict)
    serial_number: str = ""
    not_before: datetime | None = None
    not_after: datetime | None = None
    sans_dns: list[str] = Field(default_factory=list)
    sans_ip: list[str] = Field(default_factory=list)
    is_ca: bool = False
    is_expired: bool = False
    days_remaining: int = 0
    fingerprint_sha256: str = ""
    key_type: str = "RSA"
    key_size: int = 2048
    signature_algorithm: str = "sha256"


class CAGenerationRequest(BaseModel):
    """Parameters for generating a self-signed Root Certificate Authority (CA)."""

    model_config = ConfigDict(frozen=False)

    common_name: str = "Homelab Root CA"
    organization: str = "Homelab DevOps"
    country: str = "US"
    validity_days: int = 3650  # 10 years default for CA
    key_size: int = 2048
    output_dir: Path | None = None


class CertGenerationRequest(BaseModel):
    """Parameters for generating a leaf/server/client TLS certificate."""

    model_config = ConfigDict(frozen=False)

    common_name: str = "localhost"
    sans: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    ca_cert_path: Path | None = None
    ca_key_path: Path | None = None
    validity_days: int = 365  # 1 year default for leaf certs
    key_size: int = 2048
    organization: str = "Homelab DevOps"
    country: str = "US"
    is_server: bool = True
    is_client: bool = True
    output_dir: Path | None = None


class KubernetesTLSSecretResult(BaseModel):
    """Result of creating or updating a kubernetes.io/tls secret."""

    model_config = ConfigDict(frozen=False)

    secret_name: str
    namespace: str
    created: bool = False
    updated: bool = False
    cert_path: str = ""
    key_path: str = ""
    error: str | None = None


class TLSEnablementSummary(BaseModel):
    """Overall summary of TLS generation and Kubernetes enablement."""

    model_config = ConfigDict(frozen=False)

    ca_cert_path: str = ""
    ca_key_path: str = ""
    server_cert_path: str = ""
    server_key_path: str = ""
    fullchain_path: str = ""
    sans: list[str] = Field(default_factory=list)
    k8s_secrets: list[KubernetesTLSSecretResult] = Field(default_factory=list)
    services_configured: list[str] = Field(default_factory=list)

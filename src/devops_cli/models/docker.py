"""Pydantic resource models for Docker operations and CLI functions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class DockerPruneRequest(BaseModel):
    """Request parameters for Docker cleanup and prune operations."""

    all_resources: bool = Field(
        default=False, description="Remove all unused images, not just dangling ones"
    )
    volumes: bool = Field(default=False, description="Prune unused Docker volumes")
    dry_run: bool = Field(
        default=False, description="Simulate pruning without removing containers or images"
    )


class DockerPruneResult(BaseModel):
    """Execution result for Docker prune operations."""

    containers_deleted: int = Field(default=0, description="Number of containers removed")
    images_deleted: int = Field(default=0, description="Number of images removed")
    volumes_deleted: int = Field(default=0, description="Number of volumes removed")
    space_reclaimed_bytes: int = Field(
        default=0, description="Total storage space reclaimed in bytes"
    )
    space_reclaimed_human: str = Field(
        default="0B", description="Human-readable storage space reclaimed"
    )
    success: bool = Field(default=True, description="Whether the prune operation completed cleanly")
    details: list[str] = Field(
        default_factory=list, description="Detailed log records from docker prune"
    )


class ContainerStatEntry(BaseModel):
    """Real-time performance and resource utilization metrics for a container."""

    container_id: str = Field(..., description="Container ID or truncated hash")
    name: str = Field(..., description="Container name")
    cpu_percentage: float = Field(default=0.0, description="CPU utilization percentage")
    memory_usage_bytes: int = Field(default=0, description="Memory used in bytes")
    memory_limit_bytes: int = Field(default=0, description="Memory limit in bytes")
    memory_percentage: float = Field(default=0.0, description="Memory utilization percentage")
    net_io_in_bytes: int = Field(default=0, description="Network ingress bytes")
    net_io_out_bytes: int = Field(default=0, description="Network egress bytes")
    block_io_read_bytes: int = Field(default=0, description="Block storage read bytes")
    block_io_write_bytes: int = Field(default=0, description="Block storage write bytes")
    pids_count: int = Field(default=0, description="Active PID count")


class DockerStatsRequest(BaseModel):
    """Request parameters for Docker container statistics."""

    all_containers: bool = Field(
        default=False, description="Include stopped containers in statistics query"
    )
    no_stream: bool = Field(default=True, description="Capture single snapshot without streaming")


class DockerStatsResult(BaseModel):
    """Aggregated statistics snapshot for Docker containers."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Snapshot capture timestamp"
    )
    containers: list[ContainerStatEntry] = Field(
        default_factory=list, description="Container statistics entries"
    )
    total_containers: int = Field(default=0, description="Total number of running containers")


class DockerLayerAnalysisRequest(BaseModel):
    """Request parameters for Dive container layer efficiency analysis."""

    image_tag: str = Field(..., description="Target container image name and tag")
    lowest_efficiency: float = Field(
        default=0.9, description="Minimum acceptable image efficiency score (0.0 - 1.0)"
    )
    highest_wasted_bytes: int = Field(
        default=20000000, description="Maximum acceptable wasted storage space in bytes"
    )


class DockerLayerAnalysisResult(BaseModel):
    """Results from Dive container image layer analysis."""

    image_tag: str = Field(..., description="Analyzed container image name and tag")
    efficiency_score: float = Field(default=1.0, description="Overall image efficiency score (0-1)")
    wasted_space_bytes: int = Field(
        default=0, description="Total wasted duplicate/overwritten bytes"
    )
    wasted_space_human: str = Field(default="0B", description="Human-readable wasted storage space")
    layer_count: int = Field(default=0, description="Total number of filesystem layers")
    passed: bool = Field(default=True, description="Whether the image meets efficiency thresholds")
    recommendations: list[str] = Field(
        default_factory=list, description="Optimization suggestions for layer size reduction"
    )
    raw_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Raw analyzer metrics payload"
    )


class DockerSignRequest(BaseModel):
    """Request parameters for Sigstore Cosign container image signing."""

    image: str = Field(..., description="Target container image reference (name:tag or digest)")
    key: str | None = Field(default=None, description="Path to private key or keyring:<name>")
    keyless: bool = Field(default=True, description="Sign keylessly using OIDC/Fulcio")
    oidc_token: str | None = Field(
        default=None, description="OIDC identity token or keyring:<name> for keyless signing"
    )
    annotations: list[str] = Field(
        default_factory=list, description="Custom supply chain key=value annotations"
    )
    upload: bool = Field(default=True, description="Upload signature to remote registry")
    dry_run: bool = Field(default=False, description="Simulate signing without modifying registry")


class DockerSignResult(BaseModel):
    """Result of Sigstore Cosign container image signing."""

    image: str = Field(..., description="Signed container image reference")
    digest: str | None = Field(default=None, description="Resolved image digest if available")
    signature_ref: str | None = Field(
        default=None, description="Pushed signature OCI tag or digest"
    )
    keyless: bool = Field(default=True, description="Whether keyless signing was utilized")
    annotations: list[str] = Field(
        default_factory=list, description="Applied supply-chain annotations"
    )
    success: bool = Field(default=True, description="Whether signing completed successfully")
    duration_seconds: float = Field(
        default=0.0, description="Duration of signing operation in seconds"
    )
    details: str | None = Field(default=None, description="Diagnostic output from cosign CLI")


class DockerVerifyRequest(BaseModel):
    """Request parameters for Sigstore Cosign container image signature verification."""

    image: str = Field(..., description="Target container image reference to verify")
    key: str | None = Field(default=None, description="Path to public key or keyring:<name>")
    cert_identity: str | None = Field(
        default=None, description="Expected signer certificate identity (SAN/email/URI)"
    )
    cert_issuer: str | None = Field(
        default=None, description="Expected OIDC certificate issuer URL"
    )
    attestation: bool = Field(
        default=False, description="Verify in-toto attestation predicate instead of signature"
    )
    predicate_type: str | None = Field(
        default=None, description="Attestation predicate type (e.g. slsaprovenance, spdx, custom)"
    )
    insecure_ignore_tlog: bool = Field(
        default=False,
        description="Ignore Rekor transparency log verification (for offline/airgapped)",
    )
    dry_run: bool = Field(default=False, description="Simulate verification without network calls")


class DockerVerifyResult(BaseModel):
    """Result of Sigstore Cosign container image signature verification."""

    image: str = Field(..., description="Verified container image reference")
    verified: bool = Field(
        default=True, description="Whether signature or attestation verified successfully"
    )
    signatures: list[dict[str, Any]] = Field(
        default_factory=list, description="Extracted signatures and verified payload records"
    )
    claims: list[dict[str, Any]] = Field(
        default_factory=list, description="Parsed claims and certificate identities"
    )
    duration_seconds: float = Field(
        default=0.0, description="Duration of verification operation in seconds"
    )
    details: str | None = Field(default=None, description="Diagnostic output from cosign CLI")

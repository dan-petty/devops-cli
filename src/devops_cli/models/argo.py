"""Shared domain models for Argo CD API responses."""

from __future__ import annotations

from pydantic import BaseModel


class ArgoCDApp(BaseModel):
    """An ArgoCD application with sync and health status."""

    name: str
    project: str = ""
    sync_status: str = "Unknown"
    health_status: str = "Unknown"
    repo_url: str = ""
    revision: str = ""

    @classmethod
    def from_api_item(cls, item: dict[str, object]) -> ArgoCDApp:
        """Parse a single item from the ArgoCD /api/v1/applications response."""
        meta = item.get("metadata", {})
        if not isinstance(meta, dict):
            meta = {}
        status = item.get("status", {})
        if not isinstance(status, dict):
            status = {}
        spec = item.get("spec", {})
        if not isinstance(spec, dict):
            spec = {}
        sync = status.get("sync", {})
        if not isinstance(sync, dict):
            sync = {}
        health = status.get("health", {})
        if not isinstance(health, dict):
            health = {}
        source = spec.get("source", {})
        if not isinstance(source, dict):
            source = {}
        return cls(
            name=str(meta.get("name", "")),
            project=str(spec.get("project", "")),
            sync_status=str(sync.get("status", "Unknown")),
            health_status=str(health.get("status", "Unknown")),
            repo_url=str(source.get("repoURL", "")),
            revision=str(sync.get("revision", ""))[:8],
        )


class ArgoFleetAppTarget(BaseModel):
    """Synchronization state for a single cluster target within an Argo fleet."""

    app_name: str
    cluster: str
    status: str = "Pending"
    message: str = ""
    duration_seconds: float = 0.0


class ArgoFleetSyncResult(BaseModel):
    """Aggregated outcome of multi-cluster fleet application synchronization."""

    fleet_name: str = "default-fleet"
    targets: list[ArgoFleetAppTarget] = []
    total_synced: int = 0
    total_failed: int = 0
    success: bool = True


class RolloutMetricThreshold(BaseModel):
    """Metric comparison threshold gate for progressive delivery rollout analysis."""

    metric_name: str
    query: str
    threshold: float
    operator: str = "lte"


class RolloutAnalysisResult(BaseModel):
    """Analysis result of progressive rollout health evaluation and gate triggers."""

    rollout_name: str
    namespace: str = "default"
    passed: bool = True
    metric_results: list[dict[str, object]] = []
    action_taken: str = "promoted"
    reason: str = ""

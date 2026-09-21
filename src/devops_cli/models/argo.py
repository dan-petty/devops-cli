"""Shared domain models for Argo CD API responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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
    operator: Literal["lte", "lt", "gte", "gt", "eq"] = "lte"

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        valid = {"lte", "lt", "gte", "gt", "eq"}
        if v not in valid:
            raise ValueError(f"Unsupported rollout metric operator '{v}'. Allowed: {sorted(valid)}")
        return v


class RolloutAnalysisResult(BaseModel):
    """Analysis result of progressive rollout health evaluation and gate triggers."""

    rollout_name: str
    namespace: str = "default"
    passed: bool = True
    metric_results: list[dict[str, object]] = []
    action_taken: str = "promoted"
    reason: str = ""


class GitOpsDriftEvent(BaseModel):
    """Single file drift detection event."""

    path: str
    change_type: Literal["modified", "created", "deleted"]
    timestamp: float
    file_hash: str = ""


class GitOpsSyncTriggerResult(BaseModel):
    """Outcome of an automated GitOps sync trigger."""

    app_name: str
    changed_files: list[str] = []
    status: Literal["Synced", "Triggered", "Skipped", "Failed", "DryRun"] = "Synced"
    sync_mode: Literal["api", "webhook"] = "api"
    message: str = ""
    duration_seconds: float = 0.0
    timestamp: float = 0.0
    success: bool = True


def _section(manifest: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a named custom resource section, normalising absent or null sections."""
    section = manifest.get(key)
    return section if isinstance(section, dict) else {}


class ArgoResourceState(BaseModel):
    """Typed projection of an Argo custom resource returned by the Kubernetes API.

    Replaces `kubectl`/`argocd` stdout scraping with a structured view of the
    resource's identity, sync state, and health.
    """

    name: str = Field(default="", description="Custom resource name")
    namespace: str = Field(default="", description="Namespace the resource lives in")
    kind: str = Field(default="", description="Custom resource kind")
    project: str = Field(default="", description="ArgoCD project the resource belongs to")
    sync_status: str = Field(default="Unknown", description="ArgoCD sync status")
    health_status: str = Field(default="Unknown", description="ArgoCD health status")
    revision: str = Field(default="", description="Synced source revision")
    repo_url: str = Field(default="", description="Source repository URL")
    created_at: str = Field(default="", description="RFC 3339 creation timestamp")

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> ArgoResourceState:
        """Project a raw Kubernetes custom resource payload into a typed state."""
        meta = _section(manifest, "metadata")
        spec = _section(manifest, "spec")
        status = _section(manifest, "status")
        sync = _section(status, "sync")
        return cls(
            name=str(meta.get("name", "")),
            namespace=str(meta.get("namespace", "")),
            kind=str(manifest.get("kind", "")),
            project=str(spec.get("project", "")),
            sync_status=str(sync.get("status", "Unknown")),
            health_status=str(_section(status, "health").get("status", "Unknown")),
            revision=str(sync.get("revision", ""))[:8],
            repo_url=str(_section(spec, "source").get("repoURL", "")),
            created_at=str(meta.get("creationTimestamp", "")),
        )


class ArgoRolloutState(BaseModel):
    """Typed projection of an Argo Rollout's progressive delivery state."""

    name: str = Field(default="", description="Rollout name")
    namespace: str = Field(default="", description="Namespace the Rollout lives in")
    phase: str = Field(default="Unknown", description="Rollout phase (Progressing, Healthy, ...)")
    message: str = Field(default="", description="Controller status message")
    strategy: str = Field(default="", description="Delivery strategy (canary or blueGreen)")
    current_step: int | None = Field(default=None, description="Active canary step index")
    total_steps: int = Field(default=0, description="Total configured canary steps")
    desired_replicas: int = Field(default=0, description="Desired replica count")
    ready_replicas: int = Field(default=0, description="Ready replica count")
    updated_replicas: int = Field(default=0, description="Replicas running the new revision")
    available_replicas: int = Field(default=0, description="Available replica count")
    paused: bool = Field(default=False, description="Whether the Rollout is paused at a step")
    aborted: bool = Field(default=False, description="Whether the Rollout has been aborted")

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> ArgoRolloutState:
        """Project a raw Rollout custom resource payload into a typed state."""
        meta = _section(manifest, "metadata")
        spec = _section(manifest, "spec")
        status = _section(manifest, "status")
        strategy = _section(spec, "strategy")
        canary = _section(strategy, "canary")
        steps = canary.get("steps")
        active_strategy = "canary" if canary else ("blueGreen" if strategy else "")

        return cls(
            name=str(meta.get("name", "")),
            namespace=str(meta.get("namespace", "")),
            phase=str(status.get("phase", "Unknown")),
            message=str(status.get("message", "")),
            strategy=active_strategy,
            current_step=status.get("currentStepIndex"),
            total_steps=len(steps) if isinstance(steps, list) else 0,
            desired_replicas=int(spec.get("replicas", 0) or 0),
            ready_replicas=int(status.get("readyReplicas", 0) or 0),
            updated_replicas=int(status.get("updatedReplicas", 0) or 0),
            available_replicas=int(status.get("availableReplicas", 0) or 0),
            paused=bool(status.get("pauseConditions") or status.get("controllerPause")),
            aborted=bool(status.get("abort", False)),
        )


class ArgoWorkflowState(BaseModel):
    """Typed projection of an Argo Workflow's execution state."""

    name: str = Field(default="", description="Workflow name")
    namespace: str = Field(default="", description="Namespace the Workflow lives in")
    phase: str = Field(default="Unknown", description="Workflow phase (Running, Succeeded, ...)")
    message: str = Field(default="", description="Controller status message")
    started_at: str = Field(default="", description="RFC 3339 workflow start timestamp")
    finished_at: str = Field(default="", description="RFC 3339 workflow completion timestamp")
    progress: str = Field(default="", description="Completed/total node progress ratio")
    node_count: int = Field(default=0, description="Number of workflow DAG nodes")

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> ArgoWorkflowState:
        """Project a raw Workflow custom resource payload into a typed state."""
        meta = _section(manifest, "metadata")
        status = _section(manifest, "status")
        return cls(
            name=str(meta.get("name", "")),
            namespace=str(meta.get("namespace", "")),
            phase=str(status.get("phase", "Unknown")),
            message=str(status.get("message", "")),
            started_at=str(status.get("startedAt", "") or ""),
            finished_at=str(status.get("finishedAt", "") or ""),
            progress=str(status.get("progress", "") or ""),
            node_count=len(_section(status, "nodes")),
        )

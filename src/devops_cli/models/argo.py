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

"""DevOps CLI subcommand apps and domain operation handlers."""

from __future__ import annotations

COMMAND_NAMES: list[str] = [
    "ai",
    "analyze",
    "argo",
    "benchmark",
    "branches",
    "ci",
    "config",
    "devcontainer",
    "docker",
    "docs",
    "grafana",
    "install-tools",
    "k8s",
    "kustomize",
    "mcp",
    "pr",
    "prometheus",
    "rag",
    "release",
    "repos",
    "review",
    "scan",
    "serve",
    "ssh",
    "telemetry",
    "tf",
    "tls",
    "uv",
    "workspace",
]

__all__ = [
    "COMMAND_NAMES",
]

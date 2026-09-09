"""Interactive Terminal UI dashboard module."""

from __future__ import annotations

from devops_cli.ui.dashboard import DashboardApp, HelpScreen
from devops_cli.ui.data_providers import (
    DockerSummary,
    K8sSummary,
    ReviewSummary,
    TelemetrySummary,
    ValkeySummary,
    fetch_docker_status,
    fetch_k8s_status,
    fetch_review_status,
    fetch_telemetry_status,
    fetch_valkey_status,
)

__all__ = [
    "DashboardApp",
    "DockerSummary",
    "HelpScreen",
    "K8sSummary",
    "ReviewSummary",
    "TelemetrySummary",
    "ValkeySummary",
    "fetch_docker_status",
    "fetch_k8s_status",
    "fetch_review_status",
    "fetch_telemetry_status",
    "fetch_valkey_status",
]

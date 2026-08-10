"""Domain model registry for devops-cli.

All Pydantic models for structured data exchange are defined in submodules
and re-exported here for convenient single-import access:

    from devops_cli.models import ArgoCDApp, BranchListing, ChatMessage, ...
"""

from __future__ import annotations

from devops_cli.models.ai import ChatMessage
from devops_cli.models.argo import ArgoCDApp
from devops_cli.models.git import BranchListing
from devops_cli.models.github import SSHKeyInfo
from devops_cli.models.grafana import GrafanaAlertRule, GrafanaDashboard, GrafanaDatasource
from devops_cli.models.prometheus import PrometheusQueryResult, PrometheusSeries
from devops_cli.models.ssh import ManagedSSHKey

__all__ = [
    "ArgoCDApp",
    "BranchListing",
    "ChatMessage",
    "GrafanaAlertRule",
    "GrafanaDashboard",
    "GrafanaDatasource",
    "ManagedSSHKey",
    "PrometheusQueryResult",
    "PrometheusSeries",
    "SSHKeyInfo",
]

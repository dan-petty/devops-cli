"""Domain model registry for devops-cli.

All Pydantic models for structured data exchange are defined in submodules
and re-exported here for convenient single-import access:

    from devops_cli.models import ArgoCDApp, BranchListing, ChatMessage, ...
"""

from __future__ import annotations

from devops_cli.dry_run import CommandDryRunResult
from devops_cli.models.ai import (
    AnalysisMetadata,
    ChatMessage,
    FileAnalysisMeta,
    MCPToolInfo,
    ProjectAnalysisMeta,
)
from devops_cli.models.benchmark import (
    BenchmarkCategory,
    BenchmarkReport,
    BenchmarkTask,
    ModelBenchmarkSummary,
    PeerGrade,
    TaskResponse,
)
from devops_cli.models.git import BranchListing
from devops_cli.models.github import SSHKeyInfo
from devops_cli.models.grafana import GrafanaAlertRule, GrafanaDashboard, GrafanaDatasource
from devops_cli.models.prometheus import PrometheusQueryResult, PrometheusSeries
from devops_cli.models.ssh import ManagedSSHKey

__all__ = [
    "AnalysisMetadata",
    "ArgoCDApp",
    "BenchmarkCategory",
    "BenchmarkReport",
    "BenchmarkTask",
    "BranchListing",
    "ChatMessage",
    "CommandDryRunResult",
    "FileAnalysisMeta",
    "GrafanaAlertRule",
    "GrafanaDashboard",
    "GrafanaDatasource",
    "MCPToolInfo",
    "ManagedSSHKey",
    "ModelBenchmarkSummary",
    "PeerGrade",
    "ProjectAnalysisMeta",
    "PrometheusQueryResult",
    "PrometheusSeries",
    "SSHKeyInfo",
    "TaskResponse",
]

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
from devops_cli.models.argo import ArgoCDApp
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
from devops_cli.models.tls import (
    CAGenerationRequest,
    CertGenerationRequest,
    CertificateInfo,
    KubernetesTLSSecretResult,
    TLSEnablementSummary,
)
from devops_cli.models.vulnerability import (
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
    VulnerabilityRecord,
)

__all__ = [
    "AnalysisMetadata",
    "ArgoCDApp",
    "BenchmarkCategory",
    "BenchmarkReport",
    "BenchmarkTask",
    "BranchListing",
    "CAGenerationRequest",
    "CertGenerationRequest",
    "CertificateInfo",
    "ChatMessage",
    "CommandDryRunResult",
    "DependencySpec",
    "FileAnalysisMeta",
    "GrafanaAlertRule",
    "GrafanaDashboard",
    "GrafanaDatasource",
    "KubernetesTLSSecretResult",
    "MCPToolInfo",
    "ManagedSSHKey",
    "ModelBenchmarkSummary",
    "NetworkReference",
    "NetworkReputationRecord",
    "PeerGrade",
    "ProjectAnalysisMeta",
    "PrometheusQueryResult",
    "PrometheusSeries",
    "SSHKeyInfo",
    "TLSEnablementSummary",
    "TaskResponse",
    "VulnerabilityRecord",
]

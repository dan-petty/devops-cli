"""Standardized domain exception hierarchy for devops-cli.

Each subject module holds the errors of one subject, and this module re-exports them. The one
exception that it defines itself, `AgentAuditFilingError`, belongs to the one command that raises
it (#2346), and a subject module of one error would name a subject that no other error shares.
"""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.argo import (
    ArgoError,
    ArgoResourceNotFoundError,
    ArgoWorkflowTimeoutError,
)
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.cloudflare import (
    CloudflareAPIError,
    CloudflareAuthError,
    CloudflareError,
)
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.docker import (
    CosignError,
    CosignVerificationError,
    DockerDaemonUnavailableError,
    DockerEngineError,
    DockerError,
    DockerSandboxError,
    RegistryReadError,
    RegistryTagNotFoundError,
)
from devops_cli.exceptions.git import (
    BranchAlreadyExistsError,
    GitHubApiAccessRefusedError,
    GitHubFileNotFoundError,
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubScopeError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
    GitOperationError,
    InvalidBranchNameError,
)
from devops_cli.exceptions.gitea import (
    GiteaAccessBlocked,
    GiteaError,
)
from devops_cli.exceptions.http import ServiceRequestError
from devops_cli.exceptions.k8s import (
    ChaosExecutionError,
    ClusterJobError,
    ClusterSecretPushError,
    ClusterSecretWriteError,
    KubernetesContextError,
    KubernetesDeployError,
    KubernetesError,
    KubernetesLoggingError,
)
from devops_cli.exceptions.roadmap import (
    ImplementEvalError,
    RefusedPullReply,
    RoadmapAlternativesError,
    RoadmapClaimError,
    RoadmapImplementError,
    RoadmapIntakeError,
    RoadmapItemChangedError,
    RoadmapOpenRefusedError,
    RoadmapPlanReadBackError,
    RoadmapPlanRewriteError,
    RoadmapPullReviewLimitError,
    RoadmapRecordMarkLostError,
    RoadmapRefineError,
    RoadmapRunError,
    RoadmapStageDegenerateError,
    RoadmapStageError,
    RoadmapStatusLostError,
    RoadmapTimeBudgetError,
    ServiceStoppingError,
    ended_by_stop,
)
from devops_cli.exceptions.sandbox import (
    SandboxError,
    SandboxNotFoundError,
    SandboxPortAllocationError,
    SandboxUnavailableError,
    SandboxValidationError,
)
from devops_cli.exceptions.security import (
    KeyringUnavailableError,
    SecurityError,
    SSRFBlockedError,
)
from devops_cli.exceptions.telemetry import (
    LogfireConfigurationError,
    ServiceStatusError,
    TelemetryError,
)
from devops_cli.exceptions.tools import (
    DependencyError,
    SubprocessError,
    ToolDownloadError,
    ToolExecutionError,
)
from devops_cli.exceptions.validation import (
    DocsSiteError,
    InvalidURLError,
    ValidationError,
)
from devops_cli.exceptions.valkey import (
    ValkeyAuthenticationError,
    ValkeyCommandError,
    ValkeyConnectionError,
    ValkeyError,
    ValkeyTimeoutError,
)
from devops_cli.exceptions.vault import (
    VaultAuthenticationError,
    VaultConfigurationError,
    VaultError,
    VaultKeyError,
    VaultLeaseError,
    VaultOperationError,
    VaultUnreachableError,
)


class AgentAuditFilingError(DevOpsCLIError):
    """Raised when `devops roadmap intake` does not file one draft of `devops ai agent-audit` (#2346).

    The audit stops at the first draft that intake does not file: a later draft would file an issue
    on a roadmap that the failed run left part-written. The message names the draft by its title,
    the exit status of the child and the last line that it printed, and the base class masks each
    secret of that line; `draft` holds the title.
    """

    error_code = "AGENT_AUDIT_FILING_FAILED"

    def __init__(
        self,
        draft: str,
        *,
        status: int,
        detail: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.draft = draft
        super().__init__(
            f"The audit filed no issue for the draft '{draft}': `devops roadmap intake` exited "
            f"with status {status} and printed: {detail}",
            details={"draft": draft, "status": status, **(details or {})},
        )


__all__ = [
    "AgentAuditFilingError",
    "ArgoError",
    "ArgoResourceNotFoundError",
    "ArgoWorkflowTimeoutError",
    "BranchAlreadyExistsError",
    "ChaosExecutionError",
    "CloudflareAPIError",
    "CloudflareAuthError",
    "CloudflareError",
    "ClusterJobError",
    "ClusterSecretPushError",
    "ClusterSecretWriteError",
    "ConfigurationError",
    "CosignError",
    "CosignVerificationError",
    "DependencyError",
    "DevOpsCLIError",
    "DockerDaemonUnavailableError",
    "DockerEngineError",
    "DockerError",
    "DockerSandboxError",
    "DocsSiteError",
    "GitHubApiAccessRefusedError",
    "GitHubFileNotFoundError",
    "GitHubNotFoundError",
    "GitHubOperationError",
    "GitHubRateLimitError",
    "GitHubScopeError",
    "GitHubUnauthenticatedError",
    "GitHubUnreadError",
    "GitOperationError",
    "GiteaAccessBlocked",
    "GiteaError",
    "ImplementEvalError",
    "InvalidBranchNameError",
    "InvalidURLError",
    "KeyringUnavailableError",
    "KubernetesContextError",
    "KubernetesDeployError",
    "KubernetesError",
    "KubernetesLoggingError",
    "LogfireConfigurationError",
    "RefusedPullReply",
    "RegistryReadError",
    "RegistryTagNotFoundError",
    "RoadmapAlternativesError",
    "RoadmapClaimError",
    "RoadmapImplementError",
    "RoadmapIntakeError",
    "RoadmapItemChangedError",
    "RoadmapOpenRefusedError",
    "RoadmapPlanReadBackError",
    "RoadmapPlanRewriteError",
    "RoadmapPullReviewLimitError",
    "RoadmapRecordMarkLostError",
    "RoadmapRefineError",
    "RoadmapRunError",
    "RoadmapStageDegenerateError",
    "RoadmapStageError",
    "RoadmapStatusLostError",
    "RoadmapTimeBudgetError",
    "SSRFBlockedError",
    "SandboxError",
    "SandboxNotFoundError",
    "SandboxPortAllocationError",
    "SandboxUnavailableError",
    "SandboxValidationError",
    "SecurityError",
    "ServiceRequestError",
    "ServiceStatusError",
    "ServiceStoppingError",
    "SubprocessError",
    "TelemetryError",
    "ToolDownloadError",
    "ToolExecutionError",
    "ValidationError",
    "ValkeyAuthenticationError",
    "ValkeyCommandError",
    "ValkeyConnectionError",
    "ValkeyError",
    "ValkeyTimeoutError",
    "VaultAuthenticationError",
    "VaultConfigurationError",
    "VaultError",
    "VaultKeyError",
    "VaultLeaseError",
    "VaultOperationError",
    "VaultUnreachableError",
    "ended_by_stop",
]

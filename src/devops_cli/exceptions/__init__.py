"""Standardized domain exception hierarchy for devops-cli."""

from __future__ import annotations

from devops_cli.exceptions.argo import ArgoError, ArgoResourceNotFoundError
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
)
from devops_cli.exceptions.git import (
    BranchAlreadyExistsError,
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
    RoadmapAlternativesError,
    RoadmapClaimError,
    RoadmapImplementError,
    RoadmapIntakeError,
    RoadmapItemChangedError,
    RoadmapRefineError,
    RoadmapRunError,
    RoadmapStageError,
    ServiceStoppingError,
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
    ChecksumMismatchError,
    DependencyError,
    SubprocessError,
    ToolDownloadError,
    ToolExecutionError,
)
from devops_cli.exceptions.validation import (
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

__all__ = [
    "ArgoError",
    "ArgoResourceNotFoundError",
    "BranchAlreadyExistsError",
    "ChaosExecutionError",
    "ChecksumMismatchError",
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
    "GitHubFileNotFoundError",
    "GitHubNotFoundError",
    "GitHubOperationError",
    "GitHubRateLimitError",
    "GitHubScopeError",
    "GitHubUnauthenticatedError",
    "GitHubUnreadError",
    "GitOperationError",
    "ImplementEvalError",
    "InvalidBranchNameError",
    "InvalidURLError",
    "KeyringUnavailableError",
    "KubernetesContextError",
    "KubernetesDeployError",
    "KubernetesError",
    "KubernetesLoggingError",
    "LogfireConfigurationError",
    "RegistryReadError",
    "RoadmapAlternativesError",
    "RoadmapClaimError",
    "RoadmapImplementError",
    "RoadmapIntakeError",
    "RoadmapItemChangedError",
    "RoadmapRefineError",
    "RoadmapRunError",
    "RoadmapStageError",
    "SSRFBlockedError",
    "SandboxError",
    "SandboxNotFoundError",
    "SandboxPortAllocationError",
    "SandboxUnavailableError",
    "SandboxValidationError",
    "SecurityError",
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
]

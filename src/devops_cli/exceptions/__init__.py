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
)
from devops_cli.exceptions.docs import DocCompactionError
from devops_cli.exceptions.git import (
    BranchAlreadyExistsError,
    GitHubFileNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
    GitOperationError,
    InvalidBranchNameError,
    ReleaseBranchMissingError,
    ReleasePRCreationError,
    ReleasePushError,
    ReleasePushRefusedError,
    ReleaseRemoteFetchError,
    ReleaseWorkingTreeDirtyError,
)
from devops_cli.exceptions.k8s import (
    ChaosExecutionError,
    ClusterJobError,
    ClusterSecretPushError,
    ClusterSecretWriteError,
    GitOpsSyncError,
    KubernetesContextError,
    KubernetesDeployError,
    KubernetesError,
    KubernetesLoggingError,
)
from devops_cli.exceptions.roadmap import (
    RoadmapCardChangedError,
    RoadmapRefineError,
    RoadmapRunError,
)
from devops_cli.exceptions.sandbox import (
    SandboxError,
    SandboxNotFoundError,
    SandboxPortAllocationError,
    SandboxValidationError,
)
from devops_cli.exceptions.security import (
    KeyringUnavailableError,
    SecretExposureError,
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
    InvalidVersionError,
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
    "DocCompactionError",
    "DockerDaemonUnavailableError",
    "DockerEngineError",
    "DockerError",
    "DockerSandboxError",
    "GitHubFileNotFoundError",
    "GitHubOperationError",
    "GitHubRateLimitError",
    "GitHubUnauthenticatedError",
    "GitOperationError",
    "GitOpsSyncError",
    "InvalidBranchNameError",
    "InvalidURLError",
    "InvalidVersionError",
    "KeyringUnavailableError",
    "KubernetesContextError",
    "KubernetesDeployError",
    "KubernetesError",
    "KubernetesLoggingError",
    "LogfireConfigurationError",
    "ReleaseBranchMissingError",
    "ReleasePRCreationError",
    "ReleasePushError",
    "ReleasePushRefusedError",
    "ReleaseRemoteFetchError",
    "ReleaseWorkingTreeDirtyError",
    "RoadmapCardChangedError",
    "RoadmapRefineError",
    "RoadmapRunError",
    "SSRFBlockedError",
    "SandboxError",
    "SandboxNotFoundError",
    "SandboxPortAllocationError",
    "SandboxValidationError",
    "SecretExposureError",
    "SecurityError",
    "ServiceStatusError",
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

"""Standardized domain exception hierarchy for devops-cli."""

from __future__ import annotations

from devops_cli.exceptions.ai import (
    AgentRunError,
    ApprovalRequired,
    CallDeferred,
    ConcurrencyLimitExceeded,
    ContentFilterError,
    ContextBudgetExceededError,
    HarnessExecutionError,
    HarnessValidationError,
    IncompleteToolCall,
    LLMInferenceError,
    ModelAPIError,
    ModelBundleError,
    ModelHTTPError,
    ModelRetry,
    ModelUnavailableError,
    PersonaExecutionError,
    RunCancelled,
    SuspendedResponseExpired,
    ToolFailed,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
    UserError,
)
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.docker import (
    DockerError,
    DockerSandboxError,
)
from devops_cli.exceptions.git import (
    BranchAlreadyExistsError,
    GitHubOperationError,
    GitOperationError,
    InvalidBranchNameError,
)
from devops_cli.exceptions.k8s import (
    ChaosExecutionError,
    KubernetesContextError,
    KubernetesDeployError,
    KubernetesError,
)
from devops_cli.exceptions.security import (
    KeyringUnavailableError,
    SecretExposureError,
    SecurityError,
    SSRFBlockedError,
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
from devops_cli.exceptions.vault import (
    VaultConfigurationError,
    VaultError,
    VaultKeyError,
    VaultOperationError,
)

__all__ = [
    "AgentRunError",
    "ApprovalRequired",
    "BranchAlreadyExistsError",
    "CallDeferred",
    "ChaosExecutionError",
    "ChecksumMismatchError",
    "ConcurrencyLimitExceeded",
    "ConfigurationError",
    "ContentFilterError",
    "ContextBudgetExceededError",
    "DevOpsCLIError",
    "DockerError",
    "DockerSandboxError",
    "GitHubOperationError",
    "GitOperationError",
    "HarnessExecutionError",
    "HarnessValidationError",
    "IncompleteToolCall",
    "InvalidBranchNameError",
    "InvalidURLError",
    "InvalidVersionError",
    "KeyringUnavailableError",
    "KubernetesContextError",
    "KubernetesDeployError",
    "KubernetesError",
    "LLMInferenceError",
    "ModelAPIError",
    "ModelBundleError",
    "ModelHTTPError",
    "ModelRetry",
    "ModelUnavailableError",
    "PersonaExecutionError",
    "RunCancelled",
    "SSRFBlockedError",
    "SecretExposureError",
    "SecurityError",
    "SuspendedResponseExpired",
    "DependencyError",
    "SubprocessError",
    "ToolDownloadError",
    "ToolExecutionError",
    "ToolFailed",
    "UnexpectedModelBehavior",
    "UsageLimitExceeded",
    "UserError",
    "ValidationError",
    "VaultConfigurationError",
    "VaultError",
    "VaultKeyError",
    "VaultOperationError",
]

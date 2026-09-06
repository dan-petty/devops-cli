"""Standardized domain exception hierarchy for devops-cli."""

from __future__ import annotations

from devops_cli.exceptions.ai import (
    AgentRunError,
    ApprovalRequired,
    CallDeferred,
    ConcurrencyLimitExceeded,
    ContentFilterError,
    ContextBudgetExceededError,
    IncompleteToolCall,
    LLMInferenceError,
    ModelAPIError,
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
from devops_cli.exceptions.git import (
    BranchAlreadyExistsError,
    GitOperationError,
    InvalidBranchNameError,
)
from devops_cli.exceptions.security import (
    KeyringUnavailableError,
    SecretExposureError,
    SecurityError,
    SSRFBlockedError,
)
from devops_cli.exceptions.tools import (
    ChecksumMismatchError,
    ToolDownloadError,
    ToolExecutionError,
)
from devops_cli.exceptions.validation import (
    InvalidURLError,
    InvalidVersionError,
    ValidationError,
)

__all__ = [
    "AgentRunError",
    "ApprovalRequired",
    "BranchAlreadyExistsError",
    "CallDeferred",
    "ChecksumMismatchError",
    "ConcurrencyLimitExceeded",
    "ConfigurationError",
    "ContentFilterError",
    "ContextBudgetExceededError",
    "DevOpsCLIError",
    "GitOperationError",
    "IncompleteToolCall",
    "InvalidBranchNameError",
    "InvalidURLError",
    "InvalidVersionError",
    "KeyringUnavailableError",
    "LLMInferenceError",
    "ModelAPIError",
    "ModelHTTPError",
    "ModelRetry",
    "ModelUnavailableError",
    "PersonaExecutionError",
    "RunCancelled",
    "SSRFBlockedError",
    "SecretExposureError",
    "SecurityError",
    "SuspendedResponseExpired",
    "ToolDownloadError",
    "ToolExecutionError",
    "ToolFailed",
    "UnexpectedModelBehavior",
    "UsageLimitExceeded",
    "UserError",
    "ValidationError",
]

"""Standardized domain exception hierarchy for devops-cli."""

from __future__ import annotations

from devops_cli.exceptions.ai import (
    ApprovalRequired,
    CallDeferred,
    ContentFilterError,
    ContextBudgetExceededError,
    LLMInferenceError,
    ModelRetry,
    ModelUnavailableError,
    PersonaExecutionError,
    ToolFailed,
    UnexpectedModelBehavior,
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
    "ApprovalRequired",
    "BranchAlreadyExistsError",
    "CallDeferred",
    "ChecksumMismatchError",
    "ConfigurationError",
    "ContentFilterError",
    "ContextBudgetExceededError",
    "DevOpsCLIError",
    "GitOperationError",
    "InvalidBranchNameError",
    "InvalidURLError",
    "InvalidVersionError",
    "KeyringUnavailableError",
    "LLMInferenceError",
    "ModelRetry",
    "ModelUnavailableError",
    "PersonaExecutionError",
    "SSRFBlockedError",
    "SecretExposureError",
    "SecurityError",
    "ToolDownloadError",
    "ToolExecutionError",
    "ToolFailed",
    "UnexpectedModelBehavior",
    "ValidationError",
]

"""Standardized domain exception hierarchy for devops-cli."""

from __future__ import annotations

from devops_cli.exceptions.ai import (
    ContextBudgetExceededError,
    LLMInferenceError,
    ModelUnavailableError,
    PersonaExecutionError,
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
    "BranchAlreadyExistsError",
    "ChecksumMismatchError",
    "ConfigurationError",
    "ContextBudgetExceededError",
    "DevOpsCLIError",
    "GitOperationError",
    "InvalidBranchNameError",
    "InvalidURLError",
    "InvalidVersionError",
    "KeyringUnavailableError",
    "LLMInferenceError",
    "ModelUnavailableError",
    "PersonaExecutionError",
    "SSRFBlockedError",
    "SecretExposureError",
    "SecurityError",
    "ToolDownloadError",
    "ToolExecutionError",
    "ValidationError",
]

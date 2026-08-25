"""Standardized domain exception hierarchy for devops-cli."""

from __future__ import annotations

from devops_cli.exceptions.ai import (
    ContextBudgetExceededError,
    LLMInferenceError,
    ModelUnavailableError,
    PersonaExecutionError,
)
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.security import (
    KeyringUnavailableError,
    SecretExposureError,
    SecurityError,
    SSRFBlockedError,
)

__all__ = [
    "ContextBudgetExceededError",
    "DevOpsCLIError",
    "KeyringUnavailableError",
    "LLMInferenceError",
    "ModelUnavailableError",
    "PersonaExecutionError",
    "SSRFBlockedError",
    "SecretExposureError",
    "SecurityError",
]

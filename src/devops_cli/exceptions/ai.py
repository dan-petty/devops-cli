"""AI, LLM, and prompt-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import CONST_ERROR_CODE_LLM_INFERENCE, CONST_EXIT_ERROR_INFERENCE
from devops_cli.exceptions.base import DevOpsCLIError


class LLMInferenceError(DevOpsCLIError, ValueError):
    """Base exception for LLM provider invocation failures."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        exit_code: int = CONST_EXIT_ERROR_INFERENCE,
        error_code: str = CONST_ERROR_CODE_LLM_INFERENCE,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"provider": provider, "model": model}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class ContextBudgetExceededError(LLMInferenceError):
    """Raised when prompt token payload exceeds model context window limits."""

    def __init__(
        self,
        token_count: int,
        budget: int,
        *,
        model: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"Context budget exceeded: {token_count} tokens exceeds budget of {budget}"
        err_details = {"token_count": token_count, "budget": budget}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            model=model,
            exit_code=11,
            error_code="CONTEXT_BUDGET_EXCEEDED",
            details=err_details,
        )


class ModelUnavailableError(LLMInferenceError):
    """Raised when the requested LLM backend or model endpoint is unreachable."""

    def __init__(
        self,
        model: str,
        provider: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"Model '{model}' is unavailable on provider '{provider}'"
        super().__init__(
            msg,
            provider=provider,
            model=model,
            exit_code=12,
            error_code="MODEL_UNAVAILABLE",
            details=details,
        )


class PersonaExecutionError(LLMInferenceError):
    """Raised when an AI reviewer persona fails during diff analysis."""

    def __init__(
        self,
        persona: str,
        filename: str,
        reason: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"Persona '{persona}' failed to evaluate '{filename}': {reason}"
        err_details = {"persona": persona, "filename": filename, "reason": reason}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            exit_code=13,
            error_code="PERSONA_EXECUTION_ERROR",
            details=err_details,
        )


class ModelRetry(DevOpsCLIError, ValueError):
    """Raised by tools or output validators to request the model to retry with corrective feedback."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            exit_code=14,
            error_code="MODEL_RETRY_REQUESTED",
            details=details or {},
        )


class UnexpectedModelBehavior(LLMInferenceError):
    """Raised when model retry budget is exhausted or model emits unrecoverable response."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            exit_code=15,
            error_code="UNEXPECTED_MODEL_BEHAVIOR",
            details=details,
        )


class ToolFailed(DevOpsCLIError, RuntimeError):
    """Raised when a tool encounters an unrecoverable runtime failure without requesting model retry."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            exit_code=16,
            error_code="TOOL_FAILED",
            details=details or {},
        )


class ApprovalRequired(DevOpsCLIError, RuntimeError):
    """Raised by a tool or validator when human approval is required to proceed."""

    def __init__(
        self,
        message: str = "Tool call requires human approval",
        *,
        metadata: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = dict(details or {})
        if metadata:
            merged_details["metadata"] = metadata
        super().__init__(
            message,
            exit_code=17,
            error_code="APPROVAL_REQUIRED",
            details=merged_details,
        )
        self.metadata = metadata or {}


class CallDeferred(DevOpsCLIError, RuntimeError):
    """Raised by a tool when execution is deferred to an external worker or async system."""

    def __init__(
        self,
        message: str = "Tool call deferred to external execution",
        *,
        metadata: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = dict(details or {})
        if metadata:
            merged_details["metadata"] = metadata
        super().__init__(
            message,
            exit_code=18,
            error_code="CALL_DEFERRED",
            details=merged_details,
        )
        self.metadata = metadata or {}

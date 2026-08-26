"""AI, LLM, and prompt-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class LLMInferenceError(DevOpsCLIError, ValueError):
    """Base exception for LLM provider invocation failures."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        exit_code: int = 10,
        error_code: str = "LLM_INFERENCE_ERROR",
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

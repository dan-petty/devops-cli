"""AI, LLM, and prompt-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_CAPABILITY_DEGRADATION,
    CONST_ERROR_CODE_CONSTELLATION_FAILOVER,
    CONST_ERROR_CODE_CONSTELLATION_QUIESCE,
    CONST_ERROR_CODE_CONSTELLATION_RESUME,
    CONST_ERROR_CODE_DOCS_INGESTION,
    CONST_ERROR_CODE_HARNESS_VALIDATION,
    CONST_ERROR_CODE_LIBRARY_INGESTION,
    CONST_ERROR_CODE_LIBRARY_NOT_FOUND,
    CONST_ERROR_CODE_LLM_INFERENCE,
    CONST_ERROR_CODE_MODEL_BUNDLE,
    CONST_ERROR_CODE_MODEL_GATEWAY_UNREACHABLE,
    CONST_ERROR_CODE_REVIEW_POOL,
    CONST_ERROR_CODE_REVIEW_SESSION_EXISTS,
    CONST_EXIT_ERROR_INFERENCE,
    CONST_EXIT_FAILURE,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
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

    DEFAULT_ERROR_CODE = "CONTEXT_BUDGET_EXCEEDED"
    DEFAULT_EXIT_CODE = 11

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

    DEFAULT_ERROR_CODE = "MODEL_UNAVAILABLE"
    DEFAULT_EXIT_CODE = 12

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


class ModelGatewayUnreachableError(LLMInferenceError):
    """Raised when a model call through the gateway fails, so the command decided and wrote nothing."""

    DEFAULT_ERROR_CODE = CONST_ERROR_CODE_MODEL_GATEWAY_UNREACHABLE
    DEFAULT_EXIT_CODE = CONST_EXIT_FAILURE

    def __init__(self, gateway: str, cause: Exception, *, consequence: str) -> None:
        from devops_cli.security.sanitizer import mask_secrets, mask_uri_credentials

        safe_gateway = mask_uri_credentials(gateway)
        safe_cause = mask_secrets(str(cause)[:200])
        super().__init__(
            f"The model gateway {safe_gateway} did not answer ({type(cause).__name__}: "
            f"{safe_cause}), so {consequence}. Run it again once the gateway answers.",
            exit_code=CONST_EXIT_FAILURE,
            error_code=CONST_ERROR_CODE_MODEL_GATEWAY_UNREACHABLE,
            details={"gateway": safe_gateway[:256]},
        )


class CapabilityDegradationError(DevOpsCLIError, ValueError):
    """Raised when a fallback or failover model breaches minimum capability tier requirements."""

    DEFAULT_ERROR_CODE = CONST_ERROR_CODE_CAPABILITY_DEGRADATION
    DEFAULT_EXIT_CODE = CONST_EXIT_FAILURE

    def __init__(
        self,
        message: str,
        *,
        role: str,
        required_tier_b: int,
        model: str,
        candidate_tier_b: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details: dict[str, Any] = {
            "role": role,
            "required_tier_b": required_tier_b,
            "model": model,
            "candidate_tier_b": candidate_tier_b,
        }
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=self.DEFAULT_EXIT_CODE,
            error_code=self.DEFAULT_ERROR_CODE,
            details=err_details,
        )


class ModelBundleError(DevOpsCLIError, ValueError):
    """Raised when an AI model bundle cannot be located, resolved, or loaded."""

    def __init__(
        self,
        message: str,
        *,
        bundle_path: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_MODEL_BUNDLE,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"bundle_path": bundle_path}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class HarnessValidationError(DevOpsCLIError, ValueError):
    """Raised when an AI evaluation or harness schema validation fails."""

    def __init__(
        self,
        message: str,
        *,
        field_name: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_HARNESS_VALIDATION,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"field_name": field_name}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class ConstellationQuiesceError(DevOpsCLIError, RuntimeError):
    """Raised when constellation quiesce suspension fails."""

    def __init__(
        self,
        message: str,
        *,
        reason: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_CONSTELLATION_QUIESCE,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"reason": reason}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class ConstellationFailoverError(DevOpsCLIError, RuntimeError):
    """Raised when emergency failover routing fails."""

    def __init__(
        self,
        message: str,
        *,
        target_provider: str | None = None,
        target_model: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_CONSTELLATION_FAILOVER,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"target_provider": target_provider, "target_model": target_model}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class ConstellationResumeError(DevOpsCLIError, RuntimeError):
    """Raised when resuming suspended constellation tasks fails."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_CONSTELLATION_RESUME,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=details)


class ReviewPoolError(DevOpsCLIError, RuntimeError):
    """Raised when an error occurs during parallel review worker pool execution."""

    def __init__(
        self,
        message: str = "Parallel review worker pool execution failed",
        *,
        errors: list[Exception] | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_REVIEW_POOL,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = details or {}
        if errors:
            err_details["error_count"] = len(errors)
            err_details["errors"] = [str(e) for e in errors]
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)
        self.errors = errors or []


class ReviewSessionExistsError(DevOpsCLIError):
    """Raised when a review is published under the name of a session that is already published."""

    def __init__(self, name: str, *, staging: str) -> None:
        bounded_name = name[:CONST_MAX_ERROR_DETAIL_LENGTH]
        bounded_staging = staging[:CONST_MAX_ERROR_DETAIL_LENGTH]
        super().__init__(
            f"Review session {bounded_name} was not published: a session of that name already "
            f"exists. The review's files are in {bounded_staging}.",
            error_code=CONST_ERROR_CODE_REVIEW_SESSION_EXISTS,
            details={"session": bounded_name, "staging": bounded_staging},
        )


class LibraryIngestionError(DevOpsCLIError):
    """Base exception for package introspection and library ingestion errors."""

    DEFAULT_ERROR_CODE = CONST_ERROR_CODE_LIBRARY_INGESTION
    DEFAULT_EXIT_CODE = CONST_EXIT_FAILURE

    def __init__(
        self,
        message: str = "Library ingestion failed",
        *,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_LIBRARY_INGESTION,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=details)


class LibraryNotFoundError(LibraryIngestionError):
    """Raised when target package cannot be imported or found in the environment."""

    DEFAULT_ERROR_CODE = CONST_ERROR_CODE_LIBRARY_NOT_FOUND
    DEFAULT_EXIT_CODE = CONST_EXIT_FAILURE

    def __init__(
        self,
        message: str = "Target library was not found in environment",
        *,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_LIBRARY_NOT_FOUND,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=details)


class DocsIngestionError(DevOpsCLIError):
    """Base exception for documentation ingestion errors."""

    DEFAULT_ERROR_CODE = CONST_ERROR_CODE_DOCS_INGESTION
    DEFAULT_EXIT_CODE = CONST_EXIT_FAILURE

    def __init__(
        self,
        message: str = "Documentation ingestion failed",
        *,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_DOCS_INGESTION,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=details)


class StructuredOutputSchemaError(DevOpsCLIError, ValueError):
    """Raised when a schema class is missing or invalid for structured LLM output generation."""

    def __init__(
        self,
        message: str = "A schema model class must be provided.",
        *,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "STRUCTURED_OUTPUT_SCHEMA_INVALID",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=details)


_PYDANTIC_AI_NAMES: frozenset[str] = frozenset(
    {
        "AgentRunError",
        "ApprovalRequired",
        "CallDeferred",
        "ConcurrencyLimitExceeded",
        "ContentFilterError",
        "CostCalculationFailedWarning",
        "CostNotFoundWarning",
        "FallbackExceptionGroup",
        "IncompleteToolCall",
        "MessageHistoryMutatedWarning",
        "ModelAPIError",
        "ModelHTTPError",
        "ModelRetry",
        "PydanticAIDeprecationWarning",
        "RunCancelled",
        "SkipModelRequest",
        "SkipToolExecution",
        "SkipToolValidation",
        "SuspendedResponseExpired",
        "ToolFailed",
        "ToolFailedError",
        "ToolRetryError",
        "UndrainedPendingMessagesError",
        "UnexpectedModelBehavior",
        "UsageLimitExceeded",
        "UserError",
    }
)


def __getattr__(name: str) -> Any:
    if name in _PYDANTIC_AI_NAMES:
        from devops_cli.exceptions import ai_pydantic

        val = getattr(ai_pydantic, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from devops_cli.exceptions.ai_pydantic import (
        AgentRunError,
        ApprovalRequired,
        CallDeferred,
        ConcurrencyLimitExceeded,
        ContentFilterError,
        CostCalculationFailedWarning,
        CostNotFoundWarning,
        FallbackExceptionGroup,
        IncompleteToolCall,
        MessageHistoryMutatedWarning,
        ModelAPIError,
        ModelHTTPError,
        ModelRetry,
        PydanticAIDeprecationWarning,
        RunCancelled,
        SkipModelRequest,
        SkipToolExecution,
        SkipToolValidation,
        SuspendedResponseExpired,
        ToolFailed,
        ToolFailedError,
        ToolRetryError,
        UndrainedPendingMessagesError,
        UnexpectedModelBehavior,
        UsageLimitExceeded,
        UserError,
    )

__all__ = [
    "AgentRunError",
    "ApprovalRequired",
    "CallDeferred",
    "CapabilityDegradationError",
    "ConcurrencyLimitExceeded",
    "ConstellationFailoverError",
    "ConstellationQuiesceError",
    "ConstellationResumeError",
    "ContentFilterError",
    "ContextBudgetExceededError",
    "CostCalculationFailedWarning",
    "CostNotFoundWarning",
    "DocsIngestionError",
    "FallbackExceptionGroup",
    "HarnessValidationError",
    "IncompleteToolCall",
    "LLMInferenceError",
    "LibraryIngestionError",
    "LibraryNotFoundError",
    "MessageHistoryMutatedWarning",
    "ModelAPIError",
    "ModelBundleError",
    "ModelHTTPError",
    "ModelRetry",
    "ModelUnavailableError",
    "PydanticAIDeprecationWarning",
    "ReviewPoolError",
    "RunCancelled",
    "SkipModelRequest",
    "SkipToolExecution",
    "SkipToolValidation",
    "StructuredOutputSchemaError",
    "SuspendedResponseExpired",
    "ToolFailed",
    "ToolFailedError",
    "ToolRetryError",
    "UndrainedPendingMessagesError",
    "UnexpectedModelBehavior",
    "UsageLimitExceeded",
    "UserError",
]

"""AI, LLM, and prompt-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import (
    CONST_EXIT_ERROR_INFERENCE,
    CONST_EXIT_FAILURE,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.exceptions.base import DevOpsCLIError


class LLMInferenceError(DevOpsCLIError, ValueError):
    """Base exception for LLM provider invocation failures."""

    error_code = "LLM_INFERENCE_ERROR"
    exit_code = CONST_EXIT_ERROR_INFERENCE

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"provider": provider, "model": model}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class ModelGatewayUnreachableError(LLMInferenceError):
    """Raised when a model call through the gateway fails, so the command decided and wrote nothing."""

    error_code = "MODEL_GATEWAY_UNREACHABLE"
    exit_code = CONST_EXIT_FAILURE

    def __init__(self, gateway: str, cause: Exception, *, consequence: str) -> None:
        from devops_cli.security.sanitizer import mask_secrets, mask_uri_credentials

        safe_gateway = mask_uri_credentials(gateway)
        safe_cause = mask_secrets(str(cause)[:200])
        super().__init__(
            f"The model gateway {safe_gateway} did not answer ({type(cause).__name__}: "
            f"{safe_cause}), so {consequence}. Run it again once the gateway answers.",
            details={"gateway": safe_gateway[:256]},
        )


class CapabilityDegradationError(DevOpsCLIError, ValueError):
    """Raised when a fallback or failover model breaches minimum capability tier requirements."""

    error_code = "CAPABILITY_DEGRADATION"

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
        super().__init__(message, details=err_details)


class ModelBundleError(DevOpsCLIError, ValueError):
    """Raised when an AI model bundle cannot be located, resolved, or loaded."""

    error_code = "MODEL_BUNDLE_ERROR"

    def __init__(
        self,
        message: str,
        *,
        bundle_path: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"bundle_path": bundle_path}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class HarnessValidationError(DevOpsCLIError, ValueError):
    """Raised when an AI evaluation or harness schema validation fails."""

    error_code = "HARNESS_VALIDATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        field_name: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"field_name": field_name}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class ReviewPoolError(DevOpsCLIError, RuntimeError):
    """Raised when an error occurs during parallel review worker pool execution."""

    error_code = "REVIEW_POOL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        errors: list[Exception] | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = details or {}
        if errors:
            err_details["error_count"] = len(errors)
            err_details["errors"] = [str(e) for e in errors]
        super().__init__(message, exit_code=exit_code, details=err_details)
        self.errors = errors or []


class ReviewSessionExistsError(DevOpsCLIError):
    """Raised when a review is published under the name of a session that is already published."""

    error_code = "REVIEW_SESSION_EXISTS"

    def __init__(self, name: str, *, staging: str) -> None:
        bounded_name = name[:CONST_MAX_ERROR_DETAIL_LENGTH]
        bounded_staging = staging[:CONST_MAX_ERROR_DETAIL_LENGTH]
        super().__init__(
            f"Review session {bounded_name} was not published: a session of that name already "
            f"exists. The review's files are in {bounded_staging}.",
            details={"session": bounded_name, "staging": bounded_staging},
        )


class ReviewHandOffRefusedError(DevOpsCLIError):
    """Raised when `devops review intake` refuses a session that is not on merged code."""

    error_code = "REVIEW_HAND_OFF_REFUSED"

    def __init__(self, message: str, *, session: str) -> None:
        super().__init__(message, details={"session": session[:CONST_MAX_ERROR_DETAIL_LENGTH]})


class LibraryIngestionError(DevOpsCLIError):
    """Base exception for package introspection and library ingestion errors."""

    error_code = "LIBRARY_INGESTION_ERROR"


class LibraryNotFoundError(LibraryIngestionError):
    """Raised when target package could not be loaded or found in the environment."""

    error_code = "LIBRARY_NOT_FOUND_ERROR"


class DocsIngestionError(DevOpsCLIError):
    """Base exception for documentation ingestion errors."""

    error_code = "DOCS_INGESTION_ERROR"


class StructuredOutputSchemaError(DevOpsCLIError, ValueError):
    """Raised when a schema class is missing or invalid for structured LLM output generation."""

    error_code = "STRUCTURED_OUTPUT_SCHEMA_INVALID"


_PYDANTIC_AI_NAMES: frozenset[str] = frozenset(
    {
        "ApprovalRequired",
        "CallDeferred",
        "ModelRetry",
        "SkipToolExecution",
        "ToolFailed",
        "UnexpectedModelBehavior",
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
        ApprovalRequired,
        CallDeferred,
        ModelRetry,
        SkipToolExecution,
        ToolFailed,
        UnexpectedModelBehavior,
    )

__all__ = [
    "ApprovalRequired",
    "CallDeferred",
    "CapabilityDegradationError",
    "DocsIngestionError",
    "HarnessValidationError",
    "LLMInferenceError",
    "LibraryIngestionError",
    "LibraryNotFoundError",
    "ModelBundleError",
    "ModelRetry",
    "ReviewPoolError",
    "SkipToolExecution",
    "StructuredOutputSchemaError",
    "ToolFailed",
    "UnexpectedModelBehavior",
]

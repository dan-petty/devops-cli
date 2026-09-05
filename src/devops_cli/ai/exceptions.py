"""Native Pydantic AI Exceptions and unified error handling utilities."""

from __future__ import annotations

import concurrent.futures
from typing import Any

import pydantic_ai.exceptions as p_exc

from devops_cli.exceptions.ai import (
    AgentRunError,
    ApprovalRequired,
    CallDeferred,
    ConcurrencyLimitExceeded,
    ContentFilterError,
    ContextBudgetExceededError,
    CostCalculationFailedWarning,
    CostNotFoundWarning,
    FallbackExceptionGroup,
    IncompleteToolCall,
    LLMInferenceError,
    MessageHistoryMutatedWarning,
    ModelAPIError,
    ModelHTTPError,
    ModelRetry,
    ModelUnavailableError,
    PersonaExecutionError,
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

_NATIVE_EXCEPTION_TYPES = (
    p_exc.AgentRunError,
    p_exc.UserError,
    p_exc.ModelRetry,
    p_exc.ToolFailed,
    p_exc.ApprovalRequired,
    p_exc.CallDeferred,
    p_exc.SkipModelRequest,
    p_exc.SkipToolValidation,
    p_exc.SkipToolExecution,
    p_exc.ToolRetryError,
    p_exc.ToolFailedError,
    p_exc.FallbackExceptionGroup,
)


def is_pydantic_ai_exception(exc: BaseException) -> bool:
    """Check whether an exception belongs to the native or unified Pydantic AI exception hierarchy."""
    return isinstance(exc, _NATIVE_EXCEPTION_TYPES)


def extract_retry_after(exc: BaseException) -> float | None:
    """Safely extract retry delay in seconds from a ModelHTTPError or response header."""
    if isinstance(exc, p_exc.ModelHTTPError):
        return exc.retry_after
    return getattr(exc, "retry_after", None)


def extract_cancellation_state(exc: BaseException) -> p_exc.RunCancelled | None:
    """Extract RunCancelled state, message history, and token usage from an exception chain."""
    return p_exc.RunCancelled.from_cancellation(exc)


def format_pydantic_ai_error(exc: BaseException) -> str:
    """Format Pydantic AI exceptions into clear, actionable human-readable messages."""
    if isinstance(exc, p_exc.ModelHTTPError):
        retry_suffix = f" (Retry after {exc.retry_after}s)" if exc.retry_after is not None else ""
        suggestion_suffix = (
            f" [Suggestion: '{exc.suggested_model_id}']" if exc.suggested_model_id else ""
        )
        return (
            f"Model HTTP {exc.status_code} on '{exc.model_name}': {exc.message}"
            f"{retry_suffix}{suggestion_suffix}"
        )

    if isinstance(exc, p_exc.ContentFilterError):
        return f"Content filter triggered: {exc.message}"

    if isinstance(exc, p_exc.UnexpectedModelBehavior):
        body_part = f"\nResponse body: {exc.body}" if exc.body else ""
        return f"Unexpected model behavior: {exc.message}{body_part}"

    if isinstance(exc, p_exc.UsageLimitExceeded):
        return f"Usage limit exceeded: {exc.message}"

    if isinstance(exc, p_exc.ConcurrencyLimitExceeded):
        return f"Concurrency limit exceeded: {exc.message}"

    if isinstance(exc, p_exc.ToolFailed):
        return f"Tool execution failed: {exc.message}"

    if isinstance(exc, p_exc.ModelRetry):
        return f"Model retry requested: {exc.message}"

    if isinstance(exc, p_exc.RunCancelled):
        return f"Agent run cancelled: {exc.message}"

    return str(exc)


def normalize_to_pydantic_ai_error(
    exc: BaseException,
    *,
    tool_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> BaseException:
    """Wrap arbitrary runtime errors into appropriate Pydantic AI exception representations."""
    if is_pydantic_ai_exception(exc):
        return exc

    if isinstance(exc, (TimeoutError, concurrent.futures.TimeoutError)):
        msg = f"Timeout occurred: {exc}"
        if tool_name:
            return ToolFailed(
                f"Tool '{tool_name}' timed out: {exc}",
                details={"tool": tool_name, **(details or {})},
            )
        return AgentRunError(msg, details=details)

    error_msg = f"{type(exc).__name__}: {exc}"
    if tool_name:
        return ToolFailed(
            f"Tool '{tool_name}' failed: {error_msg}",
            details={"tool": tool_name, **(details or {})},
        )
    return AgentRunError(error_msg, details=details)


__all__ = [
    "AgentRunError",
    "ApprovalRequired",
    "CallDeferred",
    "ConcurrencyLimitExceeded",
    "ContentFilterError",
    "ContextBudgetExceededError",
    "CostCalculationFailedWarning",
    "CostNotFoundWarning",
    "FallbackExceptionGroup",
    "IncompleteToolCall",
    "LLMInferenceError",
    "MessageHistoryMutatedWarning",
    "ModelAPIError",
    "ModelHTTPError",
    "ModelRetry",
    "ModelUnavailableError",
    "PersonaExecutionError",
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
    "extract_cancellation_state",
    "extract_retry_after",
    "format_pydantic_ai_error",
    "is_pydantic_ai_exception",
    "normalize_to_pydantic_ai_error",
]

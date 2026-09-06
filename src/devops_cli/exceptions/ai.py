"""AI, LLM, and prompt-related exception definitions for devops-cli."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import pydantic_ai.exceptions as p_exc

from devops_cli.config.constants import (
    CONST_ERROR_CODE_HARNESS,
    CONST_ERROR_CODE_LLM_INFERENCE,
    CONST_ERROR_CODE_MODEL_BUNDLE,
    CONST_EXIT_ERROR_INFERENCE,
    CONST_EXIT_FAILURE,
)
from devops_cli.exceptions.base import DevOpsCLIError

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.usage import RunUsage


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


class PersonaExecutionError(LLMInferenceError):
    """Raised when an AI reviewer persona fails during diff analysis."""

    DEFAULT_ERROR_CODE = "PERSONA_EXECUTION_ERROR"
    DEFAULT_EXIT_CODE = 13

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


class ModelRetry(p_exc.ModelRetry, DevOpsCLIError):
    """Raised by tools or output validators to request the model to retry with corrective feedback."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.ModelRetry.__init__(self, message)
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=14,
            error_code="MODEL_RETRY_REQUESTED",
            details=details or {},
        )


class UnexpectedModelBehavior(p_exc.UnexpectedModelBehavior, LLMInferenceError):
    """Raised when model retry budget is exhausted or model emits unrecoverable response."""

    def __init__(
        self,
        message: str,
        body: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.UnexpectedModelBehavior.__init__(self, message, body=body)
        LLMInferenceError.__init__(
            self,
            message,
            exit_code=15,
            error_code="UNEXPECTED_MODEL_BEHAVIOR",
            details=details,
        )


class ToolFailed(p_exc.ToolFailed, DevOpsCLIError):
    """Raised when a tool encounters an unrecoverable runtime failure without requesting model retry."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.ToolFailed.__init__(self, message)
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=16,
            error_code="TOOL_FAILED",
            details=details or {},
        )


class ApprovalRequired(p_exc.ApprovalRequired, DevOpsCLIError):
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
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=17,
            error_code="APPROVAL_REQUIRED",
            details=merged_details,
        )
        self.metadata = metadata


class CallDeferred(p_exc.CallDeferred, DevOpsCLIError):
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
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=18,
            error_code="CALL_DEFERRED",
            details=merged_details,
        )
        self.metadata = metadata


class ContentFilterError(p_exc.ContentFilterError, UnexpectedModelBehavior):
    """Raised when a model response is filtered or refused by upstream content safety filters."""

    def __init__(
        self,
        message: str = "Model response was blocked by upstream content safety filter",
        body: Any = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        body_str = str(body) if body is not None and not isinstance(body, str) else body
        p_exc.ContentFilterError.__init__(self, message, body=body_str)
        UnexpectedModelBehavior.__init__(self, message, body=body_str, details=details)
        self.exit_code = 19
        self.error_code = "CONTENT_FILTER_TRIGGERED"
        self.body = body


class AgentRunError(p_exc.AgentRunError, DevOpsCLIError):
    """Raised when an error occurs during an agent run lifecycle."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.AgentRunError.__init__(self, message)
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=20,
            error_code="AGENT_RUN_ERROR",
            details=details or {},
        )


class UserError(p_exc.UserError, DevOpsCLIError):
    """Raised when an invalid configuration or argument is provided by the application developer."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.UserError.__init__(self, message)
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=21,
            error_code="USER_ERROR",
            details=details or {},
        )


class ModelAPIError(p_exc.ModelAPIError, LLMInferenceError):
    """Raised when a model provider API request fails."""

    DEFAULT_ERROR_CODE = "MODEL_API_ERROR"
    DEFAULT_EXIT_CODE = 22

    def __init__(
        self,
        model_name: str,
        message: str,
        *,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.ModelAPIError.__init__(self, model_name=model_name, message=message)
        err_details = {"model_name": model_name}
        if details:
            err_details.update(details)
        LLMInferenceError.__init__(
            self,
            message,
            provider=provider,
            model=model_name,
            exit_code=22,
            error_code="MODEL_API_ERROR",
            details=err_details,
        )


class ModelHTTPError(p_exc.ModelHTTPError, ModelAPIError):
    """Raised when a model provider response has a status code of 4xx or 5xx."""

    DEFAULT_ERROR_CODE = "MODEL_HTTP_ERROR"
    DEFAULT_EXIT_CODE = 23

    def __init__(
        self,
        status_code: int,
        model_name: str,
        body: object | None = None,
        *,
        headers: Mapping[str, str] | None = None,
        suggested_model_id: str | None = None,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.ModelHTTPError.__init__(
            self,
            status_code=status_code,
            model_name=model_name,
            body=body,
            headers=headers,
            suggested_model_id=suggested_model_id,
        )
        err_details: dict[str, Any] = {
            "status_code": status_code,
            "model_name": model_name,
            "body": str(body) if body is not None and not isinstance(body, dict | list) else body,
        }
        if headers:
            err_details["headers"] = dict(headers)
        if suggested_model_id:
            err_details["suggested_model_id"] = suggested_model_id
        if details:
            err_details.update(details)

        DevOpsCLIError.__init__(
            self,
            self.message,
            exit_code=23,
            error_code="MODEL_HTTP_ERROR",
            details=err_details,
        )


class UsageLimitExceeded(p_exc.UsageLimitExceeded, DevOpsCLIError):
    """Raised when an agent run exceeds configured request or token limits."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.UsageLimitExceeded.__init__(self, message)
        DevOpsCLIError.__init__(
            self,
            self.message,
            exit_code=24,
            error_code="USAGE_LIMIT_EXCEEDED",
            details=details or {},
        )


class ConcurrencyLimitExceeded(p_exc.ConcurrencyLimitExceeded, DevOpsCLIError):
    """Raised when the concurrency queue depth exceeds max_queued."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.ConcurrencyLimitExceeded.__init__(self, message)
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=25,
            error_code="CONCURRENCY_LIMIT_EXCEEDED",
            details=details or {},
        )


class RunCancelled(p_exc.RunCancelled, DevOpsCLIError):
    """Raised when an agent run was cancelled by the application or timeout."""

    def __init__(
        self,
        message: str = "Agent run was cancelled",
        *,
        messages: Sequence[ModelMessage] = (),
        new_message_index: int = 0,
        usage: RunUsage | None = None,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
        conversation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.RunCancelled.__init__(
            self,
            message,
            messages=messages,
            new_message_index=new_message_index,
            usage=usage,
            metadata=metadata,
            run_id=run_id,
            conversation_id=conversation_id,
        )
        err_details: dict[str, Any] = {"run_id": run_id, "conversation_id": conversation_id}
        if metadata:
            err_details["metadata"] = metadata
        if details:
            err_details.update(details)
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=26,
            error_code="RUN_CANCELLED",
            details=err_details,
        )


class IncompleteToolCall(p_exc.IncompleteToolCall, DevOpsCLIError):
    """Raised when a model stops due to token limit while emitting a tool call."""

    def __init__(
        self,
        message: str,
        body: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.IncompleteToolCall.__init__(self, message, body=body)
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=27,
            error_code="INCOMPLETE_TOOL_CALL",
            details=details or {},
        )


class SuspendedResponseExpired(p_exc.SuspendedResponseExpired, DevOpsCLIError):
    """Raised when resuming a suspended response whose server-side job is no longer available."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        p_exc.SuspendedResponseExpired.__init__(self, message)
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=28,
            error_code="SUSPENDED_RESPONSE_EXPIRED",
            details=details or {},
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
        error_code: str = CONST_ERROR_CODE_HARNESS,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"field_name": field_name}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class HarnessExecutionError(DevOpsCLIError, RuntimeError):
    """Raised when execution of an AI test harness or benchmark fails."""

    def __init__(
        self,
        message: str,
        *,
        harness_name: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_HARNESS,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"harness_name": harness_name}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


# Native re-exports for control flow, groups, and warnings
SkipModelRequest = p_exc.SkipModelRequest
SkipToolValidation = p_exc.SkipToolValidation
SkipToolExecution = p_exc.SkipToolExecution
UndrainedPendingMessagesError = p_exc.UndrainedPendingMessagesError
ToolRetryError = p_exc.ToolRetryError
ToolFailedError = p_exc.ToolFailedError
FallbackExceptionGroup = p_exc.FallbackExceptionGroup
MessageHistoryMutatedWarning = p_exc.MessageHistoryMutatedWarning
CostCalculationFailedWarning = p_exc.CostCalculationFailedWarning
CostNotFoundWarning = p_exc.CostNotFoundWarning
PydanticAIDeprecationWarning = p_exc.PydanticAIDeprecationWarning

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
    "HarnessExecutionError",
    "HarnessValidationError",
    "IncompleteToolCall",
    "LLMInferenceError",
    "MessageHistoryMutatedWarning",
    "ModelAPIError",
    "ModelBundleError",
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
]

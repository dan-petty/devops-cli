"""Pydantic AI exception subclasses that carry DevOps CLI exit and error codes."""

from __future__ import annotations

from typing import Any

import pydantic_ai.exceptions as p_exc
from pydantic_ai.messages import ModelResponse

from devops_cli.exceptions.ai import LLMInferenceError
from devops_cli.exceptions.base import DevOpsCLIError


class ModelRetry(p_exc.ModelRetry, DevOpsCLIError):
    """Raised by tools or output validators to request the model to retry with corrective feedback."""

    error_code = "MODEL_RETRY_REQUESTED"
    exit_code = 14

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
            details=details or {},
        )


class UnexpectedModelBehavior(p_exc.UnexpectedModelBehavior, LLMInferenceError):
    """Raised when model retry budget is exhausted or model emits unrecoverable response."""

    error_code = "UNEXPECTED_MODEL_BEHAVIOR"
    exit_code = 15

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
            details=details,
        )


class OutputCapReached(UnexpectedModelBehavior):
    """A model reply ended with the finish reason `length`: the model did not stop, and the output
    cap ended the call (#2869). The message names the cap. The run drops a reply that a hook
    rejects, so the error holds it in `response`, for the spend."""

    error_code = "OUTPUT_CAP_REACHED"

    def __init__(self, message: str, *, response: ModelResponse) -> None:
        super().__init__(message)
        self.response = response


class ToolFailed(p_exc.ToolFailed, DevOpsCLIError):
    """Raised when a tool encounters an unrecoverable runtime failure without requesting model retry."""

    error_code = "TOOL_FAILED"
    exit_code = 16

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
            details=details or {},
        )


class ApprovalRequired(p_exc.ApprovalRequired, DevOpsCLIError):
    """Raised by a tool or validator when human approval is required to proceed."""

    error_code = "APPROVAL_REQUIRED"
    exit_code = 17

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
            details=merged_details,
        )
        self.metadata = metadata


class CallDeferred(p_exc.CallDeferred, DevOpsCLIError):
    """Raised by a tool when execution is deferred to an external worker or async system."""

    error_code = "CALL_DEFERRED"
    exit_code = 18

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
            details=merged_details,
        )
        self.metadata = metadata


# Native alias the tool runner catches
SkipToolExecution = p_exc.SkipToolExecution

for _cls in list(globals().values()):
    if isinstance(_cls, type) and issubclass(_cls, DevOpsCLIError):
        _cls.__module__ = "devops_cli.exceptions.ai"

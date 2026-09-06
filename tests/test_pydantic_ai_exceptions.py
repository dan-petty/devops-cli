"""Test suite for native Pydantic AI Exceptions integration and domain error taxonomy."""

from __future__ import annotations

import asyncio
from typing import Any

import pydantic_ai.exceptions as p_exc

from devops_cli.ai.exceptions import (
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
    UndrainedPendingMessagesError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
    UserError,
    extract_cancellation_state,
    extract_retry_after,
    format_pydantic_ai_error,
    is_pydantic_ai_exception,
    normalize_to_pydantic_ai_error,
)
from devops_cli.exceptions.ai import LLMInferenceError
from devops_cli.exceptions.base import DevOpsCLIError


def test_pydantic_ai_exceptions_dual_inheritance_model_retry() -> None:
    """Verify ModelRetry conforms to both pydantic_ai.exceptions and DevOpsCLIError."""
    exc = ModelRetry("Please format as JSON", details={"field": "summary"})

    assert isinstance(exc, p_exc.ModelRetry)
    assert isinstance(exc, DevOpsCLIError)
    assert isinstance(exc, Exception)
    assert exc.message == "Please format as JSON"
    assert exc.exit_code == 14
    assert exc.error_code == "MODEL_RETRY_REQUESTED"
    assert exc.details == {"field": "summary"}
    assert str(exc) == "Please format as JSON"


def test_pydantic_ai_exceptions_dual_inheritance_tool_failed() -> None:
    """Verify ToolFailed conforms to both pydantic_ai.exceptions and DevOpsCLIError."""
    exc = ToolFailed("Resource not found on cluster", details={"resource": "pod/backend"})

    assert isinstance(exc, p_exc.ToolFailed)
    assert isinstance(exc, DevOpsCLIError)
    assert exc.message == "Resource not found on cluster"
    assert exc.exit_code == 16
    assert exc.error_code == "TOOL_FAILED"
    assert exc.details == {"resource": "pod/backend"}


def test_pydantic_ai_exceptions_dual_inheritance_approval_and_deferred() -> None:
    """Verify ApprovalRequired and CallDeferred conform to native and domain hierarchies."""
    approval = ApprovalRequired(
        "Production deployment requires approval",
        metadata={"target": "prod", "approvers": ["admin"]},
    )
    assert isinstance(approval, p_exc.ApprovalRequired)
    assert isinstance(approval, DevOpsCLIError)
    assert approval.exit_code == 17
    assert approval.error_code == "APPROVAL_REQUIRED"
    assert approval.metadata == {"target": "prod", "approvers": ["admin"]}

    deferred = CallDeferred(
        "Background indexing deferred to Celery",
        metadata={"task_id": "celery-123"},
    )
    assert isinstance(deferred, p_exc.CallDeferred)
    assert isinstance(deferred, DevOpsCLIError)
    assert deferred.exit_code == 18
    assert deferred.error_code == "CALL_DEFERRED"
    assert deferred.metadata == {"task_id": "celery-123"}


def test_pydantic_ai_exceptions_dual_inheritance_model_behavior_and_content_filter() -> None:
    """Verify UnexpectedModelBehavior and ContentFilterError conform to native and domain hierarchies."""
    unexp = UnexpectedModelBehavior(
        "Model emitted invalid structure",
        body='{"status": 500, "error": "malformed"}',
        details={"model": "qwen3"},
    )
    assert isinstance(unexp, p_exc.UnexpectedModelBehavior)
    assert isinstance(unexp, p_exc.AgentRunError)
    assert isinstance(unexp, LLMInferenceError)
    assert isinstance(unexp, DevOpsCLIError)
    assert unexp.exit_code == 15
    assert unexp.error_code == "UNEXPECTED_MODEL_BEHAVIOR"
    assert unexp.body is not None

    filter_err = ContentFilterError(
        "Model output triggered safety filter",
        body="filtered",
        details={"severity": "high"},
    )
    assert isinstance(filter_err, p_exc.ContentFilterError)
    assert isinstance(filter_err, p_exc.UnexpectedModelBehavior)
    assert isinstance(filter_err, DevOpsCLIError)
    assert filter_err.exit_code == 19
    assert filter_err.error_code == "CONTENT_FILTER_TRIGGERED"


def test_pydantic_ai_exceptions_dual_inheritance_agent_run_and_user_errors() -> None:
    """Verify AgentRunError and UserError conform to native and domain hierarchies."""
    run_err = AgentRunError("Agent pipeline terminated unexpectedly", details={"stage": "review"})
    assert isinstance(run_err, p_exc.AgentRunError)
    assert isinstance(run_err, DevOpsCLIError)
    assert run_err.exit_code == 20
    assert run_err.error_code == "AGENT_RUN_ERROR"

    user_err = UserError("Agent requires a valid model specification", details={"param": "model"})
    assert isinstance(user_err, p_exc.UserError)
    assert isinstance(user_err, DevOpsCLIError)
    assert user_err.exit_code == 21
    assert user_err.error_code == "USER_ERROR"


def test_pydantic_ai_exceptions_dual_inheritance_model_api_and_http_errors() -> None:
    """Verify ModelAPIError and ModelHTTPError conform to native and domain hierarchies."""
    api_err = ModelAPIError(
        model_name="ollama:qwen3:8b",
        message="Upstream provider failed to generate response",
    )
    assert isinstance(api_err, p_exc.ModelAPIError)
    assert isinstance(api_err, p_exc.AgentRunError)
    assert isinstance(api_err, LLMInferenceError)
    assert isinstance(api_err, DevOpsCLIError)
    assert api_err.model_name == "ollama:qwen3:8b"
    assert api_err.exit_code == 22
    assert api_err.error_code == "MODEL_API_ERROR"

    http_err = ModelHTTPError(
        status_code=429,
        model_name="gpt-4o",
        body={"error": "rate_limit_exceeded"},
        headers={"retry-after": "45"},
        suggested_model_id="gpt-4o-mini",
    )
    assert isinstance(http_err, p_exc.ModelHTTPError)
    assert isinstance(http_err, p_exc.ModelAPIError)
    assert isinstance(http_err, DevOpsCLIError)
    assert http_err.status_code == 429
    assert http_err.model_name == "gpt-4o"
    assert http_err.retry_after == 45.0
    assert http_err.suggested_model_id == "gpt-4o-mini"
    assert http_err.exit_code == 23
    assert http_err.error_code == "MODEL_HTTP_ERROR"


def test_pydantic_ai_exceptions_dual_inheritance_limits_and_cancellation() -> None:
    """Verify UsageLimitExceeded, ConcurrencyLimitExceeded, and RunCancelled conform to both hierarchies."""
    usage_err = UsageLimitExceeded("Total token budget of 5000 exhausted")
    assert isinstance(usage_err, p_exc.UsageLimitExceeded)
    assert isinstance(usage_err, DevOpsCLIError)
    assert usage_err.exit_code == 24
    assert usage_err.error_code == "USAGE_LIMIT_EXCEEDED"

    concurrency_err = ConcurrencyLimitExceeded("Maximum concurrency queue limit reached")
    assert isinstance(concurrency_err, p_exc.ConcurrencyLimitExceeded)
    assert isinstance(concurrency_err, DevOpsCLIError)
    assert concurrency_err.exit_code == 25
    assert concurrency_err.error_code == "CONCURRENCY_LIMIT_EXCEEDED"

    cancelled = RunCancelled("Agent run cancelled by user interrupt", run_id="run-999")
    assert isinstance(cancelled, p_exc.RunCancelled)
    assert isinstance(cancelled, DevOpsCLIError)
    assert cancelled.exit_code == 26
    assert cancelled.error_code == "RUN_CANCELLED"
    assert cancelled.run_id == "run-999"


def test_pydantic_ai_exceptions_dual_inheritance_incomplete_and_suspended() -> None:
    """Verify IncompleteToolCall and SuspendedResponseExpired conform to both hierarchies."""
    incomplete = IncompleteToolCall("Token limit hit while generating tool call")
    assert isinstance(incomplete, p_exc.IncompleteToolCall)
    assert isinstance(incomplete, DevOpsCLIError)
    assert incomplete.exit_code == 27
    assert incomplete.error_code == "INCOMPLETE_TOOL_CALL"

    suspended = SuspendedResponseExpired("Suspended OpenAI job expired after 10m retention")
    assert isinstance(suspended, p_exc.SuspendedResponseExpired)
    assert isinstance(suspended, DevOpsCLIError)
    assert suspended.exit_code == 28
    assert suspended.error_code == "SUSPENDED_RESPONSE_EXPIRED"


def test_native_reexports_and_warnings() -> None:
    """Verify re-exported native control flow exceptions, groups, and warnings."""
    from pydantic_ai.messages import ModelResponse, TextPart

    # SkipModelRequest
    dummy_resp = ModelResponse(parts=[TextPart(content="Cached response")])
    skip_req = SkipModelRequest(dummy_resp)
    assert isinstance(skip_req, p_exc.SkipModelRequest)
    assert skip_req.response is dummy_resp

    # SkipToolValidation
    skip_val = SkipToolValidation({"a": 1, "b": 2})
    assert isinstance(skip_val, p_exc.SkipToolValidation)
    assert skip_val.validated_args == {"a": 1, "b": 2}

    # SkipToolExecution
    skip_exec = SkipToolExecution("Direct Result")
    assert isinstance(skip_exec, p_exc.SkipToolExecution)
    assert skip_exec.result == "Direct Result"

    # UndrainedPendingMessagesError
    undrained = UndrainedPendingMessagesError("Messages undrained")
    assert isinstance(undrained, p_exc.UndrainedPendingMessagesError)

    # FallbackExceptionGroup
    sub_err1 = ValueError("fallback 1 failed")
    sub_err2 = RuntimeError("fallback 2 failed")
    fb_group = FallbackExceptionGroup("All models failed", [sub_err1, sub_err2])
    assert isinstance(fb_group, p_exc.FallbackExceptionGroup)
    assert len(fb_group.exceptions) == 2

    # Warnings
    assert issubclass(MessageHistoryMutatedWarning, Warning)
    assert issubclass(CostCalculationFailedWarning, Warning)
    assert issubclass(CostNotFoundWarning, Warning)
    assert issubclass(PydanticAIDeprecationWarning, UserWarning)


def test_is_pydantic_ai_exception_type_guard() -> None:
    """Verify is_pydantic_ai_exception accurately checks exception ancestry."""
    assert is_pydantic_ai_exception(ModelRetry("retry"))
    assert is_pydantic_ai_exception(ToolFailed("failed"))
    assert is_pydantic_ai_exception(p_exc.UsageLimitExceeded("limits"))
    assert is_pydantic_ai_exception(p_exc.UserError("dev error"))
    assert is_pydantic_ai_exception(ModelHTTPError(404, "qwen3"))

    assert not is_pydantic_ai_exception(ValueError("standard python error"))
    assert not is_pydantic_ai_exception(KeyError("missing key"))
    assert not is_pydantic_ai_exception(ZeroDivisionError())


def test_extract_retry_after_and_format_pydantic_ai_error() -> None:
    """Verify extract_retry_after and format_pydantic_ai_error formatting behaviors."""
    # ModelHTTPError with retry-after header
    http_err = ModelHTTPError(
        status_code=429,
        model_name="qwen3:8b",
        headers={"retry-after": "60"},
        body={"error": "Rate limit exceeded"},
    )
    assert extract_retry_after(http_err) == 60.0
    formatted_http = format_pydantic_ai_error(http_err)
    assert "429" in formatted_http
    assert "qwen3:8b" in formatted_http
    assert "retry after 60" in formatted_http.lower()

    # UnexpectedModelBehavior with body
    unexp = UnexpectedModelBehavior("Malformed json", body="<html>Bad Gateway</html>")
    formatted_unexp = format_pydantic_ai_error(unexp)
    assert "Malformed json" in formatted_unexp
    assert "Bad Gateway" in formatted_unexp

    # Standard ModelRetry formatting
    retry = ModelRetry("Please output integer only")
    formatted_retry = format_pydantic_ai_error(retry)
    assert "Please output integer only" in formatted_retry

    # Non-Pydantic AI exception
    val_err = ValueError("regular error")
    assert extract_retry_after(val_err) is None
    assert format_pydantic_ai_error(val_err) == "regular error"


def test_extract_cancellation_state_from_chain() -> None:
    """Verify extract_cancellation_state recovers RunCancelled from chained exceptions."""
    from pydantic_ai.messages import (
        ModelMessage,
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    msgs: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]
    cancelled_instance = RunCancelled("Run aborted", messages=msgs, run_id="run-c1")

    # Directly pass RunCancelled
    extracted = extract_cancellation_state(cancelled_instance)
    assert extracted is not None
    assert extracted.run_id == "run-c1"
    assert len(extracted.all_messages()) == 2

    # Wrapped in an external asyncio.CancelledError
    wrapper_cancel = asyncio.CancelledError("Task was cancelled")
    cancelled_instance._attach_to(wrapper_cancel)
    extracted_from_cancel = extract_cancellation_state(wrapper_cancel)
    assert extracted_from_cancel is not None
    assert extracted_from_cancel.run_id == "run-c1"

    # None for unrelated errors
    assert extract_cancellation_state(RuntimeError("not cancelled")) is None


def test_normalize_to_pydantic_ai_error() -> None:
    """Verify normalize_to_pydantic_ai_error wraps arbitrary exceptions into Pydantic AI hierarchy."""
    # Already a Pydantic AI exception returns as-is
    retry = ModelRetry("already pydantic")
    assert normalize_to_pydantic_ai_error(retry) is retry

    # TimeoutError normalizes to ToolFailed
    timeout = TimeoutError("Network timeout")
    normalized_timeout = normalize_to_pydantic_ai_error(timeout, tool_name="fetch_web")
    assert isinstance(normalized_timeout, ToolFailed)
    assert "Network timeout" in normalized_timeout.message

    # Generic Exception normalizes to AgentRunError
    runtime = RuntimeError("Unexpected agent crash")
    normalized_runtime = normalize_to_pydantic_ai_error(runtime)
    assert isinstance(normalized_runtime, AgentRunError)
    assert "Unexpected agent crash" in normalized_runtime.message


def test_runner_executes_with_pydantic_exceptions() -> None:
    """Verify _execute_single_tool in runner handles ToolFailed, SkipToolExecution, and ModelRetry."""
    from devops_cli.ai.agents.context import RunContext
    from devops_cli.ai.agents.runner import _execute_single_tool
    from devops_cli.ai.agents.tools import Tool

    def failing_tool() -> None:
        raise ToolFailed("Terminal error on database")

    def skipping_tool() -> None:
        raise SkipToolExecution({"status": "skipped_ok"})

    def retrying_tool() -> None:
        raise ModelRetry("Please specify a valid cluster context")

    tool_fail = Tool(name="fail_op", description="fail op", function=failing_tool)
    tool_skip = Tool(name="skip_op", description="skip op", function=skipping_tool)
    tool_retry = Tool(name="retry_op", description="retry op", function=retrying_tool)

    dummy_ctx: Any = RunContext(deps=None)

    # ToolFailed returns tool_failed outcome
    status_fail, _, res_fail = _execute_single_tool(
        tool_fail, "fail_op", {}, [], ctx=dummy_ctx, default_timeout=5, hooks=None
    )
    assert status_fail == "tool_failed"
    assert "Terminal error on database" in str(res_fail)

    # SkipToolExecution returns ok with provided result
    status_skip, _, res_skip = _execute_single_tool(
        tool_skip, "skip_op", {}, [], ctx=dummy_ctx, default_timeout=5, hooks=None
    )
    assert status_skip == "ok"
    assert res_skip == {"status": "skipped_ok"}

    # ModelRetry returns retry_requested
    status_retry, _, res_retry = _execute_single_tool(
        tool_retry, "retry_op", {}, [], ctx=dummy_ctx, default_timeout=5, hooks=None
    )
    assert status_retry == "retry_requested"
    assert "Please specify a valid cluster context" in str(res_retry)


def test_generate_error_catalog_includes_all_ai_exceptions() -> None:
    """Verify that all AI domain exceptions are detected by docs generator error catalog."""
    from devops_cli.docs.generator import DocGenerator

    gen = DocGenerator()
    catalog_md = gen.generate_error_catalog_docs()

    # Ensure all AI subsystem exceptions and error codes appear in the error catalog
    expected_error_codes = [
        "LLM_INFERENCE_ERROR",
        "CONTEXT_BUDGET_EXCEEDED",
        "MODEL_UNAVAILABLE",
        "PERSONA_EXECUTION_ERROR",
        "MODEL_RETRY_REQUESTED",
        "UNEXPECTED_MODEL_BEHAVIOR",
        "TOOL_FAILED",
        "APPROVAL_REQUIRED",
        "CALL_DEFERRED",
        "CONTENT_FILTER_TRIGGERED",
        "AGENT_RUN_ERROR",
        "USER_ERROR",
        "MODEL_API_ERROR",
        "MODEL_HTTP_ERROR",
        "USAGE_LIMIT_EXCEEDED",
        "CONCURRENCY_LIMIT_EXCEEDED",
        "RUN_CANCELLED",
        "INCOMPLETE_TOOL_CALL",
        "SUSPENDED_RESPONSE_EXPIRED",
    ]

    for err_code in expected_error_codes:
        assert err_code in catalog_md, (
            f"Error code {err_code} missing from error catalog documentation!"
        )

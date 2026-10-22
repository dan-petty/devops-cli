"""Test suite for native Pydantic AI Exceptions integration and domain error taxonomy."""

from __future__ import annotations

from typing import Any

import pydantic_ai.exceptions as p_exc

from devops_cli.exceptions.ai import (
    ApprovalRequired,
    CallDeferred,
    LLMInferenceError,
    ModelRetry,
    SkipToolExecution,
    ToolFailed,
    UnexpectedModelBehavior,
)
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


def test_pydantic_ai_exceptions_dual_inheritance_model_behavior() -> None:
    """Verify UnexpectedModelBehavior conforms to native and domain hierarchies."""
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


def test_runner_tool_timeout_enforced_without_blocking() -> None:
    """Verify _execute_single_tool enforces timeout and does not block on hung worker threads."""
    import time

    from devops_cli.ai.agents.context import RunContext
    from devops_cli.ai.agents.runner import _execute_single_tool
    from devops_cli.ai.agents.tools import Tool

    def slow_tool() -> str:
        time.sleep(1.0)
        return "slow_done"

    tool = Tool(name="slow_tool", description="slow tool", function=slow_tool, timeout=0.05)
    dummy_ctx: Any = RunContext(deps=None)

    start_time = time.perf_counter()
    status, _, res = _execute_single_tool(
        tool, "slow_tool", {}, [], ctx=dummy_ctx, default_timeout=None
    )
    elapsed = time.perf_counter() - start_time

    assert status == "retry_requested"
    assert "Timed out after 0.05 seconds" in str(res)
    assert elapsed < 0.5


def test_generate_error_catalog_includes_all_ai_exceptions() -> None:
    """Verify that all AI domain exceptions are detected by docs generator error catalog."""
    from devops_cli.docs.generator import DocGenerator

    gen = DocGenerator()
    catalog_md = gen.generate_error_catalog_docs()

    # Ensure all AI subsystem exceptions and error codes appear in the error catalog
    expected_error_codes = [
        "LLM_INFERENCE_ERROR",
        "MODEL_RETRY_REQUESTED",
        "UNEXPECTED_MODEL_BEHAVIOR",
        "TOOL_FAILED",
        "APPROVAL_REQUIRED",
        "CALL_DEFERRED",
    ]

    for err_code in expected_error_codes:
        assert err_code in catalog_md, (
            f"Error code {err_code} missing from error catalog documentation!"
        )

"""Unit tests for Pydantic AI HandleDeferredToolCalls capability and deferred request resolution."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.agents import (
    DeferredToolRequests,
    HandleDeferredToolCalls,
    RunContext,
    ToolApproved,
    ToolCallPart,
    ToolDenied,
)


def test_deferred_tool_requests_build_results_manual() -> None:
    """Verify manual mapping of approvals and calls in build_results."""
    reqs = DeferredToolRequests(
        approvals=[ToolCallPart(tool_name="bash", args={"cmd": "ls"}, tool_call_id="call_1")],
        calls=[
            ToolCallPart(tool_name="external_api", args={"query": "test"}, tool_call_id="call_2")
        ],
    )

    results = reqs.build_results(
        approvals={"call_1": ToolApproved(override_args={"cmd": "ls -la"})},
        calls={"call_2": {"status": "success", "data": [1, 2, 3]}},
    )

    assert "call_1" in results.approvals
    assert isinstance(results.approvals["call_1"], ToolApproved)
    assert results.approvals["call_1"].override_args == {"cmd": "ls -la"}
    assert results.calls["call_2"] == {"status": "success", "data": [1, 2, 3]}


def test_deferred_tool_requests_approve_all() -> None:
    """Verify approve_all=True auto-approves all pending approvals."""
    reqs = DeferredToolRequests(
        approvals=[
            ToolCallPart(tool_name="tool_a", tool_call_id="call_a"),
            ToolCallPart(tool_name="tool_b", tool_call_id="call_b"),
        ]
    )

    results = reqs.build_results(approve_all=True)
    assert len(results.approvals) == 2
    assert isinstance(results.approvals["call_a"], ToolApproved)
    assert isinstance(results.approvals["call_b"], ToolApproved)


def test_deferred_tool_requests_deny_all() -> None:
    """Verify deny_all=True auto-denies all pending approvals."""
    reqs = DeferredToolRequests(
        approvals=[
            ToolCallPart(tool_name="tool_a", tool_call_id="call_a"),
            ToolCallPart(tool_name="tool_b", tool_call_id="call_b"),
        ]
    )

    results = reqs.build_results(deny_all=True)
    assert len(results.approvals) == 2
    assert isinstance(results.approvals["call_a"], ToolDenied)
    assert isinstance(results.approvals["call_b"], ToolDenied)


def test_handle_deferred_tool_calls_capability() -> None:
    """Verify HandleDeferredToolCalls capability execution with 1-arg and 2-arg handlers."""

    # 1. Single argument handler (requests)
    def single_arg_handler(requests: DeferredToolRequests) -> Any:
        return requests.build_results(approve_all=True)

    cap1 = HandleDeferredToolCalls(single_arg_handler)
    reqs = DeferredToolRequests(
        approvals=[ToolCallPart(tool_name="run_command", tool_call_id="c_1")]
    )
    res1 = cap1.handle_deferred(reqs)
    assert res1 is not None
    assert isinstance(res1.approvals["c_1"], ToolApproved)

    # 2. Two argument handler (ctx, requests)
    def two_arg_handler(ctx: RunContext[Any], requests: DeferredToolRequests) -> Any:
        if ctx.session_id == "admin_session":
            return requests.build_results(approve_all=True)
        return requests.build_results(deny_all=True)

    cap2 = HandleDeferredToolCalls(two_arg_handler)

    ctx_admin = RunContext(session_id="admin_session")
    res_admin = cap2.handle_deferred(reqs, ctx_admin)
    assert res_admin is not None
    assert isinstance(res_admin.approvals["c_1"], ToolApproved)

    ctx_user = RunContext(session_id="guest_session")
    res_guest = cap2.handle_deferred(reqs, ctx_user)
    assert res_guest is not None
    assert isinstance(res_guest.approvals["c_1"], ToolDenied)

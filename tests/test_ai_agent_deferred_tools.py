"""Unit tests for Pydantic AI HandleDeferredToolCalls capability and deferred request resolution."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from devops_cli.ai.agents import (
    BaseCapability,
    DeferredToolRequests,
    DeferredToolResults,
    HandleDeferredToolCalls,
    RunContext,
    Thinking,
    ToolApproved,
    ToolCallPart,
    ToolDenied,
)
from devops_cli.ai.agents.runner import _find_deferred_tool_handler


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


def test_two_arg_handler_called_without_a_context_gets_a_run_context() -> None:
    """A (ctx, requests) handler is chosen by its signature alone, so it always gets a context (#958)."""
    contexts: list[Any] = []

    def two_arg_handler(ctx: RunContext[Any], requests: DeferredToolRequests) -> Any:
        contexts.append(ctx)
        return requests.build_results(approve_all=True)

    reqs = DeferredToolRequests(
        approvals=[ToolCallPart(tool_name="run_command", tool_call_id="c_1")]
    )
    res = HandleDeferredToolCalls(two_arg_handler).handle_deferred(reqs)

    assert (
        type(res.approvals["c_1"]) if res is not None else None,
        [isinstance(ctx, RunContext) for ctx in contexts],
    ) == (ToolApproved, [True])


class _KeywordMethodHookCapability(BaseCapability):
    """Defines a handle_deferred method taking the requests and keywords only, denying every call."""

    def handle_deferred(
        self, requests: DeferredToolRequests, **_kw: Any
    ) -> DeferredToolResults | None:
        return requests.build_results(deny_all=True)


def test_a_handler_that_can_take_the_requests_alone_gets_them_alone() -> None:
    """Only a handler that needs a second positional argument gets ``(ctx, requests)`` (#958).

    The handler's parameters were counted, so ``approve(requests, **kw)``,
    ``approve(requests, *, note='')`` and ``approve(requests, ctx=None)`` were called as
    ``approve(ctx, requests)`` and the run ended with an error. A ``handle_deferred(requests,
    **kw)`` method was called as ``handle_deferred(requests, ctx)`` the same way.
    """
    reqs = DeferredToolRequests(
        approvals=[ToolCallPart(tool_name="run_command", tool_call_id="c_1")]
    )

    def approve(requests: DeferredToolRequests, **_kw: Any) -> DeferredToolResults:
        return requests.build_results(approve_all=True)

    def keyword_only(requests: DeferredToolRequests, *, note: str = "") -> DeferredToolResults:
        return requests.build_results(approve_all=True)

    def optional_context(
        requests: DeferredToolRequests, ctx: RunContext[Any] | None = None
    ) -> DeferredToolResults:
        return requests.build_results(approve_all=True)

    def resolve(*capabilities: BaseCapability) -> dict[str, str] | None:
        ctx = RunContext[Any](session_id="user")
        return _decisions(_find_deferred_tool_handler(list(capabilities), reqs, ctx))

    assert (
        _decisions(HandleDeferredToolCalls(approve).handle_deferred(reqs)),
        resolve(HandleDeferredToolCalls(approve)),
        resolve(HandleDeferredToolCalls(keyword_only)),
        resolve(HandleDeferredToolCalls(optional_context)),
        resolve(_KeywordMethodHookCapability(), HandleDeferredToolCalls(approve)),
    ) == (
        {"c_1": "ToolApproved"},
        {"c_1": "ToolApproved"},
        {"c_1": "ToolApproved"},
        {"c_1": "ToolApproved"},
        {"c_1": "ToolDenied"},
    )


class _NativeHookCapability(BaseCapability):
    """Overrides pydantic-ai's async deferred hook, denying every call in an admin session."""

    async def handle_deferred_tool_calls(
        self, ctx: Any, *, requests: DeferredToolRequests
    ) -> DeferredToolResults | None:
        return requests.build_results(deny_all=True) if ctx.session_id == "admin" else None


class _MethodHookCapability(BaseCapability):
    """Defines a handle_deferred method taking the context, denying every call in a guest session."""

    def handle_deferred(
        self, requests: DeferredToolRequests, ctx: RunContext[Any] | None = None
    ) -> DeferredToolResults | None:
        guest = ctx is not None and ctx.session_id == "guest"
        return requests.build_results(deny_all=True) if guest else None


def _decisions(results: DeferredToolResults | None) -> dict[str, str] | None:
    if results is None:
        return None
    return {call_id: type(decision).__name__ for call_id, decision in results.approvals.items()}


def test_find_deferred_tool_handler_calls_each_hook_with_the_run_context() -> None:
    """Each capability's deferred hook is called as it is defined, with the run's context (#958).

    Every capability inherits pydantic-ai's async `handle_deferred_tool_calls(ctx, *, requests)`,
    and it was called with the requests alone, so a capability ahead of the handler, or any
    capability in a run without one, ended the run with a TypeError.
    """
    reqs = DeferredToolRequests(
        approvals=[ToolCallPart(tool_name="run_command", tool_call_id="c_1")]
    )
    approve = HandleDeferredToolCalls(lambda requests: requests.build_results(approve_all=True))

    def resolve(capabilities: list[BaseCapability], session_id: str) -> dict[str, str] | None:
        ctx = RunContext[Any](session_id=session_id)
        return _decisions(_find_deferred_tool_handler(capabilities, reqs, ctx))

    assert (
        resolve([Thinking(), approve], "user"),
        resolve([Thinking()], "user"),
        resolve([_NativeHookCapability(), approve], "admin"),
        resolve([_NativeHookCapability(), approve], "user"),
        resolve([_MethodHookCapability(), approve], "guest"),
        resolve([_MethodHookCapability(), approve], "user"),
    ) == (
        {"c_1": "ToolApproved"},
        None,
        {"c_1": "ToolDenied"},
        {"c_1": "ToolApproved"},
        {"c_1": "ToolDenied"},
        {"c_1": "ToolApproved"},
    )


async def test_async_hook_inside_a_running_loop_leaves_the_requests_to_the_caller(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An async hook that cannot run in the running loop stops the lookup, so nothing approves (#958).

    The hook's coroutine was closed and the lookup went on to the next capability, so a deny
    policy ahead of an approving handler was skipped and the approval-required tool ran.
    """
    reqs = DeferredToolRequests(
        approvals=[ToolCallPart(tool_name="run_command", tool_call_id="c_1")]
    )
    approve = HandleDeferredToolCalls(lambda requests: requests.build_results(approve_all=True))

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.agents.runner"):
        resolved = _find_deferred_tool_handler(
            [_NativeHookCapability(), approve], reqs, RunContext[Any](session_id="admin")
        )

    assert (
        _decisions(resolved),
        [
            (record.levelname, "'_NativeHookCapability'" in record.getMessage())
            for record in caplog.records
            if record.name == "devops_cli.ai.agents.runner"
        ],
    ) == (None, [("WARNING", True)])

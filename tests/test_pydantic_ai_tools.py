"""Unit tests for the native Pydantic AI tools subsystem in devops-cli."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import RunContext

from devops_cli.ai.tools import (
    DeferredToolRequests,
    DeferredToolResults,
    Tool,
    ToolApproved,
    ToolDefinition,
    ToolDenied,
    approve_all_requests,
    create_tool,
    create_tool_definition,
    deny_all_requests,
    is_native_tool,
    matches_tool_selector,
    matches_tool_selector_sync,
)


class TestPydanticAIToolsSubsystem:
    """Test suite verifying native Pydantic AI Tools API integration."""

    def test_core_classes_and_type_exports(self) -> None:
        """Verify core tool classes, types, and functions are properly exported."""
        assert Tool is not None
        assert ToolDefinition is not None
        assert DeferredToolRequests is not None
        assert DeferredToolResults is not None
        assert ToolApproved is not None
        assert ToolDenied is not None
        assert matches_tool_selector is not None
        assert create_tool is not None
        assert is_native_tool is not None

    def test_create_tool_factory(self) -> None:
        """Verify create_tool constructs a native Tool instance with explicit settings."""

        def calculate_quota(cpu: int, memory: int) -> int:
            """Calculate cluster resource quota."""
            return cpu * memory

        tool = create_tool(
            calculate_quota,
            name="resource_quota",
            description="Computes resource capacity",
            timeout=15.0,
            max_retries=3,
            requires_approval=True,
            metadata={"domain": "k8s"},
        )

        assert is_native_tool(tool) is True
        assert tool.name == "resource_quota"
        assert tool.description == "Computes resource capacity"
        assert tool.timeout == 15.0
        assert tool.max_retries == 3
        assert tool.requires_approval is True
        assert tool.metadata == {"domain": "k8s"}
        assert tool(2, 4) == 8

    def test_is_native_tool_predicate(self) -> None:
        """Verify is_native_tool accurately differentiates native Tool instances."""

        def my_func() -> str:
            return "ok"

        tool = Tool(my_func)
        assert is_native_tool(tool) is True
        assert is_native_tool(my_func) is False
        assert is_native_tool("not_a_tool") is False
        assert is_native_tool(None) is False

    @pytest.mark.asyncio
    async def test_matches_tool_selector_async(self) -> None:
        """Verify matches_tool_selector evaluates tool names and callable predicates."""
        tool_def = ToolDefinition(
            name="cluster_deploy",
            parameters_json_schema={"type": "object"},
            description="Deploys workload",
        )
        ctx = RunContext(deps=None, model=MagicMock(), usage=MagicMock(), prompt="deploy")

        # 1. Exact string match
        assert await matches_tool_selector("cluster_deploy", ctx, tool_def) is True
        assert await matches_tool_selector("other_tool", ctx, tool_def) is False

        # 2. Callable predicate
        assert (
            await matches_tool_selector(
                lambda _ctx, td: td.name.startswith("cluster_"), ctx, tool_def
            )
            is True
        )
        assert (
            await matches_tool_selector(
                lambda _ctx, td: td.name.startswith("cloud_"), ctx, tool_def
            )
            is False
        )

    def test_matches_tool_selector_sync(self) -> None:
        """Verify synchronous wrapper matches_tool_selector_sync matches properly."""
        tool_def = ToolDefinition(
            name="k8s_scale",
            parameters_json_schema={"type": "object"},
            description="Scales replica count",
        )
        ctx = RunContext(deps=None, model=MagicMock(), usage=MagicMock(), prompt="scale")

        assert matches_tool_selector_sync("k8s_scale", ctx, tool_def) is True
        assert matches_tool_selector_sync("k8s_drain", ctx, tool_def) is False
        assert (
            matches_tool_selector_sync(lambda _ctx, td: td.name.startswith("k8s_"), ctx, tool_def)
            is True
        )

    def test_create_tool_definition(self) -> None:
        """Verify create_tool_definition constructs a typed ToolDefinition dataclass."""
        td = create_tool_definition(
            name="get_pods",
            parameters_json_schema={"type": "object", "properties": {"ns": {"type": "string"}}},
            description="List Kubernetes pods",
            sequential=True,
            timeout=5.0,
            metadata={"tier": "infra"},
        )

        assert isinstance(td, ToolDefinition)
        assert td.name == "get_pods"
        assert td.description == "List Kubernetes pods"
        assert td.sequential is True
        assert td.timeout == 5.0
        assert td.metadata == {"tier": "infra"}

    def test_tool_approved_and_denied(self) -> None:
        """Verify native ToolApproved and ToolDenied instantiation and arguments."""
        appr = ToolApproved(override_args={"replicas": 5})
        assert appr.override_args == {"replicas": 5}
        assert appr.kind == "tool-approved"

        den = ToolDenied("Forbidden operation")
        assert den.message == "Forbidden operation"
        assert den.kind == "tool-denied"

    def test_deferred_tool_requests_and_results(self) -> None:
        """Verify DeferredToolRequests building DeferredToolResults with approvals/denials."""
        reqs = DeferredToolRequests(
            approvals=[
                ToolCallPart(
                    tool_name="apply_helm", args={"chart": "redis"}, tool_call_id="call_1"
                ),
                ToolCallPart(tool_name="destroy_ns", args={"ns": "prod"}, tool_call_id="call_2"),
            ],
            calls=[
                ToolCallPart(
                    tool_name="fetch_logs", args={"pod": "redis-0"}, tool_call_id="call_3"
                ),
            ],
        )

        # 1. Manual resolution
        results = reqs.build_results(
            approvals={
                "call_1": ToolApproved(override_args={"chart": "valkey"}),
                "call_2": ToolDenied("Production namespace cannot be deleted"),
            },
            calls={"call_3": "Log content"},
        )
        assert isinstance(results, DeferredToolResults)
        assert isinstance(results.approvals["call_1"], ToolApproved)
        assert results.approvals["call_1"].override_args == {"chart": "valkey"}
        assert isinstance(results.approvals["call_2"], ToolDenied)
        assert results.calls["call_3"] == "Log content"

        # 2. approve_all
        appr_all = reqs.build_results(approve_all=True)
        assert isinstance(appr_all.approvals["call_1"], ToolApproved)
        assert isinstance(appr_all.approvals["call_2"], ToolApproved)

        # 3. deny_all
        deny_all = reqs.build_results(deny_all=True)
        assert isinstance(deny_all.approvals["call_1"], ToolDenied)
        assert isinstance(deny_all.approvals["call_2"], ToolDenied)

    def test_approve_all_and_deny_all_helpers(self) -> None:
        """Verify domain helper functions approve_all_requests and deny_all_requests."""
        reqs = DeferredToolRequests(
            approvals=[
                ToolCallPart(tool_name="k8s_apply", tool_call_id="c1"),
                ToolCallPart(tool_name="k8s_delete", tool_call_id="c2"),
            ]
        )

        appr_res = approve_all_requests(reqs)
        assert isinstance(appr_res, DeferredToolResults)
        assert isinstance(appr_res.approvals["c1"], ToolApproved)
        assert isinstance(appr_res.approvals["c2"], ToolApproved)

        deny_res = deny_all_requests(reqs, message="Policy check failed")
        assert isinstance(deny_res, DeferredToolResults)
        assert isinstance(deny_res.approvals["c1"], ToolDenied)
        assert deny_res.approvals["c1"].message == "Policy check failed"

    def test_tool_from_function_and_from_schema(self) -> None:
        """Verify Tool.from_function and Tool.from_schema constructor compatibility."""

        def query_db(query: str) -> dict[str, Any]:
            """Execute database query."""
            return {"rows": 42}

        # from_function
        t1 = Tool.from_function(
            query_db,
            name="sql_query",
            timeout=30.0,
            requires_approval=True,
        )
        assert isinstance(t1, Tool)
        assert t1.name == "sql_query"
        assert t1.timeout == 30.0
        assert t1.requires_approval is True

        # from_schema
        t2 = Tool.from_schema(
            query_db,
            name="custom_sql",
            description="Custom schema query",
            json_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        assert isinstance(t2, Tool)
        assert t2.name == "custom_sql"
        assert t2.description == "Custom schema query"

    def test_package_reexports(self) -> None:
        """Verify tool symbols are cleanly exposed across public package tiers."""
        import devops_cli.ai as ai
        import devops_cli.ai.agents as agents
        import devops_cli.ai.agents.pydantic_agent as pa
        import devops_cli.ai.tools as tools

        for target in (ai, agents, pa, tools):
            assert hasattr(target, "Tool")
            assert hasattr(target, "ToolDefinition")
            assert hasattr(target, "DeferredToolRequests")
            assert hasattr(target, "DeferredToolResults")
            assert hasattr(target, "ToolApproved")
            assert hasattr(target, "ToolDenied")
            assert hasattr(target, "matches_tool_selector")
            assert hasattr(target, "create_tool")
            assert hasattr(target, "is_native_tool")

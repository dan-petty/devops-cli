"""Unit tests for the native Pydantic AI tools subsystem in devops-cli."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic_ai.messages import ToolCallPart

from devops_cli.ai.tools import (
    DeferredToolRequests,
    DeferredToolResults,
    Tool,
    ToolApproved,
    ToolDenied,
)


class TestPydanticAIToolsSubsystem:
    """Test suite verifying native Pydantic AI Tools API integration."""

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

    def test_validate_args_unconditional_path_traversal(self) -> None:
        """Verify validate_args rejects path traversal even when parameters schema is empty."""

        def dummy_action(**kwargs: Any) -> str:
            return "done"

        tool = Tool(dummy_action, parameters={})
        with pytest.raises(ValueError, match="Path traversal"):
            tool.validate_args({"filepath": "../etc/passwd"})

        # Normal valid args pass cleanly
        clean = tool.validate_args({"normal_arg": "safe_value"})
        assert clean == {"normal_arg": "safe_value"}

    def test_a_tool_is_called_and_executed_like_its_function(self) -> None:
        """Verify a Tool call runs its function and execute() awaits an async function."""

        def multiply(x: int, y: int) -> int:
            return x * y

        async def fetch(host: str) -> str:
            return f"fetched {host}"

        async def fetch_inside_a_running_loop() -> str:
            return str(Tool(fetch).execute(host="example.com"))

        assert (
            Tool(multiply)(2, 4),
            Tool(multiply).execute(x=3, y=5),
            Tool(fetch).execute(host="example.com"),
            asyncio.run(fetch_inside_a_running_loop()),
        ) == (8, 15, "fetched example.com", "fetched example.com")

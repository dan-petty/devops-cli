"""Comprehensive test suite for Native Pydantic AI Toolsets subsystem.

Tests native pydantic_ai.toolsets primitives, combinators, dual sync/async contracts,
domain helpers, and PydanticAgent integration.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

from devops_cli.ai.agents.context import RunContext
from devops_cli.ai.tools import Tool
from devops_cli.ai.toolsets import (
    AbstractToolset,
    AgentToolset,
    ApprovalRequiredToolset,
    CombinedToolset,
    DeferredLoadingToolset,
    DynamicToolset,
    ExternalToolset,
    FilteredToolset,
    FunctionToolset,
    IncludeReturnSchemasToolset,
    PrefixedToolset,
    PreparedToolset,
    RenamedToolset,
    SetMetadataToolset,
    ToolsetFunc,
    ToolsetTool,
    WrapperToolset,
    combine_toolsets,
    create_function_toolset,
    defer_loading_toolset,
    extract_tools_from_toolset,
    filter_toolset,
    is_toolset,
    prefix_toolset,
    rename_toolset,
    require_approval_toolset,
)


class TestPydanticAIToolsetsSubsystem:
    """Test suite verifying full native toolsets integration and backward compatibility."""

    def test_package_reexports(self) -> None:
        """Verify all native classes, types, combinators, and helpers are re-exported."""
        expected_symbols = [
            AbstractToolset,
            AgentToolset,
            ApprovalRequiredToolset,
            CombinedToolset,
            DeferredLoadingToolset,
            DynamicToolset,
            ExternalToolset,
            FilteredToolset,
            FunctionToolset,
            IncludeReturnSchemasToolset,
            PrefixedToolset,
            PreparedToolset,
            RenamedToolset,
            SetMetadataToolset,
            ToolsetFunc,
            ToolsetTool,
            WrapperToolset,
            create_function_toolset,
            combine_toolsets,
            prefix_toolset,
            filter_toolset,
            rename_toolset,
            require_approval_toolset,
            defer_loading_toolset,
            is_toolset,
            extract_tools_from_toolset,
        ]
        for sym in expected_symbols:
            assert sym is not None

    def test_function_toolset_tool_and_plain_decorators(self) -> None:
        """Verify @tool (context-aware) and @tool_plain (context-free) decorators."""
        ts = FunctionToolset()

        @ts.tool
        def inspect_cluster(ctx: RunContext[Any], namespace: str) -> str:
            """Inspect cluster namespace."""
            return f"Cluster namespace: {namespace}"

        @ts.tool_plain
        def calculate_quota(cpu: int, memory: int) -> int:
            """Calculate quota score."""
            return cpu * memory

        sync_tools = ts.get_tools()
        assert len(sync_tools) == 2
        tool_names = {t.name for t in sync_tools}
        assert "inspect_cluster" in tool_names
        assert "calculate_quota" in tool_names

        # Verify takes_ctx flags
        inspect_tool = next(t for t in sync_tools if t.name == "inspect_cluster")
        quota_tool = next(t for t in sync_tools if t.name == "calculate_quota")
        assert inspect_tool.takes_ctx is True
        assert quota_tool.takes_ctx is False

    def test_function_toolset_add_tool_and_function(self) -> None:
        """Verify add_tool and add_function on FunctionToolset."""
        ts = FunctionToolset()

        def raw_fn(x: int) -> int:
            """Raw multiplier function."""
            return x * 2

        tool_inst = Tool.from_function(raw_fn, name="custom_mult", description="Multiply by two")
        ts.add_tool(tool_inst)

        ts.add_function(lambda msg: f"Echo: {msg}", name="echo_msg", description="Echo message")

        tools = ts.get_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert "custom_mult" in names
        assert "echo_msg" in names

    def test_function_toolset_sync_and_async_get_tools(self) -> None:
        """Verify dual sync (list[Tool]) and async (dict[str, ToolsetTool]) get_tools."""
        ts = FunctionToolset()

        @ts.tool_plain
        def status_check() -> str:
            """Check health status."""
            return "healthy"

        # 1. Sync invocation without arguments
        sync_tools = ts.get_tools()
        assert isinstance(sync_tools, list)
        assert len(sync_tools) == 1
        assert sync_tools[0].name == "status_check"

        # 2. Async invocation with RunContext
        rc: Any = RunContext()

        async def run_async_test() -> None:
            async_tools = await ts.get_tools(rc)
            assert isinstance(async_tools, dict)
            assert "status_check" in async_tools
            tool_tool = async_tools["status_check"]
            assert tool_tool.tool_def.name == "status_check"

        asyncio.run(run_async_test())

    def test_function_toolset_call_tool(self) -> None:
        """Verify async call_tool execution against registered tools."""
        ts = FunctionToolset()

        @ts.tool_plain
        def add_nums(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        rc: Any = RunContext()

        async def run_call_test() -> None:
            tools_map = await ts.get_tools(rc)
            tool_entry = tools_map["add_nums"]
            res = await ts.call_tool("add_nums", {"a": 10, "b": 25}, rc, tool_entry)
            assert res == 35

        asyncio.run(run_call_test())

    def test_function_toolset_instructions(self) -> None:
        """Verify get_instructions formatted synchronously and asynchronously."""
        ts = FunctionToolset(instructions="Strictly adhere to semver specifications.")

        # Sync instructions
        sync_inst = ts.get_instructions()
        assert isinstance(sync_inst, list)
        assert len(sync_inst) == 1
        assert "Strictly adhere to semver" in sync_inst[0]

        # Async instructions with RunContext
        rc: Any = RunContext()

        async def run_inst_test() -> None:
            async_inst = await ts.get_instructions(rc)
            assert async_inst is not None

        asyncio.run(run_inst_test())

    def test_prefixed_toolset_combinator(self) -> None:
        """Verify .prefixed() and prefix_toolset combinator prefixes tool names."""
        base_ts = FunctionToolset()

        @base_ts.tool_plain
        def restart_pod(pod_name: str) -> str:
            """Restart pod."""
            return f"Pod {pod_name} restarted"

        prefixed_ts = base_ts.prefixed("k8s")
        assert isinstance(prefixed_ts, PrefixedToolset)

        rc: Any = RunContext()

        async def run_prefix_test() -> None:
            tools_map = await prefixed_ts.get_tools(rc)
            assert "k8s_restart_pod" in tools_map
            tool_entry = tools_map["k8s_restart_pod"]
            res = await prefixed_ts.call_tool(
                "k8s_restart_pod", {"pod_name": "api-1"}, rc, tool_entry
            )
            assert res == "Pod api-1 restarted"

        asyncio.run(run_prefix_test())

        # Also verify prefix_toolset helper
        h_ts = prefix_toolset(base_ts, "cluster_")
        assert isinstance(h_ts, PrefixedToolset)

    def test_filtered_toolset_combinator(self) -> None:
        """Verify .filtered() and filter_toolset combinator filters tool exposure."""
        base_ts = FunctionToolset()

        @base_ts.tool_plain
        def public_tool() -> str:
            """Public utility."""
            return "public"

        @base_ts.tool_plain
        def internal_tool() -> str:
            """Internal utility."""
            return "internal"

        filtered_ts = base_ts.filtered(lambda ctx, tool_def: tool_def.name == "public_tool")
        assert isinstance(filtered_ts, FilteredToolset)

        rc: Any = RunContext()

        async def run_filter_test() -> None:
            tools_map = await filtered_ts.get_tools(rc)
            assert "public_tool" in tools_map
            assert "internal_tool" not in tools_map

        asyncio.run(run_filter_test())

        # Also verify filter_toolset helper
        h_ts = filter_toolset(base_ts, lambda ctx, tool_def: True)
        assert isinstance(h_ts, FilteredToolset)

    def test_renamed_toolset_combinator(self) -> None:
        """Verify .renamed() and rename_toolset renames registered tools."""
        base_ts = FunctionToolset()

        @base_ts.tool_plain
        def get_log() -> str:
            """Get log content."""
            return "log data"

        renamed_ts = base_ts.renamed({"fetch_log": "get_log"})
        assert isinstance(renamed_ts, RenamedToolset)

        rc: Any = RunContext()

        async def run_renamed_test() -> None:
            tools_map = await renamed_ts.get_tools(rc)
            assert "fetch_log" in tools_map
            assert "get_log" not in tools_map

        asyncio.run(run_renamed_test())

        # Also verify rename_toolset helper
        h_ts = rename_toolset(base_ts, {"read_log": "get_log"})
        assert isinstance(h_ts, RenamedToolset)

    def test_combined_toolset_combinator(self) -> None:
        """Verify CombinedToolset and combine_toolsets merges multiple toolsets."""
        ts1 = FunctionToolset()
        ts2 = FunctionToolset()

        @ts1.tool_plain
        def tool_alpha() -> str:
            return "alpha"

        @ts2.tool_plain
        def tool_beta() -> str:
            return "beta"

        combined = combine_toolsets(ts1, ts2)
        assert isinstance(combined, CombinedToolset)

        rc: Any = RunContext()

        async def run_combined_test() -> None:
            tools_map = await combined.get_tools(rc)
            assert "tool_alpha" in tools_map
            assert "tool_beta" in tools_map

        asyncio.run(run_combined_test())

    def test_approval_and_deferred_loading_combinators(self) -> None:
        """Verify approval_required and defer_loading combinators and helpers."""
        ts = FunctionToolset()

        @ts.tool_plain
        def drop_database() -> str:
            return "dropped"

        app_ts = require_approval_toolset(ts)
        assert isinstance(app_ts, ApprovalRequiredToolset)

        def_ts = defer_loading_toolset(ts)
        assert isinstance(def_ts, DeferredLoadingToolset)

    def test_domain_helper_factories(self) -> None:
        """Verify create_function_toolset, is_toolset, and extract_tools_from_toolset."""

        def fn_one() -> str:
            return "one"

        def fn_two(x: int) -> int:
            return x * 2

        ts = create_function_toolset(
            tools=[fn_one, Tool.from_function(fn_two, name="fn_two")],
            instructions="Domain instruction set.",
        )
        assert isinstance(ts, FunctionToolset)
        assert is_toolset(ts) is True
        assert is_toolset("not a toolset") is False

        extracted = extract_tools_from_toolset(ts)
        assert len(extracted) == 2
        names = {t.name for t in extracted}
        assert "fn_one" in names
        assert "fn_two" in names

    def test_abstract_custom_toolset_subclassing(self) -> None:
        """Verify custom AbstractToolset subclasses integrating with sync and async consumers."""

        class MetricToolset(AbstractToolset):
            prefix: str = "metric_"

            def get_tools(self, ctx: Any = None) -> Any:
                def get_mem() -> str:
                    return "memory: 60%"

                tools_list = [Tool.from_function(get_mem, name=f"{self.prefix}mem")]
                if ctx is None:
                    return tools_list
                fts = FunctionToolset()
                for t in tools_list:
                    fts.add_tool(t)
                return fts.get_tools(ctx)

            def get_instructions(self, ctx: Any = None) -> Any:
                inst = ["Always report metrics in percentage."]
                if ctx is None:
                    return inst
                return inst

        mt = MetricToolset(prefix="sys_")
        assert is_toolset(mt) is True

        # Sync verification
        sync_tools = mt.get_tools()
        assert len(sync_tools) == 1
        assert sync_tools[0].name == "sys_mem"
        assert "Always report metrics" in mt.get_instructions()[0]

        # Async verification with RunContext
        rc: Any = RunContext()

        async def run_custom_test() -> None:
            async_tools = await mt.get_tools(rc)
            assert "sys_mem" in async_tools

        asyncio.run(run_custom_test())

    def test_pydantic_agent_integration(self) -> None:
        """Verify PydanticAgent seamlessly absorbs and registers native toolsets."""
        from devops_cli.ai.agents import PydanticAgent

        ts = FunctionToolset(instructions="Ensure release branches follow convention.")

        @ts.tool_plain
        def check_branch(name: str) -> bool:
            return name.startswith("release/v")

        mock_client = MagicMock()
        mock_client.model = "test-model"

        agent: Any = PydanticAgent(
            client=mock_client,
            name="BranchAuditor",
            toolsets=[ts],
        )

        assert "check_branch" in agent._tools
        sys_prompt = agent._build_system_prompt_with_tools()
        assert "Ensure release branches follow convention." in sys_prompt

"""A function toolset registers tools, lists them, calls them and carries instructions."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic_ai import RunContext as NativeRunContext

from devops_cli.ai.agents.context import RunContext
from devops_cli.ai.tools import Tool
from devops_cli.ai.toolsets import (
    FunctionToolset,
)


def test_function_toolset_tool_and_plain_decorators() -> None:
    """Verify @tool (context-aware) and @tool_plain (context-free) decorators."""
    ts = FunctionToolset()

    @ts.tool
    def inspect_cluster(ctx: NativeRunContext[Any], namespace: str) -> str:
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


def test_function_toolset_add_tool_and_function() -> None:
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


def test_function_toolset_sync_and_async_get_tools() -> None:
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


def test_function_toolset_call_tool() -> None:
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


def test_function_toolset_instructions() -> None:
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

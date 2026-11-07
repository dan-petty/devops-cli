"""A domain builds a toolset with the helper factories or by subclassing the abstract toolset."""

from __future__ import annotations

import asyncio
from typing import Any

from devops_cli.ai.agents.context import RunContext
from devops_cli.ai.tools import Tool
from devops_cli.ai.toolsets import (
    AbstractToolset,
    FunctionToolset,
    create_function_toolset,
    extract_tools_from_toolset,
)


def test_domain_helper_factories() -> None:
    """Verify create_function_toolset and extract_tools_from_toolset."""

    def fn_one() -> str:
        return "one"

    def fn_two(x: int) -> int:
        return x * 2

    ts = create_function_toolset(
        tools=[fn_one, Tool.from_function(fn_two, name="fn_two")],
        instructions="Domain instruction set.",
    )
    assert isinstance(ts, FunctionToolset)

    extracted = extract_tools_from_toolset(ts)
    assert len(extracted) == 2
    names = {t.name for t in extracted}
    assert "fn_one" in names
    assert "fn_two" in names


def test_abstract_custom_toolset_subclassing() -> None:
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

"""A toolset combinator prefixes, filters, renames, combines, gates or defers the tools it wraps."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic_ai.toolsets import (
    ApprovalRequiredToolset,
    CombinedToolset,
    DeferredLoadingToolset,
    FilteredToolset,
    PrefixedToolset,
    RenamedToolset,
)

from devops_cli.ai.agents.context import RunContext
from devops_cli.ai.toolsets import (
    FunctionToolset,
)


def test_prefixed_toolset_combinator() -> None:
    """Verify .prefixed() prefixes the tool names of a FunctionToolset."""
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
        res = await prefixed_ts.call_tool("k8s_restart_pod", {"pod_name": "api-1"}, rc, tool_entry)
        assert res == "Pod api-1 restarted"

    asyncio.run(run_prefix_test())


def test_filtered_toolset_combinator() -> None:
    """Verify .filtered() filters the tools a FunctionToolset exposes."""
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


def test_renamed_toolset_combinator() -> None:
    """Verify .renamed() renames the tools of a FunctionToolset."""
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


def test_combined_toolset_combinator() -> None:
    """Verify CombinedToolset merges FunctionToolsets."""
    ts1 = FunctionToolset()
    ts2 = FunctionToolset()

    @ts1.tool_plain
    def tool_alpha() -> str:
        return "alpha"

    @ts2.tool_plain
    def tool_beta() -> str:
        return "beta"

    combined = CombinedToolset([ts1, ts2])
    assert isinstance(combined, CombinedToolset)

    rc: Any = RunContext()

    async def run_combined_test() -> None:
        tools_map = await combined.get_tools(rc)
        assert "tool_alpha" in tools_map
        assert "tool_beta" in tools_map

    asyncio.run(run_combined_test())


def test_approval_and_deferred_loading_combinators() -> None:
    """Verify approval_required and defer_loading wrap a FunctionToolset."""
    ts = FunctionToolset()

    @ts.tool_plain
    def drop_database() -> str:
        return "dropped"

    app_ts = ts.approval_required()
    assert isinstance(app_ts, ApprovalRequiredToolset)
    assert app_ts.wrapped is ts

    def_ts = ts.defer_loading()
    assert isinstance(def_ts, DeferredLoadingToolset)
    assert def_ts.wrapped is ts

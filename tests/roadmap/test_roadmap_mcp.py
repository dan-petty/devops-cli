"""Tests for the roadmap MCP client integration (#3221).

Tests run in-process against FastMCP role endpoints, making no network requests.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ToolReturn
from pydantic_ai.models.test import TestModel

from devops_cli.config.settings import (
    RoadmapConfig,
    RoadmapImplementConfig,
    RoadmapMcpConfig,
    RoadmapStageConfig,
    Settings,
    get_mcp_implement_token,
    get_mcp_stage_token,
)
from devops_cli.exceptions.roadmap import RoadmapMcpUnavailableError
from devops_cli.roadmap.agent_run import RunTrace, ToolOutcome
from devops_cli.roadmap.implement.implement_limits import StepBudget
from devops_cli.roadmap.implement.implement_step import (
    IMPLEMENT_LOCAL_TOOL_NAMES,
    StepInputs,
    TaskGroup,
    _attempt,
    build_agent,
)
from devops_cli.roadmap.implement.implement_tool_log import ToolCallLog
from devops_cli.roadmap.mcp import (
    ROLE_IMPLEMENTATION,
    ROLE_PLANNING,
    RoadmapMcpToolset,
    build_roadmap_mcp_toolset,
    roadmap_mcp_url,
)
from devops_cli.roadmap.refine.refine_investigation import investigate

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_default_mcp_settings() -> None:
    settings = Settings()
    assert settings.roadmap.mcp.url is None
    assert settings.roadmap.mcp.timeout_seconds == 30.0
    assert settings.roadmap.stage.mcp is False
    assert settings.roadmap.implement.mcp is False


def test_roadmap_mcp_unavailable_error_attributes() -> None:
    err = RoadmapMcpUnavailableError("http://mcp.local:8000")
    assert err.url == "http://mcp.local:8000"
    assert "http://mcp.local:8000" in str(err)
    assert err.error_code == "ROADMAP_MCP_UNAVAILABLE"


def test_roadmap_mcp_url() -> None:
    base = "http://mcp-server:8000"
    assert roadmap_mcp_url(base, ROLE_PLANNING) == "http://mcp-server:8000/planning/mcp"
    assert roadmap_mcp_url(base, ROLE_IMPLEMENTATION) == "http://mcp-server:8000/implementation/mcp"
    # Existing trailing slash or subpath
    assert (
        roadmap_mcp_url("http://mcp-server:8000/", ROLE_PLANNING)
        == "http://mcp-server:8000/planning/mcp"
    )
    assert (
        roadmap_mcp_url("http://mcp-server:8000/planning/mcp", ROLE_PLANNING)
        == "http://mcp-server:8000/planning/mcp"
    )


def test_build_roadmap_mcp_toolset_disabled() -> None:
    settings = Settings(
        roadmap=RoadmapConfig(
            mcp=RoadmapMcpConfig(url="http://mcp-server:8000"),
            stage=RoadmapStageConfig(mcp=False),
            implement=RoadmapImplementConfig(mcp=False),
        )
    )
    assert build_roadmap_mcp_toolset(ROLE_PLANNING, settings=settings) is None
    assert build_roadmap_mcp_toolset(ROLE_IMPLEMENTATION, settings=settings) is None


def test_build_roadmap_mcp_toolset_missing_url() -> None:
    settings = Settings(
        roadmap=RoadmapConfig(
            stage=RoadmapStageConfig(mcp=True),
        )
    )
    with pytest.raises(
        RoadmapMcpUnavailableError, match=r"Roadmap MCP server URL is not configured\."
    ):
        build_roadmap_mcp_toolset(ROLE_PLANNING, settings=settings)


def test_build_roadmap_mcp_toolset_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_MCP_STAGE_TOKEN", "stage-secret-token")
    settings = Settings(
        roadmap=RoadmapConfig(
            mcp=RoadmapMcpConfig(url="http://mcp-server:8000"),
            stage=RoadmapStageConfig(mcp=True),
        )
    )
    toolset = build_roadmap_mcp_toolset(ROLE_PLANNING, settings=settings)
    assert toolset is not None
    assert toolset._target_url == "http://mcp-server:8000/planning/mcp"


def test_get_mcp_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_MCP_STAGE_TOKEN", "stage-secret-token")
    monkeypatch.setenv("DEVOPS_CLI_MCP_IMPLEMENT_TOKEN", "implement-secret-token")
    assert get_mcp_stage_token() == "stage-secret-token"
    assert get_mcp_implement_token() == "implement-secret-token"


def test_build_roadmap_mcp_toolset_implement_and_client_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_MCP_IMPLEMENT_TOKEN", "implement-token")
    server = FastMCP("override-server")
    settings = Settings(
        roadmap=RoadmapConfig(
            mcp=RoadmapMcpConfig(url="http://mcp-server:8000"),
            implement=RoadmapImplementConfig(mcp=True),
        )
    )
    toolset = build_roadmap_mcp_toolset(
        ROLE_IMPLEMENTATION,
        client=server,
        settings=settings,
    )
    assert toolset is not None
    assert toolset._target_url == "http://mcp-server:8000"

    toolset_default = build_roadmap_mcp_toolset(ROLE_IMPLEMENTATION, settings=settings)
    assert toolset_default is not None
    assert toolset_default._target_url == "http://mcp-server:8000/implementation/mcp"


@pytest.mark.asyncio
async def test_roadmap_mcp_toolset_raw_tool_return(monkeypatch: pytest.MonkeyPatch) -> None:
    server = FastMCP("in-process-raw")
    toolset = RoadmapMcpToolset(server)

    async def fake_super_call(*args: Any, **kwargs: Any) -> Any:
        return ToolReturn("custom result", metadata={"custom": "meta"})

    monkeypatch.setattr(MCPToolset, "call_tool", fake_super_call)
    res = await toolset.call_tool("echo_server", {}, None, None)  # type: ignore[arg-type]
    assert isinstance(res, ToolReturn)
    assert res.metadata["custom"] == "meta"
    assert res.metadata["outcome"] == ToolOutcome.OK


@pytest.mark.asyncio
async def test_remote_tools_join_toolset_and_trace() -> None:
    server = FastMCP("in-process-mcp")

    @server.tool
    def echo_server(message: str) -> str:
        return f"echo: {message}"

    toolset = RoadmapMcpToolset(server, timeout_seconds=10.0)
    model = TestModel(call_tools=["echo_server"])
    agent = Agent(model, toolsets=[toolset])
    trace = RunTrace()
    result = await agent.run("ping")
    assert result.output is not None

    trace.absorb(result.all_messages(), tools=toolset.tool_names)
    assert len(trace.tool_calls) == 1
    call = trace.tool_calls[0]
    assert call.name == "echo_server"
    assert call.outcome == ToolOutcome.OK
    assert call.timeout == 10.0
    assert call.chars is not None
    assert call.chars > 0


@pytest.mark.asyncio
async def test_local_tools_win_on_name_clash() -> None:
    server = FastMCP("in-process-clash")

    @server.tool
    def my_tool(arg: str) -> str:
        return "remote"

    def my_tool_local(arg: str) -> str:
        return "local"

    # Set function name for local tool
    my_tool_local.__name__ = "my_tool"

    toolset = RoadmapMcpToolset(server, local_tool_names=["my_tool"])
    tools = await toolset.list_tools()
    assert not any(t.name == "my_tool" for t in tools)

    model = TestModel(call_tools=["my_tool"])
    agent = Agent(model, tools=[my_tool_local], toolsets=[toolset])
    trace = RunTrace()
    result = await agent.run("call")
    assert result.output is not None

    trace.absorb(result.all_messages(), tools={"my_tool"})
    assert len(trace.tool_calls) == 1
    call = trace.tool_calls[0]
    assert call.name == "my_tool"
    assert call.outcome == ToolOutcome.OK
    # Local tool calls do not have a timeout recorded
    assert call.timeout is None


@pytest.mark.asyncio
async def test_remote_call_timeout() -> None:
    server = FastMCP("in-process-timeout")

    @server.tool
    async def slow_call() -> str:
        await asyncio.sleep(0.5)
        return "finished"

    toolset = RoadmapMcpToolset(server, timeout_seconds=0.05)
    model = TestModel(call_tools=["slow_call"])
    agent = Agent(model, toolsets=[toolset])
    trace = RunTrace()
    result = await agent.run("call slow")
    assert result.output is not None

    trace.absorb(result.all_messages(), tools=toolset.tool_names)
    assert len(trace.tool_calls) == 1
    call = trace.tool_calls[0]
    assert call.name == "slow_call"
    assert call.outcome == ToolOutcome.ERROR
    assert call.timeout == 0.05


@pytest.mark.asyncio
async def test_remote_failure_is_tool_error() -> None:
    server = FastMCP("in-process-failure")

    @server.tool
    def failing_call() -> str:
        raise RuntimeError("simulated server crash")

    toolset = RoadmapMcpToolset(server, timeout_seconds=5.0)
    model = TestModel(call_tools=["failing_call"])
    agent = Agent(model, toolsets=[toolset])
    trace = RunTrace()
    # Agent run must not crash
    result = await agent.run("call failing")
    assert result.output is not None

    trace.absorb(result.all_messages(), tools=toolset.tool_names)
    assert len(trace.tool_calls) == 1
    call = trace.tool_calls[0]
    assert call.name == "failing_call"
    assert call.outcome == ToolOutcome.ERROR
    assert call.timeout == 5.0


@pytest.mark.asyncio
async def test_server_unavailable_at_start(refusing_port: int) -> None:
    url = f"http://127.0.0.1:{refusing_port}/mcp"
    toolset = RoadmapMcpToolset(url, target_url=url)
    with pytest.raises(RoadmapMcpUnavailableError) as exc_info:
        async with toolset:
            pass
    assert exc_info.value.url == url


def test_implement_step_build_agent_with_mcp(tmp_path: Path) -> None:
    server = FastMCP("implement-mcp")

    @server.tool
    def scan_infra() -> str:
        return "infra ok"

    mcp_toolset = RoadmapMcpToolset(server, local_tool_names=IMPLEMENT_LOCAL_TOOL_NAMES)
    model = TestModel()
    log = ToolCallLog()
    budget = StepBudget(progress=log.progress)
    agent = build_agent(
        model,
        tmp_path,
        "instructions",
        10000,
        tmp_path / "home",
        log,
        budget,
        mcp_toolset=mcp_toolset,
    )
    assert mcp_toolset in agent.toolsets


class _OutputSchema(BaseModel):
    reply: str


def test_investigate_with_mcp_toolset() -> None:
    server = FastMCP("stage-investigate-mcp")

    @server.tool
    def investigate_remote() -> str:
        return "remote data"

    mcp_toolset = RoadmapMcpToolset(server)
    model = TestModel(call_tools=["investigate_remote"])

    class FakeToolSet:
        def tools(self) -> list[Any]:
            return []

    trace = RunTrace()
    result = investigate(
        model,
        "instructions",
        "request",
        FakeToolSet(),
        _OutputSchema,
        toolsets=[mcp_toolset],
        trace=trace,
    )
    assert not isinstance(result, type(None))
    assert len(trace.tool_calls) == 1
    assert trace.tool_calls[0].name == "investigate_remote"
    assert trace.tool_calls[0].outcome == ToolOutcome.OK


def test_implement_attempt_builds_mcp_toolset_from_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = FastMCP("implement-attempt-mcp")
    settings = Settings(
        roadmap=RoadmapConfig(
            implement=RoadmapImplementConfig(mcp=True),
        )
    )
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_step.load_settings",
        lambda: settings,
    )
    in_proc_toolset = RoadmapMcpToolset(server, local_tool_names=IMPLEMENT_LOCAL_TOOL_NAMES)
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_step.build_roadmap_mcp_toolset",
        lambda *args, **kwargs: in_proc_toolset,
    )

    captured: dict[str, Any] = {}

    def fake_turn(agent: Any, *args: Any, **kwargs: Any) -> Any:
        captured["toolsets"] = agent.toolsets
        raise RuntimeError("stop after turn")

    monkeypatch.setattr("devops_cli.roadmap.implement.implement_step._turn", fake_turn)
    tg = TaskGroup(1, "title", "prompt", "text")
    inputs = StepInputs(tg, tmp_path, "tasks", "item", "inst", "msg", 1000)
    log = ToolCallLog()

    with pytest.raises(RuntimeError, match="stop after turn"):
        _attempt(
            tmp_path,
            TestModel(),
            1000,
            inputs,
            1,
            None,  # type: ignore[arg-type]
            log,
            tiers=(),
            model_for_tier=None,
            tier_health=lambda _: {},
            limits=StepBudget(progress=log.progress),
        )

    assert in_proc_toolset in captured.get("toolsets", [])

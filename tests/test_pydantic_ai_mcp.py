"""Unit and integration test suite for native Pydantic AI MCP integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pydantic_ai.mcp as p_mcp
import pytest
from pydantic_ai.toolsets import PrefixedToolset

from devops_cli.ai.agents import PydanticAgent
from devops_cli.ai.agents.testing import TestModel
from devops_cli.ai.agents.tools import MCPToolset as AgentMCPToolset
from devops_cli.ai.mcp import (
    EmbeddedResource,
    Icon,
    MCPError,
    MCPToolset,
    Prompt,
    PromptArgument,
    PromptMessage,
    PromptResult,
    Resource,
    ResourceAnnotations,
    ResourceLink,
    ResourceTemplate,
    ServerCapabilities,
    create_devops_mcp_toolset,
    create_mcp_toolset,
    load_devops_mcp_toolsets,
    load_mcp_toolsets,
)
from devops_cli.ai.tools.mcp_bridge import get_devops_mcp_toolset, get_mcp_agent_tools


def test_native_mcp_type_reexports() -> None:
    """Verify all native classes and types are cleanly re-exported from pydantic_ai.mcp."""
    assert MCPToolset is p_mcp.MCPToolset
    assert load_mcp_toolsets is p_mcp.load_mcp_toolsets
    assert MCPError is p_mcp.MCPError
    assert Resource is p_mcp.Resource
    assert ResourceAnnotations is p_mcp.ResourceAnnotations
    assert ResourceTemplate is p_mcp.ResourceTemplate
    assert ServerCapabilities is p_mcp.ServerCapabilities
    assert Prompt is p_mcp.Prompt
    assert PromptArgument is p_mcp.PromptArgument
    assert PromptMessage is p_mcp.PromptMessage
    assert PromptResult is p_mcp.PromptResult
    assert Icon is p_mcp.Icon
    assert ResourceLink is p_mcp.ResourceLink
    assert EmbeddedResource is p_mcp.EmbeddedResource


async def test_create_devops_mcp_toolset() -> None:
    """Verify create_devops_mcp_toolset creates an MCPToolset bound to devops-cli FastMCP."""
    ts = create_devops_mcp_toolset()
    assert isinstance(ts, p_mcp.MCPToolset)

    # Discovered tools on in-process FastMCP server
    tools = await ts.list_tools()
    tool_names = {t.name for t in tools}
    assert len(tools) >= 70
    assert "review_path" in tool_names
    assert "k8s_pods" in tool_names
    assert "docker_stats" in tool_names
    assert "config_show" in tool_names
    assert "scan_trivy" in tool_names
    assert "vault_set" in tool_names
    assert "ai_architecture" in tool_names

    # Discovered prompts and resources on in-process server
    prompts = await ts.list_prompts()
    prompt_names = {p.name for p in prompts}
    assert "code_review_prompt" in prompt_names
    assert "security_audit_prompt" in prompt_names

    resources = await ts.list_resources()
    resource_uris = {str(r.uri) for r in resources}
    assert "resource://vault/status" in resource_uris
    assert "resource://mcp/tools" in resource_uris

    # Direct tool call via in-process server
    res = await ts.direct_call_tool("config_output", {"output_format": "json"})
    assert isinstance(res, str)
    assert "DEVOPS_CLI_CONFIG" in res or "config" in res.lower()


async def test_create_mcp_toolset_variations() -> None:
    """Verify create_mcp_toolset adapts FastMCP servers, URLs, and tool prefixing."""
    from devops_cli.ai.mcp.server import mcp as devops_server

    # 1. From FastMCP server instance
    ts_server = create_mcp_toolset(devops_server)
    assert isinstance(ts_server, p_mcp.MCPToolset)

    # 2. With prefixing
    ts_prefixed = create_mcp_toolset(devops_server, tool_prefix="devops")
    assert isinstance(ts_prefixed, PrefixedToolset)

    # 3. From URL target
    ts_url = create_mcp_toolset("http://localhost:8000/sse")
    assert isinstance(ts_url, p_mcp.MCPToolset)


def test_load_devops_mcp_toolsets_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify load_devops_mcp_toolsets loads JSON configuration with env var interpolation."""
    monkeypatch.setenv("TEST_MCP_PORT", "9090")
    config_data = {
        "mcpServers": {
            "remote_api": {
                "url": "http://localhost:${TEST_MCP_PORT}/sse",
            },
            "default_api": {
                "url": "http://localhost:${FALLBACK_PORT:-8080}/sse",
            },
        }
    }
    cfg_file = tmp_path / "mcp_config.json"
    cfg_file.write_text(json.dumps(config_data), encoding="utf-8")

    toolsets = load_devops_mcp_toolsets(cfg_file)
    assert len(toolsets) == 2
    assert all(isinstance(ts, PrefixedToolset) for ts in toolsets)


def test_load_devops_mcp_toolsets_yaml(tmp_path: Path) -> None:
    """Verify load_devops_mcp_toolsets handles YAML configuration files."""
    yaml_content = """
mcpServers:
  devops_service:
    url: "http://localhost:8080/sse"
"""
    cfg_file = tmp_path / "mcp_config.yaml"
    cfg_file.write_text(yaml_content, encoding="utf-8")

    toolsets = load_devops_mcp_toolsets(cfg_file)
    assert len(toolsets) == 1
    assert isinstance(toolsets[0], PrefixedToolset)


def test_load_devops_mcp_toolsets_missing_file() -> None:
    """Verify load_devops_mcp_toolsets raises FileNotFoundError for missing configs."""
    with pytest.raises(FileNotFoundError):
        load_devops_mcp_toolsets("/nonexistent/mcp_servers.json")


def test_agent_mcp_toolset_to_native() -> None:
    """Verify AgentMCPToolset converts to a native pydantic_ai.mcp.MCPToolset."""
    from devops_cli.ai.mcp.server import mcp as devops_server

    toolset = AgentMCPToolset(server=devops_server)
    native_ts = toolset.to_native_toolset()
    assert isinstance(native_ts, p_mcp.MCPToolset)

    # Convert with prefixing
    toolset_prefixed = AgentMCPToolset(server=devops_server, tool_prefix="cli")
    native_prefixed = toolset_prefixed.to_native_toolset()
    assert isinstance(native_prefixed, PrefixedToolset)


def test_mcp_bridge_dynamic_discovery() -> None:
    """Verify get_mcp_agent_tools returns dynamic tools from FastMCP rather than a static list."""
    tools = get_mcp_agent_tools()
    assert len(tools) >= 50
    tool_names = {getattr(t, "__name__", getattr(t, "name", str(t))) for t in tools}
    assert "review_path" in tool_names
    assert "k8s_pods" in tool_names

    native_ts = get_devops_mcp_toolset()
    assert isinstance(native_ts, p_mcp.MCPToolset)


async def test_pydantic_agent_with_native_mcp_toolset() -> None:
    """Verify PydanticAgent accepts native MCPToolset and executes within async lifecycle."""
    native_ts = create_devops_mcp_toolset()
    agent: PydanticAgent[Any, Any] = PydanticAgent(
        name="MCPDevOpsAgent",
        system_prompt="You are a DevOps assistant with MCP tools.",
        toolsets=[native_ts],
    )

    async with agent:
        with agent.override(model=TestModel(custom_output_text="MCP execution successful")):
            res = agent.run("Run cluster check")
            assert res.content == "MCP execution successful"


def test_public_package_reexports() -> None:
    """Verify MCP tools and types are re-exported across public package tiers."""
    import devops_cli.ai as ai
    import devops_cli.ai.agents as agents
    import devops_cli.ai.agents.pydantic_agent as pydantic_agent
    import devops_cli.ai.mcp as mcp_pkg

    assert hasattr(mcp_pkg, "create_devops_mcp_toolset")
    assert hasattr(mcp_pkg, "load_devops_mcp_toolsets")
    assert hasattr(mcp_pkg, "MCPToolset")
    assert hasattr(mcp_pkg, "load_mcp_toolsets")
    assert hasattr(mcp_pkg, "MCPError")

    assert hasattr(ai, "create_devops_mcp_toolset")
    assert hasattr(ai, "load_mcp_toolsets")
    assert hasattr(ai, "MCPError")

    assert hasattr(agents, "create_devops_mcp_toolset")
    assert hasattr(agents, "load_mcp_toolsets")
    assert hasattr(pydantic_agent, "create_devops_mcp_toolset")

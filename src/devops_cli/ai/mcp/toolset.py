"""Native Pydantic AI MCP toolset integration, factory helpers, and configuration loading."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from pydantic_ai.mcp import (
    CallToolFunc,
    ContentBlock,
    EmbeddedResource,
    Icon,
    MCPError,
    MCPToolset,
    MCPToolsetClient,
    ProcessToolCallback,
    Prompt,
    PromptArgument,
    PromptMessage,
    PromptResult,
    PromptRole,
    Resource,
    ResourceAnnotations,
    ResourceLink,
    ResourceTemplate,
    ServerCapabilities,
    ToolResult,
    load_mcp_toolsets,
)
from pydantic_ai.toolsets import AbstractToolset, PrefixedToolset

NativeMCPToolset = MCPToolset

__all__ = (
    "CallToolFunc",
    "ContentBlock",
    "EmbeddedResource",
    "Icon",
    "MCPError",
    "MCPToolset",
    "MCPToolsetClient",
    "NativeMCPToolset",
    "ProcessToolCallback",
    "Prompt",
    "PromptArgument",
    "PromptMessage",
    "PromptResult",
    "PromptRole",
    "Resource",
    "ResourceAnnotations",
    "ResourceLink",
    "ResourceTemplate",
    "ServerCapabilities",
    "ToolResult",
    "create_devops_mcp_toolset",
    "create_mcp_toolset",
    "load_devops_mcp_toolsets",
    "load_mcp_toolsets",
)

_ENV_VAR_PATTERN = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)(?::-([^}]*))?\}")


def _expand_env_vars(text: str) -> str:
    """Expand ${VAR} and ${VAR:-default} syntax in configuration text."""

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_val = match.group(2)
        if var_name in os.environ:
            return os.environ[var_name]
        if default_val is not None:
            return default_val
        raise ValueError(
            f"Environment variable '{var_name}' is not defined and no default was provided."
        )

    return _ENV_VAR_PATTERN.sub(replacer, text)


def create_devops_mcp_toolset(
    *,
    server: Any | None = None,
    prefer_tasks: bool = True,
    cache_tools: bool = True,
    cache_resources: bool = True,
    cache_prompts: bool = True,
    tool_prefix: str | None = None,
    **kwargs: Any,
) -> MCPToolset | PrefixedToolset:
    """Construct a native Pydantic AI MCPToolset connected to the in-process devops-cli FastMCP server."""
    if server is None:
        from devops_cli.ai.mcp.server import mcp as devops_server

        server = devops_server

    ts = MCPToolset(
        server,
        prefer_tasks=prefer_tasks,
        cache_tools=cache_tools,
        cache_resources=cache_resources,
        cache_prompts=cache_prompts,
        **kwargs,
    )
    if tool_prefix:
        return ts.prefixed(tool_prefix)
    return ts


def create_mcp_toolset(
    target: Any,
    *,
    tool_prefix: str | None = None,
    **kwargs: Any,
) -> MCPToolset | PrefixedToolset:
    """Adapt a URL, script path, FastMCP server, or client into a native Pydantic AI MCPToolset."""
    ts = MCPToolset(target, **kwargs)
    if tool_prefix:
        return ts.prefixed(tool_prefix)
    return ts


def load_devops_mcp_toolsets(config_path: str | Path) -> list[AbstractToolset[Any]]:
    """Load MCPToolsets from a JSON or YAML configuration file with environment variable expansion."""
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"MCP configuration file not found: {p}")

    raw_text = p.read_text(encoding="utf-8")
    expanded_text = _expand_env_vars(raw_text)

    if p.suffix in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(expanded_text) or {}
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(data, tmp)
            tmp_path = Path(tmp.name)
        try:
            return load_mcp_toolsets(tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        tmp.write(expanded_text)
        tmp_path = Path(tmp.name)
    try:
        return load_mcp_toolsets(tmp_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

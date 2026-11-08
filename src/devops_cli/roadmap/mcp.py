"""The MCP client toolset for roadmap stage and implement jobs (#3221).

`RoadmapMcpToolset` inherits `pydantic_ai.mcp.MCPToolset`. It connects a roadmap job to role-scoped
remote tools over streamable HTTP. It bounds each remote tool call with `roadmap.mcp.timeout_seconds`.
When a remote tool call fails or times out, it returns a tool error and records the outcome and timeout
in `RunTrace`. When a remote tool has the name of a local tool, the local tool wins and the remote
tool is omitted. When the MCP server is down at start, the job stops and raises
`RoadmapMcpUnavailableError`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Any, Final, Self

if TYPE_CHECKING:
    import mcp.types as mcp_types
from pydantic_ai import RunContext
from pydantic_ai.exceptions import AgentRunError, ModelRetry, ToolFailedError, UserError
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ToolReturn
from pydantic_ai.toolsets import ToolsetTool

from devops_cli.config.settings import (
    Settings,
    get_mcp_implement_token,
    get_mcp_stage_token,
    load_settings,
    setting_default,
)
from devops_cli.exceptions.roadmap import RoadmapMcpUnavailableError
from devops_cli.roadmap.agent_run import ToolOutcome

logger = logging.getLogger(__name__)

ROLE_PLANNING: Final[str] = "planning"
ROLE_IMPLEMENTATION: Final[str] = "implementation"


def roadmap_mcp_url(base_url: str, role: str) -> str:
    """Return the MCP endpoint URL for `role`.

    The stage job authenticates to `/planning/mcp`. The implement job authenticates to
    `/implementation/mcp`.
    """
    path = "/planning/mcp" if role == ROLE_PLANNING else "/implementation/mcp"
    cleaned = base_url.rstrip("/")
    if cleaned.endswith(path):
        return cleaned
    return f"{cleaned}{path}"


class RoadmapMcpToolset(MCPToolset):
    """An MCP toolset for roadmap jobs with timeout bounds, local tool precedence, and startup error
    handling."""

    def __init__(
        self,
        client: Any,
        *,
        local_tool_names: Collection[str] = (),
        timeout_seconds: float | None = None,
        target_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(client, **kwargs)
        self._local_tool_names = frozenset(local_tool_names)
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else float(setting_default("roadmap.mcp.timeout_seconds"))
        )
        self._target_url = target_url or (str(client) if isinstance(client, str) else "")
        self.tool_names: set[str] = set()

    async def __aenter__(self) -> Self:
        try:
            return await super().__aenter__()
        except Exception as exc:
            raise RoadmapMcpUnavailableError(self._target_url, message=str(exc)) from exc

    async def list_tools(self) -> list[mcp_types.Tool]:
        tools = await super().list_tools()
        if self._local_tool_names:
            tools = [tool for tool in tools if tool.name not in self._local_tool_names]
        self.tool_names.update(tool.name for tool in tools)
        return tools

    async def get_tools(self, ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        tools = await super().get_tools(ctx)
        if self._local_tool_names:
            tools = {k: v for k, v in tools.items() if k not in self._local_tool_names}
        self.tool_names.update(tools.keys())
        return tools

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> Any:
        self.tool_names.add(name)
        try:
            async with asyncio.timeout(self._timeout_seconds):
                raw = await super().call_tool(name, tool_args, ctx, tool)
        except TimeoutError:
            return ToolReturn(
                f"Tool '{name}' timed out after {self._timeout_seconds} seconds.",
                metadata={"outcome": ToolOutcome.ERROR, "timeout": self._timeout_seconds},
            )
        except (
            ModelRetry,
            ToolFailedError,
            UserError,
            AgentRunError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            ExceptionGroup,
        ) as exc:
            return ToolReturn(
                f"Tool '{name}' failed: {exc}",
                metadata={"outcome": ToolOutcome.ERROR, "timeout": self._timeout_seconds},
            )

        if isinstance(raw, ToolReturn):
            meta = dict(raw.metadata) if isinstance(raw.metadata, Mapping) else {}
            meta.setdefault(
                "outcome",
                ToolOutcome.OK if str(raw.return_value).strip() else ToolOutcome.EMPTY,
            )
            meta.setdefault("timeout", self._timeout_seconds)
            return ToolReturn(raw.return_value, metadata=meta)

        text = str(raw) if raw is not None else ""
        outcome = ToolOutcome.OK if text.strip() else ToolOutcome.EMPTY
        return ToolReturn(raw, metadata={"outcome": outcome, "timeout": self._timeout_seconds})


def build_roadmap_mcp_toolset(
    role: str,
    *,
    local_tool_names: Collection[str] = (),
    settings: Settings | None = None,
    client: Any | None = None,
) -> RoadmapMcpToolset | None:
    """Build the MCP toolset for a roadmap job if enabled, or None if disabled.

    `role` must be ROLE_PLANNING or ROLE_IMPLEMENTATION.
    `client` overrides the transport/client (e.g. for testing with an in-process FastMCP server).
    """
    cfg = settings or load_settings()
    enabled = cfg.roadmap.stage.mcp if role == ROLE_PLANNING else cfg.roadmap.implement.mcp
    if not enabled:
        return None

    timeout_seconds = cfg.roadmap.mcp.timeout_seconds
    if client is not None:
        return RoadmapMcpToolset(
            client,
            local_tool_names=local_tool_names,
            timeout_seconds=timeout_seconds,
            target_url=cfg.roadmap.mcp.url or getattr(client, "name", "in-process"),
        )

    base_url = cfg.roadmap.mcp.url
    if not base_url:
        raise RoadmapMcpUnavailableError("", message="Roadmap MCP server URL is not configured.")

    target_url = roadmap_mcp_url(base_url, role)
    token = get_mcp_stage_token() if role == ROLE_PLANNING else get_mcp_implement_token()
    auth = token if token else None

    return RoadmapMcpToolset(
        target_url,
        auth=auth,
        local_tool_names=local_tool_names,
        timeout_seconds=timeout_seconds,
        target_url=target_url,
    )


__all__ = [
    "ROLE_IMPLEMENTATION",
    "ROLE_PLANNING",
    "RoadmapMcpToolset",
    "build_roadmap_mcp_toolset",
    "roadmap_mcp_url",
]

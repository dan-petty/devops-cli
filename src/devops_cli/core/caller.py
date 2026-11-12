"""Who runs devops-cli: a person, or an agent tool, an MCP call or a cluster Job.

`detect_agent` reads the markers that agent tools set, `AI_AGENT` first. An MCP tool runs its
command inside `mcp_call`. Kubernetes sets `KUBERNETES_SERVICE_HOST` in every container of a pod,
so a command that runs in a cluster Job sees it. The usage-error record and the agent access level
of an infra repo read these markers. A tool that sets no marker counts as a person.
"""

from __future__ import annotations

import contextvars
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from devops_cli.config.constants import CONST_K8S_SERVICE_HOST_ENV

_KILO_MARKER: Final = "KILO"
_OTHER_TOOL: Final = "other"
# The agent tools that a caller names, each with the names that `detect_agent` or the `AI_AGENT`
# variable gives it, in lower case with `_` for `-`. A name that starts with one of them, then
# `_`, is that tool too: Claude Code sets `AI_AGENT` to `claude-code_<version>_agent`.
_AGENT_TOOLS: Final[tuple[tuple[str, str], ...]] = (
    ("claude_code", "claude_code"),
    ("cowork", "claude_code"),
    ("gemini_cli", "gemini_cli"),
    ("codex", "codex"),
    ("cursor", "cursor"),
    ("kilo", "kilo"),
    ("open_code", "opencode"),
    ("opencode", "opencode"),
    ("antigravity", "antigravity"),
    ("devops_implement", "devops_implement"),
)

_MCP_CALL: Final[contextvars.ContextVar[bool]] = contextvars.ContextVar(
    "devops_cli_mcp_call", default=False
)


@contextmanager
def mcp_call() -> Iterator[None]:
    """Mark the commands that run in the block as calls of an MCP tool."""
    token = _MCP_CALL.set(True)
    try:
        yield
    finally:
        _MCP_CALL.reset(token)


def in_mcp_call() -> bool:
    """Whether the command runs as the call of an MCP tool."""
    return _MCP_CALL.get()


def agent_tool() -> str | None:
    """The agent tool that runs devops-cli, from the markers that `detect_agent` reads, or None."""
    from detect_agent import determine_agent

    agent = determine_agent()["agent"]
    if agent is None:
        return None
    name = agent["name"].strip().lower().replace("-", "_")
    # Kilo is a fork of OpenCode: its shell sets `OPENCODE`, which `detect_agent` reads, and `KILO`.
    if name == "open_code" and os.environ.get(_KILO_MARKER):
        name = "kilo"
    return next(
        (tool for prefix, tool in _AGENT_TOOLS if name == prefix or name.startswith(f"{prefix}_")),
        _OTHER_TOOL,
    )


def runs_in_cluster() -> bool:
    """Whether the command runs in a container of a Kubernetes pod, such as a cluster Job."""
    return bool(os.environ.get(CONST_K8S_SERVICE_HOST_ENV))


def is_agent_caller() -> bool:
    """Whether an agent runs the command: an agent tool, an MCP call or a cluster Job."""
    return in_mcp_call() or runs_in_cluster() or agent_tool() is not None


__all__ = ["agent_tool", "in_mcp_call", "is_agent_caller", "mcp_call", "runs_in_cluster"]

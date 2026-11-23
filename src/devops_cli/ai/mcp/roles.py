"""The tool set of each MCP role: which tools a connection to the HTTP server may see and call.

A job role (`planning`, `implementation`, `review`) holds the tools that its table names, and only
those that the exposure table marks read-only. The `ops` role holds the whole catalogue and is
never served over the network: no job role maps to it. A tool that no table names is in no job
role, so a new tool stays out of every job until a person adds its name here.

The tables name only tools that need nothing from the files of the job. A tool that reads or
writes a path that the model gives is not named, because on the server the path is a path of the
server (#3219).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Final

from devops_cli.roadmap.tools import tool_names

ROLE_PLANNING: Final = "planning"
ROLE_IMPLEMENTATION: Final = "implementation"
ROLE_REVIEW: Final = "review"
ROLE_OPS: Final = "ops"

# The roles a job can hold, and the only roles that the HTTP server serves.
JOB_ROLES: Final[tuple[str, ...]] = (ROLE_PLANNING, ROLE_IMPLEMENTATION, ROLE_REVIEW)

# The one tool that changes which tools a caller sees. It writes process-wide state, so no role
# server holds it: the tool set of a connection is its role and nothing else.
_HYDRATE_TOOL: Final = "hydrate_tool_domain"

_JOB_ROLE_TOOLS: Final[dict[str, frozenset[str]]] = {
    role: frozenset(tool_names(role)) for role in JOB_ROLES
}


def named_job_tools() -> frozenset[str]:
    """Every tool name that a job role table holds, for the check that each one exists."""
    return frozenset().union(*_JOB_ROLE_TOOLS.values())


def _read_only(tool: Any) -> bool:
    annotations = getattr(tool, "annotations", None)
    return getattr(annotations, "read_only_hint", None) is True


def tools_for_role(role: str, tools: Iterable[Any]) -> list[Any]:
    """The tools of `tools` that `role` holds.

    A role that is not `ops` or a job role raises `ValueError`. A job role holds a tool only when
    its table names the tool and the tool is read-only, so a tool whose flag turns false leaves
    every job role. A name in a job table that no tool carries raises `ValueError`: a renamed
    tool must not leave a role silently smaller than its table.
    """
    catalogue = [tool for tool in tools if tool.name != _HYDRATE_TOOL]
    if role == ROLE_OPS:
        return catalogue
    if role not in _JOB_ROLE_TOOLS:
        raise ValueError(f"Unknown MCP role '{role}'.")
    wanted = _JOB_ROLE_TOOLS[role]
    missing = sorted(wanted - {tool.name for tool in catalogue})
    if missing:
        raise ValueError(f"The MCP role '{role}' names tools that do not exist: {missing}.")
    return [tool for tool in catalogue if tool.name in wanted and _read_only(tool)]

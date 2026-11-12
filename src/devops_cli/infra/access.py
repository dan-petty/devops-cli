"""The agent access level of an infra repo: what an agent may do on its hosts (#5120).

Each infra repo has its own level, `infra.repos[].agent_access`, and a repo with no level is at
`none`. Only a person sets a level above `none`: an agent that gives one is refused before a file
is read or written. The level stops an agent error. It is not a security boundary, because an
agent with a shell can run Ansible itself.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Final

from devops_cli.core.caller import is_agent_caller
from devops_cli.exceptions.infra import InfraAccessRefusedError
from devops_cli.lang import ERRORS
from devops_cli.models.infra import HostPlan

AGENT_ACCESS_KEY: Final[str] = "infra.repos[].agent_access"


class AgentAccess(StrEnum):
    """What an agent may do on the hosts of one infra repo. A person may do everything."""

    NONE = "none"
    PLAN = "plan"
    SAFE = "safe"
    FULL = "full"


# The levels from the lowest to the highest: each level allows what the levels below it allow.
_ORDER: Final[tuple[AgentAccess, ...]] = (
    AgentAccess.NONE,
    AgentAccess.PLAN,
    AgentAccess.SAFE,
    AgentAccess.FULL,
)


def require_agent_level(level: AgentAccess, needed: AgentAccess, *, action: str, repo: str) -> None:
    """Refuse `action` when an agent runs it on a repo at a level below `needed`. A person may
    run every action.

    Raises:
        InfraAccessRefusedError: an agent tool, an MCP call or a cluster Job runs `action` on a
            repo at a lower level.
    """
    if _ORDER.index(level) >= _ORDER.index(needed) or not is_agent_caller():
        return
    raise InfraAccessRefusedError(
        ERRORS.infra.agent_access_too_low.format(
            action=action, repo=repo, level=level.value, needed=needed.value, key=AGENT_ACCESS_KEY
        ),
        key=AGENT_ACCESS_KEY,
    )


def apply_level(hosts: Iterable[HostPlan]) -> AgentAccess:
    """The level that an agent needs to apply a plan with the plan of each host in `hosts`:
    `safe` when no host has a disruptive class or a task that check mode skipped, else `full`."""
    risky = any(host.disruptive or host.unchecked for host in hosts)
    return AgentAccess.FULL if risky else AgentAccess.SAFE


def refuse_agent_raise(level: AgentAccess | None) -> None:
    """Refuse a level above `none` when an agent gives it.

    Raises:
        InfraAccessRefusedError: an agent tool, an MCP call or a cluster Job gives `plan`, `safe`
            or `full`.
    """
    if level is None or level is AgentAccess.NONE or not is_agent_caller():
        return
    raise InfraAccessRefusedError(
        ERRORS.infra.agent_access_refused.format(level=level.value, key=AGENT_ACCESS_KEY),
        key=AGENT_ACCESS_KEY,
    )


__all__ = [
    "AGENT_ACCESS_KEY",
    "AgentAccess",
    "apply_level",
    "refuse_agent_raise",
    "require_agent_level",
]

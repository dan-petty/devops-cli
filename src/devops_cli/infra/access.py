"""The agent access level of an infra repo: what an agent may do on its hosts (#5120).

Each infra repo has its own level, `infra.repos[].agent_access`, and a repo with no level is at
`none`. Only a person sets a level above `none`: an agent that gives one is refused before a file
is read or written. The level stops an agent error. It is not a security boundary, because an
agent with a shell can run Ansible itself.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from devops_cli.core.caller import is_agent_caller
from devops_cli.exceptions.infra import InfraAccessRefusedError
from devops_cli.lang import ERRORS

AGENT_ACCESS_KEY: Final[str] = "infra.repos[].agent_access"


class AgentAccess(StrEnum):
    """What an agent may do on the hosts of one infra repo. A person may do everything."""

    NONE = "none"
    PLAN = "plan"
    SAFE = "safe"
    FULL = "full"


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


__all__ = ["AGENT_ACCESS_KEY", "AgentAccess", "refuse_agent_raise"]

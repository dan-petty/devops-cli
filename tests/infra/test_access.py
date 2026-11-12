"""The agent access level of an infra repo: what an agent may run on its hosts (#5120, #5123)."""

from __future__ import annotations

import pytest

from devops_cli.exceptions.infra import InfraAccessRefusedError
from devops_cli.infra.access import AgentAccess, require_agent_level

ACTION = "devops infra status --ping"
REPO = "example-org/infra"


@pytest.mark.parametrize("level", [AgentAccess.PLAN, AgentAccess.SAFE, AgentAccess.FULL])
def test_an_agent_at_the_level_or_above_may_run(level: AgentAccess, agent_caller: None) -> None:
    assert require_agent_level(level, AgentAccess.PLAN, action=ACTION, repo=REPO) is None


def test_an_agent_below_the_level_is_refused(agent_caller: None) -> None:
    with pytest.raises(InfraAccessRefusedError) as caught:
        require_agent_level(AgentAccess.NONE, AgentAccess.PLAN, action=ACTION, repo=REPO)

    assert caught.value.message == (
        f"An agent cannot run {ACTION} on the infra repo {REPO}: its agent access level is none, "
        f"and {ACTION} needs plan. Only a person raises the level, in the setting "
        "infra.repos[].agent_access."
    )


def test_a_person_may_run_at_every_level(person_caller: None) -> None:
    assert require_agent_level(AgentAccess.NONE, AgentAccess.FULL, action=ACTION, repo=REPO) is None

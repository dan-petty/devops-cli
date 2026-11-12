"""The environment markers that make a caller an agent, and callers with and without them.

`detect_agent` publishes its table of agent markers. devops-cli also reads `KILO`, the CI markers
and `KUBERNETES_SERVICE_HOST` (`devops_cli.core.caller`). A test that runs inside an agent tool
inherits that tool's markers, so a test of a person's call removes every marker first.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

import pytest


def _marker_names(condition: dict[str, Any]) -> set[str]:
    """The variables that one condition of the agent table of `detect_agent` reads."""
    own = {condition["name"]} if "name" in condition else set()
    return own.union(*(_marker_names(nested) for nested in condition.get("conditions", ())))


def agent_marker_names() -> set[str]:
    """Every variable that marks a caller as an agent, as CI or as a cluster Job, from the
    published agent table of `detect_agent`, and the markers that devops-cli reads besides it."""
    table = json.loads(files("detect_agent").joinpath("agents.json").read_text(encoding="utf-8"))
    names = {
        table["aiAgentVar"],
        "PI_CODING_AGENT",
        "KILO",
        "CI",
        "GITHUB_ACTIONS",
        "KUBERNETES_SERVICE_HOST",
    }
    for agent in table["agents"]:
        names |= _marker_names(agent["match"])
    names.discard("PATH")
    return names


@pytest.fixture
def person_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller with no agent, CI or cluster marker: a person."""
    for name in agent_marker_names():
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def agent_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller that an agent tool marks: `AI_AGENT` names Claude Code, and no other marker is
    set."""
    for name in agent_marker_names():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI_AGENT", "claude-code_2.1.0_agent")

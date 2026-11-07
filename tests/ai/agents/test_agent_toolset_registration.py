"""An agent absorbs the tools and the instructions of the toolsets it receives."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from devops_cli.ai.toolsets import (
    FunctionToolset,
)


def test_pydantic_agent_integration() -> None:
    """Verify PydanticAgent seamlessly absorbs and registers native toolsets."""
    from devops_cli.ai.agents.agent import PydanticAgent

    ts = FunctionToolset(instructions="Ensure topic branches follow convention.")

    @ts.tool_plain
    def check_branch(name: str) -> bool:
        return name.startswith("feat/")

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent: Any = PydanticAgent(
        client=mock_client,
        name="BranchAuditor",
        toolsets=[ts],
    )

    assert "check_branch" in agent._tools
    sys_prompt = agent._build_system_prompt_with_tools()
    assert "Ensure topic branches follow convention." in sys_prompt

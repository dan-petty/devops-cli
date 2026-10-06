"""Unit tests for Agent pinned invariants head injection and cadenced reminders."""

from __future__ import annotations

import textwrap
from typing import Any
from unittest.mock import MagicMock, patch

from devops_cli.ai.agents.agent import PydanticAgent
from devops_cli.ai.agents.memory import AgentMemory
from devops_cli.commands.ai import _stream_interactive_chat_turn
from devops_cli.config.defaults import (
    DEFAULT_CHAT_INVARIANTS,
    DEFAULT_INVARIANT_REMINDER_CHARS,
    DEFAULT_INVARIANT_REMINDER_ID,
    DEFAULT_PLAN_REMINDER_ID,
)


def test_invariants_head_every_run_and_remind_on_cadence() -> None:
    """Verify invariants lead every system prompt and reminders recur on cadence."""
    inv_a = "Never echo plaintext secrets, tokens or private keys."
    inv_b = "Never write internal hostnames or topology."
    recorded_systems: list[str] = []

    def fake_chat_messages(system: str, _messages: list[Any], enable_thinking: bool = False) -> str:
        recorded_systems.append(system)
        return "ok"

    fake_client = MagicMock()
    fake_client.chat_messages = fake_chat_messages
    fake_client.chat.return_value = "earlier turns summarized"

    mem = AgentMemory(
        session_id="inv-agent",
        max_entries=4,
        keep_recent=2,
        invariants=[inv_a, inv_b],
    )
    agent = PydanticAgent(
        client=fake_client,
        system_prompt="You are a math helper",
        memory=mem,
    )

    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        for i in range(6):
            agent.run(f"query {i}")

    assert len(recorded_systems) == 6

    # Verify head invariants on every run
    for sys in recorded_systems:
        assert (
            sys.startswith(f"## Invariants\n- {inv_a}"),
            sys.index(inv_b) < sys.index("You are a math helper"),
        ) == (True, True)

    # Invariant reminder appears on runs 3 and 6 only
    reminder_presence = [("## Invariant reminder" in sys) for sys in recorded_systems]
    assert reminder_presence == [False, False, True, False, False, True]

    # When present, ## Invariant reminder is the last ## heading
    headings_run_3 = [line for line in recorded_systems[2].splitlines() if line.startswith("## ")]
    headings_run_6 = [line for line in recorded_systems[5].splitlines() if line.startswith("## ")]
    assert (headings_run_3[-1], headings_run_6[-1]) == (
        "## Invariant reminder",
        "## Invariant reminder",
    )

    # Invariants survived summarization and are still present in head
    assert (
        bool(agent.memory.summary),
        recorded_systems[-1].startswith(f"## Invariants\n- {inv_a}"),
        inv_b in recorded_systems[-1],
    ) == (True, True, True)


def test_agent_invariants_cadence_on_context_less_paths() -> None:
    """Verify cadence advances on run_stream and streamed interactive chat turn."""
    inv = "Never echo plaintext secrets."
    recorded_stream_systems: list[str] = []

    def fake_stream(system: str, _messages: list[Any], enable_thinking: bool = False) -> Any:
        recorded_stream_systems.append(system)
        yield "ok"

    fake_client = MagicMock()
    fake_client.chat_messages_stream = fake_stream

    mem = AgentMemory(session_id="ctx-less", invariants=[inv])
    agent = PydanticAgent(client=fake_client, memory=mem)

    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        for i in range(3):
            list(agent.run_stream(f"stream prompt {i}"))

    assert len(recorded_stream_systems) == 3
    assert all(s.startswith(f"## Invariants\n- {inv}") for s in recorded_stream_systems)
    assert [("## Invariant reminder" in s) for s in recorded_stream_systems] == [
        False,
        False,
        True,
    ]

    # Counter continues across _stream_interactive_chat_turn calls
    recorded_turn_systems: list[str] = []

    def fake_chat_turn_stream(
        system: str, _messages: list[Any], enable_thinking: bool = False
    ) -> Any:
        recorded_turn_systems.append(system)
        yield "ok"

    turn_client = MagicMock(chat_messages_stream=fake_chat_turn_stream)
    with patch("devops_cli.commands.ai.get_console"):
        for i in range(3):
            _stream_interactive_chat_turn(turn_client, agent, False, f"turn prompt {i}")

    assert len(recorded_turn_systems) == 3
    assert all(s.startswith(f"## Invariants\n- {inv}") for s in recorded_turn_systems)
    # The counter was at 3 after run_stream, so turns 4, 5, 6 remind on 6 only
    assert [("## Invariant reminder" in s) for s in recorded_turn_systems] == [
        False,
        False,
        True,
    ]


def test_invariant_constants_and_formatting() -> None:
    """Verify DEFAULT_CHAT_INVARIANTS and reminder compression with example.com."""
    assert (
        DEFAULT_INVARIANT_REMINDER_ID != DEFAULT_PLAN_REMINDER_ID,
        len(DEFAULT_CHAT_INVARIANTS) == 4,
        all("\n" not in inv and 0 < len(inv) < 300 for inv in DEFAULT_CHAT_INVARIANTS),
    ) == (True, True, True)

    inv0 = DEFAULT_CHAT_INVARIANTS[0]
    assert all(term in inv0 for term in ("secrets", "tokens", "private keys", ".gitignored"))

    # An invariant longer than 120 chars containing example.com
    inv_with_example = (
        "Use example.com for all dummy test domains and endpoints rather than inventing internal "
        "hostnames or ad-hoc subdomains in tests."
    )
    assert len(inv_with_example) > 120
    assert "example.com" in inv_with_example

    expected_shortened = textwrap.shorten(
        inv_with_example, width=DEFAULT_INVARIANT_REMINDER_CHARS, placeholder="..."
    )
    assert (
        len(expected_shortened) <= DEFAULT_INVARIANT_REMINDER_CHARS,
        expected_shortened.endswith("..."),
        "example.com" in expected_shortened,
    ) == (True, True, True)

    # Verify agent reminder formatting matches textwrap.shorten on cadence
    agent = PydanticAgent(
        client=MagicMock(),
        memory=AgentMemory(invariants=[inv_with_example]),
    )
    # Turn 3 triggers cadence
    agent._invariant_reminders._turn_counter = 2
    prompt = agent._build_system_prompt_with_tools()
    assert "## Invariant reminder" in prompt
    reminder_section = prompt.split("## Invariant reminder\n")[1].strip()
    reminder_lines = [
        line.removeprefix("- ").strip() for line in reminder_section.splitlines() if line.strip()
    ]
    assert reminder_lines == [expected_shortened]


def test_agent_without_invariants_has_no_head_or_reminder() -> None:
    """Verify an agent with no invariants produces default system prompt with no reminders."""
    fake_client = MagicMock()
    fake_client.chat_messages.return_value = "ok"
    agent = PydanticAgent(
        client=fake_client,
        system_prompt="You are a helpful DevOps assistant.",
    )
    sys = agent._build_system_prompt_with_tools()
    assert (
        sys.startswith("You are a helpful DevOps assistant."),
        "## Invariants" in sys,
        "## Invariant reminder" in sys,
    ) == (True, False, False)

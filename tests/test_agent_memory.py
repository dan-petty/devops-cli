"""Unit tests for AgentMemory, auto-summarization on size threshold, and ScratchpadBuffer."""

from __future__ import annotations

from unittest.mock import MagicMock

from devops_cli.ai.agents.memory import AgentMemory, MemoryEntry
from devops_cli.ai.agents.pipeline import MultiAgentPipeline
from devops_cli.ai.agents.pydantic_agent import PydanticAgent
from devops_cli.models.ai import ScratchpadBuffer


def test_agent_memory_basic_operations() -> None:
    memory = AgentMemory(session_id="test-session", max_entries=5, max_chars=500)
    e1 = memory.add_interaction("user", "Hello world")
    assert isinstance(e1, MemoryEntry)
    assert len(memory.entries) == 1
    assert memory.total_chars == len("Hello world")
    assert memory.should_summarize() is False


def test_agent_memory_auto_summarize_extractive() -> None:
    memory = AgentMemory(session_id="test-session", max_entries=4, max_chars=100, keep_recent=2)
    for i in range(6):
        memory.add_interaction("user" if i % 2 == 0 else "assistant", f"Message payload number {i}")

    assert memory.should_summarize() is True
    summarized = memory.auto_summarize_if_needed()
    assert summarized is True
    assert len(memory.entries) == 2
    assert memory.summary != ""
    assert "Message payload number 0" in memory.summary
    assert memory.entries[0].content == "Message payload number 4"
    assert memory.entries[1].content == "Message payload number 5"


def test_agent_memory_auto_summarize_with_llm() -> None:
    mock_client = MagicMock()
    mock_client.chat.return_value = (
        "User asked for infrastructure setup and assistant generated manifests."
    )

    memory = AgentMemory(session_id="llm-mem", max_entries=3, keep_recent=1)
    memory.add_interaction("user", "Setup terraform AWS VPC")
    memory.add_interaction("assistant", "Generated main.tf and vpc.tf")
    memory.add_interaction("user", "Now add subnets")
    memory.add_interaction("assistant", "Added private and public subnets")

    assert memory.should_summarize() is True
    summarized = memory.auto_summarize_if_needed(llm_client=mock_client)
    assert summarized is True
    assert len(memory.entries) == 1
    assert "User asked for infrastructure setup" in memory.summary
    assert memory.entries[0].content == "Added private and public subnets"


def test_agent_memory_render_and_chat_messages() -> None:
    memory = AgentMemory(session_id="render-test", max_entries=10)
    memory.summary = "Prior discussion: User requested microservices architecture."
    memory.add_interaction("user", "What database should we use?")
    memory.add_interaction("assistant", "PostgreSQL is recommended.")

    rendered = memory.render_memory_context()
    assert "## Prior Interaction Context & Summary" in rendered
    assert "Prior discussion: User requested microservices" in rendered
    assert "What database should we use?" in rendered

    messages = memory.to_chat_messages(system_instruction="You are a senior architect.")
    assert len(messages) == 3
    assert messages[0].role == "system"
    assert "Prior discussion" in messages[0].content
    assert messages[1].role == "user"
    assert messages[2].role == "assistant"


def test_scratchpad_buffer_auto_summarize() -> None:
    scratchpad = ScratchpadBuffer(session_id="sp-test", max_entries=4, keep_recent=2)
    for i in range(6):
        scratchpad.add_entry(
            persona=f"agent_{i}",
            stage=f"Stage {i}",
            hypothesis=f"Hypothesis {i} analyzing security boundaries",
            notes=[f"Note {i}"],
        )

    # Adding entries automatically triggered summarization and kept entries <= max_entries
    assert len(scratchpad.entries) <= scratchpad.max_entries
    assert scratchpad.summary != ""
    assert "[AGENT_0/Stage 0]" in scratchpad.summary
    rendered = scratchpad.render_context_summary()
    assert "[ACCUMULATED SUMMARY]" in rendered


def test_pydantic_agent_with_memory() -> None:
    mock_client = MagicMock()
    mock_client.chat_messages.return_value = "Plan created successfully."

    agent = PydanticAgent(client=mock_client, name="TestAgent", system_prompt="System prompt")
    res = agent.run("Deploy to kubernetes")

    assert res.content == "Plan created successfully."
    assert len(agent.memory.entries) == 2
    assert agent.memory.entries[0].role == "user"
    assert agent.memory.entries[0].content == "Deploy to kubernetes"
    assert agent.memory.entries[1].role == "assistant"
    assert agent.memory.entries[1].content == "Plan created successfully."


def test_multi_agent_pipeline_with_memory() -> None:
    mock_client = MagicMock()
    mock_client.chat_messages.return_value = "Stage output"

    a1 = PydanticAgent(client=mock_client, name="Agent1")
    a2 = PydanticAgent(client=mock_client, name="Agent2")

    pipeline = MultiAgentPipeline(agents=[a1, a2], session_id="pip-test")
    res = pipeline.run("Analyze code")

    assert len(res.steps) == 2
    assert pipeline.memory.entries[0].role == "user"
    assert pipeline.memory.entries[1].role == "assistant"
    assert pipeline.memory.entries[1].metadata.get("agent") == "Agent1"
    assert pipeline.memory.entries[2].role == "assistant"
    assert pipeline.memory.entries[2].metadata.get("agent") == "Agent2"


def test_agent_memory_with_context_window_awareness() -> None:
    mock_client = MagicMock()
    mock_client.get_context_window.return_value = 32768

    memory = AgentMemory(session_id="ctx-aware", max_entries=50, max_chars=96000)
    for i in range(10):
        memory.add_interaction("user" if i % 2 == 0 else "assistant", "a" * 500)

    # Under 32k context window, it should not summarize
    assert memory.auto_summarize_if_needed(llm_client=mock_client) is False
    assert len(memory.entries) == 10

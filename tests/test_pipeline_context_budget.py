"""Unit and contract tests for multi-agent pipeline stage context budgeting."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.ai.agents.pipeline import MultiAgentPipeline
from devops_cli.ai.agents.pydantic_agent import PydanticAgent
from devops_cli.ai.client import LLMClient
from devops_cli.ai.context_budget import count_tokens
from devops_cli.commands.ai import app as ai_app
from devops_cli.config.constants import CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX
from devops_cli.config.defaults import DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS
from devops_cli.config.settings import Settings


def _create_fake_agent(client: LLMClient, idx: int, name: str | None = None) -> PydanticAgent[Any]:
    """Helper to instantiate a mock PydanticAgent."""
    agent_name = name or f"Agent{idx}"
    return PydanticAgent(client=client, name=agent_name, system_prompt=f"System {idx}")


def test_pipeline_stage_context_budget_default_constant_and_constructor() -> None:
    """Verify DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS is 4096 and cuts nothing for 1K replies."""
    pipe = MultiAgentPipeline[Any]()
    assert (DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS, pipe.stage_context_tokens) == (4096, 4096)

    sent_prompts: list[str] = []

    def fake_chat(_system: str, messages: list[Any], **_kwargs: Any) -> str:
        sent_prompts.append(messages[-1].content)
        return ("Finding: " + "x" * 70 + "\n") * 12  # ~960 chars (1K-char reply)

    client = MagicMock(spec=LLMClient)
    client.chat_messages.side_effect = fake_chat

    agents = [_create_fake_agent(client, i) for i in range(1, 6)]
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        pipeline = MultiAgentPipeline[Any](agents=agents)
        res = pipeline.run("Analyze workspace")

    truncated_flags = tuple(step.context_truncated for step in res.steps)
    assert (
        len(res.steps),
        truncated_flags,
    ) == (5, (False, False, False, False, False))


def test_pipeline_stage_context_budget_holds() -> None:
    """Verify 2048 budget caps carried context, preserves newest stage, and appends scratchpad once."""
    sent_prompts: list[str] = []
    stage_replies: dict[int, str] = {}

    def fake_chat(_system: str, messages: list[Any], **_kwargs: Any) -> str:
        sent_prompts.append(messages[-1].content)
        stage_num = len(sent_prompts)
        reply = f"Stage {stage_num} report:\n" + ("Finding: " + "x" * 70 + "\n") * 49
        stage_replies[stage_num] = reply
        return reply

    client = MagicMock(spec=LLMClient)
    client.chat_messages.side_effect = fake_chat

    agents = [_create_fake_agent(client, i) for i in range(1, 6)]
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        pipeline = MultiAgentPipeline[Any](agents=agents, stage_context_tokens=2048)
        res = pipeline.run("Analyze workspace")

    max_carried_tokens = max(step.context_tokens for step in res.steps)
    prompt_5 = sent_prompts[4]
    has_stage_4_verbatim = stage_replies[4] in prompt_5
    has_stage_1_verbatim = stage_replies[1] in prompt_5
    has_truncation_marker = (
        CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX in prompt_5 or "omitted, over budget" in prompt_5
    )
    scratchpad_counts = tuple(p.count("### Scratchpad Reasoning Context") for p in sent_prompts[1:])

    assert (
        max_carried_tokens <= 2048,
        has_stage_4_verbatim,
        has_stage_1_verbatim,
        has_truncation_marker,
        scratchpad_counts,
    ) == (True, True, False, True, (1, 1, 1, 1))


def test_pipeline_stage_context_budget_recorded_metrics() -> None:
    """Verify PipelineStepResult context_tokens and context_truncated across execution steps."""
    sent_prompts: list[str] = []

    def fake_chat(_system: str, messages: list[Any], **_kwargs: Any) -> str:
        sent_prompts.append(messages[-1].content)
        return ("Finding: " + "x" * 70 + "\n") * 50

    client = MagicMock(spec=LLMClient)
    client.chat_messages.side_effect = fake_chat

    agents = [_create_fake_agent(client, i) for i in range(1, 6)]
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        pipeline = MultiAgentPipeline[Any](agents=agents, stage_context_tokens=2048)
        res = pipeline.run("Analyze workspace")

    three_outputs_raw = "\n\n".join(
        f"### Stage {i} (Agent{i}) Output:\n" + (("Finding: " + "x" * 70 + "\n") * 50)
        for i in range(1, 4)
    )
    expected_step_4_truncated = count_tokens(three_outputs_raw) > 2048
    actual_truncated = tuple(step.context_truncated for step in res.steps)
    expected_truncated = (False, False, False, expected_step_4_truncated, True)

    tokens_match = [res.steps[0].context_tokens == 0]
    for i in range(1, 5):
        p = sent_prompts[i]
        start = p.find("## Pipeline Context from Previous Stages\n\n") + len(
            "## Pipeline Context from Previous Stages\n\n"
        )
        scratch = p.find("\n\n### Scratchpad Reasoning Context")
        carried_block = p[start:scratch]
        tokens_match.append(res.steps[i].context_tokens == count_tokens(carried_block))

    assert (actual_truncated, all(tokens_match)) == (expected_truncated, True)


def test_pipeline_stage_context_budget_fallback_token_counting() -> None:
    """Verify recorded metrics behavior under character-fallback tokenizer mode."""
    with patch("devops_cli.ai.context_budget._get_tiktoken_encoding", return_value=None):
        sent_prompts: list[str] = []

        def fake_chat(_system: str, messages: list[Any], **_kwargs: Any) -> str:
            sent_prompts.append(messages[-1].content)
            return ("Finding: " + "x" * 70 + "\n") * 50

        client = MagicMock(spec=LLMClient)
        client.chat_messages.side_effect = fake_chat

        agents = [_create_fake_agent(client, i) for i in range(1, 6)]
        with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
            pipeline = MultiAgentPipeline[Any](agents=agents, stage_context_tokens=2048)
            res = pipeline.run("Analyze workspace")

        three_outputs_raw = "\n\n".join(
            f"### Stage {i} (Agent{i}) Output:\n" + (("Finding: " + "x" * 70 + "\n") * 50)
            for i in range(1, 4)
        )
        expected_step_4_truncated = count_tokens(three_outputs_raw) > 2048
        actual_truncated = tuple(step.context_truncated for step in res.steps)
        expected_truncated = (False, False, False, expected_step_4_truncated, True)

        assert (
            expected_step_4_truncated,
            actual_truncated,
            max(s.context_tokens for s in res.steps) <= 2048,
        ) == (True, expected_truncated, True)


def test_pipeline_stage_context_budget_off() -> None:
    """Verify stage_context_tokens=0 carries all earlier outputs verbatim without truncation."""
    stage_replies: dict[int, str] = {}
    sent_prompts: list[str] = []

    def fake_chat(_system: str, messages: list[Any], **_kwargs: Any) -> str:
        sent_prompts.append(messages[-1].content)
        stage_num = len(sent_prompts)
        reply = f"Stage {stage_num} report:\n" + ("Finding: " + "x" * 70 + "\n") * 49
        stage_replies[stage_num] = reply
        return reply

    client = MagicMock(spec=LLMClient)
    client.chat_messages.side_effect = fake_chat

    agents = [_create_fake_agent(client, i) for i in range(1, 6)]
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        pipeline = MultiAgentPipeline[Any](agents=agents, stage_context_tokens=0)
        res = pipeline.run("Analyze workspace")

    prompt_5 = sent_prompts[4]
    all_verbatim = all(stage_replies[i] in prompt_5 for i in range(1, 5))
    truncated_flags = tuple(step.context_truncated for step in res.steps)

    assert (all_verbatim, truncated_flags) == (True, (False, False, False, False, False))


def test_pipeline_skip_rag_forwarded() -> None:
    """Verify skip_rag propagation to agent.run in sequential MultiAgentPipeline execution."""
    client = MagicMock(spec=LLMClient)
    client.chat_messages.return_value = "Stage output"

    agent1 = _create_fake_agent(client, 1)
    agent2 = _create_fake_agent(client, 2)

    with patch("devops_cli.ai.rag.investigator.investigate_rag_context") as mock_rag:
        pipeline = MultiAgentPipeline[Any](agents=[agent1, agent2])
        pipeline.run("Task", skip_rag=True)
        calls_when_skipped = mock_rag.call_count

    agent1_b = _create_fake_agent(client, 1)
    agent2_b = _create_fake_agent(client, 2)

    with patch("devops_cli.ai.rag.investigator.investigate_rag_context") as mock_rag:
        pipeline_b = MultiAgentPipeline[Any](agents=[agent1_b, agent2_b])
        pipeline_b.run("Task", skip_rag=False)
        calls_when_enabled = mock_rag.call_count

    assert (calls_when_skipped, calls_when_enabled) == (0, 2)


def test_pipeline_cli_options_and_dry_run() -> None:
    """Verify --stage-context-tokens option, --no-rag forwarding, and dry-run output."""
    runner = CliRunner()

    mock_pipeline_inst = MagicMock()
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline_inst)
    mock_result = MagicMock()
    mock_result.steps = []
    mock_result.total_turns = 0
    mock_result.all_tool_calls = []
    mock_pipeline_inst.run.return_value = mock_result

    with (
        patch("devops_cli.ai.agents.pipeline.MultiAgentPipeline", mock_pipeline_cls),
        patch("devops_cli.ai.tools.get_default_tools", return_value=[]),
        patch("devops_cli.config.settings.load_settings", return_value=Settings()),
    ):
        res = runner.invoke(
            ai_app,
            ["pipeline", "Review", "--stage-context-tokens", "512", "--no-rag"],
        )
        constructed_tokens = mock_pipeline_cls.call_args.kwargs.get("stage_context_tokens")
        run_skip_rag = mock_pipeline_inst.run.call_args.kwargs.get("skip_rag")
        assert (res.exit_code, constructed_tokens, run_skip_rag) == (0, 512, True)

    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        res_dry = runner.invoke(
            ai_app,
            ["pipeline", "Review", "--stage-context-tokens", "512"],
        )
        assert (
            res_dry.exit_code,
            "stage_context_tokens" in res_dry.output,
            "512" in res_dry.output,
        ) == (0, True, True)

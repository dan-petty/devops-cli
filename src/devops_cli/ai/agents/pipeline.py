"""Multi-agent sequential and parallel pipeline orchestrator.

Example:
    >>> from devops_cli.ai.agents.pipeline import MultiAgentPipeline
    >>> from devops_cli.ai.agents.pydantic_agent import PydanticAgent
    >>> from devops_cli.ai.client import LLMClient
    >>>
    >>> client = LLMClient()
    >>> agent = PydanticAgent(
    ...     client=client, name="DevSecOps", system_prompt="Review code security."
    ... )
    >>> pipeline = MultiAgentPipeline(agents=[agent])
    >>> result = pipeline.run("Analyze authentication logic in src/auth.py")
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from devops_cli.ai.concurrency import AbstractConcurrencyLimiter, AnyConcurrencyLimit

from devops_cli.ai.agents.agent import PydanticAgent
from devops_cli.ai.agents.memory import AgentMemory
from devops_cli.ai.agents.tools import AgentTool, Tool, ToolCall
from devops_cli.ai.analyze.outlines import _mask_sensitive_data
from devops_cli.ai.context_budget import count_tokens, truncate_to_token_limit
from devops_cli.ai.review_schema import extract_json_block
from devops_cli.config.constants import CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX
from devops_cli.config.defaults import (
    DEFAULT_AGENT_MAX_TURNS,
    DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS,
)
from devops_cli.exceptions import ValidationError
from devops_cli.models.ai import ChatMessage, ScratchpadBuffer

logger = logging.getLogger(__name__)


class PipelineStepResult(BaseModel):
    """Result of an individual agent stage in a MultiAgentPipeline."""

    agent_name: str
    content: str
    parsed_data: Any | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    thoughts: list[str] = Field(default_factory=list)
    passed_context: str = ""
    backend_info: str | None = None
    context_tokens: int = 0
    context_truncated: bool = False


class MultiAgentPipelineResult[T](BaseModel):
    """Aggregated output of a multi-agent pipeline execution."""

    final_content: str
    final_data: T | None = None
    steps: list[PipelineStepResult] = Field(default_factory=list)
    total_turns: int = 0
    all_tool_calls: list[ToolCall] = Field(default_factory=list)
    scratchpad: ScratchpadBuffer = Field(default_factory=ScratchpadBuffer)
    memory: AgentMemory = Field(default_factory=AgentMemory)


def _parse_pipeline_output[T](schema: type[T] | None, content: str) -> T | None:
    """Safely extract and validate JSON content against pipeline output schema."""
    if schema is None or not content:
        return None
    try:
        json_data = extract_json_block(content)
        if isinstance(json_data, dict):
            return cast(T, schema.model_validate(json_data))  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Failed to validate pipeline output schema: %s", exc)
    return None


def _format_omitted_stage(idx: int, name: str) -> str:
    """Format omitted stage output line when stage budget is exhausted."""
    return f"### Stage {idx} ({name}) Output: omitted, over budget"


def _reconcile_stage_budget_excess(
    allocated: dict[int, str],
    stage_outputs: list[tuple[int, str, str]],
    budget: int,
    trim_idx: int | None,
) -> str:
    """Trim excess tokens from the oldest retained stage if delimiter joins exceeded budget."""
    result = "\n\n".join(allocated[idx] for idx, _, _ in stage_outputs)
    excess = count_tokens(result) - budget
    if excess <= 0 or trim_idx is None:
        return result

    idx, name, content = next(s for s in stage_outputs if s[0] == trim_idx)
    header = f"### Stage {idx} ({name}) Output:\n"
    curr_tokens = count_tokens(allocated[trim_idx])
    new_budget = max(0, curr_tokens - count_tokens(header) - excess)
    suffix_tokens = count_tokens(CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX)
    if new_budget > suffix_tokens:
        trunc_content = truncate_to_token_limit(
            content,
            new_budget,
            suffix=CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX,
        )
        allocated[trim_idx] = f"{header}{trunc_content}"
    else:
        allocated[trim_idx] = _format_omitted_stage(idx, name)

    return "\n\n".join(allocated[idx] for idx, _, _ in stage_outputs)


def _allocate_stage_context(
    stage_outputs: list[tuple[int, str, str]],
    budget: int,
) -> str:
    """Allocate context budget newest-first, listing over-budget older stages by name only."""
    reversed_stages = list(reversed(stage_outputs))
    allocated: dict[int, str] = {}
    remaining_budget = budget
    trim_idx: int | None = None

    for i, (idx, name, content) in enumerate(reversed_stages):
        header = f"### Stage {idx} ({name}) Output:\n"
        full_block = f"{header}{content}"
        block_tokens = count_tokens(full_block)

        older_omitted_tokens = sum(
            count_tokens(_format_omitted_stage(o_idx, o_name))
            for o_idx, o_name, _ in reversed_stages[i + 1 :]
        )
        available_budget = remaining_budget - older_omitted_tokens
        header_tokens = count_tokens(header)
        suffix_tokens = count_tokens(CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX)

        if block_tokens <= available_budget:
            allocated[idx] = full_block
            remaining_budget -= block_tokens
            trim_idx = idx
        elif available_budget > header_tokens + suffix_tokens:
            content_budget = available_budget - header_tokens
            trunc_content = truncate_to_token_limit(
                content,
                content_budget,
                suffix=CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX,
            )
            trunc_block = f"{header}{trunc_content}"
            allocated[idx] = trunc_block
            remaining_budget -= count_tokens(trunc_block)
            trim_idx = idx
        else:
            omitted = _format_omitted_stage(idx, name)
            allocated[idx] = omitted
            remaining_budget -= count_tokens(omitted)

    return _reconcile_stage_budget_excess(allocated, stage_outputs, budget, trim_idx)


class MultiAgentPipeline[T]:
    """Orchestrates multi-agent stage pipelines with shared tools, memory, and handovers."""

    def __init__(
        self,
        agents: list[PydanticAgent[Any]] | None = None,
        *,
        output_schema: type[T] | None = None,
        shared_tools: list[AgentTool | Tool | Callable[..., Any]] | None = None,
        session_id: str = "pipeline-session",
        memory: AgentMemory | None = None,
        concurrency_limit: AnyConcurrencyLimit = None,
        stage_context_tokens: int = DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS,
    ) -> None:
        self.agents: list[PydanticAgent[Any]] = agents or []
        self.output_schema = output_schema
        self.shared_tools = shared_tools or []
        self.stage_context_tokens = stage_context_tokens
        self.scratchpad = ScratchpadBuffer(session_id=session_id)
        self.memory: AgentMemory = memory or AgentMemory(session_id=session_id)
        self.concurrency_limit = concurrency_limit
        if concurrency_limit is not None:
            from devops_cli.ai.concurrency import normalize_to_limiter

            self.concurrency_limiter: AbstractConcurrencyLimiter | None = normalize_to_limiter(
                concurrency_limit, name=f"pipeline:{session_id}"
            )
        else:
            self.concurrency_limiter = None
        if self.shared_tools:
            for tool in self.shared_tools:
                if not (isinstance(tool, (AgentTool, Tool)) or callable(tool)):
                    msg = f"Shared tool must be an AgentTool or callable, got {type(tool)}"
                    raise TypeError(msg)
            for agent in self.agents:
                for tool in self.shared_tools:
                    agent.add_tool(tool)

    def _build_carried_context(self, stage_outputs: list[tuple[int, str, str]]) -> tuple[str, bool]:
        """Format and budget carried stage outputs up to stage_context_tokens newest-first."""
        if not stage_outputs:
            return "", False

        full_blocks = [
            f"### Stage {idx} ({name}) Output:\n{content}" for idx, name, content in stage_outputs
        ]
        full_text = "\n\n".join(full_blocks)

        if self.stage_context_tokens <= 0:
            return full_text, False

        if count_tokens(full_text) <= self.stage_context_tokens:
            return full_text, False

        return _allocate_stage_context(stage_outputs, self.stage_context_tokens), True

    def add_agent(self, agent: PydanticAgent[Any]) -> MultiAgentPipeline[T]:
        """Append a PydanticAgent to the pipeline stage sequence."""
        if self.shared_tools:
            for tool in self.shared_tools:
                if not (isinstance(tool, (AgentTool, Tool)) or callable(tool)):
                    msg = f"Shared tool must be an AgentTool or callable, got {type(tool)}"
                    raise TypeError(msg)
                agent.add_tool(tool)
        self.agents.append(agent)
        return self

    def run(
        self,
        initial_prompt: str,
        *,
        max_turns_per_agent: int = DEFAULT_AGENT_MAX_TURNS,
        enable_thinking: bool = True,
        parallel: bool = False,
        skip_rag: bool = False,
        max_workers: int | None = None,
        message_history: list[ChatMessage] | None = None,
    ) -> MultiAgentPipelineResult[T]:
        """Run the multi-agent pipeline sequentially or in parallel, passing accumulated context forward.

        ``message_history`` replaces each agent's own memory as the conversation sent to the model;
        an empty list sends only the current prompt. ``None`` keeps each agent's memory.
        """
        if parallel:
            return self.run_parallel(
                initial_prompt,
                max_turns_per_agent=max_turns_per_agent,
                enable_thinking=enable_thinking,
                skip_rag=skip_rag,
                max_workers=max_workers,
                message_history=message_history,
            )
        if max_turns_per_agent <= 0:
            msg = f"max_turns_per_agent must be a positive integer, got {max_turns_per_agent}"
            raise ValidationError(msg, field="max_turns_per_agent")

        steps: list[PipelineStepResult] = []
        all_tool_calls: list[ToolCall] = []
        total_turns = 0
        stage_outputs: list[tuple[int, str, str]] = []

        self.memory.add_interaction("user", initial_prompt)
        self.memory.auto_summarize_if_needed()

        for idx, agent in enumerate(self.agents, 1):
            carried_block, context_truncated = self._build_carried_context(stage_outputs)
            context_tokens = count_tokens(carried_block) if carried_block else 0

            scratchpad_summary = self.scratchpad.render_context_summary()
            if carried_block or scratchpad_summary:
                context_parts: list[str] = []
                if carried_block:
                    context_parts.append(carried_block)
                if scratchpad_summary:
                    context_parts.append(scratchpad_summary)
                context_section = "\n\n".join(context_parts)
                prompt = (
                    f"## Pipeline Context from Previous Stages\n\n"
                    f"{context_section}\n\n"
                    f"## Current Stage Task ({agent.name})\n\n"
                    f"{initial_prompt}"
                )
            else:
                prompt = initial_prompt

            res = agent.run(
                prompt,
                max_turns=max_turns_per_agent,
                enable_thinking=enable_thinking,
                skip_rag=skip_rag,
                message_history=message_history,
            )

            total_turns += res.turns
            all_tool_calls.extend(res.tool_calls)

            step = PipelineStepResult(
                agent_name=agent.name,
                content=res.content,
                parsed_data=res.data,
                tool_calls=res.tool_calls,
                thoughts=res.thoughts,
                passed_context=res.content,
                backend_info=res.backend_info,
                context_tokens=context_tokens,
                context_truncated=context_truncated,
            )
            steps.append(step)

            self.memory.add_interaction("assistant", res.content, agent=agent.name)
            self.memory.auto_summarize_if_needed()

            raw_hyp = res.content[:150].replace("\n", " ") + "..."

            self.scratchpad.add_entry(
                persona=agent.name,
                stage=f"Stage {idx}",
                hypothesis=_mask_sensitive_data(raw_hyp),
                notes=[f"Executed {len(res.tool_calls)} tool calls in {res.turns} turns."],
            )

            stage_outputs.append((idx, agent.name, res.content))

        final_content = steps[-1].content if steps else ""
        parsed_data = _parse_pipeline_output(self.output_schema, final_content)

        return MultiAgentPipelineResult[T](
            final_content=final_content,
            final_data=parsed_data,
            steps=steps,
            total_turns=total_turns,
            all_tool_calls=all_tool_calls,
            scratchpad=self.scratchpad,
            memory=self.memory,
        )

    def run_parallel(
        self,
        initial_prompt: str,
        *,
        max_turns_per_agent: int = 1,
        enable_thinking: bool = False,
        skip_rag: bool = True,
        max_workers: int | None = None,
        message_history: list[ChatMessage] | None = None,
    ) -> MultiAgentPipelineResult[T]:
        """Run multi-agent pipeline stages concurrently across available worker threads."""
        if not self.agents:
            return MultiAgentPipelineResult[T](final_content="")

        from devops_cli.telemetry import ContextPropagatingThreadPoolExecutor as ThreadPoolExecutor

        workers = max_workers or min(len(self.agents), 8)

        def _execute_agent(
            agent_idx_tuple: tuple[int, PydanticAgent[Any]],
        ) -> tuple[int, PipelineStepResult, int, list[ToolCall]]:
            idx, agent = agent_idx_tuple
            res = agent.run(
                initial_prompt,
                max_turns=max_turns_per_agent,
                enable_thinking=enable_thinking,
                skip_rag=skip_rag,
                message_history=message_history,
            )
            step = PipelineStepResult(
                agent_name=agent.name,
                content=res.content,
                parsed_data=res.data,
                tool_calls=res.tool_calls,
                thoughts=res.thoughts,
                passed_context=res.content,
                backend_info=res.backend_info,
            )
            return idx, step, res.turns, res.tool_calls

        with ThreadPoolExecutor(max_workers=workers) as executor:
            raw_results = list(executor.map(_execute_agent, list(enumerate(self.agents, 1))))

        raw_results.sort(key=lambda x: x[0])
        steps = [r[1] for r in raw_results]
        total_turns = sum(r[2] for r in raw_results)
        all_tool_calls = [tc for r in raw_results for tc in r[3]]

        for r in raw_results:
            idx, step, _, _ = r
            raw_hyp = step.content[:150].replace("\n", " ") + "..."
            self.scratchpad.add_entry(
                persona=step.agent_name,
                stage=f"Stage {idx}",
                hypothesis=_mask_sensitive_data(raw_hyp),
                notes=[f"Executed {len(step.tool_calls)} tool calls."],
            )

        final_content = steps[-1].content if steps else ""
        parsed_data = _parse_pipeline_output(self.output_schema, final_content)

        return MultiAgentPipelineResult[T](
            final_content=final_content,
            final_data=parsed_data,
            steps=steps,
            total_turns=total_turns,
            all_tool_calls=all_tool_calls,
            scratchpad=self.scratchpad,
            memory=self.memory,
        )

    async def run_async(
        self,
        initial_prompt: str,
        *,
        max_turns_per_agent: int = DEFAULT_AGENT_MAX_TURNS,
        enable_thinking: bool = True,
        parallel: bool = False,
        skip_rag: bool = False,
    ) -> MultiAgentPipelineResult[T]:
        """Run the multi-agent pipeline asynchronously, sequentially or in parallel."""
        if parallel:
            return await self.run_parallel_async(
                initial_prompt,
                max_turns_per_agent=max_turns_per_agent,
                enable_thinking=enable_thinking,
                skip_rag=skip_rag,
            )
        from functools import partial

        loop = asyncio.get_running_loop()
        fn = partial(
            self.run,
            initial_prompt,
            max_turns_per_agent=max_turns_per_agent,
            enable_thinking=enable_thinking,
            parallel=False,
            skip_rag=skip_rag,
        )
        return await loop.run_in_executor(None, fn)

    async def run_parallel_async(
        self,
        initial_prompt: str,
        *,
        max_turns_per_agent: int = 1,
        enable_thinking: bool = False,
        skip_rag: bool = True,
    ) -> MultiAgentPipelineResult[T]:
        """Run multi-agent stages concurrently with native concurrency limits."""
        if not self.agents:
            return MultiAgentPipelineResult[T](final_content="")

        from devops_cli.ai.concurrency import get_concurrency_context

        async def _execute_agent(
            idx: int, agent: PydanticAgent[Any]
        ) -> tuple[int, PipelineStepResult, int, list[ToolCall]]:
            limiter = self.concurrency_limiter or getattr(agent, "_concurrency_limiter", None)
            async with get_concurrency_context(limiter, f"stage:{agent.name}"):
                res = await agent.run_async(
                    initial_prompt,
                    max_turns=max_turns_per_agent,
                    enable_thinking=enable_thinking,
                    skip_rag=skip_rag,
                )
                step = PipelineStepResult(
                    agent_name=agent.name,
                    content=res.content,
                    parsed_data=res.data,
                    tool_calls=res.tool_calls,
                    thoughts=res.thoughts,
                    passed_context=res.content,
                    backend_info=res.backend_info,
                )
                return idx, step, res.turns, res.tool_calls

        tasks = [_execute_agent(idx, agent) for idx, agent in enumerate(self.agents, 1)]
        raw_results = list(await asyncio.gather(*tasks))
        raw_results.sort(key=lambda x: x[0])
        steps = [r[1] for r in raw_results]
        total_turns = sum(r[2] for r in raw_results)
        all_tool_calls = [tc for r in raw_results for tc in r[3]]

        for r in raw_results:
            idx, step, _, _ = r
            raw_hyp = step.content[:150].replace("\n", " ") + "..."
            self.scratchpad.add_entry(
                persona=step.agent_name,
                stage=f"Stage {idx}",
                hypothesis=_mask_sensitive_data(raw_hyp),
                notes=[f"Executed {len(step.tool_calls)} tool calls."],
            )

        final_content = steps[-1].content if steps else ""
        parsed_data = _parse_pipeline_output(self.output_schema, final_content)

        return MultiAgentPipelineResult[T](
            final_content=final_content,
            final_data=parsed_data,
            steps=steps,
            total_turns=total_turns,
            all_tool_calls=all_tool_calls,
            scratchpad=self.scratchpad,
            memory=self.memory,
        )

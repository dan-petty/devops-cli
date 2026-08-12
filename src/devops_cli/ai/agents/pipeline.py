"""Multi-agent sequential and parallel pipeline orchestrator."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.agents.pydantic_agent import AgentTool, PydanticAgent, ToolCall
from devops_cli.ai.review_schema import extract_json_block
from devops_cli.config.defaults import DEFAULT_AGENT_MAX_TURNS


class PipelineStepResult(BaseModel):
    """Result of an individual agent stage in a MultiAgentPipeline."""

    agent_name: str
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    passed_context: str = ""


class MultiAgentPipelineResult[T](BaseModel):
    """Aggregated output of a multi-agent pipeline execution."""

    final_content: str
    final_data: T | None = None
    steps: list[PipelineStepResult] = Field(default_factory=list)
    total_turns: int = 0
    all_tool_calls: list[ToolCall] = Field(default_factory=list)


class MultiAgentPipeline[T]:
    """Orchestrates multi-agent stage pipelines with shared tools and handovers."""

    def __init__(
        self,
        agents: list[PydanticAgent[Any]] | None = None,
        *,
        output_schema: type[T] | None = None,
        shared_tools: list[AgentTool | Callable[..., Any]] | None = None,
    ) -> None:
        self.agents: list[PydanticAgent[Any]] = agents or []
        self.output_schema = output_schema
        self.shared_tools = shared_tools or []
        if self.shared_tools:
            for agent in self.agents:
                for tool in self.shared_tools:
                    agent.add_tool(tool)

    def add_agent(self, agent: PydanticAgent[Any]) -> MultiAgentPipeline[T]:
        """Append a PydanticAgent to the pipeline stage sequence."""
        if self.shared_tools:
            for tool in self.shared_tools:
                agent.add_tool(tool)
        self.agents.append(agent)
        return self

    def run(
        self,
        initial_prompt: str,
        *,
        max_turns_per_agent: int = DEFAULT_AGENT_MAX_TURNS,
        enable_thinking: bool = True,
    ) -> MultiAgentPipelineResult[T]:
        """Run the multi-agent pipeline sequentially, passing accumulated context forward."""
        steps: list[PipelineStepResult] = []
        all_tool_calls: list[ToolCall] = []
        total_turns = 0
        accumulated_context = ""

        for idx, agent in enumerate(self.agents, 1):
            prompt = initial_prompt
            if accumulated_context:
                prompt = (
                    f"## Pipeline Context from Previous Stages\n\n"
                    f"{accumulated_context}\n\n"
                    f"## Current Stage Task ({agent.name})\n\n"
                    f"{initial_prompt}"
                )

            res = agent.run(
                prompt,
                max_turns=max_turns_per_agent,
                enable_thinking=enable_thinking,
            )

            total_turns += res.turns
            all_tool_calls.extend(res.tool_calls)

            step = PipelineStepResult(
                agent_name=agent.name,
                content=res.content,
                tool_calls=res.tool_calls,
                passed_context=res.content,
            )
            steps.append(step)

            accumulated_context += f"\n### Stage {idx} ({agent.name}) Output:\n{res.content}\n"

        final_content = steps[-1].content if steps else ""
        parsed_data: T | None = None

        if self.output_schema is not None and final_content:
            try:
                json_data = extract_json_block(final_content)
                if isinstance(json_data, dict):
                    parsed_data = self.output_schema.model_validate(json_data)  # type: ignore[attr-defined]
            except Exception:
                pass

        return MultiAgentPipelineResult[T](
            final_content=final_content,
            final_data=parsed_data,
            steps=steps,
            total_turns=total_turns,
            all_tool_calls=all_tool_calls,
        )

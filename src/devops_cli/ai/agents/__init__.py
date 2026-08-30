"""Multi-agent orchestrator, memory management, and structured Pydantic agent models."""

from __future__ import annotations

from devops_cli.ai.agents.memory import AgentMemory, MemoryEntry
from devops_cli.ai.agents.pipeline import (
    MultiAgentPipeline,
    MultiAgentPipelineResult,
    PipelineStepResult,
)
from devops_cli.ai.agents.pydantic_agent import (
    AgentHooks,
    AgentResponse,
    AgentRetries,
    AgentSpec,
    AgentStepNode,
    AgentTool,
    AgentUsage,
    BaseCapability,
    Capability,
    FunctionToolset,
    PydanticAgent,
    RunContext,
    TemplateStr,
    Tool,
    ToolCall,
    ToolReturn,
)

__all__ = [
    "AgentHooks",
    "AgentMemory",
    "AgentResponse",
    "AgentRetries",
    "AgentSpec",
    "AgentStepNode",
    "AgentTool",
    "AgentUsage",
    "BaseCapability",
    "Capability",
    "FunctionToolset",
    "MemoryEntry",
    "MultiAgentPipeline",
    "MultiAgentPipelineResult",
    "PipelineStepResult",
    "PydanticAgent",
    "RunContext",
    "TemplateStr",
    "Tool",
    "ToolCall",
    "ToolReturn",
]

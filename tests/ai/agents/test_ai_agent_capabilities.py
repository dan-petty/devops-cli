"""Unit tests for agent tools, custom toolsets, embedding cost and the model override."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.agents.tools import Tool

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_agent_tool_args_validator() -> None:
    """Verify args_validator_func supports pre-execution argument validation and transformation."""
    from devops_cli.ai.agents.tools import FunctionToolset

    def sample_tool(ctx: Any, target: str, count: int) -> str:
        return f"{target}:{count}"

    def validator(args: dict[str, Any]) -> dict[str, Any]:
        # Transform target to uppercase and clamp count to positive
        args["target"] = str(args.get("target", "")).upper()
        args["count"] = max(1, int(args.get("count", 1)))
        return args

    tool = Tool.from_function(sample_tool, args_validator_func=validator)
    validated = tool.validate_args({"target": "production", "count": -5})
    assert validated["target"] == "PRODUCTION"
    assert validated["count"] == 1

    # Via FunctionToolset decorator
    toolset = FunctionToolset()

    @toolset.tool(args_validator_func=validator)
    def decorated_tool(ctx: Any, target: str, count: int) -> str:
        return f"{target}:{count}"

    registered_tool = toolset.get_tools()[0]
    assert isinstance(registered_tool, Tool)
    res = registered_tool.validate_args({"target": "staging", "count": 0})
    assert res["target"] == "STAGING"
    assert res["count"] == 1


def test_abstract_custom_toolset() -> None:
    """Verify custom AbstractToolset subclasses produce configured tools."""
    from devops_cli.ai.agents.tools import AbstractToolset, AgentTool

    class DynamicMetricToolset(AbstractToolset):
        prefix: str = "metric_"

        def get_tools(self) -> list[AgentTool]:
            def fetch_cpu() -> str:
                return "cpu: 45%"

            return [Tool.from_function(fetch_cpu, name=f"{self.prefix}cpu")]

        def get_instructions(self, ctx: Any = None) -> list[str]:
            return ["Query metrics using the metric_ prefix tools."]

    ts = DynamicMetricToolset(prefix="k8s_")
    tools = ts.get_tools()
    assert len(tools) == 1
    assert tools[0].name == "k8s_cpu"
    assert ts.get_instructions() == ["Query metrics using the metric_ prefix tools."]


def test_embedding_cost_of_a_local_model_is_zero_whatever_its_custom_price(tmp_path: Path) -> None:
    """A local embedding model costs nothing, also when a custom price names it, because its
    tokens count in local savings (#1631)."""
    from datetime import UTC, datetime

    from pydantic_ai.usage import RequestUsage

    from devops_cli.ai.rag.embeddings import EmbeddingCost, EmbeddingResult
    from devops_cli.ai.spend.pricing import get_pricing_registry

    pricing = get_pricing_registry(data_dir=tmp_path)
    result = EmbeddingResult(
        embeddings=[[0.1, 0.2]],
        inputs=["test text"],
        model_name="local-embed",
        provider_name="ollama",
        usage=RequestUsage(input_tokens=100_000),
        timestamp=datetime(2026, 10, 11, 12, 0, 0, tzinfo=UTC),
    )
    unpriced_cost = result.cost()
    pricing.set_custom_pricing("local-embed", 1.5, 0.0)
    custom_priced_cost = result.cost()

    assert (unpriced_cost, custom_priced_cost) == (
        EmbeddingCost(total_price=0.0),
        EmbeddingCost(total_price=0.0),
    )


def test_agent_override_swaps_the_model(model_fake: ModelFake) -> None:
    """`Agent.override` answers from the given model for its block."""
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    agent: Agent[None, str] = Agent(TestModel(custom_output_text="Initial Model Response"))

    model_fake.answer("Mocked Agent Response")
    with agent.override(model=model_fake):
        res = agent.run_sync("What is the k8s status?")
    assert res.output == "Mocked Agent Response"

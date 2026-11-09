"""Unit tests for SystemReminders, custom capabilities, toolsets, embeddings and testing utilities."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.agents.capabilities import (
    BaseCapability,
    SystemReminders,
)
from devops_cli.ai.agents.context import RunContext
from devops_cli.ai.agents.tools import Tool

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_system_reminders_cadence_and_condition() -> None:
    """Verify SystemReminders cadence and custom condition predicates."""
    # 1. Cadence-based reminder (every 2 turns)
    sr_cadence = SystemReminders(
        reminders=["Follow PEP 8 strictly", "Output JSON format only"],
        cadence=2,
    )

    ctx = RunContext()
    assert sr_cadence.should_remind(ctx, 1) is False
    assert sr_cadence.get_reminders(ctx, 1) == []

    assert sr_cadence.should_remind(ctx, 2) is True
    assert sr_cadence.get_reminders(ctx, 2) == ["Follow PEP 8 strictly", "Output JSON format only"]

    assert sr_cadence.should_remind(ctx, 3) is False
    assert sr_cadence.should_remind(ctx, 4) is True

    # 2. Condition-based reminder
    def custom_cond(c: RunContext[Any], turn: int) -> bool:
        return c.session_id == "strict_mode"

    sr_cond = SystemReminders(
        reminders=["Strict security check required"],
        condition=custom_cond,
    )

    assert sr_cond.should_remind(RunContext(session_id="normal"), 1) is False
    assert sr_cond.should_remind(RunContext(session_id="strict_mode"), 1) is True
    assert sr_cond.get_reminders(RunContext(session_id="strict_mode"), 1) == [
        "Strict security check required"
    ]

    # 3. get_system_prompt_additions turn accumulation
    sr_auto = SystemReminders(reminders=["Turn reminder"], cadence=1)
    prompts1 = sr_auto.get_system_prompt_additions(ctx)
    assert prompts1 == ["Turn reminder"]


def test_custom_capability_creation() -> None:
    """Verify creating a custom capability by subclassing BaseCapability."""

    class SecurityContextCapability(BaseCapability):
        id: str = "security_context"
        audit_mode: bool = True

        def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
            return [f"Audit mode: {self.audit_mode}"]

        def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
            return {"temperature": 0.0}

        def get_tools(self) -> list[Any]:
            return [Tool.from_function(lambda: "ok", name="audit_ping")]

    sec_cap = SecurityContextCapability(audit_mode=True)
    assert sec_cap.id == "security_context"
    assert sec_cap.get_system_prompt_additions(RunContext()) == ["Audit mode: True"]
    assert sec_cap.get_model_settings(RunContext()) == {"temperature": 0.0}
    assert len(sec_cap.get_tools()) == 1


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


@pytest.mark.anyio
async def test_embedder_and_embedding_result() -> None:
    """Verify Embedder interface and EmbeddingResult container indexing and cost calculation."""
    from unittest.mock import MagicMock

    from devops_cli.ai.rag.embeddings import Embedder, EmbeddingResult

    mock_engine = MagicMock()
    mock_engine.embed_query.return_value = [0.1, 0.2, 0.3, 0.4]
    mock_engine.embed_texts.side_effect = lambda texts, is_query=False: [
        [0.1 * (i + 1), 0.2, 0.3, 0.4] for i in range(len(texts))
    ]

    embedder = Embedder(model="openai:text-embedding-3-small", engine=mock_engine)

    # 1. Async Query Embedding
    res_query = await embedder.embed_query("What is Kubernetes?")
    assert isinstance(res_query, EmbeddingResult)
    assert len(res_query) == 1
    assert res_query[0] == [0.1, 0.2, 0.3, 0.4]
    assert res_query["What is Kubernetes?"] == [0.1, 0.2, 0.3, 0.4]
    # The engine sent no request, so no provider counted a token and none is estimated.
    assert res_query.usage.input_tokens == 0
    cost = res_query.cost()
    assert cost.total_price >= 0.0

    # 2. Async Documents Embedding
    docs = ["Doc 1 content", "Doc 2 content"]
    res_docs = await embedder.embed_documents(docs)
    assert len(res_docs) == 2
    assert res_docs[0] == [0.1, 0.2, 0.3, 0.4]
    assert res_docs[1] == [0.2, 0.2, 0.3, 0.4]
    assert res_docs["Doc 1 content"] == [0.1, 0.2, 0.3, 0.4]
    assert res_docs["Doc 2 content"] == [0.2, 0.2, 0.3, 0.4]

    # 3. Key error on missing text
    with pytest.raises(KeyError, match="not found in embedding result inputs"):
        _ = res_docs["Missing doc"]

    with pytest.raises(TypeError, match="indices must be integers or strings"):
        _ = res_docs[1.5]  # type: ignore[index]

    # 4. Sync methods
    res_sync = embedder.embed_query_sync("Sync test")
    assert len(res_sync) == 1
    assert res_sync[0] == [0.1, 0.2, 0.3, 0.4]

    docs_sync = embedder.embed_documents_sync(["Sync doc"])
    assert len(docs_sync) == 1
    assert docs_sync[0] == [0.1, 0.2, 0.3, 0.4]

    # 5. Default engine initialization and dimension control
    local_embedder = Embedder(model="ollama:all-minilm", dimensions=384)
    engine = local_embedder._get_engine()
    assert engine._dimension == 384

    # 6. Pydantic AI TestEmbeddingModel and EmbeddingSettings integration
    from pydantic_ai.embeddings import EmbeddingSettings, TestEmbeddingModel

    test_embedder = Embedder(TestEmbeddingModel(), settings=EmbeddingSettings())
    res_test = test_embedder.embed_query_sync("Test query")
    assert isinstance(res_test, EmbeddingResult)
    assert len(res_test) == 1
    assert len(res_test[0]) > 0
    assert res_test["Test query"] == res_test[0]


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

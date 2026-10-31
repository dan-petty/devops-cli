"""Unit tests for SystemReminders, custom capabilities, toolsets, embeddings and testing utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.agents.capabilities import (
    BaseCapability,
    SystemReminders,
)
from devops_cli.ai.agents.context import RunContext
from devops_cli.ai.agents.tools import Tool

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
    """Verify custom AbstractToolset subclasses integrate with PydanticAgent."""
    from devops_cli.ai.agents.agent import PydanticAgent
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

    agent = PydanticAgent(toolsets=[ts])
    assert "k8s_cpu" in agent._tools


@pytest.mark.anyio
async def test_mcp_toolset() -> None:
    """Verify MCPToolset lifecycle, tool registration, prefixing and config loading."""
    from devops_cli.ai.agents.agent import PydanticAgent
    from devops_cli.ai.agents.testing import TestModel
    from devops_cli.ai.agents.tools import AgentTool, MCPToolset

    # 1. MCPToolset instantiation and lifecycle
    tool1 = AgentTool(
        name="mcp_query", description="Query remote MCP", func=lambda q: f"Result: {q}"
    )
    mcp_ts = MCPToolset(url="https://example.com/api", tools=[tool1])

    assert len(mcp_ts.get_tools()) == 1
    assert mcp_ts.get_tools()[0].name == "mcp_query"
    instructions = mcp_ts.get_instructions()
    assert len(instructions) == 1
    assert "https://example.com/api" in instructions[0]

    # Context manager lifecycle
    async with mcp_ts as ts:
        assert len(ts.get_tools()) == 1

    # 2. Tool prefixing and from_config loading
    mcp_prefix = MCPToolset(
        "https://example.com/api",
        tool_prefix="slack",
        tools=[tool1],
    )
    prefixed_tools = mcp_prefix.get_tools()
    assert len(prefixed_tools) == 1
    assert prefixed_tools[0].name == "slack_mcp_query"

    config = {
        "mcpServers": {
            "github": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]},
            "fetch": {"url": "http://localhost:8000/sse"},
        }
    }
    loaded = MCPToolset.from_config(config)
    assert len(loaded) == 2
    assert loaded[0].tool_prefix == "github"
    assert loaded[1].url == "http://localhost:8000/sse"

    # 3. End-to-end execution with agent and async context manager
    agent = PydanticAgent(name="MCPAgent", model="openai:gpt-4o", toolsets=[mcp_ts])
    async with agent:
        with agent.override(model=TestModel(custom_output_text="MCP processed")):
            res = agent.run("Run mcp tool")
            assert res.content == "MCP processed"


@pytest.mark.anyio
async def test_embedder_and_embedding_result() -> None:
    """Verify Embedder interface and EmbeddingResult container indexing and cost calculation."""
    from unittest.mock import MagicMock

    from devops_cli.ai.agents.embeddings import Embedder, EmbeddingResult

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
    from pydantic_ai.embeddings import TestEmbeddingModel

    from devops_cli.ai.agents.embeddings import EmbeddingSettings

    test_embedder = Embedder(TestEmbeddingModel(), settings=EmbeddingSettings())
    res_test = test_embedder.embed_query_sync("Test query")
    assert isinstance(res_test, EmbeddingResult)
    assert len(res_test) == 1
    assert len(res_test[0]) > 0
    assert res_test["Test query"] == res_test[0]


def test_embedding_cost_of_a_local_model_is_zero_whatever_its_custom_price(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A local embedding model costs nothing, also when a custom price names it, because its
    tokens count in local savings (#1631). Provider and timestamp reach the registry."""
    from datetime import UTC, datetime

    from pydantic_ai.usage import RequestUsage

    from devops_cli.ai.agents.embeddings import EmbeddingCost, EmbeddingResult
    from devops_cli.ai.spend.pricing import PricingRegistry, RequestCost

    pricing = PricingRegistry(data_dir=tmp_path)
    priced_requests: list[dict[str, Any]] = []
    price_request = pricing.calculate_request_cost

    def record_request(
        model: str, prompt_tokens: int, completion_tokens: int, **context: Any
    ) -> RequestCost:
        priced_requests.append(
            {
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                **context,
            }
        )
        return price_request(model, prompt_tokens, completion_tokens, **context)

    monkeypatch.setattr(pricing, "calculate_request_cost", record_request)
    monkeypatch.setattr("devops_cli.ai.spend.get_pricing_registry", lambda: pricing)

    request_timestamp = datetime(2026, 10, 11, 12, 0, 0, tzinfo=UTC)
    result = EmbeddingResult(
        embeddings=[[0.1, 0.2]],
        inputs=["test text"],
        model_name="local-embed",
        provider_name="ollama",
        usage=RequestUsage(input_tokens=100_000),
        timestamp=request_timestamp,
    )
    unpriced_cost = result.cost()
    pricing.set_custom_pricing("local-embed", 1.5, 0.0)
    custom_priced_cost = result.cost()

    request = {
        "model": "local-embed",
        "prompt_tokens": 100_000,
        "completion_tokens": 0,
        "provider": "ollama",
        "request_timestamp": request_timestamp,
    }
    assert (unpriced_cost, custom_priced_cost, priced_requests) == (
        EmbeddingCost(total_price=0.0),
        EmbeddingCost(total_price=0.0),
        [request, request],
    )


def test_testing_utilities_and_agent_override() -> None:
    """Verify TestModel, FunctionModel, Agent.override, capture_run_messages, and ALLOW_MODEL_REQUESTS."""
    import json

    import devops_cli.ai.agents.testing as testing_module
    from devops_cli.ai.agents.agent import PydanticAgent
    from devops_cli.ai.agents.testing import (
        AgentInfo,
        FunctionModel,
        ModelNotAllowedError,
        TestModel,
        capture_run_messages,
    )
    from devops_cli.ai.agents.tools import FunctionToolset

    # 1. TestModel custom outputs
    tm1 = TestModel(custom_output_text="Custom Output")
    assert tm1.chat("hello") == "Custom Output"
    assert tm1.chat_messages([]) == "Custom Output"

    tm2 = TestModel(custom_output_args={"status": "passed", "code": 0})
    assert json.loads(tm2.chat("hello")) == {"status": "passed", "code": 0}

    # 2. FunctionModel custom callbacks
    def custom_fn(msgs: Any, info: AgentInfo) -> str:
        return f"Echo from {info.agent_name}"

    fm = FunctionModel(function=custom_fn)
    assert fm.chat([], agent_name="CustomAgent") == "Echo from CustomAgent"

    def custom_dict_fn(msgs: Any, info: AgentInfo) -> dict[str, Any]:
        return {"handled": True}

    fm_dict = FunctionModel(function=custom_dict_fn)
    assert json.loads(fm_dict.chat([])) == {"handled": True}

    # 3. capture_run_messages context manager and Agent.override
    agent = PydanticAgent(name="TestAssistant", model="openai:gpt-4o")

    # With override using TestModel
    with capture_run_messages() as captured:
        with agent.override(model=TestModel(custom_output_text="Mocked Agent Response")):
            res = agent.run("What is the k8s status?")
            assert res.content == "Mocked Agent Response"
    assert len(captured) > 0

    # 4. Agent.override with toolsets
    ts = FunctionToolset()

    @ts.tool_plain()
    def custom_tool(x: int) -> int:
        return x * 2

    with agent.override(toolsets=[ts]):
        assert "custom_tool" in agent._tools
    assert "custom_tool" not in agent._tools

    # 5. ALLOW_MODEL_REQUESTS enforcement
    orig_allow = testing_module.ALLOW_MODEL_REQUESTS
    try:
        testing_module.ALLOW_MODEL_REQUESTS = False
        import devops_cli.ai.agents.agent as agent_module

        agent_module.ALLOW_MODEL_REQUESTS = False

        # Real model request fails
        real_agent = PydanticAgent(name="RealAgent", model="openai:gpt-4o")
        with pytest.raises(ModelNotAllowedError) as raised:
            real_agent.run("Test query")
        assert raised.value.error_code == "MODEL_REQUESTS_DISABLED"

        # TestModel succeeds even when ALLOW_MODEL_REQUESTS is False
        with real_agent.override(model=TestModel(custom_output_text="Safe test")):
            safe_res = real_agent.run("Test query")
            assert safe_res.content == "Safe test"
    finally:
        testing_module.ALLOW_MODEL_REQUESTS = orig_allow
        agent_module.ALLOW_MODEL_REQUESTS = orig_allow

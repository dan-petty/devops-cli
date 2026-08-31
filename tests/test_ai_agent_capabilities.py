"""Unit tests for Pydantic AI SystemReminders, Instrumentation, and custom capability creation."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.ai.agents import (
    BaseCapability,
    Capability,
    Instrumentation,
    RunContext,
    SystemReminders,
    Tool,
)


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


def test_instrumentation_capability() -> None:
    """Verify Instrumentation capability attributes and lifecycle hooks."""
    inst = Instrumentation(tracer_name="custom_tracer", record_spans=True, record_metrics=True)
    assert inst.tracer_name == "custom_tracer"
    assert inst.record_spans is True
    assert inst.record_metrics is True

    hooks = inst.get_hooks()
    assert hooks is not None
    assert len(hooks.before_tool_execute) > 0
    assert len(hooks.after_tool_execute) > 0

    ctx = RunContext()
    hooks.before_tool_execute[0](ctx, "tool_a", {"arg1": "val1"})
    hooks.after_tool_execute[0](ctx, "tool_a", "result1")


def test_custom_capability_creation() -> None:
    """Verify creating custom capabilities using BaseCapability and Capability subclassing."""
    # 1. Using concrete Capability with tool decorator
    cap = Capability(instructions="Use custom helper tools.")

    @cap.tool
    def helper_tool(x: int) -> int:
        """Double an integer."""
        return x * 2

    tools = cap.get_tools()
    assert len(tools) == 1
    assert callable(tools[0])

    prompts = cap.get_system_prompt_additions(RunContext())
    assert prompts == ["Use custom helper tools."]

    # 2. Subclassing BaseCapability directly
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


def test_use_thread_executor_capability() -> None:
    """Verify UseThreadExecutor and ThreadExecutor synchronous execution."""
    from concurrent.futures import ThreadPoolExecutor

    from devops_cli.ai.agents import ThreadExecutor, UseThreadExecutor

    # 1. Default initialization
    cap = UseThreadExecutor(max_workers=4, thread_name_prefix="test-worker")
    assert cap.id == "use_thread_executor"

    def sync_compute(a: int, b: int) -> int:
        return a * b + 10

    result = cap.run_sync(sync_compute, 5, 6)
    assert result == 40

    # 2. Custom external ThreadPoolExecutor
    custom_executor = ThreadPoolExecutor(max_workers=2)
    cap_custom = ThreadExecutor(executor=custom_executor)

    def fetch_data(name: str) -> str:
        return f"payload_{name}"

    res = cap_custom.run_sync(fetch_data, name="test")
    assert res == "payload_test"
    custom_executor.shutdown()


def test_select_model_capability() -> None:
    """Verify SelectModel dynamic runtime model selection."""
    from devops_cli.ai.agents import ModelSelectionContext, RunContext, SelectModel

    def model_selector(ctx: ModelSelectionContext[dict[str, Any]]) -> str:
        deps = ctx.deps or {}
        if deps.get("task_complexity") == "complex":
            return "openai:gpt-4o"
        return "openai:gpt-4o-mini"

    cap = SelectModel(model_selector)
    assert cap.id == "select_model"

    # 1. Standard model selection context
    ctx_simple = ModelSelectionContext(deps={"task_complexity": "simple"})
    assert cap.select_model(ctx_simple) == "openai:gpt-4o-mini"

    ctx_complex = ModelSelectionContext(deps={"task_complexity": "complex"})
    assert cap.select_model(ctx_complex) == "openai:gpt-4o"

    # 2. RunContext interoperability
    run_ctx = RunContext(deps={"task_complexity": "complex"}, session_id="s1")
    assert cap.select_model(run_ctx) == "openai:gpt-4o"


def test_resolve_model_id_capability() -> None:
    """Verify ResolveModelId custom alias and tenant-specific model resolution."""
    from devops_cli.ai.agents import ModelResolutionContext, ResolveModelId, RunContext

    def custom_resolver(ctx: ModelResolutionContext[dict[str, Any]], model_id: str) -> str | None:
        if model_id.startswith("tenant:"):
            tenant = (ctx.deps or {}).get("tenant", "default")
            return f"openai:{tenant}-{model_id.removeprefix('tenant:')}"
        if model_id == "alias:fast":
            return "openai:gpt-4o-mini"
        if model_id == "alias:reasoning":
            return "openai:o1"
        return None

    resolver_cap = ResolveModelId(custom_resolver)
    assert resolver_cap.id == "resolve_model_id"

    # 1. Alias mapping
    assert resolver_cap.resolve("alias:fast") == "openai:gpt-4o-mini"
    assert resolver_cap.resolve("alias:reasoning") == "openai:o1"

    # 2. Unknown passes through as None
    assert resolver_cap.resolve("openai:gpt-4o") is None

    # 3. Tenant resolution via context
    ctx = ModelResolutionContext(deps={"tenant": "acme"}, model_id="tenant:prod-model")
    assert resolver_cap.resolve("tenant:prod-model", ctx) == "openai:acme-prod-model"

    # 4. RunContext adapter
    run_ctx = RunContext(deps={"tenant": "globex"}, model="tenant:staging-model")
    assert resolver_cap.resolve("tenant:staging-model", run_ctx) == "openai:globex-staging-model"


def test_prepare_tools_capability() -> None:
    """Verify PrepareTools dynamic filtering and modification of tool definitions."""
    from devops_cli.ai.agents import PrepareTools, RunContext, Tool

    def filter_admin_tools(ctx: RunContext[dict[str, Any]], tools: list[Any]) -> list[Any]:
        is_admin = (ctx.deps or {}).get("is_admin", False)
        if not is_admin:
            return [t for t in tools if not getattr(t, "name", "").startswith("admin_")]
        return tools

    cap = PrepareTools(filter_admin_tools)
    assert cap.id == "prepare_tools"

    t_read = Tool.from_function(lambda: "read", name="read_data")
    t_admin = Tool.from_function(lambda: "admin", name="admin_delete")
    all_tools = [t_read, t_admin]

    # 1. Non-admin context filters out admin_delete
    user_ctx = RunContext(deps={"is_admin": False})
    filtered = cap.prepare_tools(user_ctx, all_tools)
    assert len(filtered) == 1
    assert filtered[0].name == "read_data"

    # 2. Admin context keeps all tools
    admin_ctx = RunContext(deps={"is_admin": True})
    allowed = cap.prepare_tools(admin_ctx, all_tools)
    assert len(allowed) == 2
    assert {t.name for t in allowed} == {"read_data", "admin_delete"}


def test_prefix_tools_capability() -> None:
    """Verify PrefixTools namespacing capability and .prefix_tools() convenience method."""
    from devops_cli.ai.agents import Capability, PrefixTools

    cap = Capability()

    @cap.tool
    def search_query(q: str) -> str:
        """Search query."""
        return f"result for {q}"

    @cap.tool
    def list_items() -> list[str]:
        """List items."""
        return ["item1", "item2"]

    # 1. Using PrefixTools class constructor
    prefixed_cap = PrefixTools(cap, prefix="api1")
    assert prefixed_cap.id == "prefix_tools"
    prefixed_tools = prefixed_cap.get_tools()
    assert len(prefixed_tools) == 2
    names = {getattr(t, "name", "") for t in prefixed_tools}
    assert names == {"api1_search_query", "api1_list_items"}

    # 2. Using .prefix_tools() method on BaseCapability
    method_prefixed = cap.prefix_tools("v2")
    assert isinstance(method_prefixed, PrefixTools)
    assert method_prefixed.prefix == "v2"
    tools_v2 = method_prefixed.get_tools()
    assert {getattr(t, "name", "") for t in tools_v2} == {"v2_search_query", "v2_list_items"}


def test_include_tool_return_schemas_capability() -> None:
    """Verify IncludeToolReturnSchemas capability applying schema inclusion flag."""
    from devops_cli.ai.agents import IncludeToolReturnSchemas, RunContext, Tool

    cap = IncludeToolReturnSchemas(include_return_schema=True)
    assert cap.id == "include_tool_return_schemas"
    assert cap.include_return_schema is True

    tool_a = Tool.from_function(lambda x: x + 1, name="inc")
    tool_b = Tool.from_function(lambda y: f"val={y}", name="fmt")

    prepared = cap.prepare_tools(RunContext(), [tool_a, tool_b])
    assert len(prepared) == 2
    assert all(getattr(t, "include_return_schema", False) is True for t in prepared)


def test_set_tool_metadata_capability() -> None:
    """Verify SetToolMetadata capability attaching custom tags/attributes to tools."""
    from devops_cli.ai.agents import Capability, RunContext, SetToolMetadata, Tool

    cap = Capability()

    @cap.tool
    def fetch_data(key: str) -> str:
        """Fetch data."""
        return f"val:{key}"

    # 1. Using SetToolMetadata class constructor
    meta_cap = SetToolMetadata({"tier": "premium", "read_only": True}, capability=cap)
    assert meta_cap.id == "set_tool_metadata"
    tools = meta_cap.get_tools()
    assert len(tools) == 1
    assert tools[0].metadata == {"tier": "premium", "read_only": True}

    # 2. Using .with_metadata() convenience method on BaseCapability
    tagged_cap = cap.with_metadata(source="db", cache_ttl=300)
    assert isinstance(tagged_cap, SetToolMetadata)
    tagged_tools = tagged_cap.get_tools()
    assert tagged_tools[0].metadata == {"source": "db", "cache_ttl": 300}

    # 3. Dynamic prepare_tools runtime metadata injection
    runtime_tool = Tool.from_function(lambda: 42, name="num", metadata={"initial": True})
    prepared = meta_cap.prepare_tools(RunContext(), [runtime_tool])
    assert prepared[0].metadata["initial"] is True
    assert prepared[0].metadata["tier"] == "premium"


def test_raise_content_filter_error_capability() -> None:
    """Verify RaiseContentFilterError capability detecting content safety block finish reasons."""
    from devops_cli.ai.agents import RaiseContentFilterError
    from devops_cli.exceptions.ai import ContentFilterError

    cap = RaiseContentFilterError()
    assert cap.id == "raise_content_filter_error"

    # 1. Normal finish reasons pass without raising
    cap.check_response({"finish_reason": "stop", "text": "Hello world"})
    cap.check_response({"finish_reason": "length", "text": "Truncated"})

    # 2. content_filter triggers ContentFilterError with body inspection
    response_blocked = {
        "finish_reason": "content_filter",
        "text": "I cannot fulfill this request.",
        "safety_ratings": [{"category": "HATE_SPEECH", "probability": "HIGH"}],
    }
    with pytest.raises(ContentFilterError) as exc_info:
        cap.check_response(response_blocked)

    assert exc_info.value.error_code == "CONTENT_FILTER_TRIGGERED"
    assert exc_info.value.body == response_blocked


def test_reinject_system_prompt_capability() -> None:
    """Verify ReinjectSystemPrompt capability ensuring agent system prompt presence."""
    from devops_cli.ai.agents import ReinjectSystemPrompt

    cap = ReinjectSystemPrompt()
    assert cap.id == "reinject_system_prompt"
    assert cap.replace_existing is False

    # 1. Missing system prompt gets prepended
    user_msgs = [{"role": "user", "content": "What is Python?"}]
    injected = cap.reinject(user_msgs, "You are a senior DevOps architect.")
    assert len(injected) == 2
    assert injected[0]["role"] == "system"
    assert injected[0]["content"] == "You are a senior DevOps architect."

    # 2. Existing system prompt preserved by default
    existing_msgs = [
        {"role": "system", "content": "Initial prompt"},
        {"role": "user", "content": "hello"},
    ]
    preserved = cap.reinject(existing_msgs, "New prompt")
    assert len(preserved) == 2
    assert preserved[0]["content"] == "Initial prompt"

    # 3. replace_existing=True replaces existing system prompt
    replace_cap = ReinjectSystemPrompt(replace_existing=True)
    replaced = replace_cap.reinject(existing_msgs, "Overridden authoritative prompt")
    assert len(replaced) == 2
    assert replaced[0]["content"] == "Overridden authoritative prompt"


def test_process_history_capability() -> None:
    """Verify ProcessHistory capability applying message history processors."""
    from devops_cli.ai.agents import ProcessHistory, RunContext

    # 1. Trimming processor (keep last N messages)
    def keep_recent(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        return messages[-2:]

    trim_cap = ProcessHistory(keep_recent)
    assert trim_cap.id == "process_history"

    history = [
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": "2"},
        {"role": "user", "content": "3"},
        {"role": "assistant", "content": "4"},
    ]
    processed = trim_cap.process_history(history)
    assert len(processed) == 2
    assert processed[0]["content"] == "3"
    assert processed[1]["content"] == "4"

    # 2. Context-aware processor (redaction or tagging)
    def redact_secrets(
        ctx: RunContext[dict[str, Any]], messages: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        redact = (ctx.deps or {}).get("redact", False)
        if not redact:
            return messages
        return [{**m, "content": m["content"].replace("SECRET", "[REDACTED]")} for m in messages]

    redact_cap = ProcessHistory(redact_secrets)
    msgs_with_secret = [{"role": "user", "content": "api key is SECRET"}]

    # Without redact flag
    assert (
        redact_cap.process_history(msgs_with_secret, RunContext())[0]["content"]
        == "api key is SECRET"
    )

    # With redact flag
    ctx_redact = RunContext(deps={"redact": True})
    assert (
        redact_cap.process_history(msgs_with_secret, ctx_redact)[0]["content"]
        == "api key is [REDACTED]"
    )


@pytest.mark.anyio
async def test_process_event_stream_capability() -> None:
    """Verify ProcessEventStream capability handling streaming events and observers."""
    from devops_cli.ai.agents import AgentStreamEvent, ProcessEventStream, RunContext

    observed_events: list[AgentStreamEvent] = []

    async def log_events(ctx: RunContext[dict[str, Any]], events: list[AgentStreamEvent]) -> None:
        for event in events:
            observed_events.append(event)

    cap = ProcessEventStream(log_events)
    assert cap.id == "process_event_stream"

    event1 = AgentStreamEvent(event_kind="token", content="Hello")
    event2 = AgentStreamEvent(event_kind="token", content=" world")
    event3 = AgentStreamEvent(event_kind="tool_call", content="search_query")

    stream = [event1, event2, event3]
    result = await cap.handle_stream(stream, RunContext(deps={"stream_id": "s1"}))
    assert result is None
    assert len(observed_events) == 3
    assert observed_events[0].content == "Hello"
    assert observed_events[2].event_kind == "tool_call"


def test_subagents_usage_forwarding() -> None:
    """Verify SubAgents capability forwards usage tracking to child agents."""
    from unittest.mock import MagicMock

    from devops_cli.ai.agents import AgentUsage, RunContext
    from devops_cli.ai.harness.workflow import SubAgent, SubAgents

    child_agent = MagicMock()
    child_resp = MagicMock()
    child_resp.content = "Child agent result"

    def child_run(task: str, usage: AgentUsage | None = None) -> Any:
        if usage is not None:
            usage.input_tokens += 100
            usage.output_tokens += 50
            usage.total_tokens += 150
        return child_resp

    child_agent.run.side_effect = child_run

    sub_agent_def = SubAgent(name="specialist", description="Domain specialist", agent=child_agent)
    subagents_cap = SubAgents(agents=[sub_agent_def], forward_usage=True)

    tools = subagents_cap.get_tools()
    delegate_tool = next(t for t in tools if getattr(t, "name", "") == "delegate_task")

    parent_usage = AgentUsage(input_tokens=20, output_tokens=10, total_tokens=30)
    ctx = RunContext(usage=parent_usage)

    res = delegate_tool.func(ctx=ctx, agent_name="specialist", task="analyze logs")
    assert res == "Child agent result"
    assert parent_usage.input_tokens == 120
    assert parent_usage.output_tokens == 60
    assert parent_usage.total_tokens == 180


def test_agent_tool_args_validator() -> None:
    """Verify args_validator_func supports pre-execution argument validation and transformation."""
    from devops_cli.ai.agents import FunctionToolset, Tool

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
    from devops_cli.ai.agents import AbstractToolset, AgentTool, PydanticAgent, Tool

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
async def test_embedder_and_embedding_result() -> None:
    """Verify Embedder interface and EmbeddingResult container indexing and cost calculation."""
    from unittest.mock import MagicMock

    from devops_cli.ai.agents import Embedder, EmbeddingResult

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
    assert res_query.usage.input_tokens > 0
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
    with pytest.raises(KeyError):
        _ = res_docs["Missing doc"]

    with pytest.raises(TypeError):
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


def test_testing_utilities_and_agent_override() -> None:
    """Verify TestModel, FunctionModel, Agent.override, capture_run_messages, and ALLOW_MODEL_REQUESTS."""
    import json

    import devops_cli.ai.agents.testing as testing_module
    from devops_cli.ai.agents import (
        AgentInfo,
        FunctionModel,
        FunctionToolset,
        ModelNotAllowedError,
        PydanticAgent,
        TestModel,
        capture_run_messages,
    )

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
        with pytest.raises(ModelNotAllowedError):
            real_agent.run("Test query")

        # TestModel succeeds even when ALLOW_MODEL_REQUESTS is False
        with real_agent.override(model=TestModel(custom_output_text="Safe test")):
            safe_res = real_agent.run("Test query")
            assert safe_res.content == "Safe test"
    finally:
        testing_module.ALLOW_MODEL_REQUESTS = orig_allow
        agent_module.ALLOW_MODEL_REQUESTS = orig_allow


@pytest.mark.anyio
async def test_mcp_toolset_and_capability() -> None:
    """Verify MCPToolset lifecycle, tool registration, and MCP capability adaptation."""
    from devops_cli.ai.agents import (
        MCP,
        AgentTool,
        MCPServerTool,
        MCPToolset,
        PydanticAgent,
        TestModel,
    )

    # 1. MCPToolset instantiation and lifecycle
    tool1 = AgentTool(
        name="mcp_query", description="Query remote MCP", func=lambda q: f"Result: {q}"
    )
    mcp_ts = MCPToolset(url="https://mcp.internal.net/api", tools=[tool1])

    assert len(mcp_ts.get_tools()) == 1
    assert mcp_ts.get_tools()[0].name == "mcp_query"
    instructions = mcp_ts.get_instructions()
    assert len(instructions) == 1
    assert "https://mcp.internal.net/api" in instructions[0]

    # Context manager lifecycle
    async with mcp_ts as ts:
        assert len(ts.get_tools()) == 1

    # 2. MCP capability with MCPToolset as local
    mcp_cap = MCP(url="https://mcp.internal.net/api", local=mcp_ts)
    tools = mcp_cap.get_tools()
    assert len(tools) == 1
    assert tools[0].name == "mcp_query"

    # 3. MCP capability with native=True
    mcp_native = MCP(url="https://mcp.internal.net/api", native=True)
    settings = mcp_native.get_model_settings()
    assert settings.get("native_mcp_server") is True
    assert settings["mcp_server_config"]["url"] == "https://mcp.internal.net/api"

    # 4. MCP capability with MCPServerTool instance
    server_tool = MCPServerTool(url="https://mcp.prod.cloud/sse", id="prod_mcp")
    mcp_server_cap = MCP(native=server_tool)
    server_settings = mcp_server_cap.get_model_settings()
    assert server_settings["mcp_server_config"]["url"] == "https://mcp.prod.cloud/sse"

    # 5. Tool prefixing and from_config loading
    mcp_prefix = MCPToolset(
        "https://mcp.internal.net/api",
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

    # 6. End-to-end execution with agent and async context manager
    agent = PydanticAgent(
        name="MCPAgent",
        model="openai:gpt-4o",
        capabilities=[mcp_cap],
        toolsets=[mcp_ts],
    )
    async with agent:
        with agent.override(model=TestModel(custom_output_text="MCP processed")):
            res = agent.run("Run mcp tool")
            assert res.content == "MCP processed"

    # 7. MCPSamplingModel delegation
    from unittest.mock import MagicMock

    from devops_cli.ai.agents import MCPSamplingModel

    mock_session = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = "Poem from MCP sampling client"
    mock_session.create_message.return_value = mock_msg

    sampling_model = MCPSamplingModel(session=mock_session)
    sample_res = sampling_model.chat("Write a poem")
    assert sample_res == "Poem from MCP sampling client"
    assert sampling_model.chat_messages("System", ["User query"]) == "Poem from MCP sampling client"

    # Fallback when no session is attached
    fallback_model = MCPSamplingModel()
    assert "MCP sampling" in fallback_model.chat("Test")

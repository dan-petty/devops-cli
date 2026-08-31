"""Unit tests for Pydantic AI SystemReminders, Instrumentation, and custom capability creation."""

from __future__ import annotations

from typing import Any

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

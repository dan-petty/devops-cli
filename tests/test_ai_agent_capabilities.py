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

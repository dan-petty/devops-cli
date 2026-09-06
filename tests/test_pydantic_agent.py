from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from devops_cli.ai.agents.pydantic_agent import (
    AgentTool,
    PydanticAgent,
    RunContext,
    _check_path_traversal,
)
from devops_cli.ai.personas import Persona
from devops_cli.ai.pydantic_ai_bridge import (
    DevOpsAgentContext,
    create_pydantic_ai_agent,
    get_persona_pydantic_agent,
    is_pydantic_ai_available,
)
from devops_cli.ai.review_schema import ReviewResult
from devops_cli.exceptions import ModelRetry, SecurityError


def test_is_pydantic_ai_available() -> None:
    assert is_pydantic_ai_available() is True


def test_devops_agent_context_model() -> None:
    ctx = DevOpsAgentContext(
        target_repo="/workspaces/test",
        active_persona="devsecops",
        context_tokens_budget=8192,
    )
    assert ctx.target_repo == "/workspaces/test"
    assert ctx.active_persona == "devsecops"
    assert ctx.context_tokens_budget == 8192


def test_create_pydantic_ai_agent() -> None:
    agent = create_pydantic_ai_agent(
        model_name="ollama:test-model",
        system_prompt="You are a test reviewer.",
        result_type=ReviewResult,
        deps_type=DevOpsAgentContext,
    )
    assert agent is not None


def test_get_persona_pydantic_agent() -> None:
    agent = get_persona_pydantic_agent(Persona.DEVSECOPS)
    assert agent is not None


def test_pydantic_agent_execution_and_tools() -> None:
    """Verify PydanticAgent tool registration, validation, path traversal guard, and run loop."""
    # 1. Path traversal guard
    with pytest.raises(SecurityError, match="Path traversal"):
        _check_path_traversal("file_path", "folder/../../../etc/passwd")

    _check_path_traversal("safe_path", "src/devops_cli/main.py")

    # 2. Tool definition and execution
    def add(a: int, b: int) -> int:
        return a + b

    tool = AgentTool(
        name="add",
        description="Add two numbers",
        func=add,
        parameters={"a": {"type": "integer"}, "b": {"type": "integer"}},
    )
    assert tool.execute(a=2, b=3) == 5
    cleaned = tool.validate_args({"a": 2, "b": 3, "extra": "ignored"})
    assert cleaned == {"a": 2, "b": 3}

    # 3. PydanticAgent with tool registration
    mock_client = MagicMock()
    mock_client.chat_messages.return_value = "The sum is 5"
    mock_client.chat_messages_stream.return_value = iter(["The ", "sum ", "is 5"])

    def multiply(x: int, y: int) -> int:
        """Multiply two numbers."""
        return x * y

    agent = PydanticAgent(
        client=mock_client,
        name="MathAgent",
        system_prompt="You are a math helper",
        tools=[multiply],
    )

    assert "multiply" in agent._tools
    assert "Multiply two numbers" in agent._tools["multiply"].description

    # 4. Agent run
    resp = agent.run("Calculate 2 + 3")
    assert resp.content == "The sum is 5"
    assert resp.turns >= 1

    # 5. Agent stream
    tokens = list(agent.run_stream("Calculate 2 + 3"))
    assert "".join(tokens) == "The sum is 5"


def test_pydantic_agent_advanced_dispatch_and_schema() -> None:
    """Verify tool execution loop, memory serialization, output schema parsing, and fallback resolution."""
    from devops_cli.ai.agents.memory import AgentMemory
    from devops_cli.ai.agents.pydantic_agent import (
        ToolCall,
        _create_tool_retry_message,
        _resolve_fallback_output,
    )

    # 1. Fallback output resolution
    assert _resolve_fallback_output("Final answer", [], []) == "Final answer"
    tc = ToolCall(tool_name="add", arguments={"a": 1, "b": 2}, result=3)
    assert _resolve_fallback_output('{"tool":"add"}', [tc], []) == "3"
    assert _resolve_fallback_output("", [], ["Deliberation thought"]) == "Deliberation thought"

    # 2. Tool retry message creation
    def sample_fn(name: str) -> str:
        """Sample function."""
        return name

    agent_tool = AgentTool(
        name="sample_fn", description="Sample", func=sample_fn, parameters={"name": "str"}
    )
    retry_msg = _create_tool_retry_message("sample_fn", agent_tool)
    assert "sample_fn" in retry_msg.content
    assert '"tool":"sample_fn"' in retry_msg.content

    # 3. Agent with memory and output schema
    mem = AgentMemory(session_id="test_sess", summary="Prior code review passed")
    mock_llm = MagicMock()
    mock_llm.chat_messages.return_value = (
        '```json\n{"summary": "Security passed", "recommendation": "APPROVE", "findings": []}\n```'
    )

    agent = PydanticAgent(
        client=mock_llm,
        name="Reviewer",
        system_prompt="Analyze code",
        output_schema=ReviewResult,
        tools=[agent_tool],
        memory=mem,
    )

    sys_prompt = agent._build_system_prompt_with_tools()
    assert "Prior code review passed" in sys_prompt
    assert "sample_fn" in sys_prompt
    assert "Required Response Format" in sys_prompt

    resp = agent.run("Generate review report")
    assert resp.data is not None
    assert resp.data.recommendation == "APPROVE"


def test_agent_memory_and_multi_agent_pipeline() -> None:
    """Verify AgentMemory auto-summarization and MultiAgentPipeline multi-stage execution."""
    from devops_cli.ai.agents.memory import AgentMemory
    from devops_cli.ai.agents.pipeline import MultiAgentPipeline

    # 1. AgentMemory operations
    mem = AgentMemory(session_id="mem-1", max_entries=4)
    for i in range(5):
        mem.add_interaction(role="user", content=f"User question {i}")
        mem.add_interaction(role="assistant", content=f"Assistant answer {i}")

    assert len(mem.entries) == 10

    mock_summarizer = MagicMock()
    mock_summarizer.chat.return_value = "Summary of conversation: 5 questions discussed."

    summarized = mem.auto_summarize_if_needed(llm_client=mock_summarizer)
    assert summarized is True
    assert "5 questions discussed" in mem.summary

    mem.clear()
    assert len(mem.entries) == 0
    assert mem.summary == ""

    # 2. MultiAgentPipeline execution
    mock_client1 = MagicMock()
    mock_client1.chat_messages.return_value = "Agent 1 output"
    mock_client2 = MagicMock()
    mock_client2.chat_messages.return_value = "Agent 2 output"

    agent1 = PydanticAgent(client=mock_client1, name="Stage1Agent", system_prompt="Stage 1")
    agent2 = PydanticAgent(client=mock_client2, name="Stage2Agent", system_prompt="Stage 2")

    pipeline = MultiAgentPipeline(agents=[agent1, agent2])
    res = pipeline.run("Initial task input", max_turns_per_agent=2)

    assert len(res.steps) == 2
    assert res.steps[0].agent_name == "Stage1Agent"
    assert res.steps[1].agent_name == "Stage2Agent"
    assert res.final_content == "Agent 2 output"


def test_multi_agent_pipeline_parallel_and_skip_rag() -> None:
    """Verify MultiAgentPipeline parallel execution and skip_rag propagation."""
    from devops_cli.ai.agents.pipeline import MultiAgentPipeline

    mock_client1 = MagicMock()
    mock_client1.chat_messages.return_value = "Persona 1 report"
    mock_client2 = MagicMock()
    mock_client2.chat_messages.return_value = "Persona 2 report"

    agent1 = PydanticAgent(client=mock_client1, name="DevSecOps", system_prompt="DevSecOps")
    agent2 = PydanticAgent(client=mock_client2, name="Architect", system_prompt="Architect")

    pipeline = MultiAgentPipeline(agents=[agent1, agent2])
    res = pipeline.run("Review task", parallel=True, skip_rag=True)

    assert len(res.steps) == 2
    assert {s.agent_name for s in res.steps} == {"DevSecOps", "Architect"}
    assert res.final_content in ("Persona 1 report", "Persona 2 report")


def test_pydantic_agent_pydantic_ai_enhancements() -> None:
    """Verify @agent.tool, @agent.tool_plain, RunContext, usage, and iter."""
    mock_client = MagicMock()
    mock_client.model = "test-model"
    mock_client.chat_messages.return_value = (
        '{"tool": "analyze_ctx", "arguments": {"target": "k8s"}}'
    )

    agent = PydanticAgent(
        client=mock_client, name="ContextAwareAgent", system_prompt="Base sys prompt"
    )

    # 1. Dynamic system prompt decorator
    @agent.system_prompt_fn
    def dynamic_prompt(ctx: RunContext[dict[str, str]]) -> str:
        dep_val = ctx.deps.get("env") if ctx and ctx.deps else "default"
        return f"Environment: {dep_val}"

    # 2. Tool with RunContext injection
    @agent.tool
    def analyze_ctx(ctx: RunContext[dict[str, str]], target: str) -> str:
        env = ctx.deps.get("env") if ctx and ctx.deps else "unknown"
        return f"Target {target} analyzed in {env}"

    # 3. Tool plain without RunContext
    @agent.tool_plain
    def ping() -> str:
        return "pong"

    assert "analyze_ctx" in agent._tools
    assert agent._tools["analyze_ctx"].takes_ctx is True
    assert "ping" in agent._tools
    assert agent._tools["ping"].takes_ctx is False

    # 4. Agent run with deps and usage
    mock_client.chat_messages.side_effect = [
        '{"tool": "analyze_ctx", "arguments": {"target": "k8s"}}',
        "Analysis of k8s completed successfully.",
    ]

    res = agent.run("Analyze k8s deployment", deps={"env": "production"}, max_turns=3)
    assert res.content == "Analysis of k8s completed successfully."
    assert len(res.tool_calls) == 1
    assert "production" in str(res.tool_calls[0].result)
    assert res.usage.total_tokens > 0
    assert res.usage.input_tokens > 0
    assert res.usage.output_tokens > 0

    # 5. Agent iter
    mock_client.chat_messages.side_effect = None
    mock_client.chat_messages.return_value = "Iter response"
    nodes = list(agent.iter("Quick prompt", deps={"env": "staging"}))
    assert len(nodes) >= 3
    assert any(n.kind == "user_prompt" for n in nodes)
    assert any(n.kind == "model_request" for n in nodes)
    assert any(n.kind == "end" for n in nodes)


def test_pydantic_agent_output_validator_and_model_retry() -> None:
    """Verify @agent.output_validator and ModelRetry handling from tools and validators."""

    class ClusterReport(BaseModel):
        cluster_name: str
        node_count: int

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent[ClusterReport](
        client=mock_client,
        name="ValidatorAgent",
        output_schema=ClusterReport,
    )

    # 1. Output validator that enforces node_count > 0
    @agent.output_validator
    def validate_cluster(report: ClusterReport) -> ClusterReport:
        if report.node_count <= 0:
            raise ModelRetry("node_count must be greater than zero")
        return report

    # Tool that raises ModelRetry on invalid arg
    @agent.tool
    def query_cluster(cluster: str) -> str:
        if cluster == "invalid":
            raise ModelRetry("Cluster name 'invalid' not found. Available: prod, staging")
        return f"Cluster {cluster} has 3 nodes."

    # Turn 1: tool fails with ModelRetry -> Turn 2: tool succeeds -> model returns invalid node_count -> Turn 3: valid output
    mock_client.chat_messages.side_effect = [
        '{"tool": "query_cluster", "arguments": {"cluster": "invalid"}}',
        '```json\n{"cluster_name": "prod", "node_count": 0}\n```',
        '```json\n{"cluster_name": "prod", "node_count": 5}\n```',
    ]

    res = agent.run("Check cluster", max_turns=4)
    assert res.data is not None
    assert res.data.cluster_name == "prod"
    assert res.data.node_count == 5
    assert res.turns == 3


def test_pydantic_agent_hooks() -> None:
    """Verify before/after model request, before/after tool execute, and on_tool_error hooks."""
    events: list[str] = []
    mock_client = MagicMock()
    mock_client.model = "test-model"
    mock_client.chat_messages.side_effect = [
        '{"tool": "calculate", "arguments": {"x": 2, "y": 3}}',
        "Result is 5",
    ]

    agent = PydanticAgent(client=mock_client, name="HookAgent", system_prompt="Hook system")

    @agent.before_model_request
    def on_before_req(ctx: RunContext[Any], msgs: list[Any]) -> None:
        events.append(f"before_model_request:msgs={len(msgs)}")

    @agent.after_model_request
    def on_after_req(ctx: RunContext[Any], resp: str) -> None:
        events.append("after_model_request")

    @agent.before_tool_execute
    def on_before_tool(ctx: RunContext[Any], name: str, args: dict[str, Any]) -> None:
        events.append(f"before_tool_execute:{name}")

    @agent.after_tool_execute
    def on_after_tool(ctx: RunContext[Any], name: str, args: dict[str, Any], res: Any) -> None:
        events.append(f"after_tool_execute:{name}:{res}")

    @agent.on_tool_error
    def on_tool_err(ctx: RunContext[Any], name: str, err: Exception) -> None:
        events.append(f"on_tool_error:{name}")

    @agent.tool
    def calculate(x: int, y: int) -> int:
        return x + y

    res = agent.run("Calculate 2 + 3", max_turns=3)
    assert res.content == "Result is 5"
    assert "before_model_request:msgs=1" in events
    assert "after_model_request" in events
    assert "before_tool_execute:calculate" in events
    assert "after_tool_execute:calculate:5" in events


def test_pydantic_agent_capabilities_and_on_demand() -> None:
    """Verify BaseCapability, Capability, and on-demand deferred loading."""
    from devops_cli.ai.agents import Capability

    # 1. Non-deferred capability
    monitoring_cap = Capability(
        id="monitoring",
        description="Grafana and Prometheus monitoring queries",
        instructions="Always include time range in queries.",
        defer_loading=False,
    )

    @monitoring_cap.tool
    def query_metric(metric: str) -> str:
        return f"Metric {metric} value: 42"

    # 2. Deferred on-demand capability
    k8s_cap = Capability(
        id="k8s_tools",
        description="Kubernetes cluster operations and pod inspection",
        instructions="Never delete production pods without confirmation.",
        defer_loading=True,
        model_settings={"enable_thinking": True},
    )

    @k8s_cap.tool
    def get_pods(namespace: str) -> str:
        return f"Pods in {namespace}: pod-1, pod-2"

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent(
        client=mock_client,
        name="CapabilityAgent",
        capabilities=[monitoring_cap, k8s_cap],
    )

    # Initial state: monitoring tool is loaded, k8s_cap is deferred (load_capability tool available)
    assert "query_metric" in agent._tools
    assert "get_pods" not in agent._tools
    assert "load_capability" in agent._tools

    # Execution turn 1: model requests load_capability('k8s_tools') -> Turn 2: model uses get_pods -> Turn 3: final answer
    mock_client.chat_messages.side_effect = [
        '{"tool": "load_capability", "arguments": {"capability_id": "k8s_tools"}}',
        '{"tool": "get_pods", "arguments": {"namespace": "default"}}',
        "Found 2 pods in default namespace.",
    ]

    res = agent.run("List pods in default namespace", max_turns=4)
    assert res.content == "Found 2 pods in default namespace."
    assert "get_pods" in agent._tools
    assert len(res.tool_calls) == 2
    assert res.tool_calls[0].tool_name == "load_capability"
    assert res.tool_calls[1].tool_name == "get_pods"
    assert k8s_cap.get_model_settings() == {"enable_thinking": True}


def test_pydantic_agent_spec_and_template_str() -> None:
    """Verify AgentSpec parsing, from_spec factory, and TemplateStr rendering against deps."""
    from devops_cli.ai.agents import AgentSpec, TemplateStr

    # 1. TemplateStr test
    tmpl = TemplateStr("You are assisting {{user_name}} in {{environment}}.")
    rendered = tmpl.render({"user_name": "Alice", "environment": "production"})
    assert rendered == "You are assisting Alice in production."

    # 2. AgentSpec YAML parsing
    yaml_content = """
    model: "claude-3-5-sonnet"
    name: "ReleaseArchitect"
    instructions:
      - "Follow semantic versioning."
      - "Verify changelog integrity."
    """
    spec = AgentSpec.from_yaml(yaml_content)
    assert spec.name == "ReleaseArchitect"
    assert spec.model == "claude-3-5-sonnet"
    assert isinstance(spec.instructions, list)

    # 3. PydanticAgent.from_spec
    mock_client = MagicMock()
    mock_client.model = "test-model"
    agent = PydanticAgent.from_spec(spec, client=mock_client)
    assert agent.name == "ReleaseArchitect"
    assert "Follow semantic versioning." in agent.system_prompt
    assert "Verify changelog integrity." in agent.system_prompt


def test_pydantic_agent_message_history() -> None:
    """Verify all_messages, new_messages, and continuing conversation with message_history."""
    mock_client = MagicMock()
    mock_client.model = "test-model"

    mock_client.chat_messages.return_value = "Here is a DevOps tip: automate everything."
    agent = PydanticAgent(client=mock_client, name="TipAgent", system_prompt="DevOps assistant")

    res1 = agent.run("Give me a tip")
    assert res1.content == "Here is a DevOps tip: automate everything."
    assert len(res1.all_messages()) >= 2
    assert len(res1.new_messages()) >= 2

    # Second turn using new_messages() as message_history
    mock_client.chat_messages.return_value = "Explain: automation reduces human error."
    res2 = agent.run("Explain?", message_history=res1.new_messages())
    assert res2.content == "Explain: automation reduces human error."
    assert len(res2.all_messages()) >= 4
    assert len(res2.new_messages()) >= 2


def test_pydantic_agent_retries_and_budget_exhaustion() -> None:
    """Verify AgentRetries limits and UnexpectedModelBehavior on budget exhaustion."""
    from devops_cli.ai.agents import AgentRetries
    from devops_cli.exceptions import ModelRetry, UnexpectedModelBehavior

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent(
        client=mock_client,
        name="StrictAgent",
        retries=AgentRetries(tools=1, output=1),
    )

    @agent.tool
    def strict_tool(val: str) -> str:
        raise ModelRetry(f"Invalid val: {val}")

    # Tool fails twice consecutively -> exceeds tool retry budget of 1
    mock_client.chat_messages.side_effect = [
        '{"tool": "strict_tool", "arguments": {"val": "bad1"}}',
        '{"tool": "strict_tool", "arguments": {"val": "bad2"}}',
    ]

    with pytest.raises(UnexpectedModelBehavior) as exc_info:
        agent.run("Run strict tool", max_turns=3, skip_rag=True)
    assert "exceeded retry budget" in str(exc_info.value)


def test_pydantic_agent_tool_class_and_timeouts() -> None:
    """Verify Tool.from_function, timeout enforcement, and retry feedback."""
    import time

    from devops_cli.ai.agents import Tool

    # 1. Tool.from_function
    def slow_fn(sec: float) -> str:
        """A function that sleeps."""
        time.sleep(sec)
        return "done"

    tool_obj = Tool.from_function(slow_fn, name="slow_tool", timeout=0.05)
    assert tool_obj.name == "slow_tool"
    assert tool_obj.timeout == 0.05
    assert tool_obj.takes_ctx is False

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent(
        client=mock_client,
        name="TimeoutAgent",
        tools=[tool_obj],
    )

    # Turn 1: tool times out -> Turn 2: model provides direct answer
    mock_client.chat_messages.side_effect = [
        '{"tool": "slow_tool", "arguments": {"sec": 0.2}}',
        "Tool timed out, completed with fallback.",
    ]

    res = agent.run("Run slow task", max_turns=2, skip_rag=True)
    assert "completed with fallback" in res.content
    assert len(res.tool_calls) == 1
    assert "Timed out" in str(res.tool_calls[0].result)


def test_pydantic_agent_advanced_tools_and_tool_return() -> None:
    """Verify ToolReturn metadata/content handling and Tool.from_schema custom schemas."""
    from devops_cli.ai.agents import Tool, ToolReturn

    # 1. Tool.from_schema
    def custom_sum(**kwargs: Any) -> ToolReturn:
        total = kwargs.get("a", 0) + kwargs.get("b", 0)
        return ToolReturn(
            return_value=f"Sum is {total}",
            content=[
                f"Detailed calculation breakdown: {kwargs.get('a')} + {kwargs.get('b')} = {total}"
            ],
            metadata={"source": "math_engine", "calc_total": total},
            tools=["deferred_calculator"],
        )

    schema_tool = Tool.from_schema(
        function=custom_sum,
        name="custom_sum",
        description="Compute sum of two integers",
        json_schema={
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            }
        },
        strict=True,
    )
    assert schema_tool.name == "custom_sum"
    assert schema_tool.strict is True
    assert "a" in schema_tool.parameters

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent(
        client=mock_client,
        name="AdvancedToolAgent",
        tools=[schema_tool],
    )

    mock_client.chat_messages.side_effect = [
        '{"tool": "custom_sum", "arguments": {"a": 10, "b": 20}}',
        "Final total evaluated to 30.",
    ]

    res = agent.run("Calculate 10 + 20", max_turns=2, skip_rag=True)
    assert res.content == "Final total evaluated to 30."
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].result == "Sum is 30"
    assert res.tool_calls[0].metadata.get("calc_total") == 30
    assert any("Detailed calculation breakdown" in m.content for m in res.all_messages())


def test_function_toolset_and_instructions() -> None:
    """Verify FunctionToolset tools, static instructions, and agent prompt composition."""
    from devops_cli.ai.agents import FunctionToolset

    toolset = FunctionToolset(instructions="Always follow semver when calculating releases.")

    @toolset.tool_plain
    def bump_semver(current: str, part: str) -> str:
        return f"{current} bumped {part}"

    toolset.add_function(lambda: "2026-08-30", name="get_date")

    assert len(toolset.get_tools()) == 2
    assert "Always follow semver" in toolset.get_instructions()[0]

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent(
        client=mock_client,
        name="ReleaseAgent",
        system_prompt="Base release engineer.",
        toolsets=[toolset],
    )

    sys_prompt = agent._build_system_prompt_with_tools()
    assert "Base release engineer." in sys_prompt
    assert "Always follow semver when calculating releases." in sys_prompt
    assert "bump_semver" in agent._tools
    assert "get_date" in agent._tools


def test_deferred_tools_approval_required_and_handler() -> None:
    """Verify requires_approval flag, ApprovalRequired exception, and HandleDeferredToolCalls capability."""
    from devops_cli.ai.agents import (
        DeferredToolRequests,
        DeferredToolResults,
        HandleDeferredToolCalls,
        ToolApproved,
        ToolDenied,
    )
    from devops_cli.exceptions.ai import ApprovalRequired

    # 1. Tool requiring approval
    def delete_prod_cluster(cluster_name: str) -> str:
        return f"Cluster {cluster_name} deleted"

    # 2. Tool requiring dynamic approval via exception
    def modify_config(ctx: RunContext[Any], key: str, value: str) -> str:
        if key == "secret" and not ctx.tool_call_approved:
            raise ApprovalRequired("Modifying secret requires approval", metadata={"risk": "high"})
        return f"Config {key}={value} applied"

    # Handler capability that denies delete and approves modify_config
    def sample_handler(reqs: DeferredToolRequests) -> DeferredToolResults:
        approvals: dict[str, Any] = {}
        for app in reqs.approvals:
            if app.tool_name == "delete_prod_cluster":
                approvals[app.tool_call_id] = ToolDenied(
                    "Production cluster deletion is blocked by policy"
                )
            elif app.tool_name == "modify_config":
                approvals[app.tool_call_id] = ToolApproved(
                    override_args={"value": "sanitized_secret"}
                )
        return reqs.build_results(approvals=approvals)

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent(
        client=mock_client,
        name="SecurityAgent",
        capabilities=[HandleDeferredToolCalls(handler=sample_handler)],
    )
    agent.tool_plain(delete_prod_cluster, requires_approval=True)
    agent.tool(modify_config)

    # Turn 1: model tries to delete cluster -> handler denies it
    # Turn 2: model tries modify config -> handler approves with overridden arg
    # Turn 3: model final response
    mock_client.chat_messages.side_effect = [
        '{"tool": "delete_prod_cluster", "arguments": {"cluster_name": "prod-east"}}',
        '{"tool": "modify_config", "arguments": {"key": "secret", "value": "raw_pass"}}',
        "Operations executed with security compliance.",
    ]

    res = agent.run("Perform infrastructure modifications", max_turns=4, skip_rag=True)
    assert res.content == "Operations executed with security compliance."
    assert len(res.tool_calls) == 2
    assert "blocked by policy" in str(res.tool_calls[0].result)
    assert "Config secret=sanitized_secret applied" in str(res.tool_calls[1].result)


def test_deferred_tools_stop_the_world_and_resume() -> None:
    """Verify stop-the-world workflow returning DeferredToolRequests and resuming with DeferredToolResults."""
    from devops_cli.ai.agents import (
        DeferredToolRequests,
        DeferredToolResults,
    )
    from devops_cli.exceptions.ai import CallDeferred

    def async_batch_job(task_name: str) -> str:
        raise CallDeferred(
            "Task deferred to background worker", metadata={"queue": "batch_priority"}
        )

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent(
        client=mock_client,
        name="BatchAgent",
    )
    agent.tool_plain(async_batch_job)

    # Step 1: Tool call raises CallDeferred, no inline handler -> agent stops and returns DeferredToolRequests
    mock_client.chat_messages.return_value = (
        '{"tool": "async_batch_job", "arguments": {"task_name": "backup_db"}}'
    )

    res1 = agent.run("Trigger backup", max_turns=2, skip_rag=True)
    assert isinstance(res1.data, DeferredToolRequests)
    assert len(res1.data.calls) == 1
    assert res1.data.calls[0].tool_name == "async_batch_job"
    assert res1.data.metadata["async_batch_job"]["queue"] == "batch_priority"

    # Step 2: Supply external results in subsequent run
    results = DeferredToolResults(
        calls={"async_batch_job": "Job #42 finished successfully with snapshot-123"}
    )
    mock_client.chat_messages.side_effect = [
        '{"tool": "async_batch_job", "arguments": {"task_name": "backup_db"}}',
        "Backup job #42 finished successfully.",
    ]

    res2 = agent.run("Trigger backup", max_turns=2, skip_rag=True, deferred_tool_results=results)
    assert res2.content == "Backup job #42 finished successfully."
    assert len(res2.tool_calls) == 1
    assert "snapshot-123" in str(res2.tool_calls[0].result)


def test_native_tools_web_search_and_code_execution() -> None:
    """Verify NativeTool capability with WebSearchTool and CodeExecutionTool configurations."""
    from devops_cli.ai.agents import (
        CodeExecutionTool,
        NativeTool,
        WebSearchTool,
        WebSearchUserLocation,
    )

    loc = WebSearchUserLocation(city="San Francisco", country="US", timezone="America/Los_Angeles")
    search_tool = WebSearchTool(
        search_context_size="high",
        user_location=loc,
        blocked_domains=["spam.com"],
        max_uses=5,
    )
    native_search_cap = NativeTool(tool=search_tool)
    settings = native_search_cap.get_model_settings()
    assert settings["native_web_search"] is True
    assert settings["web_search_config"]["search_context_size"] == "high"
    assert settings["web_search_config"]["user_location"]["city"] == "San Francisco"
    assert settings["web_search_config"]["blocked_domains"] == ["spam.com"]

    code_tool = CodeExecutionTool(language="python", timeout=30.0)
    native_code_cap = NativeTool(tool=code_tool)
    code_settings = native_code_cap.get_model_settings()
    assert code_settings["native_code_execution"] is True
    assert code_settings["code_execution_config"]["language"] == "python"

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent(
        client=mock_client,
        name="SearchAgent",
        capabilities=[native_search_cap],
    )
    prompt = agent._build_system_prompt_with_tools()
    assert "Provider-native web search capability is enabled." in prompt


def test_mcp_capability_and_native_server_tool() -> None:
    """Verify MCP capability and MCPServerTool integration."""
    from devops_cli.ai.agents import (
        MCP,
        MCPServerTool,
        NativeTool,
        Tool,
    )

    # 1. Native MCP server tool
    mcp_tool = MCPServerTool(
        id="cluster-mcp",
        url="https://mcp.devops.internal/sse",
        authorization_token="bearer-token-123",
        description="Kubernetes cluster MCP server",
    )
    native_cap = NativeTool(tool=mcp_tool)
    settings = native_cap.get_model_settings()
    assert settings["native_mcp_server"] is True
    assert settings["mcp_server_config"]["id"] == "cluster-mcp"
    assert settings["mcp_server_config"]["authorization_token"] == "bearer-token-123"

    # 2. Adaptive MCP capability with local tools
    def sample_mcp_tool(x: int) -> int:
        return x * 2

    local_t = Tool.from_function(sample_mcp_tool, name="calc_double")
    mcp_cap = MCP(
        url="https://mcp.devops.internal/sse",
        native=True,
        local=[local_t],
    )
    mcp_tools = mcp_cap.get_tools()
    assert len(mcp_tools) == 1
    assert mcp_tools[0].name == "calc_double"

    mcp_settings = mcp_cap.get_model_settings()
    assert mcp_settings["native_mcp_server"] is True
    assert mcp_settings["mcp_server_config"]["url"] == "https://mcp.devops.internal/sse"

    # 3. Strict native mode (local=False)
    strict_native = MCP("https://mcp.devops.internal/sse", native=True, local=False)
    assert strict_native.get_tools() == []


def test_web_search_capability_adaptive() -> None:
    """Verify WebSearch adaptive capability with native and local fallbacks."""
    from devops_cli.ai.agents import (
        WebSearch,
        WebSearchTool,
    )

    # 1. Native-only
    cap_native = WebSearch(native=WebSearchTool(search_context_size="high"))
    assert cap_native.get_tools() == []
    settings = cap_native.get_model_settings()
    assert settings["native_web_search"] is True
    assert settings["web_search_config"]["search_context_size"] == "high"

    # 2. DuckDuckGo local fallback
    cap_ddg = WebSearch(local="duckduckgo", native=False)
    tools = cap_ddg.get_tools()
    assert len(tools) == 1
    assert tools[0].name == "duckduckgo_search"
    assert cap_ddg.get_model_settings() == {}

    # 3. Custom callable local fallback
    def custom_search(q: str) -> str:
        return f"result for {q}"

    cap_custom = WebSearch(local=custom_search)
    custom_tools = cap_custom.get_tools()
    assert len(custom_tools) == 1
    assert custom_tools[0].name == "custom_search"


def test_web_fetch_capability_adaptive() -> None:
    """Verify WebFetch adaptive capability with native and local fallbacks."""
    from devops_cli.ai.agents import (
        WebFetch,
        WebFetchTool,
    )

    # 1. Native-only
    cap_native = WebFetch(
        native=WebFetchTool(
            allowed_domains=["example.com"],
            max_uses=3,
        )
    )
    assert cap_native.get_tools() == []
    settings = cap_native.get_model_settings()
    assert settings["native_web_fetch"] is True
    assert settings["web_fetch_config"]["allowed_domains"] == ["example.com"]
    assert settings["web_fetch_config"]["max_uses"] == 3

    # 2. Local fallback
    cap_local = WebFetch(allowed_domains=["docs.python.org"], local=True, native=False)
    tools = cap_local.get_tools()
    assert len(tools) == 1
    assert tools[0].name == "web_fetch"
    assert cap_local.get_model_settings() == {}

    # 3. Custom callable local fallback
    def custom_fetch(url: str) -> str:
        return f"content for {url}"

    cap_custom = WebFetch(local=custom_fetch)
    custom_tools = cap_custom.get_tools()
    assert len(custom_tools) == 1
    assert custom_tools[0].name == "custom_fetch"


def test_thinking_capability_and_parts() -> None:
    from devops_cli.ai.agents import (
        Thinking,
        ThinkingPart,
    )

    part = ThinkingPart(content="Step-by-step reasoning...", encrypted_content="enc_123")
    assert part.content == "Step-by-step reasoning..."
    assert part.encrypted_content == "enc_123"
    assert part.part_kind == "thinking"

    thinking_cap = Thinking(
        effort="high",
        budget_tokens=8192,
        include_thoughts=True,
        include_encrypted_content=True,
    )

    prompt_additions = thinking_cap.get_system_prompt_additions()
    assert "Thinking capability is enabled (effort=high)." in prompt_additions[0]

    settings = thinking_cap.get_model_settings()
    assert settings["thinking"] == "high"
    assert settings["budget_tokens"] == 8192
    assert settings["include_thoughts"] is True
    assert settings["include_encrypted_content"] is True
    assert settings["xai_include_encrypted_content"] is True


def test_native_tool_all_variants() -> None:
    from pydantic import BaseModel

    from devops_cli.ai.agents.pydantic_agent import (
        CodeExecutionTool,
        MCPServerTool,
        NativeTool,
        WebFetchTool,
        WebSearchTool,
    )

    # 1. WebSearchTool
    nt_search = NativeTool(tool=WebSearchTool(max_uses=5, search_context_size="large"))
    assert nt_search.get_model_settings()["native_web_search"] is True
    assert "Provider-native web search" in nt_search.get_system_prompt_additions()[0]

    # 2. WebFetchTool
    nt_fetch = NativeTool(tool=WebFetchTool(max_uses=3, enable_citations=True))
    assert nt_fetch.get_model_settings()["native_web_fetch"] is True
    assert "Provider-native web fetch" in nt_fetch.get_system_prompt_additions()[0]

    # 3. CodeExecutionTool
    nt_code = NativeTool(tool=CodeExecutionTool())
    assert nt_code.get_model_settings()["native_code_execution"] is True
    assert "sandboxed code execution" in nt_code.get_system_prompt_additions()[0]

    # 4. MCPServerTool
    nt_mcp = NativeTool(tool=MCPServerTool(id="mcp-srv", url="http://localhost:8080"))
    assert nt_mcp.get_model_settings()["native_mcp_server"] is True
    assert "Provider-native MCP server" in nt_mcp.get_system_prompt_additions()[0]

    # 5. Generic BaseModel
    class GenericTool(BaseModel):
        foo: str = "bar"

    nt_gen = NativeTool(tool=GenericTool())
    assert nt_gen.get_model_settings()["native_tool"]["foo"] == "bar"
    assert nt_gen.get_system_prompt_additions() == []


def test_mcp_capability_variants() -> None:
    from devops_cli.ai.agents.pydantic_agent import (
        MCP,
        MCPServerTool,
        Tool,
    )

    # 1. Native MCPServerTool
    mcp_native = MCP(native=MCPServerTool(id="srv-1", url="http://example.com"))
    settings = mcp_native.get_model_settings()
    assert settings["native_mcp_server"] is True
    assert settings["mcp_server_config"]["id"] == "srv-1"
    native_additions = mcp_native.get_system_prompt_additions()
    assert len(native_additions) > 0
    assert native_additions[0].startswith("Model Context Protocol (MCP) capability active")

    # 2. Native with URL
    mcp_url = MCP(url="http://localhost:3000", native=True)
    assert mcp_url.get_model_settings()["native_mcp_server"] is True
    url_additions = mcp_url.get_system_prompt_additions()
    assert len(url_additions) > 0
    assert url_additions[0].startswith("Model Context Protocol (MCP) capability active")

    # 3. Local tools list
    def dummy_fn() -> str:
        return "dummy"

    t = Tool.from_function(dummy_fn)
    mcp_local_list = MCP(local=[t])
    assert len(mcp_local_list.get_tools()) == 1

    # 4. Local object with get_tools
    class CustomLocal:
        def get_tools(self) -> list[Any]:
            return [dummy_fn]

    mcp_custom = MCP(local=CustomLocal())
    assert len(mcp_custom.get_tools()) == 1

    # 5. Local is False
    mcp_no_local = MCP(local=False)
    assert mcp_no_local.get_tools() == []


def test_web_search_and_web_fetch_full_branches() -> None:
    from devops_cli.ai.agents.pydantic_agent import (
        Tool,
        WebFetch,
        WebFetchTool,
        WebSearch,
    )

    # WebSearch native=True, local=False
    ws_native = WebSearch(native=True, local=False)
    assert ws_native.get_model_settings()["native_web_search"] is True
    assert "Provider-native web search" in ws_native.get_system_prompt_additions()[0]
    assert ws_native.get_tools() == []

    # WebSearch local=Tool
    def search_fn(q: str) -> str:
        return f"result: {q}"

    ws_tool = WebSearch(native=False, local=Tool.from_function(search_fn))
    assert len(ws_tool.get_tools()) == 1
    assert "Local web search" in ws_tool.get_system_prompt_additions()[0]

    # WebSearch local=list
    ws_list = WebSearch(native=False, local=[search_fn])
    assert len(ws_list.get_tools()) == 1

    # WebFetch native=WebFetchTool, local=False
    wf_tool_obj = WebFetchTool(allowed_domains=["example.com"], max_uses=2)
    wf_native = WebFetch(native=wf_tool_obj, local=False)
    assert wf_native.get_model_settings()["native_web_fetch"] is True
    assert "Provider-native web fetch" in wf_native.get_system_prompt_additions()[0]

    # WebFetch native=True with domains
    wf_domains = WebFetch(
        native=True, allowed_domains=["example.com"], blocked_domains=["evil.com"], local=False
    )
    settings = wf_domains.get_model_settings()
    assert settings["web_fetch_config"]["allowed_domains"] == ["example.com"]
    assert settings["web_fetch_config"]["blocked_domains"] == ["evil.com"]

    # WebFetch local=Tool
    def fetch_fn(u: str) -> str:
        return f"body: {u}"

    wf_tool = WebFetch(native=False, local=Tool.from_function(fetch_fn))
    assert len(wf_tool.get_tools()) == 1
    assert "Local web fetch" in wf_tool.get_system_prompt_additions()[0]

    # WebFetch local=list
    wf_list = WebFetch(native=False, local=[fetch_fn])
    assert len(wf_list.get_tools()) == 1


def test_native_agent_exports_and_models() -> None:
    """Verify native pydantic_ai Agent types are re-exported and accessible."""
    from devops_cli.ai.agents import (
        AbstractAgent,
        Agent,
        AgentModelSettings,
        AgentRun,
        AgentRunResult,
        EndStrategy,
        InstrumentationSettings,
    )
    from devops_cli.ai.agents.pydantic_agent import (
        CallToolsNode,
        EventStreamHandler,
        EventStreamProcessor,
        ModelRequestNode,
        NativeToolFunc,
        ParallelExecutionMode,
        ToolsPrepareFunc,
        UserPromptNode,
    )

    assert Agent is not None
    assert AbstractAgent is not None
    assert AgentRun is not None
    assert AgentRunResult is not None
    assert AgentModelSettings is not None
    assert InstrumentationSettings is not None
    assert EndStrategy is not None
    assert CallToolsNode is not None
    assert EventStreamHandler is not None
    assert EventStreamProcessor is not None
    assert ModelRequestNode is not None
    assert NativeToolFunc is not None
    assert ToolsPrepareFunc is not None
    assert UserPromptNode is not None
    assert ParallelExecutionMode is not None


def test_resolve_pydantic_ai_model() -> None:
    """Verify resolve_pydantic_ai_model correctly handles Ollama, TestModel, and models."""
    from pydantic_ai.models.ollama import OllamaModel
    from pydantic_ai.models.test import TestModel

    from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model
    from devops_cli.config.settings import Settings

    # 1. Test model string
    m_test = resolve_pydantic_ai_model("test")
    assert isinstance(m_test, TestModel)

    # 2. Existing Model instance passed directly
    existing = TestModel()
    assert resolve_pydantic_ai_model(existing) is existing

    # 3. None model returns None
    assert resolve_pydantic_ai_model(None) is None

    # 4. Ollama model resolution with settings
    custom_settings = Settings()
    custom_settings.ai.ollama_urls = ["http://my-ollama-cluster:11434"]
    m_ollama = resolve_pydantic_ai_model("ollama:qwen2.5-coder:latest", settings=custom_settings)
    assert isinstance(m_ollama, OllamaModel)
    assert m_ollama.model_name == "qwen2.5-coder:latest"
    assert "my-ollama-cluster" in str(m_ollama.provider.base_url)


def test_create_pydantic_ai_agent_native_execution() -> None:
    """Verify create_pydantic_ai_agent constructs native Agent and supports run_sync with TestModel."""
    from pydantic_ai.agent import Agent
    from pydantic_ai.models.test import TestModel

    from devops_cli.ai.pydantic_ai_bridge import create_pydantic_ai_agent
    from devops_cli.ai.review_schema import ReviewResult

    agent = create_pydantic_ai_agent(
        model_name=TestModel(custom_output_args={"summary": "Automated code review passed"}),
        system_prompt="You are a reviewer.",
        output_type=ReviewResult,
    )
    assert isinstance(agent, Agent)
    assert agent.output_type is ReviewResult

    # Run native run_sync
    run_res = agent.run_sync("Review this diff")
    assert run_res.output.summary == "Automated code review passed"
    assert run_res.usage.requests >= 1


def test_pydantic_agent_native_parity() -> None:
    """Verify PydanticAgent supports output_type, output_json_schema, run_sync, and decorators."""
    from unittest.mock import MagicMock

    from devops_cli.ai.agents.agent import PydanticAgent
    from devops_cli.ai.review_schema import ReviewResult

    mock_client = MagicMock()
    mock_client.chat_messages.return_value = '{"summary": "Parity test passed"}'
    mock_client.chat_messages_stream.return_value = iter(["Parity ", "passed"])

    agent = PydanticAgent[ReviewResult](
        client=mock_client,
        name="ParityAgent",
        output_type=ReviewResult,
    )

    assert agent.output_type is ReviewResult
    assert isinstance(agent.output_json_schema, dict)
    assert "properties" in agent.output_json_schema

    # Decorator parity
    @agent.system_prompt
    def dynamic_inst() -> str:
        return "Always check boundaries"

    assert dynamic_inst in agent._dynamic_system_prompts

    # run_sync execution
    resp = agent.run_sync("Check security")
    assert resp.content == '{"summary": "Parity test passed"}'
    assert resp.output == resp.data if resp.data is not None else resp.content

    # run_stream_sync execution
    tokens = list(agent.run_stream_sync("Check stream"))
    assert "".join(tokens) == "Parity passed"

    # to_cli execution
    cli_out = agent.to_cli_sync("Run CLI prompt")
    assert cli_out == str(resp.output)


def test_agent_response_output_and_from_run_result() -> None:
    """Verify AgentResponse.output and AgentResponse.from_run_result adaptation."""
    from pydantic_ai.agent import Agent
    from pydantic_ai.models.test import TestModel

    from devops_cli.ai.agents.models import AgentResponse

    # 1. Output property fallback
    resp_text = AgentResponse(content="Simple text")
    assert resp_text.output == "Simple text"

    resp_data = AgentResponse(content="{}", data={"key": "val"})
    assert resp_data.output == {"key": "val"}

    # 2. Adaptation from native AgentRunResult
    native_agent = Agent(TestModel(custom_output_text="From native run"))
    native_run_res = native_agent.run_sync("Hi")

    adapted = AgentResponse.from_run_result(native_run_res)
    assert adapted.content == "From native run"
    assert adapted.output == "From native run"
    assert adapted.usage.input_tokens == native_run_res.usage.input_tokens
    assert adapted.usage.output_tokens == native_run_res.usage.output_tokens

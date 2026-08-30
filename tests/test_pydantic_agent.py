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

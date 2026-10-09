"""Test suite for native Pydantic AI Durable Execution integration."""

from __future__ import annotations

from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities.abstract import AbstractCapability
from pydantic_ai.durable_exec import BaseDurabilityCapability
from pydantic_ai.messages import AgentStreamEvent, FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.models.test import TestModel

from devops_cli.ai.agents.persistence import InMemoryStepStore, SqliteStepStore, StepPersistence
from devops_cli.ai.durable import (
    LocalDurabilityCapability,
    create_durable_pydantic_agent,
    get_available_durable_engines,
    is_dbos_available,
    is_prefect_available,
    is_temporal_available,
    resolve_durability_capability,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_DURABLE_ENGINE,
    DEFAULT_AI_DURABLE_STORE_PATH,
    DEFAULT_AI_DURABLE_TASK_QUEUE,
    DEFAULT_AI_DURABLE_WORKFLOW_PREFIX,
)
from devops_cli.config.settings import AIDurableConfig, Settings
from devops_cli.exceptions import ConfigurationError


def test_native_durable_reexports_and_availability_helpers() -> None:
    """Verify BaseDurabilityCapability re-export and boolean availability checkers."""
    from devops_cli.ai import BaseDurabilityCapability as ExportedBaseDurability
    from devops_cli.ai import LocalDurabilityCapability as ExportedLocalDurability
    from devops_cli.ai import resolve_durability_capability as exported_resolve

    assert ExportedBaseDurability is BaseDurabilityCapability
    assert ExportedLocalDurability is LocalDurabilityCapability
    assert exported_resolve is resolve_durability_capability

    assert isinstance(is_temporal_available(), bool)
    assert isinstance(is_dbos_available(), bool)
    assert isinstance(is_prefect_available(), bool)

    engines = get_available_durable_engines()
    assert isinstance(engines, dict)
    assert "local" in engines
    assert "sqlite" in engines
    assert "memory" in engines
    assert "temporal" in engines
    assert "dbos" in engines
    assert "prefect" in engines
    assert engines["local"] is True
    assert engines["sqlite"] is True
    assert engines["memory"] is True


def test_local_durability_capability_init_and_bind() -> None:
    """Verify LocalDurabilityCapability initialization, validation, and agent binding."""
    store = InMemoryStepStore()
    model_a = TestModel(custom_output_text="Model A")
    model_b = TestModel(custom_output_text="Model B")

    cap = LocalDurabilityCapability(
        name="test_worker",
        store=store,
        models={"extra_model": model_b},
    )

    assert cap.name == "test_worker"
    assert cap.engine_name == "Local"
    assert isinstance(cap, BaseDurabilityCapability)
    assert isinstance(cap, AbstractCapability)

    agent = Agent(model=model_a, name="durable_agent")
    bound_cap = cap.for_agent(agent)

    assert bound_cap.name == "test_worker"
    assert bound_cap._agent is agent


def test_local_durability_capability_unnamed_agent_raises() -> None:
    """Verify binding without capability or agent name raises UserError."""
    from pydantic_ai.exceptions import UserError

    cap = LocalDurabilityCapability()
    agent = Agent(model=TestModel())  # Unnamed agent

    with pytest.raises(UserError, match="unique `name`"):
        cap.for_agent(agent)


def test_local_durability_capability_model_resolution() -> None:
    """Verify model registry lookup and resolution across durable boundaries."""
    default_model = TestModel(custom_output_text="default")
    extra_model = TestModel(custom_output_text="extra")

    cap = LocalDurabilityCapability(
        name="test_durable",
        models={"custom_llm": extra_model},
    )
    agent = Agent(model=default_model, name="agent_with_models")
    bound_cap = cap.for_agent(agent)

    from pydantic_ai.models import ModelResolutionContext

    ctx = ModelResolutionContext[Any](agent=agent, deps=None)

    # Resolution of registered extra model
    resolved_extra = bound_cap.resolve_model_id_sync(cast(Any, ctx), model_id="custom_llm")
    assert resolved_extra is extra_model

    # Resolution of unknown model defers
    resolved_unknown = bound_cap.resolve_model_id_sync(cast(Any, ctx), model_id="unknown_model")
    assert resolved_unknown is None


@pytest.mark.asyncio
async def test_local_durability_capability_step_recording_and_execution() -> None:
    """Verify step recording and execution with a LocalDurabilityCapability."""
    store = InMemoryStepStore()
    cap = LocalDurabilityCapability(name="test_runner", store=store)

    model = TestModel(custom_output_text="Durable greeting")
    agent = Agent(
        model=model,
        name="greeter_agent",
        capabilities=[cap],
    )

    result = await agent.run("Hello durable agent!")
    assert result.output == "Durable greeting"

    # Verify steps recorded in store
    steps = cap.get_steps()
    assert len(steps) >= 1
    latest = cap.get_latest_step()
    assert latest is not None


def test_local_durability_capability_with_sqlite_store(tmp_path: Path) -> None:
    """Verify LocalDurabilityCapability with persistent SqliteStepStore."""
    db_file = tmp_path / "runs" / "test_durable.db"
    store = SqliteStepStore(db_path=str(db_file))

    cap1 = LocalDurabilityCapability(name="sqlite_worker", store=store)
    step1 = cap1.save_step(kind="checkpoint", payload={"state": "initialized"})

    assert step1.kind == "checkpoint"
    assert step1.payload == {"state": "initialized"}

    # Reconnect via a second capability instance pointing to the same sqlite store
    store2 = SqliteStepStore(db_path=str(db_file))
    cap2 = LocalDurabilityCapability(name="sqlite_worker_2", store=store2)
    steps = cap2.get_steps(run_id=cap1.current_run_id)

    assert len(steps) == 1
    assert steps[0].payload == {"state": "initialized"}


def test_resolve_durability_capability_local_engines(tmp_path: Path) -> None:
    """Verify resolve_durability_capability for memory, sqlite, and local engines."""
    cap_mem = resolve_durability_capability("memory", name="mem_agent")
    assert isinstance(cap_mem, LocalDurabilityCapability)
    assert isinstance(cap_mem.store, InMemoryStepStore)
    assert cap_mem.name == "mem_agent"

    db_path = tmp_path / "durable.db"
    cap_sqlite = resolve_durability_capability("sqlite", name="sql_agent", store_path=str(db_path))
    assert isinstance(cap_sqlite, LocalDurabilityCapability)
    assert isinstance(cap_sqlite.store, SqliteStepStore)
    assert cap_sqlite.name == "sql_agent"

    cap_local = resolve_durability_capability("local", name="local_agent")
    assert isinstance(cap_local, LocalDurabilityCapability)


def test_resolve_durability_capability_missing_external_engines() -> None:
    """Verify informative ConfigurationError when requesting uninstalled external engines."""
    if not is_temporal_available():
        with pytest.raises(ConfigurationError, match=r"Temporal.*pydantic-ai-slim\[temporal\]"):
            resolve_durability_capability("temporal")

    if not is_dbos_available():
        with pytest.raises(ConfigurationError, match=r"DBOS.*pydantic-ai-slim\[dbos\]"):
            resolve_durability_capability("dbos")

    if not is_prefect_available():
        with pytest.raises(ConfigurationError, match=r"Prefect.*pydantic-ai-slim\[prefect\]"):
            resolve_durability_capability("prefect")

    with pytest.raises(ConfigurationError, match="Unknown durable execution engine"):
        resolve_durability_capability("unsupported_backend")


@pytest.mark.asyncio
async def test_create_durable_pydantic_agent_helper() -> None:
    """Verify create_durable_pydantic_agent factory function."""
    agent = create_durable_pydantic_agent(
        model=TestModel(custom_output_text="Durable response"),
        name="durable_worker",
        engine="memory",
    )

    result = await agent.run("Perform durable audit")
    assert result.output == "Durable response"

    # Bound durability capability is accessible via BaseDurabilityCapability.from_agent
    bound_cap = BaseDurabilityCapability.from_agent(agent)
    assert bound_cap is not None
    assert isinstance(bound_cap, LocalDurabilityCapability)


def test_step_persistence_abstract_capability_conformance() -> None:
    """Verify StepPersistence adheres to AbstractCapability and bridges to LocalDurabilityCapability."""
    legacy_store = InMemoryStepStore()
    persistence = StepPersistence(store=legacy_store, name="legacy_persistence")

    # Adheres to AbstractCapability protocol
    assert isinstance(persistence, AbstractCapability)

    agent = Agent(model=TestModel(), name="agent_persisted")
    bound = persistence.for_agent(agent)
    assert bound is not None

    # Bridge to LocalDurabilityCapability
    durable_cap = persistence.to_durability_capability()
    assert isinstance(durable_cap, LocalDurabilityCapability)
    assert durable_cap.store is legacy_store


def test_ai_durable_config_settings() -> None:
    """Verify AIDurableConfig model and defaults."""
    cfg = AIDurableConfig()
    assert cfg.engine == DEFAULT_AI_DURABLE_ENGINE
    assert cfg.store_path == DEFAULT_AI_DURABLE_STORE_PATH
    assert cfg.task_queue == DEFAULT_AI_DURABLE_TASK_QUEUE
    assert cfg.workflow_id_prefix == DEFAULT_AI_DURABLE_WORKFLOW_PREFIX

    custom = AIDurableConfig(
        engine="temporal",
        store_path=Path("/var/run/custom.db"),
        task_queue="custom-tasks",
        workflow_id_prefix="custom-wf-",
    )
    assert custom.engine == "temporal"
    assert custom.store_path == Path("/var/run/custom.db")
    assert custom.task_queue == "custom-tasks"
    assert custom.workflow_id_prefix == "custom-wf-"


def test_local_durability_capability_checkpoint() -> None:
    """Verify checkpointing with label and metadata."""
    cap = LocalDurabilityCapability(name="checkpointer")
    step = cap.checkpoint("milestone_1", {"items": 42})
    assert step.kind == "checkpoint"
    assert step.payload["label"] == "milestone_1"
    assert step.payload["items"] == 42

    steps = cap.get_steps()
    assert len(steps) == 1
    assert steps[0].kind == "checkpoint"


@pytest.mark.asyncio
async def test_local_durability_capability_tool_execution() -> None:
    """Verify tool execution tracking (before_tool_execute, after_tool_execute)."""
    store = InMemoryStepStore()
    cap = LocalDurabilityCapability(name="tool_agent", store=store)

    agent = Agent(
        model=TestModel(custom_output_text="Result with tool"),
        name="tool_worker",
        capabilities=[cap],
    )

    @agent.tool_plain
    def calculate_sum(a: int, b: int) -> int:
        return a + b

    # Test before_tool_execute and after_tool_execute directly
    from types import SimpleNamespace

    mock_ctx = SimpleNamespace(agent=agent)
    mock_call = SimpleNamespace(tool_name="calculate_sum")
    mock_def = SimpleNamespace(name="calculate_sum")

    args = await cap.before_tool_execute(
        mock_ctx, call=mock_call, tool_def=mock_def, args={"a": 1, "b": 2}
    )  # type: ignore[arg-type]
    assert args == {"a": 1, "b": 2}

    res = await cap.after_tool_execute(
        mock_ctx, call=mock_call, tool_def=mock_def, args=args, result=3
    )  # type: ignore[arg-type]
    assert res == 3

    steps = cap.get_steps()
    kinds = [s.kind for s in steps]
    assert "tool_call" in kinds
    assert "tool_result" in kinds


@pytest.mark.asyncio
async def test_local_durability_delivers_run_events_and_leaves_toolsets_unwrapped() -> None:
    """Verify a run hands its tool events to the async handler and calls the tool unwrapped."""
    events: list[AgentStreamEvent] = []

    async def handler(ctx: RunContext[Any], stream: AsyncIterable[AgentStreamEvent]) -> None:
        async for event in stream:
            events.append(event)

    cap = LocalDurabilityCapability(name="streamer", event_stream_handler=handler)
    agent = Agent(model=TestModel(), name="stream_worker", capabilities=[cap])

    @agent.tool_plain
    def calculate_sum(a: int, b: int) -> int:
        return a + b

    await agent.run("Add two numbers")
    bound = LocalDurabilityCapability.from_agent(agent)

    assert bound is not None
    assert {type(e) for e in events} >= {FunctionToolCallEvent, FunctionToolResultEvent}
    assert all(bound.get_wrapper_toolset(ts) is None for ts in agent.toolsets)
    assert {"tool_call", "tool_result"} <= {s.kind for s in cap.get_steps()}


def test_resolve_durability_capability_mocked_external_engines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify resolve_durability_capability branch when external drivers are available."""
    import sys
    from unittest.mock import MagicMock

    # Mock Temporal
    mock_temporal_mod = MagicMock()
    mock_temporal_durability = MagicMock(return_value="mock_temporal_instance")
    mock_temporal_mod.TemporalDurability = mock_temporal_durability
    monkeypatch.setitem(sys.modules, "temporalio", MagicMock())
    monkeypatch.setitem(sys.modules, "pydantic_ai.durable_exec.temporal", mock_temporal_mod)
    monkeypatch.setattr("devops_cli.ai.durable.is_temporal_available", lambda: True)

    temporal_cap = resolve_durability_capability("temporal", name="wf")
    assert cast(Any, temporal_cap) == "mock_temporal_instance"

    # Mock DBOS
    mock_dbos_mod = MagicMock()
    mock_dbos_durability = MagicMock(return_value="mock_dbos_instance")
    mock_dbos_mod.DBOSDurability = mock_dbos_durability
    monkeypatch.setitem(sys.modules, "dbos", MagicMock())
    monkeypatch.setitem(sys.modules, "pydantic_ai.durable_exec.dbos", mock_dbos_mod)
    monkeypatch.setattr("devops_cli.ai.durable.is_dbos_available", lambda: True)

    dbos_cap = resolve_durability_capability("dbos", name="wf_dbos")
    assert cast(Any, dbos_cap) == "mock_dbos_instance"

    # Mock Prefect
    mock_prefect_mod = MagicMock()
    mock_prefect_durability = MagicMock(return_value="mock_prefect_instance")
    mock_prefect_mod.PrefectDurability = mock_prefect_durability
    monkeypatch.setitem(sys.modules, "prefect", MagicMock())
    monkeypatch.setitem(sys.modules, "pydantic_ai.durable_exec.prefect", mock_prefect_mod)
    monkeypatch.setattr("devops_cli.ai.durable.is_prefect_available", lambda: True)

    prefect_cap = resolve_durability_capability("prefect", name="wf_prefect")
    assert cast(Any, prefect_cap) == "mock_prefect_instance"


def test_create_durable_pydantic_agent_extended_options() -> None:
    """Verify create_durable_pydantic_agent with string model, custom capabilities, and system prompt."""
    extra_cap = StepPersistence(name="extra_persistence")
    agent = create_durable_pydantic_agent(
        model="test",
        name="configured_worker",
        engine="memory",
        capabilities=[extra_cap],
        system_prompt="You are a durable automation engineer.",
    )
    assert agent.name == "configured_worker"
    from pydantic_ai.capabilities.abstract import leaf_capabilities

    leaves = leaf_capabilities(agent.root_capability)
    assert len(leaves) >= 2


def test_durable_agent_does_not_swallow_a_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a model its configured endpoint cannot serve raises instead of being passed on.

    Handed the bare string, the Agent would infer it against the vendor's public endpoint and
    send the prompts there rather than to the malformed `ai.api_base_url`.
    """
    from devops_cli.ai import pydantic_ai_bridge

    settings = Settings()
    settings.ai.provider = "openai"
    settings.ai.api_base_url = "localhost:8000/v1"
    monkeypatch.setattr(pydantic_ai_bridge, "_is_testing_mode_active", lambda: False)
    monkeypatch.setattr(pydantic_ai_bridge, "load_settings", lambda: settings)
    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _settings: "sk-test")

    with pytest.raises(ConfigurationError, match=r"^ai\.api_base_url cannot serve model"):
        create_durable_pydantic_agent("openai:gpt-4o", engine="memory")


def test_durable_store_opens_under_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With DEVOPS_CLI_DATA_DIR set to tmp_path, the durable store opens under it and leaves
    nothing in the working directory (#1036)."""
    from devops_cli.config.settings import reset_settings_cache

    custom_data = tmp_path / "custom_data"
    custom_data.mkdir()
    (Path.cwd() / ".data" / "durable_runs.db").unlink(missing_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(custom_data))
    reset_settings_cache()

    cap = resolve_durability_capability("local", name="isolated_agent")
    assert isinstance(cap, LocalDurabilityCapability)
    assert isinstance(cap.store, SqliteStepStore)

    # Explicit store_path is used as given
    explicit_file = tmp_path / "explicit.db"
    explicit_cap = resolve_durability_capability(
        "local", name="explicit_agent", store_path=explicit_file
    )
    assert isinstance(explicit_cap.store, SqliteStepStore)

    assert (
        Path(cap.store.db_path).resolve().is_relative_to(custom_data.resolve()),
        (Path.cwd() / ".data" / "durable_runs.db").exists(),
        Path(explicit_cap.store.db_path).resolve(),
    ) == (True, False, explicit_file.resolve())

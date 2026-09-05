"""Native Pydantic AI durable execution subsystem, local step persistence, and engine bridges."""

from __future__ import annotations

import inspect
import json
import re
import sqlite3
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.agent import EventStreamHandler
from pydantic_ai.agent.abstract import AbstractAgent
from pydantic_ai.capabilities.abstract import AbstractCapability
from pydantic_ai.durable_exec._base import BaseDurabilityCapability
from pydantic_ai.durable_exec._runtime_toolsets import RuntimeToolsetKind
from pydantic_ai.messages import AgentStreamEvent
from pydantic_ai.models import KnownModelName, Model, ModelRequestContext, ModelResolutionContext
from pydantic_ai.tools import AgentDepsT, RunContext
from pydantic_ai.toolsets import AbstractToolset, WrapperToolset

from devops_cli.config.defaults import (
    DEFAULT_AI_DURABLE_ENGINE,
    DEFAULT_AI_DURABLE_STORE_PATH,
    DEFAULT_AI_DURABLE_TASK_QUEUE,
    DEFAULT_AI_DURABLE_WORKFLOW_PREFIX,
)
from devops_cli.exceptions import ConfigurationError
from devops_cli.telemetry.tracer import trace_span

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelResponse


# ── Step Persistence Data Models & Storage Protocol ───────────────────────────


class StepRecord(BaseModel):
    """Represents a single persisted execution step or node in an agent run."""

    step_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    run_id: str
    step_number: int = 0
    kind: str  # "model_request", "tool_call", "tool_result", "checkpoint", "error", "run_start", "run_end"
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


@runtime_checkable
class StepStore(Protocol):
    """Storage backend protocol for persisting and retrieving agent step records."""

    def save_step(self, step: StepRecord) -> None: ...
    def get_steps(self, run_id: str) -> list[StepRecord]: ...
    def get_latest_step(self, run_id: str) -> StepRecord | None: ...
    def fork_run(
        self, source_run_id: str, new_run_id: str, up_to_step: int | None = None
    ) -> list[StepRecord]: ...


class InMemoryStepStore(BaseModel):
    """In-memory step storage implementation."""

    steps_by_run: dict[str, list[StepRecord]] = Field(default_factory=dict)

    def save_step(self, step: StepRecord) -> None:
        """Persist a single step record."""
        if step.run_id not in self.steps_by_run:
            self.steps_by_run[step.run_id] = []
        if step.step_number == 0:
            step.step_number = len(self.steps_by_run[step.run_id]) + 1
        self.steps_by_run[step.run_id].append(step)

    def get_steps(self, run_id: str) -> list[StepRecord]:
        """Retrieve all step records for a run in sequence."""
        return list(self.steps_by_run.get(run_id, []))

    def get_latest_step(self, run_id: str) -> StepRecord | None:
        """Retrieve the most recent step record for a run."""
        steps = self.steps_by_run.get(run_id, [])
        return steps[-1] if steps else None

    def fork_run(
        self, source_run_id: str, new_run_id: str, up_to_step: int | None = None
    ) -> list[StepRecord]:
        """Branch execution from a source run up to a specified step number."""
        source_steps = self.get_steps(source_run_id)
        if up_to_step is not None:
            source_steps = [s for s in source_steps if s.step_number <= up_to_step]

        forked_steps = [
            StepRecord(
                step_id=uuid.uuid4().hex[:12],
                run_id=new_run_id,
                step_number=idx + 1,
                kind=s.kind,
                payload=dict(s.payload),
                timestamp=time.time(),
            )
            for idx, s in enumerate(source_steps)
        ]
        self.steps_by_run[new_run_id] = forked_steps
        return forked_steps


class SqliteStepStore:
    """SQLite-backed persistent step storage implementation."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn: sqlite3.Connection | None = None
        if db_path != ":memory:":
            if ".." in str(db_path):
                raise ValueError(f"Directory traversal not permitted in db_path: {db_path}")
            path_obj = Path(db_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(path_obj.resolve())
        else:
            self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        assert self._conn is not None
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_steps (
                    step_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_steps_run_id ON agent_steps(run_id, step_number)"
            )

    def save_step(self, step: StepRecord) -> None:
        assert self._conn is not None
        if step.step_number == 0:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM agent_steps WHERE run_id = ?", (step.run_id,))
            count = cur.fetchone()[0]
            step.step_number = count + 1

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO agent_steps (step_id, run_id, step_number, kind, payload, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    step.step_id,
                    step.run_id,
                    step.step_number,
                    step.kind,
                    json.dumps(step.payload),
                    step.timestamp,
                ),
            )

    def get_steps(self, run_id: str) -> list[StepRecord]:
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute(
            "SELECT step_id, run_id, step_number, kind, payload, timestamp FROM agent_steps WHERE run_id = ? ORDER BY step_number ASC",
            (run_id,),
        )
        rows = cur.fetchall()
        return [
            StepRecord(
                step_id=r[0],
                run_id=r[1],
                step_number=r[2],
                kind=r[3],
                payload=json.loads(r[4]),
                timestamp=r[5],
            )
            for r in rows
        ]

    def get_latest_step(self, run_id: str) -> StepRecord | None:
        steps = self.get_steps(run_id)
        return steps[-1] if steps else None

    def fork_run(
        self, source_run_id: str, new_run_id: str, up_to_step: int | None = None
    ) -> list[StepRecord]:
        source_steps = self.get_steps(source_run_id)
        if up_to_step is not None:
            source_steps = [s for s in source_steps if s.step_number <= up_to_step]

        forked: list[StepRecord] = []
        for idx, s in enumerate(source_steps):
            forked_step = StepRecord(
                step_id=uuid.uuid4().hex[:12],
                run_id=new_run_id,
                step_number=idx + 1,
                kind=s.kind,
                payload=dict(s.payload),
                timestamp=time.time(),
            )
            self.save_step(forked_step)
            forked.append(forked_step)
        return forked

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        conn = getattr(self, "_conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._conn = None

    def __del__(self) -> None:
        self.close()


_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:token|secret|password|passwd|api[_-]?key|credential|private[_-]?key|auth)",
    re.IGNORECASE,
)


def _mask_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive keys and credentials in step payloads."""
    if isinstance(data, dict):
        masked: dict[str, Any] = {}
        for k, v in data.items():
            if _SENSITIVE_KEY_PATTERN.search(str(k)):
                masked[k] = "***REDACTED***"
            else:
                masked[k] = _mask_sensitive_data(v)
        return masked
    if isinstance(data, list):
        return [_mask_sensitive_data(x) for x in data]
    return data


# ── Engine Availability Checkers ──────────────────────────────────────────────


def is_temporal_available() -> bool:
    """Check whether Temporal durable execution dependencies are available."""
    try:
        import temporalio  # type: ignore[import-not-found]  # noqa: F401
        from pydantic_ai.durable_exec.temporal import TemporalDurability  # noqa: F401

        return True
    except ImportError, ModuleNotFoundError:
        return False


def is_dbos_available() -> bool:
    """Check whether DBOS durable execution dependencies are available."""
    try:
        import dbos  # type: ignore[import-not-found]  # noqa: F401
        from pydantic_ai.durable_exec.dbos import DBOSDurability  # noqa: F401

        return True
    except ImportError, ModuleNotFoundError:
        return False


def is_prefect_available() -> bool:
    """Check whether Prefect durable execution dependencies are available."""
    try:
        import prefect  # type: ignore[import-not-found]  # noqa: F401
        from pydantic_ai.durable_exec.prefect import PrefectDurability  # noqa: F401

        return True
    except ImportError, ModuleNotFoundError:
        return False


def get_available_durable_engines() -> dict[str, bool]:
    """Return dictionary of durable engines and their availability."""
    return {
        "local": True,
        "sqlite": True,
        "memory": True,
        "temporal": is_temporal_available(),
        "dbos": is_dbos_available(),
        "prefect": is_prefect_available(),
    }


# ── Local Durability Capability ───────────────────────────────────────────────


class LocalDurabilityCapability(BaseDurabilityCapability[AgentDepsT]):
    """Local, workstation-ready durability capability adhering to BaseDurabilityCapability.

    Provides step-by-step recording, model resolution, tool execution tracking, and checkpointing
    backed by SQLite or In-Memory step stores without requiring external server orchestration.
    """

    engine_name: ClassVar[str] = "Local"
    _unsupported_runtime_toolset_kinds: ClassVar[frozenset[RuntimeToolsetKind]] = frozenset()
    _durable_unit_noun: ClassVar[str] = "step"
    _durable_container_noun: ClassVar[str] = "run"

    def __init__(
        self,
        *,
        name: str | None = None,
        store: StepStore | None = None,
        models: Mapping[str, Model] | None = None,
        event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
        current_run_id: str | None = None,
    ) -> None:
        super().__init__(
            models=models,
            event_stream_handler=event_stream_handler,
            name=name,
        )
        self.store: StepStore = store if store is not None else InMemoryStepStore()
        self.current_run_id: str = current_run_id or uuid.uuid4().hex[:16]

    @property
    def in_durable_context(self) -> bool:
        """Whether execution is currently inside the local durable container."""
        return True

    def _bind_to_agent(self, agent: AbstractAgent[AgentDepsT, Any]) -> None:
        """Register local durability units on this bound capability."""
        self._agent = agent

    def _wrap_leaf_toolset(
        self, ts: AbstractToolset[AgentDepsT]
    ) -> WrapperToolset[AgentDepsT] | None:
        """Wrap dynamic or leaf toolsets with durability tracking if needed."""
        return None

    async def _dispatch_event_stream_event(
        self, ctx: RunContext[AgentDepsT], event: AgentStreamEvent
    ) -> None:
        """Deliver one workflow-side event inside the local durable boundary."""
        if self._event_stream_handler is not None:
            res = self._event_stream_handler(ctx, self._single_event_stream(event))
            if inspect.isawaitable(res):
                await res

    def resolve_model_id_sync(
        self,
        ctx: ModelResolutionContext[AgentDepsT],
        *,
        model_id: KnownModelName | str,
    ) -> Model | None:
        """Synchronously map a model-name string to its models= registry instance or None."""
        return self._models_by_id.get(model_id)

    def save_step(
        self, kind: str, payload: dict[str, Any], *, run_id: str | None = None
    ) -> StepRecord:
        """Persist a discrete step record into the active step store."""
        target_run_id = run_id or self.current_run_id
        step = StepRecord(run_id=target_run_id, kind=kind, payload=payload)
        self.store.save_step(step)
        return step

    def get_steps(self, run_id: str | None = None) -> list[StepRecord]:
        """Retrieve all recorded steps for a given run ID."""
        target_run_id = run_id or self.current_run_id
        steps = self.store.get_steps(target_run_id)
        return list(steps) if isinstance(steps, list) else []

    def get_latest_step(self, run_id: str | None = None) -> StepRecord | None:
        """Retrieve the most recent step record for a given run ID."""
        target_run_id = run_id or self.current_run_id
        return self.store.get_latest_step(target_run_id)

    def checkpoint(
        self, label: str, metadata: dict[str, Any] | None = None, *, run_id: str | None = None
    ) -> StepRecord:
        """Create a designated execution checkpoint record."""
        payload = {"label": label, **(metadata or {})}
        return self.save_step("checkpoint", payload, run_id=run_id)

    async def before_run(self, ctx: RunContext[AgentDepsT]) -> None:
        """Lifecycle hook executed prior to agent run invocation."""
        await super().before_run(ctx)
        self.save_step("run_start", {"run_id": self.current_run_id})

    async def after_run(
        self,
        ctx: RunContext[AgentDepsT],
        *,
        result: Any = None,
    ) -> Any:
        """Lifecycle hook executed upon completion of an agent run."""
        self.save_step("run_end", {"run_id": self.current_run_id})
        return result

    async def before_model_request(
        self, ctx: RunContext[AgentDepsT], request_context: ModelRequestContext
    ) -> ModelRequestContext:
        """Lifecycle hook recording model invocation parameters."""
        model_repr = getattr(request_context.model, "model_id", str(request_context.model))
        self.save_step("model_request", {"model": model_repr})
        return request_context

    async def after_model_request(
        self,
        ctx: RunContext[AgentDepsT],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        """Lifecycle hook recording model response outcomes."""
        self.save_step("model_response", {"parts": len(response.parts)})
        return response

    async def before_tool_execute(
        self,
        ctx: RunContext[AgentDepsT],
        *,
        call: Any,
        tool_def: Any,
        args: Any,
    ) -> Any:
        """Lifecycle hook recording tool execution dispatch."""
        tool_name = getattr(call, "tool_name", getattr(tool_def, "name", "tool"))
        self.save_step("tool_call", {"tool_name": tool_name})
        return args

    async def after_tool_execute(
        self,
        ctx: RunContext[AgentDepsT],
        *,
        call: Any,
        tool_def: Any,
        args: Any,
        result: Any,
    ) -> Any:
        """Lifecycle hook recording tool execution completion."""
        tool_name = getattr(call, "tool_name", getattr(tool_def, "name", "tool"))
        self.save_step("tool_result", {"tool_name": tool_name, "result": str(result)[:500]})
        return result


# ── Durability Capability Resolver ────────────────────────────────────────────


@trace_span("pydantic_ai.durable.resolve_capability")
def resolve_durability_capability(
    engine: str = "sqlite",
    *,
    name: str | None = None,
    store: StepStore | None = None,
    store_path: str | Path | None = None,
    models: Mapping[str, Model] | None = None,
    event_stream_handler: EventStreamHandler[Any] | None = None,
    **kwargs: Any,
) -> BaseDurabilityCapability[Any]:
    """Resolve and instantiate a durability capability matching the requested engine.

    Supported engines:
    - 'sqlite', 'local': Native LocalDurabilityCapability backed by SqliteStepStore.
    - 'memory': Native LocalDurabilityCapability backed by InMemoryStepStore.
    - 'temporal': TemporalDurability via temporalio driver.
    - 'dbos': DBOSDurability via dbos driver.
    - 'prefect': PrefectDurability via prefect driver.
    """
    engine_key = engine.strip().lower()

    if engine_key in ("sqlite", "local"):
        resolved_store = store
        if resolved_store is None:
            db_path = str(store_path or DEFAULT_AI_DURABLE_STORE_PATH)
            resolved_store = SqliteStepStore(db_path=db_path)
        return LocalDurabilityCapability(
            name=name,
            store=resolved_store,
            models=models,
            event_stream_handler=event_stream_handler,
            **kwargs,
        )

    if engine_key == "memory":
        resolved_store = store or InMemoryStepStore()
        return LocalDurabilityCapability(
            name=name,
            store=resolved_store,
            models=models,
            event_stream_handler=event_stream_handler,
            **kwargs,
        )

    if engine_key == "temporal":
        if not is_temporal_available():
            raise ConfigurationError(
                "Temporal durable execution requires the `temporalio` package. "
                'Install with: pip install "pydantic-ai-slim[temporal]" or uv add temporalio'
            )
        from pydantic_ai.durable_exec.temporal import TemporalDurability

        return TemporalDurability(
            name=name,
            models=models,
            event_stream_handler=event_stream_handler,
            **kwargs,
        )

    if engine_key == "dbos":
        if not is_dbos_available():
            raise ConfigurationError(
                "DBOS durable execution requires the `dbos` package. "
                'Install with: pip install "pydantic-ai-slim[dbos]" or uv add dbos'
            )
        from pydantic_ai.durable_exec.dbos import DBOSDurability

        return DBOSDurability(
            name=name,
            models=models,
            event_stream_handler=event_stream_handler,
            **kwargs,
        )

    if engine_key == "prefect":
        if not is_prefect_available():
            raise ConfigurationError(
                "Prefect durable execution requires the `prefect` package. "
                'Install with: pip install "pydantic-ai-slim[prefect]" or uv add prefect'
            )
        from pydantic_ai.durable_exec.prefect import PrefectDurability

        return PrefectDurability(
            name=name,
            models=models,
            event_stream_handler=event_stream_handler,
            **kwargs,
        )

    raise ConfigurationError(
        f"Unknown durable execution engine: {engine!r}. "
        "Supported engines: 'sqlite', 'memory', 'local', 'temporal', 'dbos', 'prefect'."
    )


# ── Durable Agent Factory ─────────────────────────────────────────────────────


@trace_span("pydantic_ai.durable.create_agent")
def create_durable_pydantic_agent(
    model: Model | KnownModelName | str | None = None,
    *,
    name: str = "durable_agent",
    engine: str = "sqlite",
    store: StepStore | None = None,
    store_path: str | Path | None = None,
    capabilities: Sequence[AbstractCapability[Any]] | None = None,
    models: Mapping[str, Model] | None = None,
    system_prompt: str | None = None,
    **kwargs: Any,
) -> Agent[Any, Any]:
    """Create a native Pydantic AI Agent bound to a durable execution capability."""
    from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model

    resolved_model: Model | KnownModelName | str | None = model
    if isinstance(resolved_model, str) and not isinstance(resolved_model, Model):
        try:
            resolved_model = resolve_pydantic_ai_model(resolved_model)
        except Exception:
            resolved_model = model

    durability_cap = resolve_durability_capability(
        engine=engine,
        name=name,
        store=store,
        store_path=store_path,
        models=models,
    )

    combined_capabilities: list[AbstractCapability[Any]] = [durability_cap]
    if capabilities:
        combined_capabilities.extend(capabilities)

    agent_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "name": name,
        "capabilities": combined_capabilities,
        **kwargs,
    }
    if system_prompt is not None:
        agent_kwargs["system_prompt"] = system_prompt

    return Agent(**agent_kwargs)


__all__ = [
    "DEFAULT_AI_DURABLE_ENGINE",
    "DEFAULT_AI_DURABLE_STORE_PATH",
    "DEFAULT_AI_DURABLE_TASK_QUEUE",
    "DEFAULT_AI_DURABLE_WORKFLOW_PREFIX",
    "BaseDurabilityCapability",
    "InMemoryStepStore",
    "LocalDurabilityCapability",
    "SqliteStepStore",
    "StepRecord",
    "StepStore",
    "create_durable_pydantic_agent",
    "get_available_durable_engines",
    "is_dbos_available",
    "is_prefect_available",
    "is_temporal_available",
    "resolve_durability_capability",
]

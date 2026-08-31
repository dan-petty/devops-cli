"""Pydantic AI Step Persistence capability for durable runs, checkpointing, and execution branching."""

from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from devops_cli.ai.agents.capabilities import BaseCapability
from devops_cli.ai.agents.context import AgentHooks, RunContext


class StepRecord(BaseModel):
    """Represents a single persisted execution step or node in an agent run."""

    step_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    run_id: str
    step_number: int = 0
    kind: str  # "model_request", "tool_call", "tool_result", "checkpoint", "error"
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
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
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
        import json

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
        import json

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

        forked = []
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


class StepPersistence(BaseCapability):
    """Capability providing step-by-step durable execution, checkpointing, and run forking."""

    id: str = "step_persistence"
    store: Any = Field(default_factory=InMemoryStepStore)
    current_run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])

    def save_step(
        self, kind: str, payload: dict[str, Any], *, run_id: str | None = None
    ) -> StepRecord:
        """Persist a discrete step record."""
        target_run_id = run_id or self.current_run_id
        step = StepRecord(run_id=target_run_id, kind=kind, payload=payload)
        self.store.save_step(step)
        return step

    def continue_run(self, run_id: str) -> list[StepRecord]:
        """Resume or inspect an existing run from storage."""
        self.current_run_id = run_id
        steps = self.store.get_steps(run_id)
        return list(steps) if isinstance(steps, list) else []

    def fork_run(
        self, new_run_id: str | None = None, *, up_to_step: int | None = None
    ) -> tuple[str, list[StepRecord]]:
        """Fork current execution into a new branch."""
        target_new_id = new_run_id or uuid.uuid4().hex[:16]
        forked_steps = self.store.fork_run(
            source_run_id=self.current_run_id,
            new_run_id=target_new_id,
            up_to_step=up_to_step,
        )
        self.current_run_id = target_new_id
        return target_new_id, list(forked_steps) if isinstance(forked_steps, list) else []

    def get_hooks(self) -> AgentHooks | None:
        """Attach automatic step recording hooks."""

        def before_tool(ctx: RunContext[Any], tool_name: str, args: dict[str, Any]) -> None:
            self.save_step("tool_call", {"tool_name": tool_name, "args": args})

        def after_tool(ctx: RunContext[Any], tool_name: str, result: Any) -> None:
            self.save_step("tool_result", {"tool_name": tool_name, "result": str(result)[:500]})

        return AgentHooks(before_tool_execute=[before_tool], after_tool_execute=[after_tool])

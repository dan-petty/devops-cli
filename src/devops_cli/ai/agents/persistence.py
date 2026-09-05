"""Pydantic AI Step Persistence capability for durable runs, checkpointing, and execution branching."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from devops_cli.ai.agents.capabilities import BaseCapability
from devops_cli.ai.agents.context import AgentHooks, RunContext
from devops_cli.ai.durable import (
    InMemoryStepStore,
    LocalDurabilityCapability,
    SqliteStepStore,
    StepRecord,
    StepStore,
    _mask_sensitive_data,
)


class StepPersistence(BaseCapability):
    """Capability providing step-by-step durable execution, checkpointing, and run forking."""

    id: str = "step_persistence"
    name: str = "step_persistence"
    store: Any = Field(default_factory=InMemoryStepStore)
    current_run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])

    def to_durability_capability(self) -> LocalDurabilityCapability:
        """Convert or bridge to a native LocalDurabilityCapability sharing the store."""
        return LocalDurabilityCapability(name=self.name, store=self.store)

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
            clean_args = _mask_sensitive_data(args)
            self.save_step("tool_call", {"tool_name": tool_name, "args": clean_args})

        def after_tool(ctx: RunContext[Any], tool_name: str, result: Any) -> None:
            clean_res = (
                _mask_sensitive_data(result)
                if isinstance(result, (dict, list))
                else str(result)[:500]
            )
            self.save_step("tool_result", {"tool_name": tool_name, "result": clean_res})

        return AgentHooks(before_tool_execute=[before_tool], after_tool_execute=[after_tool])


__all__ = [
    "InMemoryStepStore",
    "LocalDurabilityCapability",
    "SqliteStepStore",
    "StepPersistence",
    "StepRecord",
    "StepStore",
]

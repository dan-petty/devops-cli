"""Domain models and schemas for Agent Constellation Quiesce & Emergency Failover Controller."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QuiesceState(StrEnum):
    """Lifecycle state of constellation agent fleet."""

    IDLE = "idle"
    QUIESCED = "quiesced"
    FAILOVER = "failover"
    RESUMED = "resumed"


class AgentTaskType(StrEnum):
    """Classification of background agent tasks and loops."""

    REVIEW_LOOP = "review_loop"
    CRON_JOB = "cron_job"
    FILE_WATCHER = "file_watcher"
    SLOT_WORKER = "slot_worker"
    SUBAGENT = "subagent"
    BENCHMARK = "benchmark"


def _utc_now_iso() -> str:
    """Return current UTC timestamp formatted as ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _generate_snapshot_id() -> str:
    """Generate compact unique snapshot identifier."""
    return f"snap-{uuid.uuid4().hex[:8]}"


class SuspendedTask(BaseModel):
    """Model tracking state and routing for a suspended constellation task."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    task_type: AgentTaskType
    name: str
    original_provider: str
    original_model: str
    fallback_provider: str | None = None
    fallback_model: str | None = None
    status: str = "suspended"
    state_payload: dict[str, Any] = Field(default_factory=dict)
    suspended_at: str = Field(default_factory=_utc_now_iso)
    resumed_at: str | None = None


class QuiesceSnapshot(BaseModel):
    """Persisted snapshot capturing constellation state during provider outages."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    snapshot_id: str = Field(default_factory=_generate_snapshot_id)
    state: QuiesceState = QuiesceState.QUIESCED
    reason: str = "Emergency quiesce"
    quiesced_at: str = Field(default_factory=_utc_now_iso)
    tasks: list[SuspendedTask] = Field(default_factory=list)
    active_fallback: tuple[str, str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuiesceResult(BaseModel):
    """Execution result from devops ai quiesce operation."""

    success: bool
    state: QuiesceState
    reason: str
    suspended_count: int
    snapshot_path: str
    message: str
    dry_run: bool = False


class FailoverResult(BaseModel):
    """Execution result from devops ai failover operation."""

    success: bool
    state: QuiesceState
    target_provider: str
    target_model: str
    rerouted_count: int
    snapshot_path: str
    message: str
    dry_run: bool = False


class ResumeResult(BaseModel):
    """Execution result from devops ai resume operation."""

    success: bool
    state: QuiesceState
    resumed_count: int
    snapshot_path: str
    message: str
    dry_run: bool = False


class ConstellationStatus(BaseModel):
    """System status report for constellation quiesce and active fallback routing."""

    state: QuiesceState = QuiesceState.IDLE
    is_quiesced: bool = False
    reason: str = ""
    quiesced_at: str | None = None
    suspended_task_count: int = 0
    tasks: list[SuspendedTask] = Field(default_factory=list)
    active_fallback: tuple[str, str] | None = None
    snapshot_path: str = ""

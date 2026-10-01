"""Domain models and schemas for Agent Constellation Quiesce & Emergency Failover Controller."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.lang import MESSAGES


class QuiesceState(StrEnum):
    """Lifecycle state of constellation agent fleet."""

    IDLE = "idle"
    QUIESCED = "quiesced"
    FAILOVER = "failover"
    RESUMED = "resumed"


def _utc_now_iso() -> str:
    """Return current UTC timestamp formatted as ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _generate_snapshot_id() -> str:
    """Generate compact unique snapshot identifier."""
    return f"snap-{uuid.uuid4().hex[:8]}"


class QuiesceSnapshot(BaseModel):
    """The persisted constellation flag: its state, why it was set, and any recorded fallback.

    It records an operator's intent; no running task reads it.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    snapshot_id: str = Field(default_factory=_generate_snapshot_id)
    state: QuiesceState = QuiesceState.QUIESCED
    reason: str = MESSAGES.ai.default_quiesce_reason
    quiesced_at: str = Field(default_factory=_utc_now_iso)
    active_fallback: tuple[str, str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuiesceResult(BaseModel):
    """Execution result from devops ai quiesce operation."""

    success: bool
    state: QuiesceState
    reason: str
    snapshot_path: str
    message: str
    dry_run: bool = False


class FailoverResult(BaseModel):
    """Execution result from devops ai failover operation."""

    success: bool
    state: QuiesceState
    target_provider: str
    target_model: str
    snapshot_path: str
    message: str
    dry_run: bool = False


class ResumeResult(BaseModel):
    """Execution result from devops ai resume operation."""

    success: bool
    state: QuiesceState
    snapshot_path: str
    message: str
    dry_run: bool = False


class ConstellationStatus(BaseModel):
    """The constellation flag as last set: state, reason and recorded fallback route."""

    state: QuiesceState = QuiesceState.IDLE
    is_quiesced: bool = False
    reason: str = ""
    quiesced_at: str | None = None
    active_fallback: tuple[str, str] | None = None
    snapshot_path: str = ""

"""Domain models and execution state schemas for the pipeline engine."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StageStatus(StrEnum):
    """Execution status of an individual pipeline stage."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class PipelineStatus(StrEnum):
    """Aggregate execution status of a multi-stage workflow pipeline."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StageExecutionResult[ResultT](BaseModel):
    """Outcome and metadata for an individual stage execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    stage_name: str
    status: StageStatus = StageStatus.PENDING
    result: ResultT | None = None
    error: str | None = None
    duration_seconds: float = 0.0


class PipelineExecutionResult[ResultT](BaseModel):
    """Aggregated outcome of a full pipeline execution run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pipeline_name: str
    status: PipelineStatus = PipelineStatus.PENDING
    stage_results: list[StageExecutionResult[Any]] = Field(default_factory=list)
    duration_seconds: float = 0.0
    error: str | None = None

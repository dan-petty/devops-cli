"""Universal multi-stage workflow orchestration protocol for agentic AI pipelines."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, Field

from devops_cli.telemetry import record_metric, trace_span

ContextT = TypeVar("ContextT")
ContextT_contra = TypeVar("ContextT_contra", contravariant=True)
ResultT = TypeVar("ResultT")


class StageExecutionRecord(BaseModel):
    """Execution telemetry and outcome for an individual pipeline stage."""

    stage_name: str
    skipped: bool = False
    success: bool = True
    duration_seconds: float = 0.0
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class StageHook(Protocol[ContextT_contra]):
    """Lifecycle hook invoked before or after individual pipeline stages."""

    def on_stage_start(self, stage_name: str, context: ContextT_contra) -> None:
        """Called immediately before a stage executes."""
        ...

    def on_stage_complete(
        self, stage_name: str, context: ContextT_contra, record: StageExecutionRecord
    ) -> None:
        """Called immediately after a stage completes."""
        ...


class BasePipelineStage[ContextT, ResultT](ABC):
    """Abstract base class for a single distinct phase in an AI workflow pipeline."""

    def __init__(self, name: str) -> None:
        self.name = name

    def is_enabled(self, context: ContextT) -> bool:
        """Determine whether this stage should execute for the given context."""
        return True

    @abstractmethod
    def execute(self, context: ContextT) -> ResultT:
        """Execute the domain logic for this stage."""
        ...


class StagePipeline[ContextT, ResultT]:
    """Universal multi-stage workflow pipeline executing ordered stages with telemetry and error isolation."""

    def __init__(
        self,
        name: str,
        stages: Sequence[BasePipelineStage[ContextT, Any]] | None = None,
        hooks: Sequence[StageHook[ContextT]] | None = None,
    ) -> None:
        self.name = name
        self.stages: list[BasePipelineStage[ContextT, Any]] = list(stages or [])
        self.hooks: list[StageHook[ContextT]] = list(hooks or [])

    def add_stage(self, stage: BasePipelineStage[ContextT, Any]) -> None:
        """Append an execution stage to the pipeline."""
        self.stages.append(stage)

    def add_hook(self, hook: StageHook[ContextT]) -> None:
        """Register a lifecycle hook on the pipeline."""
        self.hooks.append(hook)

    def _notify_hooks_start(self, stage_name: str, context: Any) -> None:
        """Safely notify all registered hooks of stage start."""
        for h in self.hooks:
            try:
                h.on_stage_start(stage_name, context)
            except Exception:
                pass

    def _notify_hooks_complete(
        self, stage_name: str, context: Any, rec: StageExecutionRecord
    ) -> None:
        """Safely notify all registered hooks of stage completion."""
        for h in self.hooks:
            try:
                h.on_stage_complete(stage_name, context, rec)
            except Exception:
                pass

    def _run_stage_with_span(
        self,
        stage: BasePipelineStage[Any, Any],
        context: Any,
        rec: StageExecutionRecord,
        t_start: float,
    ) -> None:
        """Execute a single stage within a dedicated trace span."""
        stage_name = stage.name
        with trace_span(
            f"pipeline.{self.name}.{stage_name}",
            attributes={"stage.name": stage_name, "pipeline.name": self.name},
        ) as stage_span:
            try:
                stage.execute(context)
                rec.success = True
            except Exception as exc:
                rec.success = False
                rec.error_message = str(exc)
                stage_span.record_exception(exc)
            finally:
                rec.duration_seconds = time.perf_counter() - t_start
                stage_span.set_attribute("stage.duration_seconds", rec.duration_seconds)
                stage_span.set_attribute("stage.success", rec.success)

    def _execute_stage(
        self, stage: BasePipelineStage[Any, Any], context: Any
    ) -> StageExecutionRecord:
        """Execute a single stage lifecycle including hooks and telemetry."""
        stage_name = stage.name
        if not stage.is_enabled(context):
            return StageExecutionRecord(stage_name=stage_name, skipped=True, success=True)

        self._notify_hooks_start(stage_name, context)
        t_start = time.perf_counter()
        rec = StageExecutionRecord(stage_name=stage_name, skipped=False)
        self._run_stage_with_span(stage, context, rec, t_start)

        record_metric(
            "pipeline.stage.duration_seconds",
            rec.duration_seconds,
            attributes={"pipeline": self.name, "stage": stage_name, "success": rec.success},
        )
        self._notify_hooks_complete(stage_name, context, rec)
        return rec

    def run(self, context: ContextT) -> list[StageExecutionRecord]:
        """Execute all enabled pipeline stages in sequential order with telemetry."""
        records: list[StageExecutionRecord] = []

        with trace_span(
            f"pipeline.{self.name}",
            attributes={"pipeline.name": self.name, "pipeline.stages_count": len(self.stages)},
        ) as pipe_span:
            pipe_span.add_event("pipeline_started", {"stages": [s.name for s in self.stages]})
            for stage in self.stages:
                rec = self._execute_stage(stage, context)
                records.append(rec)

            all_ok = all(r.success for r in records if not r.skipped)
            pipe_span.set_attribute("pipeline.success", all_ok)

        return records

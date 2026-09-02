"""StagePipeline orchestration engine."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.pipeline.models import (
    PipelineExecutionResult,
    PipelineStatus,
    StageExecutionResult,
    StageStatus,
)
from devops_cli.pipeline.stage import PipelineStage
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import trace_span


class StagePipeline[ContextT, ResultT](BaseModel):
    """Orchestrates execution of an ordered sequence of stages."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "pipeline"
    stages: list[PipelineStage[ContextT, Any]] = Field(default_factory=list)
    fail_fast: bool = True

    def add_stage(self, stage: PipelineStage[ContextT, Any]) -> StagePipeline[ContextT, ResultT]:
        """Append a stage to the pipeline execution chain."""
        self.stages.append(stage)
        return self

    @trace_span("pipeline.run")
    def run(self, context: ContextT) -> PipelineExecutionResult[ResultT]:
        """Execute all configured stages sequentially and synchronously."""
        start_time = time.perf_counter()
        stage_results: list[StageExecutionResult[Any]] = []
        overall_status = PipelineStatus.SUCCESS
        error_msg: str | None = None

        for stage in self.stages:
            if not stage.should_run(context):
                stage_results.append(
                    StageExecutionResult(
                        stage_name=stage.name,
                        status=StageStatus.SKIPPED,
                    )
                )
                continue

            stage_start = time.perf_counter()
            try:
                res = stage.execute(context)
                duration = time.perf_counter() - stage_start
                stage_results.append(
                    StageExecutionResult(
                        stage_name=stage.name,
                        status=StageStatus.SUCCESS,
                        result=res,
                        duration_seconds=duration,
                    )
                )
            except Exception as exc:
                duration = time.perf_counter() - stage_start
                overall_status = PipelineStatus.FAILED
                error_msg = str(exc)
                stage_results.append(
                    StageExecutionResult(
                        stage_name=stage.name,
                        status=StageStatus.FAILED,
                        error=error_msg,
                        duration_seconds=duration,
                    )
                )
                if self.fail_fast:
                    break

        total_duration = time.perf_counter() - start_time
        GLOBAL_METRICS.increment_counter("pipeline_runs_total")
        GLOBAL_METRICS.record_histogram("pipeline_run_duration_seconds", total_duration)
        return PipelineExecutionResult(
            pipeline_name=self.name,
            status=overall_status,
            stage_results=stage_results,
            duration_seconds=total_duration,
            error=error_msg,
        )

    @trace_span("pipeline.run_async")
    async def run_async(self, context: ContextT) -> PipelineExecutionResult[ResultT]:
        """Execute all configured stages sequentially and asynchronously."""
        start_time = time.perf_counter()
        stage_results: list[StageExecutionResult[Any]] = []
        overall_status = PipelineStatus.SUCCESS
        error_msg: str | None = None

        for stage in self.stages:
            if not stage.should_run(context):
                stage_results.append(
                    StageExecutionResult(
                        stage_name=stage.name,
                        status=StageStatus.SKIPPED,
                    )
                )
                continue

            stage_start = time.perf_counter()
            try:
                res = await stage.execute_async(context)
                duration = time.perf_counter() - stage_start
                stage_results.append(
                    StageExecutionResult(
                        stage_name=stage.name,
                        status=StageStatus.SUCCESS,
                        result=res,
                        duration_seconds=duration,
                    )
                )
            except Exception as exc:
                duration = time.perf_counter() - stage_start
                overall_status = PipelineStatus.FAILED
                error_msg = str(exc)
                stage_results.append(
                    StageExecutionResult(
                        stage_name=stage.name,
                        status=StageStatus.FAILED,
                        error=error_msg,
                        duration_seconds=duration,
                    )
                )
                if self.fail_fast:
                    break

        total_duration = time.perf_counter() - start_time
        GLOBAL_METRICS.increment_counter("pipeline_runs_total")
        GLOBAL_METRICS.record_histogram("pipeline_run_duration_seconds", total_duration)
        return PipelineExecutionResult(
            pipeline_name=self.name,
            status=overall_status,
            stage_results=stage_results,
            duration_seconds=total_duration,
            error=error_msg,
        )

"""Unit tests for the Universal Multi-Stage Workflow Orchestration Pipeline."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from devops_cli.pipeline.models import PipelineStatus, StageStatus
from devops_cli.pipeline.pipeline import StagePipeline
from devops_cli.pipeline.stage import FunctionStage, PipelineStage


class SampleContext(BaseModel):
    items: list[str] = []
    metadata: dict[str, Any] = {}
    should_skip_second: bool = False


class StageOne(PipelineStage[SampleContext, str]):
    name: str = "stage_one"
    description: str = "First test stage"

    def execute(self, context: SampleContext) -> str:
        context.items.append("one")
        return "result_one"


class StageTwo(PipelineStage[SampleContext, str]):
    name: str = "stage_two"
    description: str = "Second test stage"

    def should_run(self, context: SampleContext) -> bool:
        return not context.should_skip_second

    def execute(self, context: SampleContext) -> str:
        context.items.append("two")
        return "result_two"


class AsyncStage(PipelineStage[SampleContext, str]):
    name: str = "async_stage"

    async def execute_async(self, context: SampleContext) -> str:
        await asyncio.sleep(0.01)
        context.items.append("async_done")
        return "async_result"


class FailingStage(PipelineStage[SampleContext, None]):
    name: str = "failing_stage"

    def execute(self, context: SampleContext) -> None:
        raise ValueError("Simulated stage error")


def test_pipeline_sequential_execution() -> None:
    pipeline: StagePipeline[SampleContext, str] = StagePipeline(name="test_pipeline")
    pipeline.add_stage(StageOne())
    pipeline.add_stage(StageTwo())

    ctx = SampleContext()
    result = pipeline.run(ctx)

    assert result.status == PipelineStatus.SUCCESS
    assert ctx.items == ["one", "two"]
    assert len(result.stage_results) == 2
    assert result.stage_results[0].status == StageStatus.SUCCESS
    assert result.stage_results[0].result == "result_one"
    assert result.stage_results[1].status == StageStatus.SUCCESS
    assert result.stage_results[1].result == "result_two"
    assert result.duration_seconds >= 0.0


def test_pipeline_stage_conditional_skip() -> None:
    pipeline: StagePipeline[SampleContext, str] = StagePipeline(name="skip_pipeline")
    pipeline.add_stage(StageOne())
    pipeline.add_stage(StageTwo())

    ctx = SampleContext(should_skip_second=True)
    result = pipeline.run(ctx)

    assert result.status == PipelineStatus.SUCCESS
    assert ctx.items == ["one"]
    assert result.stage_results[0].status == StageStatus.SUCCESS
    assert result.stage_results[1].status == StageStatus.SKIPPED


def test_pipeline_failing_stage_fail_fast() -> None:
    pipeline: StagePipeline[SampleContext, Any] = StagePipeline(
        name="fail_pipeline", fail_fast=True
    )
    pipeline.add_stage(StageOne())
    pipeline.add_stage(FailingStage())
    pipeline.add_stage(StageTwo())

    ctx = SampleContext()
    result = pipeline.run(ctx)

    assert result.status == PipelineStatus.FAILED
    assert ctx.items == ["one"]
    assert len(result.stage_results) == 2
    assert result.stage_results[0].status == StageStatus.SUCCESS
    assert result.stage_results[1].status == StageStatus.FAILED
    assert "Simulated stage error" in str(result.stage_results[1].error)


def test_pipeline_failing_stage_continue_on_error() -> None:
    pipeline: StagePipeline[SampleContext, Any] = StagePipeline(
        name="continue_pipeline", fail_fast=False
    )
    pipeline.add_stage(StageOne())
    pipeline.add_stage(FailingStage())
    pipeline.add_stage(StageTwo())

    ctx = SampleContext()
    result = pipeline.run(ctx)

    assert result.status == PipelineStatus.FAILED
    assert ctx.items == ["one", "two"]
    assert len(result.stage_results) == 3
    assert result.stage_results[0].status == StageStatus.SUCCESS
    assert result.stage_results[1].status == StageStatus.FAILED
    assert result.stage_results[2].status == StageStatus.SUCCESS


@pytest.mark.asyncio
async def test_pipeline_async_execution() -> None:
    pipeline: StagePipeline[SampleContext, str] = StagePipeline(name="async_pipeline")
    pipeline.add_stage(StageOne())
    pipeline.add_stage(AsyncStage())

    ctx = SampleContext()
    result = await pipeline.run_async(ctx)

    assert result.status == PipelineStatus.SUCCESS
    assert ctx.items == ["one", "async_done"]
    assert result.stage_results[1].status == StageStatus.SUCCESS
    assert result.stage_results[1].result == "async_result"


def test_function_stage_convenience_wrapper() -> None:
    def custom_step(ctx: SampleContext) -> int:
        ctx.items.append("custom")
        return 42

    stage = FunctionStage(name="custom_fn", func=custom_step)
    pipeline: StagePipeline[SampleContext, int] = StagePipeline(name="fn_pipeline")
    pipeline.add_stage(stage)

    ctx = SampleContext()
    result = pipeline.run(ctx)

    assert result.status == PipelineStatus.SUCCESS
    assert ctx.items == ["custom"]
    assert result.stage_results[0].result == 42

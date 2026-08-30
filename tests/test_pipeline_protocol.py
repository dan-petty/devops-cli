"""Unit tests for StagePipeline and BasePipelineStage protocols."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.pipeline_protocol import (
    BasePipelineStage,
    StageExecutionRecord,
    StageHook,
    StagePipeline,
)


class DummyContext:
    def __init__(self, value: int) -> None:
        self.value = value
        self.log: list[str] = []


class AddStage(BasePipelineStage[DummyContext, int]):
    def __init__(self) -> None:
        super().__init__("add_stage")

    def execute(self, context: DummyContext) -> int:
        context.value += 10
        context.log.append("added_10")
        return context.value


class ConditionalStage(BasePipelineStage[DummyContext, None]):
    def __init__(self) -> None:
        super().__init__("conditional_stage")

    def is_enabled(self, context: DummyContext) -> bool:
        return context.value > 100

    def execute(self, context: DummyContext) -> None:
        context.log.append("conditional_ran")


class SampleStageHook(StageHook[DummyContext]):
    def __init__(self) -> None:
        self.started: list[str] = []
        self.completed: list[str] = []

    def on_stage_start(self, stage_name: str, context: DummyContext) -> None:
        self.started.append(stage_name)

    def on_stage_complete(
        self, stage_name: str, context: DummyContext, record: StageExecutionRecord
    ) -> None:
        self.completed.append(stage_name)


def test_stage_pipeline_execution() -> None:
    """StagePipeline should execute enabled stages in order and invoke hooks."""
    hook = SampleStageHook()
    pipeline = StagePipeline[DummyContext, Any]("test_pipe", hooks=[hook])
    pipeline.add_stage(AddStage())
    pipeline.add_stage(ConditionalStage())

    ctx = DummyContext(5)
    records = pipeline.run(ctx)

    assert ctx.value == 15
    assert ctx.log == ["added_10"]
    assert len(records) == 2
    assert records[0].stage_name == "add_stage"
    assert records[0].skipped is False
    assert records[0].success is True
    assert records[1].stage_name == "conditional_stage"
    assert records[1].skipped is True

    assert hook.started == ["add_stage"]
    assert hook.completed == ["add_stage"]

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


class FailingStage(BasePipelineStage[DummyContext, None]):
    def __init__(self) -> None:
        super().__init__("failing_stage")

    def execute(self, context: DummyContext) -> None:
        raise ValueError(
            "Failed connecting with token=ghp_secrettoken123456789012345678901234567890"
        )


def test_stage_pipeline_error_masking() -> None:
    """StagePipeline should mask sensitive credentials in error_message."""
    pipeline = StagePipeline[DummyContext, Any]("test_err_pipe")
    pipeline.add_stage(FailingStage())

    ctx = DummyContext(1)
    records = pipeline.run(ctx)

    assert len(records) == 1
    assert records[0].success is False
    assert records[0].error_message is not None
    assert "token=<masked-github-token>" in records[0].error_message
    assert "ghp_secrettoken" not in records[0].error_message


def test_span_handle_record_exception_masks_secrets() -> None:
    """SpanHandle.record_exception must sanitize sensitive tokens in message and stack trace."""
    from devops_cli.telemetry.tracer import SpanHandle

    span = SpanHandle("test-span-id")
    try:
        raise ValueError("Secret failure: ghp_supersecretaccesstoken123456789012345")
    except ValueError as exc:
        span.record_exception(exc)

    assert "ghp_supersecretaccesstoken" not in span._attributes.get("exception.message", "")
    assert "<masked-github-token>" in span._attributes.get("exception.message", "")
    assert "ghp_supersecretaccesstoken" not in span._attributes.get("exception.stacktrace", "")
    assert "<masked-github-token>" in span._attributes.get("exception.stacktrace", "")

"""ContextVar scope and validation for AI request execution stages."""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from contextvars import ContextVar

current_stage: ContextVar[str | None] = ContextVar("current_stage", default=None)


@contextlib.contextmanager
def stage_scope(stage: str | None) -> Generator[None]:
    """Set the spend tracking stage for the current task or thread context."""
    token = current_stage.set(stage)
    try:
        yield
    finally:
        current_stage.reset(token)


def resolve_spend_stage(
    explicit_stage: str | None = None, task_name: str | None = None
) -> str | None:
    """Determine valid execution stage from scope ContextVar, parameter, or task name."""
    raw_stage = explicit_stage or current_stage.get() or task_name
    if not raw_stage:
        return None
    from devops_cli.config.settings import AITasksConfig

    valid_stages = set(AITasksConfig.model_fields.keys()) | {
        "review.file_review",
        "review.verification",
        "file_review",
        "verification",
    }
    return raw_stage if raw_stage in valid_stages else None

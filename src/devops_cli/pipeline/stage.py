"""Base stage protocols and implementations for the pipeline engine."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict


class PipelineStage[ContextT, ResultT](BaseModel):
    """Abstract base class and protocol for a pipeline stage."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "stage"
    description: str = ""
    enabled: bool = True
    timeout_seconds: float | None = None

    def should_run(self, context: ContextT) -> bool:
        """Predicate checking whether this stage should run for given context."""
        return self.enabled

    def execute(self, context: ContextT) -> ResultT:
        """Execute stage logic synchronously."""
        raise NotImplementedError(
            "PipelineStage subclasses must implement execute or execute_async"
        )

    async def execute_async(self, context: ContextT) -> ResultT:
        """Execute stage logic asynchronously."""
        return self.execute(context)


class FunctionStage[ContextT, ResultT](PipelineStage[ContextT, ResultT]):
    """Convenience pipeline stage wrapping a callable function."""

    func: Callable[[ContextT], ResultT] | Callable[..., Any]

    def execute(self, context: ContextT) -> ResultT:
        res = self.func(context)
        return res

    async def execute_async(self, context: ContextT) -> ResultT:
        if inspect.iscoroutinefunction(self.func):
            res = await self.func(context)
            return res  # type: ignore[no-any-return]
        return self.execute(context)

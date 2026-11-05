"""The budgets of an implement step and of a run of an item (#3053).

A step ran with no bound on the tokens it used or the time it took: one step used 10 million input
tokens before it stopped, and the stop named no limit. `StepBudget` holds four limits, all settings
of `roadmap.implement`: the input tokens and the seconds of the step, and the input tokens and the
seconds of the run of the item. `limit_hooks` is a pydantic-ai `Hooks` capability. It adds the input
tokens of each reply to the count of the step, and before each model request it raises
`LimitReached` when a limit is spent. The error names the setting and its value, so the stop names
the limit that ended it.

The hook reads typed values, the usage of each reply and the clock. `UsageLimits` of pydantic-ai
raises an error that holds a message and no field, so a stop could name its setting only by a
match on library text. The check runs before a request, so the reply that crosses a limit is
whole and its tokens count: at most one request goes over a limit. The count of the step spans its
turns, its tiers and the sends again of a request, as the usage of one conversation does not.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Hooks
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import ModelRequestContext

from devops_cli.config.settings import load_settings
from devops_cli.exceptions.ai_pydantic import LimitReached
from devops_cli.lang import MESSAGES

__all__ = ["ItemSpend", "StepBudget", "limit_hooks"]

_SETTINGS = "roadmap.implement"


@dataclass(frozen=True)
class ItemSpend:
    """What a run of an item spent before a step: the input tokens of its earlier steps, and the
    time at which the run began (`None`: when the first step began). `clock` gives the seconds; a
    test passes its own."""

    input_tokens: int = 0
    started: float | None = None
    clock: Callable[[], float] = time.monotonic


class StepBudget:
    """The count of one step against the limits of the step and of the item."""

    def __init__(self, item: ItemSpend | None = None) -> None:
        limits = load_settings().roadmap.implement
        spend = item or ItemSpend()
        clock = spend.clock
        self._began = clock()
        started = self._began if spend.started is None else spend.started
        self.used = 0
        # Each limit: its setting, its value, and what it has spent now.
        self._limits: tuple[tuple[str, int, Callable[[], float]], ...] = (
            ("step_token_budget", limits.step_token_budget, lambda: self.used),
            (
                "item_token_budget",
                limits.item_token_budget,
                lambda: spend.input_tokens + self.used,
            ),
            (
                "step_time_limit_seconds",
                limits.step_time_limit_seconds,
                lambda: clock() - self._began,
            ),
            (
                "item_time_limit_seconds",
                limits.item_time_limit_seconds,
                lambda: clock() - started,
            ),
        )

    def add(self, input_tokens: int) -> None:
        """Count the input tokens of one reply."""
        self.used += input_tokens

    def spent(self) -> str | None:
        """The reason of the first limit that is spent, naming its setting and its value, or None
        when every limit holds."""
        for setting, value, spend in self._limits:
            if spend() >= value:
                return MESSAGES.roadmap.implement_stop_limit.format(
                    setting=f"{_SETTINGS}.{setting}", value=value
                )
        return None


def limit_hooks(budget: StepBudget) -> Hooks[None]:
    """The capability for the agent of a step: it counts the input tokens of each reply, and
    raises `LimitReached` before a request when `budget` is spent."""

    async def count(
        _ctx: RunContext[Any], /, *, request_context: ModelRequestContext, response: ModelResponse
    ) -> ModelResponse:
        """Add the input tokens of a reply to the count of the step, and pass the reply on."""
        budget.add(response.usage.input_tokens)
        return response

    async def check(
        _ctx: RunContext[Any], request_context: ModelRequestContext, /
    ) -> ModelRequestContext:
        """Pass on a request, or raise `LimitReached` when a limit is spent."""
        reason = budget.spent()
        if reason is not None:
            raise LimitReached(reason)
        return request_context

    return Hooks(before_model_request=check, after_model_request=count)

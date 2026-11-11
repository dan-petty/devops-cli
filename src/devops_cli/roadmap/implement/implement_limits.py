"""The budgets of an implement step and of a run of an item (#3053).

A step ran with no bound on the tokens it used or the time it took: one step used 10 million input
tokens before it stopped, and the stop named no limit. `StepBudget` holds four limits, all settings
of `roadmap.implement`: the new tokens and the seconds of the step, and the new tokens and the
seconds of the run of the item. `limit_hooks` is a pydantic-ai `Hooks` capability. It adds the new
tokens of each reply to the count of the step, and before each model request it raises
`LimitReached` when a limit is spent. The error names the setting and its value, so the stop names
the limit that ended it.

The new tokens of a reply (`new_tokens`) are its input tokens that the provider did not read from
its cache, and its output tokens (#4387). Each request sends the whole conversation again, and the
pydantic-ai `input_tokens` of a reply includes the prefix that the provider read from its cache.
In the runner Jobs, 98.6% of the input tokens were cache reads, at 3% of the input price, so a count
of all input tokens capped a step at about 100 requests and not at its cost. A provider that caches
nothing gives cache reads of 0, so each input token counts.

The hook reads typed values, the usage of each reply and the clock. `UsageLimits` of pydantic-ai
raises an error that holds a message and no field, so a stop could name its setting only by a
match on library text. The check runs before a request, so the reply that crosses a limit is
whole and its tokens count: at most one request goes over a limit. The count of the step spans its
turns, its tiers and the sends again of a request, as the usage of one conversation does not.

A step that reaches `step_token_budget` gets one extension when it makes progress (#4394). This is
the decision point `implement.extension` of ADR 0020, and its resolver is a rule: the digest of the
last tool calls of the step (`ProgressDigest`, from the step's `ToolCallLog`) holds at least
`CONST_ROADMAP_IMPLEMENT_EXTENSION_MIN_EDITS` successful edits and at most
`CONST_ROADMAP_IMPLEMENT_EXTENSION_MAX_REFUSED` refused commands. The extension adds
`CONST_ROADMAP_IMPLEMENT_EXTENSION_PERCENT` percent of the budget, up to `step_token_ceiling`. A
missing digest, a digest that fails the rule, a ceiling that leaves no room and a second arrival at
the limit all stop the step as before. No decision model takes part. The item budget and the time
limits get no extension.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, TypeGuard

from pydantic import BaseModel, ConfigDict
from pydantic_ai import RunContext
from pydantic_ai.capabilities import Hooks
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import ModelRequestContext

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_EXTENSION_CALLS,
    CONST_ROADMAP_IMPLEMENT_EXTENSION_MAX_REFUSED,
    CONST_ROADMAP_IMPLEMENT_EXTENSION_MIN_EDITS,
    CONST_ROADMAP_IMPLEMENT_EXTENSION_PERCENT,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.ai_pydantic import LimitReached
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.telemetry.instruments import ROADMAP_IMPLEMENT_EXTENSION_TOTAL, emit

__all__ = [
    "BudgetExtension",
    "ItemSpend",
    "ProgressDigest",
    "StepBudget",
    "TokenCounts",
    "extends",
    "limit_hooks",
    "new_tokens",
]

_SETTINGS = "roadmap.implement"
_STEP_BUDGET = f"{_SETTINGS}.step_token_budget"
_CEILING = f"{_SETTINGS}.step_token_ceiling"


class TokenCounts(Protocol):
    """The token counts of a reply or of a sum of replies, as pydantic-ai `RequestUsage` holds
    them: `input_tokens` includes `cache_read_tokens`."""

    @property
    def input_tokens(self) -> int: ...

    @property
    def cache_read_tokens(self) -> int: ...

    @property
    def output_tokens(self) -> int: ...


def new_tokens(counts: TokenCounts) -> int:
    """The tokens that a budget counts: the input tokens that the provider did not read from its
    cache, and the output tokens."""
    return counts.input_tokens - counts.cache_read_tokens + counts.output_tokens


@dataclass(frozen=True)
class ProgressDigest:
    """The counts of the last `calls` tool calls of a step: the successful edits (`write_file` and
    `edit_file` with the outcome ok) and the commands that the shell refused by its policy."""

    calls: int
    edits: int
    refused: int


class BudgetExtension(BaseModel):
    """The one extension of the token budget of a step: the budget before it (`limit`) and after it
    (`budget`), the counts of the digest that gave it, and whether `step_token_ceiling` cut it. It
    holds counts only."""

    model_config = ConfigDict(frozen=True)

    limit: int
    budget: int
    calls: int
    edits: int
    refused: int
    ceiling: bool = False


class _Decision(StrEnum):
    """What the rule decided when a step reached its token budget: the label of the counter."""

    EXTENDED = "extended"
    HALTED = "halted"


def extends(digest: ProgressDigest | None) -> TypeGuard[ProgressDigest]:
    """Whether the rule of `implement.extension` extends a step whose last calls give `digest`:
    at least one successful edit and at most three refused commands. No digest, as for a log with
    fewer calls than the window, never extends."""
    return (
        digest is not None
        and digest.edits >= CONST_ROADMAP_IMPLEMENT_EXTENSION_MIN_EDITS
        and digest.refused <= CONST_ROADMAP_IMPLEMENT_EXTENSION_MAX_REFUSED
    )


def _count(decision: _Decision) -> None:
    """Add 1 to the series of `decision` and 0 to the other, so both series exist."""
    for each in _Decision:
        emit(ROADMAP_IMPLEMENT_EXTENSION_TOTAL, 1 if each is decision else 0, {"decision": each})


@dataclass(frozen=True)
class ItemSpend:
    """What a run of an item spent before a step: the new tokens of its earlier steps, and the
    time at which the run began (`None`: when the first step began). `clock` gives the seconds; a
    test passes its own."""

    tokens: int = 0
    started: float | None = None
    clock: Callable[[], float] = time.monotonic


class StepBudget:
    """The count of one step against the limits of the step and of the item. `progress` gives the
    digest of the last tool calls of the step, which the rule of the extension reads when the step
    reaches its token budget. `extension` holds the one extension that the step got, or None."""

    def __init__(
        self,
        item: ItemSpend | None = None,
        *,
        progress: Callable[[], ProgressDigest | None],
    ) -> None:
        limits = load_settings().roadmap.implement
        spend = item or ItemSpend()
        clock = spend.clock
        self._began = clock()
        started = self._began if spend.started is None else spend.started
        self.used = 0
        self.extension: BudgetExtension | None = None
        self._progress = progress
        self._budget = limits.step_token_budget
        self._ceiling = limits.token_ceiling
        self._step_limit = self._budget
        # The reason of the stop at the token budget of the step, once the rule has halted.
        self._stop: str | None = None
        # The other limits: their setting, their value, and what they have spent now.
        self._limits: tuple[tuple[str, int, Callable[[], float]], ...] = (
            (
                "item_token_budget",
                limits.item_token_budget,
                lambda: spend.tokens + self.used,
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

    def add(self, tokens: int) -> None:
        """Count the new tokens of one reply."""
        self.used += tokens

    def spent(self) -> str | None:
        """The reason of the first limit that is spent, naming its setting and its value, or None
        when every limit holds. The token budget of the step comes first. When it is spent and no
        other limit is, the rule of the extension decides once whether the step goes on."""
        other = next(
            (
                MESSAGES.roadmap.implement_stop_limit.format(
                    setting=f"{_SETTINGS}.{setting}", value=value
                )
                for setting, value, spend in self._limits
                if spend() >= value
            ),
            None,
        )
        if self.used < self._step_limit or (other is None and self._extended()):
            return other
        if self._stop is None and self.extension is not None:
            return self._halted(None)
        return self._stop or MESSAGES.roadmap.implement_stop_limit.format(
            setting=_STEP_BUDGET, value=self._budget
        )

    def _extended(self) -> bool:
        """Decide at the token budget of the step: give the one extension, or keep the reason of
        the stop. A step decides once at each limit, so the counter counts each decision once."""
        if self._stop is not None:
            return False
        digest = self._progress() if self.extension is None else None
        wanted = self._budget + self._budget * CONST_ROADMAP_IMPLEMENT_EXTENSION_PERCENT // 100
        target = min(wanted, self._ceiling)
        if extends(digest) and target > self.used:
            self.extension = BudgetExtension(
                limit=self._budget,
                budget=target,
                calls=digest.calls,
                edits=digest.edits,
                refused=digest.refused,
                ceiling=target < wanted,
            )
            self._step_limit = target
            _count(_Decision.EXTENDED)
            print_muted(
                MESSAGES.roadmap.implement_extension_extended.format(**self.extension.model_dump()),
                to_stderr=True,
                safe=True,
            )
            return True
        self._stop = self._halted(digest)
        _count(_Decision.HALTED)
        return False

    def _halted(self, digest: ProgressDigest | None) -> str:
        """The reason of a stop at the token budget of the step: the end of the extension, a
        ceiling that leaves no room, a log too short for a digest, or the counts of the digest."""
        texts = MESSAGES.roadmap
        named = {"setting": _STEP_BUDGET, "value": self._budget}
        if (extension := self.extension) is not None:
            if extension.ceiling:
                return texts.implement_stop_limit_ceiling.format(
                    **named, ceiling=_CEILING, budget=extension.budget
                )
            return texts.implement_stop_limit_extended.format(**named, budget=extension.budget)
        if extends(digest):
            return texts.implement_stop_limit_no_room.format(
                **named, used=self.used, ceiling=_CEILING, budget=self._ceiling
            )
        if digest is None:
            return texts.implement_stop_limit_unclear.format(
                **named, calls=CONST_ROADMAP_IMPLEMENT_EXTENSION_CALLS
            )
        return texts.implement_stop_limit_halted.format(
            **named, edits=digest.edits, refused=digest.refused, calls=digest.calls
        )


def limit_hooks(budget: StepBudget) -> Hooks[None]:
    """The capability for the agent of a step: it counts the new tokens of each reply, and
    raises `LimitReached` before a request when `budget` is spent."""

    async def count(
        _ctx: RunContext[Any], /, *, request_context: ModelRequestContext, response: ModelResponse
    ) -> ModelResponse:
        """Add the new tokens of a reply to the count of the step, and pass the reply on."""
        budget.add(new_tokens(response.usage))
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

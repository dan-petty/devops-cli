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
`CONST_ROADMAP_IMPLEMENT_EXTENSION_MIN_EDITS` successful edits. The extension adds
`CONST_ROADMAP_IMPLEMENT_EXTENSION_PERCENT` percent of the budget, up to `step_token_ceiling`. A
missing digest, a digest that fails the rule, a ceiling that leaves no room and a second arrival at
the limit all stop the step as before. No decision model takes part. The item budget and the time
limits get no extension.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, Protocol, TypeGuard

from pydantic import BaseModel, ConfigDict
from pydantic_ai import RunContext
from pydantic_ai.capabilities import Hooks
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.models.decision import NoulQuestion

from devops_cli.config.constants import (
    CONST_ROADMAP_DECISION_POINT_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_EXTENSION_LOOP_FAILED_CALLS,
    CONST_ROADMAP_IMPLEMENT_EXTENSION_LOOP_IDENTICAL_CALLS,
    CONST_ROADMAP_IMPLEMENT_EXTENSION_MIN_EDITS,
    CONST_ROADMAP_IMPLEMENT_EXTENSION_PERCENT,
    CONST_ROADMAP_IMPLEMENT_EXTENSION_TIME_MARGIN_SECONDS,
    CONST_ROADMAP_IMPLEMENT_EXTENSION_WINDOW_MAX_SHARE,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.ai_pydantic import LimitReached
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.roadmap.decision_point import (
    DecisionPoint,
    Guard,
    Mode,
    Resolver,
    chain_of,
)
from devops_cli.roadmap.decision_step import Band
from devops_cli.roadmap.service_stop import service_stopping
from devops_cli.telemetry.instruments import ROADMAP_IMPLEMENT_EXTENSION_TOTAL, emit

if TYPE_CHECKING:
    from pydantic_ai.models.decision import DecisionModel

__all__ = [
    "IMPLEMENT_EXTENSION",
    "BudgetExtension",
    "ItemSpend",
    "ProgressDigest",
    "StepBudget",
    "TokenCap",
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
    `edit_file` with the outcome ok) and loop repeat counts (#4847)."""

    calls: int
    edits: int
    identical_call_answers: int = 0
    identical_failing_calls: int = 0


class BudgetExtension(BaseModel):
    """The one extension of the token budget of a step: the budget before it (`limit`) and after it
    (`budget`), the counts of the digest that gave it, and whether `step_token_ceiling` cut it. It
    holds counts only."""

    model_config = ConfigDict(frozen=True)

    limit: int
    budget: int
    calls: int
    edits: int
    ceiling: bool = False


class _Decision(StrEnum):
    """What the rule decided when a step reached its token budget: the label of the counter."""

    EXTENDED = "extended"
    HALTED = "halted"


def _allows_service_not_draining(state: dict[str, Any]) -> bool:
    """Block soft-cap extension when the Service is draining."""
    return not (service_stopping() or bool(state.get("service_draining")))


def _allows_hard_ceiling(state: dict[str, Any]) -> bool:
    """Block soft-cap extension when `value + step` exceeds `hard_ceiling` or `token_ceiling`."""
    ceiling = state.get("hard_ceiling")
    if ceiling is None:
        return True
    used = int(state.get("used", state.get("value", 0)))
    step = int(state.get("step", 0))
    return used < int(ceiling) and used + step <= int(ceiling)


def _allows_outer_limits(state: dict[str, Any]) -> bool:
    """Block soft-cap extension when context window share or outer time/token margins fail."""
    share = state.get("window_share")
    if share is not None and float(share) > CONST_ROADMAP_IMPLEMENT_EXTENSION_WINDOW_MAX_SHARE:
        return False
    margin = float(
        state.get("time_margin_seconds", CONST_ROADMAP_IMPLEMENT_EXTENSION_TIME_MARGIN_SECONDS)
    )
    for key in ("step_seconds_remaining", "item_seconds_remaining"):
        remaining = state.get(key)
        if remaining is not None and float(remaining) < margin:
            return False
    item_rem = state.get("item_tokens_remaining")
    return item_rem is None or int(item_rem) >= int(state.get("item_token_margin", 0))


def _allows_no_loop(state: dict[str, Any]) -> bool:
    """Block soft-cap extension when repeated identical calls/answers or failing calls loop."""
    if (
        int(state.get("identical_call_answers", 0))
        >= CONST_ROADMAP_IMPLEMENT_EXTENSION_LOOP_IDENTICAL_CALLS
    ):
        return False
    if (
        int(state.get("identical_failing_calls", 0))
        >= CONST_ROADMAP_IMPLEMENT_EXTENSION_LOOP_FAILED_CALLS
    ):
        return False
    return not bool(state.get("stuck"))


def _implement_extension_rule(state: Mapping[str, Any]) -> Band | None:
    """Deterministic progress rule for `implement.extension` (#4394, #4847)."""
    calls = int(state.get("calls", 0))
    min_calls = int(state.get("min_calls", 1))
    edits = int(state.get("edits", 0))
    if calls >= min_calls and edits >= CONST_ROADMAP_IMPLEMENT_EXTENSION_MIN_EDITS:
        return Band.CONTINUE
    return None


IMPLEMENT_EXTENSION_QUESTIONS: Final[Mapping[str, NoulQuestion]] = MappingProxyType(
    {
        "making_progress": NoulQuestion(
            instructions=(
                "Does the digest of recent tool counts show forward progress toward finishing "
                "the step without repeating fruitless work?"
            )
        ),
        "safe_headroom": NoulQuestion(
            instructions=(
                "Can one extension complete within the remaining outer step and item limits?"
            )
        ),
    }
)


IMPLEMENT_EXTENSION: Final[DecisionPoint[Mapping[str, Any]]] = DecisionPoint(
    name="implement.extension",
    questions=IMPLEMENT_EXTENSION_QUESTIONS,
    evidence=dict,
    bands={
        Band.CONTINUE: "Extend the step token budget by one bounded increment.",
        Band.REVIEW: "Hold the step at its current token budget.",
        Band.FLAG: "Flag suspicious budget or loop counts and hold.",
    },
    cuts=Path(__file__).with_name("implement_extension_cuts.json"),
    guards=(
        Guard("service_draining", _allows_service_not_draining),
        Guard("hard_ceiling", _allows_hard_ceiling),
        Guard("outer_limits", _allows_outer_limits),
        Guard("loop_guard", _allows_no_loop),
    ),
    rule=_implement_extension_rule,
    asks_model=True,
    counts_only=True,
    timeout=CONST_ROADMAP_DECISION_POINT_TIMEOUT_SECONDS,
    requires_fit_bar=True,
    supports_rule_mode=True,
)


def extends(digest: ProgressDigest | None) -> TypeGuard[ProgressDigest]:
    """Whether the rule of `implement.extension` extends a step whose last calls give `digest`:
    at least one successful edit. No digest, as for a log with fewer calls than the window, never
    extends."""
    return digest is not None and digest.edits >= CONST_ROADMAP_IMPLEMENT_EXTENSION_MIN_EDITS


def _count(decision: _Decision) -> None:
    """Add 1 to the series of `decision` and 0 to the other, so both series exist."""
    for each in _Decision:
        emit(ROADMAP_IMPLEMENT_EXTENSION_TOTAL, 1 if each is decision else 0, {"decision": each})


@dataclass(frozen=True)
class TokenCap:
    """A fixed cap of the new tokens of a step, for a caller with a budget of its own, such as the
    model fix of the step `fix-checks` (#5971): `value`, and the `setting` that holds it, which the
    stop names. It replaces `step_token_budget` and its extension."""

    setting: str
    value: int


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
    reaches its token budget. `extension` holds the one extension that the step got, or None. A
    `cap` replaces the token budget of the step and its extension."""

    def __init__(
        self,
        item: ItemSpend | None = None,
        *,
        progress: Callable[[], ProgressDigest | None],
        cap: TokenCap | None = None,
        window_share: Callable[[], float] | None = None,
        decision_model: DecisionModel[Any] | None = None,
    ) -> None:
        settings = load_settings()
        limits = settings.roadmap.implement
        spend = item or ItemSpend()
        clock = spend.clock
        self._began = clock()
        started = self._began if spend.started is None else spend.started
        self.used = 0
        self.extension: BudgetExtension | None = None
        self._progress = progress
        self._cap = cap
        self._settings = settings
        self._window_share = window_share
        self._decision_model = decision_model
        self._clock = clock
        self._started = started
        self._prior_tokens = spend.tokens
        self._budget = limits.step_token_budget
        self._ceiling = limits.token_ceiling
        self._window = limits.extension_calls
        self._item_token_budget = limits.item_token_budget
        self._step_time_limit = limits.step_time_limit_seconds
        self._item_time_limit = limits.item_time_limit_seconds
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
        if self._cap is not None:
            if other is not None or self.used < self._cap.value:
                return other
            return MESSAGES.roadmap.implement_stop_limit.format(
                setting=self._cap.setting, value=self._cap.value
            )
        if self.used < self._step_limit or (other is None and self._extended()):
            return other
        if self._stop is None and self.extension is not None:
            return self._halted(None)
        return self._stop or MESSAGES.roadmap.implement_stop_limit.format(
            setting=_STEP_BUDGET, value=self._budget
        )

    def _decision_state(self, digest: ProgressDigest | None, target: int) -> dict[str, Any]:
        """Build the numeric state dictionary for the `implement.extension` decision point."""
        wanted_delta = self._budget * CONST_ROADMAP_IMPLEMENT_EXTENSION_PERCENT // 100
        step_delta = (target - self.used) if target > self.used else wanted_delta
        return {
            "used": self.used,
            "step": step_delta,
            "hard_ceiling": self._ceiling,
            "window_share": self._window_share() if self._window_share is not None else 0.0,
            "step_seconds_remaining": self._step_time_limit - (self._clock() - self._began),
            "item_seconds_remaining": self._item_time_limit - (self._clock() - self._started),
            "item_tokens_remaining": self._item_token_budget - (self._prior_tokens + self.used),
            "item_token_margin": max(step_delta, 0),
            "min_calls": self._window,
            "calls": digest.calls if digest is not None else 0,
            "edits": digest.edits if digest is not None else 0,
            "identical_call_answers": digest.identical_call_answers if digest is not None else 0,
            "identical_failing_calls": digest.identical_failing_calls if digest is not None else 0,
        }

    def _point_approves(
        self, digest: ProgressDigest | None, target: int
    ) -> tuple[bool, str | None]:
        """Consult `implement.extension` when enabled (`rule`, `shadow`, or `on`); preserve
        direct rule check when left `off`."""
        chain = chain_of(IMPLEMENT_EXTENSION, self._settings, model=self._decision_model)
        if chain is None:
            return extends(digest) and target > self.used, None
        record = chain.decide(self._decision_state(digest, target), subject=id(self))
        if record.guard is not None:
            return False, record.guard
        if target <= self.used or digest is None:
            return False, None
        if record.resolver is Resolver.RULE and record.band is Band.CONTINUE:
            return True, None
        return record.mode is Mode.ON and record.acts and record.band is Band.CONTINUE, None

    def _extended(self) -> bool:
        """Decide at the token budget of the step: give the one extension, or keep the reason of
        the stop. A step decides once at each limit, so the counter counts each decision once."""
        if self._stop is not None:
            return False
        digest = self._progress() if self.extension is None else None
        wanted = self._budget + self._budget * CONST_ROADMAP_IMPLEMENT_EXTENSION_PERCENT // 100
        target = min(wanted, self._ceiling)
        approved, guard = self._point_approves(digest, target)
        if approved and digest is not None and target > self.used:
            self.extension = BudgetExtension(
                limit=self._budget,
                budget=target,
                calls=digest.calls,
                edits=digest.edits,
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
        self._stop = self._halted(digest, guard=guard)
        _count(_Decision.HALTED)
        return False

    def _halted(self, digest: ProgressDigest | None, *, guard: str | None = None) -> str:
        """The reason of a stop at the token budget of the step: guard block, the end of the
        extension, a ceiling that leaves no room, a log too short for a digest, or the counts."""
        texts = MESSAGES.roadmap
        named = {"setting": _STEP_BUDGET, "value": self._budget}
        if (extension := self.extension) is not None:
            if extension.ceiling:
                return texts.implement_stop_limit_ceiling.format(
                    **named, ceiling=_CEILING, budget=extension.budget
                )
            return texts.implement_stop_limit_extended.format(**named, budget=extension.budget)
        base_stop = (
            texts.implement_stop_limit_no_room.format(
                **named, used=self.used, ceiling=_CEILING, budget=self._ceiling
            )
            if extends(digest)
            else (
                texts.implement_stop_limit_unclear.format(**named, calls=self._window)
                if digest is None
                else texts.implement_stop_limit_halted.format(
                    **named, edits=digest.edits, calls=digest.calls
                )
            )
        )
        return f"{base_stop} (guard: {guard})" if guard else base_stop


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

"""The budgets of an implement step and of a run of an item (#3053): four settings, and a stop that
names the setting that a step spent. The token budgets count the new tokens of each reply: the input
that the provider did not read from its cache, and the output (#4387).

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`, and `process_fake` answers every other program. The clock of the budgets is a fake that
a test moves.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_ai.usage import RequestUsage

from devops_cli.config import env
from devops_cli.config.settings import load_settings
from devops_cli.roadmap.failure import ACTION_BY_CLASS, FailureAction, FailureClass
from devops_cli.roadmap.implement.implement_limits import ItemSpend, StepBudget, new_tokens
from devops_cli.roadmap.implement.implement_step import StepOutcome, StepStatus, run_step
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    command_text,
    tool_reads,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_call, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

SETTINGS = (
    "step_token_budget",
    "item_token_budget",
    "step_time_limit_seconds",
    "item_time_limit_seconds",
)
READ = tool_call("read_file", path="src/sample.py")
BAD_TEST = "import os\n\n" + TEST_BODY
UNUSED = "F401 `os` imported but unused\n --> tests/test_sample.py:1:8"


class Clock:
    """A clock that a test moves."""

    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> float:
        return self.seconds

    def advance(self, seconds: float) -> Callable[[], None]:
        """The effect of a request that takes `seconds`."""

        def move() -> None:
            self.seconds += seconds

        return move


def _step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    script: ModelScript,
    spend: ItemSpend | None = None,
) -> StepOutcome:
    return run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        spend=spend,
    )


# ── The settings ──────────────────────────────────────────────────────────────────────────


def test_the_defaults_fit_the_measured_spend_of_steps_and_items() -> None:
    implement = load_settings().roadmap.implement

    assert (
        implement.step_token_budget,
        implement.item_token_budget,
        implement.step_time_limit_seconds,
        implement.item_time_limit_seconds,
    ) == (8_000_000, 20_000_000, 5400, 12600)


def test_a_budget_counts_the_input_that_the_cache_did_not_serve_and_the_output() -> None:
    usage = RequestUsage(input_tokens=120_000, cache_read_tokens=118_500, output_tokens=300)

    assert new_tokens(usage) == 1800


def _requests_in_the_step_budget(usage: RequestUsage) -> int:
    """The requests of `usage` that a step makes with the default settings before its token budget
    stops it."""
    budget = StepBudget(progress=lambda: None)
    requests = 0
    while budget.spent() is None:
        budget.add(new_tokens(usage))
        requests += 1
    return requests


@pytest.mark.parametrize(
    ("usage", "fewest"),
    [
        # A request of a runner Job on the local route `qwen3-coder:30b` (gateway metrics,
        # 2026-10-28 to 2026-11-05), which reports no cache reads. The count of all input tokens
        # before #4387 gave the step about 200 such requests.
        (RequestUsage(input_tokens=39_300, output_tokens=200), 200),
        # A request of a runner Job on the cached hosted route (2026-10-28 to 2026-11-11). More
        # requests than the 90 minutes of a step hold at 10 seconds each, so the time limit of the
        # step comes first.
        (RequestUsage(input_tokens=83_700, cache_read_tokens=82_200, output_tokens=440), 540),
    ],
    ids=["no-cache-reads", "cached"],
)
def test_the_default_step_budget_fits_a_route_with_and_with_no_cache_reads(
    usage: RequestUsage, fewest: int
) -> None:
    assert _requests_in_the_step_budget(usage) >= fewest


def test_each_budget_has_a_variable_named_after_its_setting() -> None:
    variables = env.setting_variables()

    assert [variables[f"roadmap.implement.{name}"] for name in SETTINGS] == [
        f"DEVOPS_CLI_ROADMAP_IMPLEMENT_{name.upper()}" for name in SETTINGS
    ]


def test_a_variable_sets_a_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_BUDGET", "5000")

    assert load_settings().roadmap.implement.step_token_budget == 5000


@pytest.mark.parametrize("name", SETTINGS)
def test_a_budget_of_zero_is_refused(config: Callable[..., Path], name: str) -> None:
    config(roadmap={"implement": {name: 0}})

    with pytest.raises(ValidationError, match=name):
        load_settings()


def test_an_item_time_limit_above_the_ceiling_of_the_job_is_refused(
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"item_time_limit_seconds": 14401}})

    with pytest.raises(ValidationError, match="item_time_limit_seconds"):
        load_settings()


def test_a_spent_budget_is_a_class_whose_action_is_to_raise_the_limit() -> None:
    assert ACTION_BY_CLASS[FailureClass.LIMIT_REACHED] is FailureAction.RAISE_LIMIT


# ── The stops ─────────────────────────────────────────────────────────────────────────────


def test_a_step_that_spends_its_token_budget_makes_no_further_request_and_names_the_setting(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"step_token_budget": 50}})
    script = ModelScript(READ, say("Done."))

    outcome = _step(implement_store, implement_checkout, script)

    assert (len(script.seen), outcome.status, outcome.failure_class) == (
        1,
        StepStatus.STOPPED,
        FailureClass.LIMIT_REACHED,
    )
    assert "`roadmap.implement.step_token_budget=50`" in outcome.reason


def test_the_tokens_of_the_earlier_steps_of_the_run_count_for_the_item_budget(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"item_token_budget": 1000}})
    script = ModelScript(READ, say("Done."))

    outcome = _step(implement_store, implement_checkout, script, ItemSpend(tokens=999))

    assert (len(script.seen), outcome.failure_class) == (1, FailureClass.LIMIT_REACHED)
    assert "`roadmap.implement.item_token_budget=1000`" in outcome.reason


def test_a_step_over_its_time_limit_makes_no_further_request_and_names_the_setting(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"step_time_limit_seconds": 60}})
    clock = Clock()
    script = ModelScript(READ, say("Done."), effects={1: clock.advance(61)})

    outcome = _step(implement_store, implement_checkout, script, ItemSpend(clock=clock))

    assert (len(script.seen), outcome.failure_class) == (1, FailureClass.LIMIT_REACHED)
    assert "`roadmap.implement.step_time_limit_seconds=60`" in outcome.reason


def test_a_run_over_its_item_time_limit_gives_the_next_step_no_request(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"item_time_limit_seconds": 60}})
    clock = Clock()
    clock.seconds = 100.0
    script = ModelScript(say("Done."))

    outcome = _step(
        implement_store, implement_checkout, script, ItemSpend(started=0.0, clock=clock)
    )

    assert (len(script.seen), outcome.failure_class) == (0, FailureClass.LIMIT_REACHED)
    assert "`roadmap.implement.item_time_limit_seconds=60`" in outcome.reason


def test_a_step_within_every_budget_is_not_stopped(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
) -> None:
    script = ModelScript(READ, say("Done."))

    outcome = _step(implement_store, implement_checkout, script)

    assert outcome.failure_class is not FailureClass.LIMIT_REACHED
    assert len(script.seen) == 2


def test_the_input_that_the_provider_read_from_its_cache_does_not_count_for_the_step_budget(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    """Each reply reports 100000 more input tokens, all read from the cache of the provider. A budget
    of 500 holds for both requests, and the outcome keeps the cached input (#4387)."""
    config(roadmap={"implement": {"step_token_budget": 500}})
    script = ModelScript(READ, say("Done."), cached=100_000)

    outcome = _step(implement_store, implement_checkout, script)

    assert outcome.failure_class is not FailureClass.LIMIT_REACHED
    assert len(script.seen) == 2
    assert (outcome.input_tokens, outcome.cache_read_tokens) == (200_100, 200_000)


def test_a_repair_turn_makes_no_request_when_the_step_has_spent_its_time(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"step_time_limit_seconds": 60}})
    clock = Clock()
    implement_programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=tool_reads("import os", UNUSED)),
    )
    first = tool_calls(
        write_call("tests/test_sample.py", BAD_TEST),
        write_call("src/sample.py", SHOUT_CODE),
        write_call(TASKS_PATH, TICKED),
    )
    script = ModelScript(first, say("Done."), effects={2: clock.advance(61)})

    outcome = _step(implement_store, implement_checkout, script, ItemSpend(clock=clock))

    assert (len(script.seen), outcome.failure_class) == (2, FailureClass.LIMIT_REACHED)

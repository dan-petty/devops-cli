"""The one extension of the token budget of an implement step that makes progress (#4394).

A step that reaches `roadmap.implement.step_token_budget` gets one extension of a fixed share of the
budget when the last tool calls of the step hold a successful edit and few refused commands. The
rule is the resolver of the decision point `implement.extension` (ADR 0020). The table of shapes
comes from pilot 3: the counts in the last 20 tool calls before the stops of 14 days of Job logs.

The model is a pydantic-ai `FunctionModel` from `ModelScript`, which reports 50 input tokens for
each streamed request and the output tokens of its parts. A first reply that makes the 20 tool
calls of the whole group and of 17 reads counts 280 new tokens (`FIRST`). Git runs for real on a checkout in `tmp_path`, and `process_fake` answers
every other program. The counter goes to a fake of the telemetry edge.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config import constants, env
from devops_cli.config.settings import load_settings, setting_default
from devops_cli.exceptions import ConfigurationError
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement.implement_limits import (
    BudgetExtension,
    ItemSpend,
    ProgressDigest,
    StepBudget,
)
from devops_cli.roadmap.implement.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.implement.implement_tool_log import (
    ToolCallLog,
    ToolOutcome,
    progress_digest,
)
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import WINDOW, the_whole_group
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

BUDGET = "`roadmap.implement.step_token_budget=50`"

# The counts (successful edits, refused commands) in the last 20 tool calls before a stop of
# pilot 3 (2026-10-27 to 2026-11-10). Each item of EXTEND stopped with the class `limit_reached`,
# and a person then finished it with a few commits on the branch of the run.
EXTEND = {
    3075: (2, 2),
    3217: (2, 1),
    3247: (1, 1),
    3251: (4, 3),
    3253: (2, 0),
    3347: (8, 0),
    3404: (4, 0),
    3417: (10, 0),
    3443: (2, 0),
    3451: (3, 0),
    3456: (1, 1),
    3485: (4, 0),
    3654: (3, 1),
    3991: (2, 0),
    4004: (1, 3),
    4079: (2, 0),
}
# Each item of SPIN stopped above 6.4 million input tokens with another class (`refused_tool`,
# `ci_infra`, `lint`, `no_change_in_fix`): the run repeated refused commands and made no progress.
SPIN = {
    2469: (0, 11),
    2554: (1, 10),
    2570: (0, 16),
    2636: (1, 4),
    3394: (0, 9),
}
# The edges of the rule: no edit, and one refused command over the limit.
EDGES = {"no edit": (0, 0), "no edit and 3 refused": (0, 3), "4 refused": (1, 4)}

READ = ("read_file", {"path": "src/sample.py"})
# The new tokens of the first reply of the whole group and 17 reads: 50 input and 230 output.
FIRST = 280
REFUSED = ("run_command", {"command": "pytest tests/test_sample.py"})


def _digest(edits: int, refused: int) -> ProgressDigest:
    return ProgressDigest(calls=20, edits=edits, refused=refused)


@pytest.fixture
def counted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, float]]:
    """The `(decision, value)` pairs that the budget sends to the counter."""
    sent: list[tuple[str, float]] = []

    def fake_emit(instrument: Any, value: float, attributes: dict[str, Any] | None = None) -> None:
        assert instrument.name == "devops_cli_roadmap_implement_extension_total"
        sent.append(((attributes or {})["decision"], value))

    monkeypatch.setattr("devops_cli.roadmap.implement.implement_limits.emit", fake_emit)
    return sent


def _budget(
    config: Callable[..., Path],
    digest: ProgressDigest | None,
    *,
    ceiling: int | None = None,
    item: ItemSpend | None = None,
) -> StepBudget:
    """A step budget of 50 new tokens whose tool log gives `digest`."""
    implement: dict[str, int] = {"step_token_budget": 50}
    if ceiling is not None:
        implement["step_token_ceiling"] = ceiling
    config(roadmap={"implement": implement})
    return StepBudget(item, progress=lambda: digest)


# ── The settings ──────────────────────────────────────────────────────────────────────────


def test_the_ceiling_is_twice_the_default_step_budget() -> None:
    implement = load_settings().roadmap.implement

    assert implement.token_ceiling == 2 * implement.step_token_budget == 16_000_000


def test_with_no_ceiling_set_the_ceiling_is_twice_the_configured_step_budget(
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"step_token_budget": 17_000_000}})

    assert load_settings().roadmap.implement.token_ceiling == 34_000_000


def test_a_variable_that_sets_only_the_step_budget_gives_twice_it_as_the_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_BUDGET", "17000000")

    assert load_settings().roadmap.implement.token_ceiling == 34_000_000


def test_config_set_of_a_step_budget_above_the_loaded_ceiling_moves_the_ceiling(
    cli: Callable[..., Any], isolate_devops_cli_config: Path
) -> None:
    """`devops config set` of a step budget above twice the loaded one exits 0, writes only the
    budget, and the unset ceiling follows it (#4505)."""
    result = cli("config", "set", "roadmap.implement.step_token_budget", "20000000")

    written = yaml.safe_load(isolate_devops_cli_config.read_text(encoding="utf-8"))
    assert (result.exit_code, written["roadmap"]["implement"]) == (
        0,
        {"step_token_budget": 20_000_000},
    )
    assert load_settings().roadmap.implement.token_ceiling == 40_000_000


def test_a_step_budget_with_no_ceiling_set_gets_its_whole_extension(
    config: Callable[..., Path], counted: list[tuple[str, float]]
) -> None:
    config(roadmap={"implement": {"step_token_budget": 12_000_000}})
    budget = StepBudget(progress=lambda: _digest(2, 0))
    budget.add(12_000_000)

    assert budget.spent() is None
    assert budget.extension == BudgetExtension(
        limit=12_000_000, budget=18_000_000, calls=20, edits=2, refused=0
    )


def test_the_ceiling_has_a_variable_named_after_its_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING", "9000000")

    assert env.setting_variables()["roadmap.implement.step_token_ceiling"] == (
        "DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING"
    )
    assert load_settings().roadmap.implement.step_token_ceiling == 9_000_000


def test_a_ceiling_below_the_step_budget_is_refused(config: Callable[..., Path]) -> None:
    config(roadmap={"implement": {"step_token_budget": 5000, "step_token_ceiling": 4999}})

    with pytest.raises(ConfigurationError, match="step_token_ceiling"):
        load_settings()


def test_the_rule_extends_by_half_the_budget_for_one_edit_and_at_most_three_refusals() -> None:
    assert (
        setting_default("roadmap.implement.extension_calls"),
        constants.CONST_ROADMAP_IMPLEMENT_EXTENSION_MIN_EDITS,
        setting_default("roadmap.implement.extension_max_refused"),
        constants.CONST_ROADMAP_IMPLEMENT_EXTENSION_PERCENT,
    ) == (20, 1, 3, 50)


def test_the_settings_set_the_window_and_the_refused_commands_of_the_rule(
    config: Callable[..., Path], counted: list[tuple[str, float]]
) -> None:
    """The step reads `roadmap.implement.extension_calls` and `extension_max_refused` when it
    starts (#5440)."""
    config(roadmap={"implement": {"extension_calls": 10, "extension_max_refused": 5}})
    log = ToolCallLog()
    for _ in range(12):
        log.recent.append(("write_file", ToolOutcome.OK))
    budget = _budget(config, ProgressDigest(calls=10, edits=1, refused=5))
    budget.add(50)

    assert (log.progress(), budget.spent()) == (
        ProgressDigest(calls=10, edits=10, refused=0),
        None,
    )
    assert budget.extension is not None


# ── The digest of the tool log ────────────────────────────────────────────────────────────


def test_the_digest_counts_the_successful_edits_and_the_refused_commands_of_the_last_calls() -> (
    None
):
    calls = [
        ("edit_file", ToolOutcome.OK),
        *[("read_file", ToolOutcome.OK)] * 15,
        ("write_file", ToolOutcome.OK),
        ("edit_file", ToolOutcome.RETRY),
        ("write_file", ToolOutcome.FAILED),
        ("shell", ToolOutcome.REFUSED),
        ("shell", ToolOutcome.REFUSED),
    ]

    assert progress_digest(calls, 20) == ProgressDigest(calls=20, edits=1, refused=2)


def test_a_log_with_fewer_calls_than_the_window_gives_no_digest() -> None:
    assert progress_digest([("write_file", ToolOutcome.OK)] * 19, 20) is None


# ── The rule, on the shapes of pilot 3 ────────────────────────────────────────────────────


@pytest.mark.parametrize(("edits", "refused"), EXTEND.values(), ids=[f"#{n}" for n in EXTEND])
def test_a_step_that_made_progress_gets_one_extension_of_half_its_budget(
    config: Callable[..., Path], counted: list[tuple[str, float]], edits: int, refused: int
) -> None:
    budget = _budget(config, _digest(edits, refused))
    budget.add(50)

    assert budget.spent() is None
    assert budget.extension == BudgetExtension(
        limit=50, budget=75, calls=20, edits=edits, refused=refused
    )
    assert counted == [("extended", 1), ("halted", 0)]


@pytest.mark.parametrize(
    ("edits", "refused"),
    [*SPIN.values(), *EDGES.values()],
    ids=[*(f"#{n}" for n in SPIN), *EDGES],
)
def test_a_step_that_spins_stops_at_its_budget_with_the_counts(
    config: Callable[..., Path], counted: list[tuple[str, float]], edits: int, refused: int
) -> None:
    budget = _budget(config, _digest(edits, refused))
    budget.add(50)

    reason = budget.spent()

    assert reason is not None
    assert BUDGET in reason
    assert (
        f"{edits} successful edit(s) and {refused} refused command(s) in its last 20 tool calls"
    ) in reason
    assert (budget.extension, counted) == (None, [("extended", 0), ("halted", 1)])


def test_a_second_limit_stops_the_step_and_names_the_extension(
    config: Callable[..., Path], counted: list[tuple[str, float]]
) -> None:
    budget = _budget(config, _digest(2, 0))
    budget.add(50)
    budget.spent()
    budget.add(25)

    reason = budget.spent()

    assert reason is not None
    assert f"{BUDGET} and its one extension to 75 new tokens" in reason
    assert counted[-2:] == [("extended", 0), ("halted", 1)]


def test_the_stop_decides_once_and_counts_once(
    config: Callable[..., Path], counted: list[tuple[str, float]]
) -> None:
    budget = _budget(config, _digest(0, 11))
    budget.add(50)

    first, second = budget.spent(), budget.spent()

    assert first == second
    assert counted == [("extended", 0), ("halted", 1)]


def test_the_ceiling_cuts_the_extension_and_the_stop_names_it(
    config: Callable[..., Path], counted: list[tuple[str, float]]
) -> None:
    budget = _budget(config, _digest(2, 0), ceiling=60)
    budget.add(50)
    extended = budget.spent()
    budget.add(10)

    reason = budget.spent()

    assert extended is None
    assert budget.extension == BudgetExtension(
        limit=50, budget=60, calls=20, edits=2, refused=0, ceiling=True
    )
    assert reason is not None
    assert "`roadmap.implement.step_token_ceiling=60`" in reason


def test_a_ceiling_at_the_budget_leaves_no_room_for_an_extension(
    config: Callable[..., Path], counted: list[tuple[str, float]]
) -> None:
    budget = _budget(config, _digest(2, 0), ceiling=50)
    budget.add(50)

    reason = budget.spent()

    assert reason is not None
    assert "`roadmap.implement.step_token_ceiling=50`" in reason
    assert (budget.extension, counted) == (None, [("extended", 0), ("halted", 1)])


def test_a_missing_digest_stops_the_step_as_before(
    config: Callable[..., Path], counted: list[tuple[str, float]]
) -> None:
    budget = _budget(config, None)
    budget.add(50)

    reason = budget.spent()

    assert reason is not None
    assert BUDGET in reason
    assert "fewer than 20 tool calls" in reason
    assert (budget.extension, counted) == (None, [("extended", 0), ("halted", 1)])


def test_the_item_budget_holds_after_an_extension(
    config: Callable[..., Path], counted: list[tuple[str, float]]
) -> None:
    config(roadmap={"implement": {"item_token_budget": 70}})
    budget = _budget(config, _digest(2, 0))
    budget.add(50)
    budget.spent()
    budget.add(20)

    reason = budget.spent()

    assert reason is not None
    assert "`roadmap.implement.item_token_budget=70`" in reason


def test_a_step_below_its_budget_asks_no_digest(config: Callable[..., Path]) -> None:
    config(roadmap={"implement": {"step_token_budget": 50}})

    def no_digest() -> ProgressDigest | None:
        raise AssertionError("the budget read the tool log below its limit")

    budget = StepBudget(progress=no_digest)
    budget.add(49)

    assert budget.spent() is None


# ── The step ──────────────────────────────────────────────────────────────────────────────


def _step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    script: ModelScript,
    config: Callable[..., Path],
    **implement: int,
) -> StepOutcome:
    config(roadmap={"implement": {"step_token_budget": 50, **implement}})
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def _reads(count: int) -> tuple[tuple[str, dict[str, Any]], ...]:
    return (READ,) * count


def test_a_step_that_edits_at_its_budget_gets_one_more_request_and_ends_done(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_calls(*the_whole_group(), *_reads(17)), say("Done."))

    outcome = _step(implement_store, implement_checkout, script, config, step_token_budget=250)

    assert (len(script.seen), outcome.status, outcome.output_tokens) == (2, StepStatus.DONE, 232)
    assert outcome.extension == BudgetExtension(limit=250, budget=375, calls=20, edits=3, refused=0)
    assert (
        "The step got one extension of its token budget (rule `implement.extension`), from 250 to "
        "375 new tokens: 3 successful edit(s) and 0 refused command(s) in its last 20 tool calls."
    ) in capsys.readouterr().err


def test_a_step_that_repeats_refused_commands_stops_at_its_budget(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    # Two replies of two refusals each: a read between them keeps the refusals from being
    # consecutive, and three in a row end the run (#4043).
    reply = tool_calls(REFUSED, REFUSED, *_reads(8))
    script = ModelScript(reply, reply, say("Done."))

    outcome = _step(implement_store, implement_checkout, script, config, step_token_budget=150)

    assert (len(script.seen), outcome.failure_class, outcome.extension) == (
        2,
        FailureClass.LIMIT_REACHED,
        None,
    )
    assert "`roadmap.implement.step_token_budget=150`" in outcome.reason
    assert "0 successful edit(s) and 4 refused command(s) in its last 20 tool calls" in (
        outcome.reason
    )


def test_an_extended_step_stops_at_its_second_limit(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    script = ModelScript(
        tool_calls(*the_whole_group(), *_reads(17)), tool_calls(READ), say("Done.")
    )

    outcome = _step(implement_store, implement_checkout, script, config, step_token_budget=200)

    assert (len(script.seen), outcome.status, outcome.failure_class) == (
        2,
        StepStatus.STOPPED,
        FailureClass.LIMIT_REACHED,
    )
    assert (
        "`roadmap.implement.step_token_budget=200` and its one extension to 300 new tokens"
    ) in outcome.reason
    assert outcome.extension == BudgetExtension(limit=200, budget=300, calls=20, edits=3, refused=0)


def test_an_extended_step_stops_at_the_ceiling(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    script = ModelScript(
        tool_calls(*the_whole_group(), *_reads(17)), tool_calls(READ), say("Done.")
    )

    outcome = _step(
        implement_store,
        implement_checkout,
        script,
        config,
        step_token_budget=200,
        step_token_ceiling=FIRST + 10,
    )

    assert (len(script.seen), outcome.failure_class) == (2, FailureClass.LIMIT_REACHED)
    assert "`roadmap.implement.step_token_ceiling=290`" in outcome.reason


def test_a_step_with_fewer_calls_than_the_window_stops_at_its_budget(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = _step(implement_store, implement_checkout, script, config)

    assert (len(script.seen), outcome.failure_class, outcome.extension) == (
        1,
        FailureClass.LIMIT_REACHED,
        None,
    )
    assert "fewer than 20 tool calls" in outcome.reason


def test_an_extended_step_stops_at_the_item_budget(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    # The edits come last, so the last 20 calls hold them whatever the order of the reads.
    script = ModelScript(
        tool_calls(*_reads(17)),
        *(tool_calls(call) for call in the_whole_group()),
        tool_calls(READ),
        say("Done."),
    )

    outcome = _step(
        implement_store,
        implement_checkout,
        script,
        config,
        step_token_budget=400,
        item_token_budget=450,
    )

    # The step counts 135, 198, 295, 430 and 485 new tokens after its 5 requests.
    assert (len(script.seen), outcome.failure_class) == (5, FailureClass.LIMIT_REACHED)
    assert outcome.extension == BudgetExtension(limit=400, budget=600, calls=20, edits=3, refused=0)
    assert "`roadmap.implement.item_token_budget=450`" in outcome.reason

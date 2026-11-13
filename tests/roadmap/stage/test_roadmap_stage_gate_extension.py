"""`devops roadmap stage`: a reply that the checks refuse at the last gate return gets one more
return when the last return made progress (#4851).

The rule reads the findings of the last two refused replies: no finding of the reply before stays,
and no finding of the last reply has the fix class `never` in `stage_finding_classes.json`. An item
gets one extra return at most, so one reply gets at most `roadmap.stage.gate_returns` + 2 planner
requests. The rule makes no model call. Each decision logs one `stage gate extension:` line and
adds one count, and each extra return logs one `stage gate extension end:` line with its result.
"""

from __future__ import annotations

import logging
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS
from devops_cli.exceptions import ServiceStoppingError, ended_by_stop
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.service_stop import begin_service_stop
from devops_cli.roadmap.stage.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_eval_cases import CASES_DIRECTORY, load_cases
from devops_cli.roadmap.stage.stage_eval_render import planned_calls
from devops_cli.roadmap.stage.stage_findings import (
    GateExtension,
    StageFinding,
    gate_extension,
    load_finding_classes,
    return_counts,
    stage_finding,
)
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

TEXTS = MESSAGES.roadmap
EXTENSION_TOTAL = "devops_cli_roadmap_stage_gate_extension_total"
EXTENSION_ENDS = "devops_cli_roadmap_stage_gate_extension_ends_total"


def _trace(path: str) -> StageFinding:
    return stage_finding("trace", TEXTS.stage_problem_trace_path.format(path=path))


def _citation(path: str) -> StageFinding:
    return stage_finding(
        "citation", TEXTS.stage_problem_citation_stale.format(field="Feasibility", path=path)
    )


def _caller() -> StageFinding:
    return stage_finding(
        "paths",
        TEXTS.stage_problem_missing_caller.format(function="read", path="src/devops_cli/a.py"),
    )


def _missing_test(path: str) -> StageFinding:
    return stage_finding(
        "paths",
        TEXTS.stage_problem_missing_test_file.format(path=path, hint=TEXTS.stage_path_no_same_name),
    )


# The refused replies of item #5136 in the stage run of 2026-11-13, 06:06Z to 06:42Z (0.127.0): the
# `stage gate findings:` lines gave return 1 `in=3 gone=2 stuck=1 new=0`, return 2 `in=1 gone=0
# stuck=1 new=0` and return 3 `in=1 gone=1 stuck=0 new=1`, and the last reply had one finding of
# the code `stage_problem_trace_path`. The texts of the first findings are stand-ins with the same
# counts. The run stopped at the third return, which was the setting.
ITEM_5136: Final[tuple[tuple[StageFinding, ...], ...]] = (
    (_citation("src/devops_cli/a.py"), _caller(), _trace("docs/a.md")),
    (_trace("docs/a.md"),),
    (_trace("docs/a.md"),),
    (_trace("docs/b.md"),),
)


def _decide(
    before: Sequence[StageFinding] | None, after: Sequence[StageFinding], *, used: int = 0
) -> GateExtension:
    return gate_extension(before, after, used=used, classes=load_finding_classes()).result


# ── The rule ──────────────────────────────────────────────────────────────────


def test_the_5136_fixture_has_the_counts_of_its_log_lines() -> None:
    counts = [tuple(return_counts(before, after)) for before, after in pairwise(ITEM_5136)]

    assert counts == [(3, 2, 1, 0), (1, 0, 1, 0), (1, 1, 0, 1)]


def test_the_last_reply_of_5136_gets_one_more_return() -> None:
    """Each finding of the reply before is gone, and the new finding has a fix class that a
    return fixes."""
    decision = gate_extension(ITEM_5136[2], ITEM_5136[3], used=0, classes=load_finding_classes())

    assert (decision.result, decision.gates) == (GateExtension.EXTENDED, ())


def test_a_finding_that_stays_from_the_reply_before_stops_the_reply() -> None:
    decision = gate_extension(ITEM_5136[1], ITEM_5136[2], used=0, classes=load_finding_classes())

    assert (decision.result, decision.gates) == (GateExtension.STUCK, ("trace",))


def test_a_finding_whose_code_no_return_fixed_stops_the_reply() -> None:
    """The saved replies fixed 0 of 17 `stage_problem_missing_test_file` findings (#4846)."""
    decision = gate_extension(
        [_missing_test("tests/test_a.py")],
        [_missing_test("tests/test_b.py")],
        used=0,
        classes=load_finding_classes(),
    )

    assert (decision.result, decision.gates) == (GateExtension.NEVER, ("paths",))


def test_the_same_stale_test_path_again_stops_the_reply_as_stuck() -> None:
    """The record of #4472 repeated one stale test path: no extra return."""
    stale = [_missing_test("tests/test_old.py")]

    assert _decide(stale, stale) is GateExtension.STUCK


def test_an_item_that_used_its_extension_gets_no_other() -> None:
    assert (
        _decide(ITEM_5136[2], ITEM_5136[3], used=CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS)
        is GateExtension.USED
    )


def test_a_reply_with_no_reply_before_it_gets_no_extension() -> None:
    """With `roadmap.stage.gate_returns` 0, no return compares two replies."""
    assert _decide(None, ITEM_5136[3]) is GateExtension.FIRST


def test_a_code_that_the_data_file_does_not_hold_does_not_stop_the_reply() -> None:
    uncoded = [stage_finding("paths", "A text that no template gives.")]

    assert _decide(ITEM_5136[2], uncoded) is GateExtension.EXTENDED


def test_the_dry_run_of_the_eval_counts_the_extra_plan_run() -> None:
    """`devops roadmap eval stage --dry-run` lists the requests of a case: the first plan run, its
    3 returns, the extra return and the split."""
    (case,) = load_cases(REPO_ROOT / CASES_DIRECTORY)[:1]

    (request,) = planned_calls([case], "https://gateway.example.com", toolbox=False)

    assert request.repeat == TEXTS.stage_eval_dry_run_repeat.format(
        count=1 + 3 + CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS + 1
    )


# ── The stage job ─────────────────────────────────────────────────────────────


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    return store


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(
        validate_args("1-the-job-drops-a-comment"), *[(0, VALID_REPORT)] * 8
    )
    return openspec_fake


@pytest.fixture
def counted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """The `(metric, result)` pairs of the extension that the stage job counts."""
    sent: list[tuple[str, str]] = []

    def fake_emit(instrument: Any, value: float, attributes: dict[str, Any] | None = None) -> None:
        if instrument.name in {EXTENSION_TOTAL, EXTENSION_ENDS}:
            sent.append((instrument.name, (attributes or {})["result"]))

    monkeypatch.setattr("devops_cli.roadmap.stage.stage.emit", fake_emit)
    return sent


def _missing(*paths: str) -> Any:
    """A reply that the `paths` gate refuses once for each of `paths`, a file that does not
    exist."""
    group = make_stage_proposal().groups[0]
    return make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, *paths]})]
    )


def _plan(store: InMemoryRoadmapStore, repo: StageRepo) -> StagePlan:
    return plan_stage(
        store, repo=STAGE_REPO, source=repo.clone, filters=parse_filters(()), model=None
    )


def _lines(caplog: pytest.LogCaptureFixture, event: str) -> list[str]:
    """The fields of each `event` line, with no version."""
    return [
        r.getMessage().removeprefix(f"{event}: ").rsplit(" version=", 1)[0]
        for r in caplog.records
        if r.getMessage().startswith(f"{event}: ")
    ]


def test_a_reply_whose_findings_fall_as_in_5136_gets_a_fourth_return_and_stages(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
    counted: list[tuple[str, str]],
) -> None:
    """The replies have the counts of #5136: 3 findings, then 1 that stays two times, then 1 new
    finding. The fourth return passes the checks."""
    model_fake.answer(
        _missing("tests/test_a.py", "tests/test_b.py", "tests/test_c.py"),
        _missing("tests/test_a.py"),
        _missing("tests/test_a.py"),
        _missing("tests/test_d.py"),
        make_stage_proposal(),
    )

    with caplog.at_level(logging.INFO):
        plan = _plan(store, stage_repo)

    (attempt,) = plan.attempts
    assert (len(plan.ready), plan.failed, model_fake.call_count) == (1, (), 5)
    assert attempt.gate_returns == 4
    assert [line.split(" item=#1 ")[1] for line in _lines(caplog, "stage gate findings")] == [
        "return=1 in=3 gone=2 stuck=1 new=0",
        "return=2 in=1 gone=0 stuck=1 new=0",
        "return=3 in=1 gone=1 stuck=0 new=1",
        "return=4 in=1 gone=1 stuck=0 new=0",
    ]
    assert _lines(caplog, "stage gate extension") == [
        f"repo={STAGE_REPO} item=#1 returns=3 in=1 gone=1 stuck=0 new=1 never=0 result=extended"
    ]
    assert _lines(caplog, "stage gate extension end") == [
        f"repo={STAGE_REPO} item=#1 returns=4 result=passed"
    ]
    assert counted == [(EXTENSION_TOTAL, "extended"), (EXTENSION_ENDS, "passed")]


def test_no_reply_gets_more_planner_requests_than_the_setting_and_one_extension(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
    counted: list[tuple[str, str]],
) -> None:
    """Each reply fixes the finding of the reply before and has a new one. The item gets one extra
    return, and the stop after it names the used extension."""
    model_fake.answer(*(_missing(f"tests/test_{name}.py") for name in "abcdefgh"))

    with caplog.at_level(logging.INFO):
        plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    assert model_fake.call_count == 1 + 3 + CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS
    assert failure.reason.startswith(
        TEXTS.stage_invalid.format(returns=4, stop=TEXTS.stage_gate_stop_used, problem="")
    )
    assert [line.rsplit(" result=", 1)[1] for line in _lines(caplog, "stage gate extension")] == [
        "extended",
        "used",
    ]
    assert _lines(caplog, "stage gate extension end") == [
        f"repo={STAGE_REPO} item=#1 returns=4 result=refused"
    ]
    assert counted == [
        (EXTENSION_TOTAL, "extended"),
        (EXTENSION_ENDS, "refused"),
        (EXTENSION_TOTAL, "used"),
    ]


def test_a_finding_that_stays_ends_the_reply_at_the_setting_and_the_failure_names_the_gate(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
    counted: list[tuple[str, str]],
) -> None:
    model_fake.answer(_missing("tests/test_a.py"))

    with caplog.at_level(logging.INFO):
        plan = _plan(store, stage_repo)

    (failure,) = plan.failed
    stop = TEXTS.stage_gate_stop_stuck.format(gates="paths")
    assert model_fake.call_count == 1 + 3
    assert failure.reason.startswith(TEXTS.stage_invalid.format(returns=3, stop=stop, problem=""))
    assert _lines(caplog, "stage gate extension end") == []
    assert counted == [(EXTENSION_TOTAL, "stuck")]


def test_the_setting_moves_the_return_of_the_decision(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    config: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    config(roadmap={"stage": {"gate_returns": 1}})
    model_fake.answer(
        _missing("tests/test_a.py"), _missing("tests/test_b.py"), make_stage_proposal()
    )

    with caplog.at_level(logging.INFO):
        plan = _plan(store, stage_repo)

    assert (len(plan.ready), model_fake.call_count) == (1, 3)
    assert [line.split(" ")[2] for line in _lines(caplog, "stage gate extension")] == ["returns=1"]


def test_no_extra_return_starts_once_the_service_stops(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
    counted: list[tuple[str, str]],
) -> None:
    """The extra return is a new plan run. Once the Service stops, it does not start, and its end
    line gives the result `ended`."""

    def last_reply_in_the_drain(prompt: str) -> Any:
        begin_service_stop()
        return _missing("tests/test_d.py")

    model_fake.answer(
        _missing("tests/test_a.py"),
        _missing("tests/test_b.py"),
        _missing("tests/test_c.py"),
        last_reply_in_the_drain,
    )

    with caplog.at_level(logging.INFO), pytest.raises(ServiceStoppingError) as stopped:
        _plan(store, stage_repo)

    assert (ended_by_stop(stopped.value), model_fake.call_count) == (True, 4)
    assert _lines(caplog, "stage gate extension end") == [
        f"repo={STAGE_REPO} item=#1 returns=3 result=ended"
    ]
    assert counted == [(EXTENSION_TOTAL, "extended"), (EXTENSION_ENDS, "ended")]

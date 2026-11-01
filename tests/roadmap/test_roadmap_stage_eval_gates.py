"""The replay of the golden set through the gates of the stage job (#3028).

The replay of the whole set runs here, offline. It fails when a gate stops refusing a known-bad
plan, and a `good` plan must pass every gate.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.stage_eval_cases import (
    CASES_DIRECTORY,
    CaseFacts,
    DefectType,
    GateName,
    StageCase,
    Verdict,
    load_cases,
)
from devops_cli.roadmap.stage_eval_gates import (
    GATES,
    PENDING_GATES,
    DefectStatus,
    PlanUnderTest,
    gate_for,
    replay_all,
    replay_case,
    run_gates,
)
from tests.support.paths import REPO_ROOT


@pytest.fixture(scope="module")
def cases() -> list[StageCase]:
    return load_cases(REPO_ROOT / CASES_DIRECTORY)


def _first_with(cases: list[StageCase], gate: GateName) -> StageCase:
    return next(case for case in cases if any(d.gate is gate and d.paths for d in case.defects))


def test_every_gate_still_refuses_every_known_bad_plan_it_must(cases: list[StageCase]) -> None:
    report = replay_all(cases)

    assert report.failures == []
    assert {total.gate.name: (total.known > 0, total.missed) for total in report.totals()} == {
        GateName.PATHS: (True, 0),
        GateName.KIND: (True, 0),
    }


def test_each_good_plan_passes_every_gate(cases: list[StageCase]) -> None:
    report = replay_all(cases)

    assert report.good() == (3, 3)
    assert all(not r.refused for r in report.replays if r.case.verdict is Verdict.GOOD)


def test_the_pending_defects_are_counted_and_fail_nothing(cases: list[StageCase]) -> None:
    report = replay_all(cases)

    pending = report.count(DefectStatus.PENDING)

    assert set(pending) == set(PENDING_GATES)
    assert report.failures == []


def test_a_defect_is_listed_for_the_gate_that_catches_its_type(cases: list[StageCase]) -> None:
    for case in cases:
        for defect in case.defects:
            assert defect.gate in (gate_for(defect.type), GateName.NONE), (case.name, defect.type)


def test_a_gate_that_stops_refusing_a_plan_fails_the_replay(cases: list[StageCase]) -> None:
    case = _first_with(cases, GateName.PATHS)
    missing = {path for d in case.defects for path in d.paths}
    healed = case.model_copy(
        update={"facts": CaseFacts(tracked=(*case.facts.tracked, *missing), capabilities=())}
    )

    replay = replay_case(healed)

    assert any(o.status is DefectStatus.MISSED for o in replay.outcomes)
    assert any("no longer refuses" in failure for failure in replay.failures)


def test_a_path_gate_that_names_other_paths_than_the_defect_fails_the_replay(
    cases: list[StageCase],
) -> None:
    case = _first_with(cases, GateName.PATHS)
    defect = next(d for d in case.defects if d.paths)
    renamed = defect.model_copy(update={"paths": ("tests/never/named.py",)})
    changed = case.model_copy(update={"defects": (renamed,)})

    assert replay_case(changed).outcomes[0].status is DefectStatus.MISSED


def test_a_good_plan_that_a_gate_refuses_fails_the_replay(cases: list[StageCase]) -> None:
    good = next(case for case in cases if case.verdict is Verdict.GOOD)
    plan = {**good.plan, "groups": [{**good.groups[0], "changes": ["src/devops_cli/nope.py"]}]}

    replay = replay_case(good.model_copy(update={"plan": plan}))

    assert replay.refused
    assert replay.failures == [f"{good.name}: a good plan is refused by the gate paths."]


def test_the_kind_gate_gives_the_message_of_the_schema_for_a_group_with_no_source(
    cases: list[StageCase],
) -> None:
    case = next(c for c in cases if any(d.gate is GateName.KIND for d in c.defects))

    problems = run_gates(PlanUnderTest.of_case(case))[GateName.KIND]

    assert problems
    assert all("changes no path under src/" in problem for problem in problems)


def test_a_pending_defect_of_a_type_with_a_gate_is_stale(cases: list[StageCase]) -> None:
    case = _first_with(cases, GateName.PATHS)
    defect = case.defects[0].model_copy(
        update={"type": DefectType.MISSING_PATH, "gate": GateName.PENDING, "paths": ()}
    )

    replay = replay_case(case.model_copy(update={"defects": (defect,)}))

    assert replay.outcomes[0].status is DefectStatus.STALE
    assert replay.failures[0].endswith("Set its gate in case.json.")


def test_a_defect_that_no_gate_judges_fails_nothing(cases: list[StageCase]) -> None:
    case = next(c for c in cases if any(d.type is DefectType.OTHER for d in c.defects))
    other = next(d for d in case.defects if d.type is DefectType.OTHER)

    replay = replay_case(case.model_copy(update={"defects": (other,)}))

    assert replay.outcomes[0].status is DefectStatus.UNJUDGED
    assert replay.failures == []


def test_the_gates_and_the_pending_gates_cover_each_type_once() -> None:
    caught = {gate.catches for gate in GATES}

    assert caught.isdisjoint(PENDING_GATES)
    assert caught | set(PENDING_GATES) | {DefectType.OTHER} == set(DefectType)

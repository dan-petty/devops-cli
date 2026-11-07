"""The replay of the golden set through the gates of the stage job (#3028).

The replay of the whole set runs here, offline. It fails when a gate stops refusing a known-bad
plan, and a `good` plan must pass every gate.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.stage import stage_change
from devops_cli.roadmap.stage.stage_eval_cases import (
    CASES_DIRECTORY,
    CaseFacts,
    DefectType,
    GateName,
    StageCase,
    Verdict,
    load_cases,
)
from devops_cli.roadmap.stage.stage_eval_gates import (
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
        GateName.CRITERIA: (False, 0),
        GateName.CONTENT: (True, 0),
    }


def test_each_good_plan_passes_every_gate(cases: list[StageCase]) -> None:
    report = replay_all(cases)

    assert report.good() == (4, 4)
    assert all(not r.refused for r in report.replays if r.case.verdict is Verdict.GOOD)


def test_no_defect_waits_for_a_gate_once_the_gates_of_3012_to_3017_are_built(
    cases: list[StageCase],
) -> None:
    report = replay_all(cases)

    assert PENDING_GATES == {}
    assert report.count(DefectStatus.PENDING) == {}
    assert report.count(DefectStatus.STALE) == {}
    assert not any(d.gate is GateName.PENDING for c in cases for d in c.defects)
    assert report.failures == []


_WAITED_FOR_A_GATE = (
    DefectType.IGNORES_EXISTING_CODE,
    DefectType.SPEC_DELTA_WRONG,
    DefectType.VERIFY_FORM,
    DefectType.TASK_ORDER,
)


def test_a_defect_of_a_type_that_waited_for_a_gate_is_judged_or_says_why_not(
    cases: list[StageCase],
) -> None:
    defects = [d for c in cases for d in c.defects if d.type in _WAITED_FOR_A_GATE]

    judged = [d for d in defects if d.gate is not GateName.NONE]
    unjudged = [d for d in defects if d.gate is GateName.NONE]

    assert len(defects) == 75
    assert all(d.gate is GateName.PATHS and d.message for d in judged)
    assert all(d.reason for d in unjudged)
    assert not any(d.reason for d in judged)


def test_the_counts_of_each_type_are_the_baseline_that_a_change_of_a_gate_beats(
    cases: list[StageCase],
) -> None:
    """The caught and unjudged defects of each type that waited for a gate (#3208). A change that
    lets a gate judge more defects raises the first number and lowers the second."""
    report = replay_all(cases)

    counts = {t.type: (t.caught, t.missed, t.unjudged) for t in report.by_type()}

    assert counts[DefectType.MISSING_PATH] == (32, 0, 0)
    assert counts[DefectType.SPEC_DELTA_WRONG] == (5, 0, 20)
    assert counts[DefectType.VERIFY_FORM] == (6, 0, 12)
    assert counts[DefectType.TASK_ORDER] == (1, 0, 8)
    assert counts[DefectType.IGNORES_EXISTING_CODE] == (0, 0, 23)
    assert report.judged() == (70, 307)


def test_the_judged_share_counts_the_caught_and_the_missed_and_not_the_rest(
    cases: list[StageCase],
) -> None:
    case = next(c for c in cases if c.pull == 2977)
    healed = case.model_copy(update={"plan": {**case.plan, "skip_specs": True, "specs": []}})

    report = replay_all([case, healed])

    assert [t.missed for t in report.by_type()].count(1) == 1
    assert report.judged()[0] == sum(t.caught + t.missed for t in report.by_type())
    assert report.judged()[1] == sum(len(c.defects) for c in (case, healed))


def test_a_defect_is_listed_for_the_gate_that_catches_its_type_or_for_a_gate_that_finds_it(
    cases: list[StageCase],
) -> None:
    """The check of the job (`paths`) refuses a defect of the types `spec_delta_wrong` and
    `verify_form`, since it runs the rules of the spec delta and of the form with the path rule
    (#3208): the case then names that gate and holds its message."""
    for case in cases:
        for defect in case.defects:
            by_type = defect.gate in (gate_for(defect.type), GateName.NONE)
            by_finding = defect.gate in {g.name for g in GATES} and defect.message
            assert by_type or by_finding, (case.name, defect.type)


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


def test_the_replay_runs_the_check_of_the_job_so_a_spec_rule_that_refuses_all_fails_it(
    cases: list[StageCase], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stage_change, "_spec_problems", lambda _spec, _known: ["A spec is wrong."])

    report = replay_all(cases)

    assert any("a good plan is refused by the gate paths" in f for f in report.failures)


def test_the_capabilities_of_the_facts_decide_if_a_spec_may_modify_a_capability(
    cases: list[StageCase],
) -> None:
    good = next(c for c in cases if c.verdict is Verdict.GOOD and c.plan["specs"][0]["modified"])
    unknown = CaseFacts(tracked=good.facts.tracked, capabilities=())

    assert not replay_case(good).refused
    assert replay_case(good.model_copy(update={"facts": unknown})).refused


def test_a_kind_defect_that_the_gate_explains_with_other_words_fails_the_replay(
    cases: list[StageCase],
) -> None:
    case = next(c for c in cases if any(d.gate is GateName.KIND for d in c.defects))
    defect = next(d for d in case.defects if d.gate is GateName.KIND)
    reworded = defect.model_copy(update={"message": "a text the schema never gives"})

    replay = replay_case(case.model_copy(update={"defects": (reworded,)}))

    assert replay.outcomes[0].status is DefectStatus.MISSED


def test_each_kind_defect_names_the_message_of_the_schema(cases: list[StageCase]) -> None:
    kinds = [d for c in cases for d in c.defects if d.gate is GateName.KIND]

    assert kinds
    assert all(defect.message for defect in kinds)


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
    other = other.model_copy(update={"gate": GateName.NONE})

    replay = replay_case(case.model_copy(update={"defects": (other,)}))

    assert replay.outcomes[0].status is DefectStatus.UNJUDGED
    assert replay.failures == []


def test_the_gates_and_the_pending_gates_cover_each_type_once_but_those_no_gate_judges() -> None:
    caught = {gate.catches for gate in GATES}
    unjudged = {
        DefectType.FALSE_PREMISE,
        DefectType.SPEC_DELTA_WRONG,
        DefectType.VERIFY_FORM,
        DefectType.TASK_ORDER,
        DefectType.IGNORES_EXISTING_CODE,
    }

    assert caught.isdisjoint(PENDING_GATES)
    assert caught | set(PENDING_GATES) | unjudged == set(DefectType)


def test_the_replay_of_the_plan_of_2977_is_refused_for_the_spec_delta_of_a_tests_only_change(
    cases: list[StageCase],
) -> None:
    case = next(c for c in cases if c.pull == 2977)
    delta = next(d for d in case.defects if d.type is DefectType.SPEC_DELTA_WRONG)

    replay = replay_case(case)

    assert (case.plan["skip_specs"], [g["changes"] for g in case.groups]) == (
        False,
        [["tests/test_scanner_tool_executor.py"]],
    )
    assert delta.gate is GateName.PATHS
    assert next(o.status for o in replay.outcomes if o.defect is delta) is DefectStatus.CAUGHT
    assert any(
        "every path in `changes` is under tests/" in problem
        for problem in replay.problems[GateName.PATHS]
    )
    assert replay.failures == []


ACCEPTANCE_BODY = "Text.\n\n### Acceptance criteria\n\n- [ ] First.\n- [ ] Second.\n"


def _with_criteria(case: StageCase, criteria: list[dict[str, object]]) -> StageCase:
    return case.model_copy(
        update={"issue_body": ACCEPTANCE_BODY, "plan": {**case.plan, "criteria": criteria}}
    )


def test_the_criteria_gate_refuses_a_plan_that_leaves_a_criterion_out(
    cases: list[StageCase],
) -> None:
    good = next(case for case in cases if case.verdict is Verdict.GOOD)
    one = [{"criterion": "First.", "group": 1, "reason": None}]

    problems = run_gates(PlanUnderTest.of_case(_with_criteria(good, one)))

    assert [p for p in problems[GateName.CRITERIA]] == [
        'The issue lists the acceptance criterion "Second.", and `criteria` has no entry with '
        "this text. Add an entry that copies the text, with the number of the group that "
        "delivers it or pending-person and a reason."
    ]


def test_the_criteria_gate_passes_a_plan_that_maps_every_criterion(
    cases: list[StageCase],
) -> None:
    good = next(case for case in cases if case.verdict is Verdict.GOOD)
    both = [{"criterion": t, "group": 1, "reason": None} for t in ("First.", "Second.")]

    assert not replay_case(_with_criteria(good, both)).refused


def test_a_recorded_plan_has_no_criteria_list_so_the_criteria_gate_does_not_judge_it(
    cases: list[StageCase],
) -> None:
    good = next(case for case in cases if case.verdict is Verdict.GOOD)
    body = good.model_copy(update={"issue_body": ACCEPTANCE_BODY})

    assert run_gates(PlanUnderTest.of_case(body))[GateName.CRITERIA] == []


def test_the_dropped_criterion_defects_of_the_set_wait_for_no_gate(cases: list[StageCase]) -> None:
    dropped = [d for c in cases for d in c.defects if d.type is DefectType.CRITERION_DROPPED]

    assert dropped
    assert {d.gate for d in dropped} == {GateName.NONE}
    assert DefectType.CRITERION_DROPPED not in PENDING_GATES


@pytest.mark.parametrize("pull", [2977, 2975, 2985, 2990], ids=lambda pull: f"pull-{pull}")
def test_the_replay_of_a_plan_with_a_pytest_verify_command_is_refused_for_its_verify_form(
    cases: list[StageCase], pull: int
) -> None:
    case = next(c for c in cases if c.pull == pull)
    forms = [d for d in case.defects if d.type is DefectType.VERIFY_FORM]
    judged = [d for d in forms if d.gate is GateName.PATHS]

    replay = replay_case(case)

    assert any(g["verify"].startswith("uv run pytest") for g in case.groups)
    assert len(judged) == 1
    assert next(o.status for o in replay.outcomes if o.defect is judged[0]) is DefectStatus.CAUGHT
    assert any("`uv run pytest " in problem for problem in replay.problems[GateName.PATHS])
    assert replay.failures == []


def _stage_move_case(cases: list[StageCase]) -> StageCase:
    return next(case for case in cases if case.pull == 3378)


def _with_verify(case: StageCase, verify: str) -> StageCase:
    groups = [
        {
            **group,
            "verify": verify,
            "implementation": (
                f"{group['implementation']}, and run "
                "`uv run devops roadmap eval stage --replay` with the score before and after "
                "the change"
            ),
        }
        for group in case.groups
    ]
    return case.model_copy(update={"plan": {**case.plan, "groups": groups}})


def test_the_replay_refuses_a_negative_search_with_no_recorded_hit(
    cases: list[StageCase],
) -> None:
    case = _with_verify(
        _stage_move_case(cases),
        "! git grep -n -F devops_cli.roadmap.stage_missing src/ tests/",
    )

    problems = run_gates(PlanUnderTest.of_case(case))[GateName.PATHS]

    assert any("already passes before the change and proves nothing" in p for p in problems)


def test_the_replay_accepts_a_negative_search_whose_recorded_hit_survives(
    cases: list[StageCase],
) -> None:
    case = _with_verify(
        _stage_move_case(cases),
        "! git grep -n -F devops_cli.roadmap.stage_ src/ tests/",
    )

    assert run_gates(PlanUnderTest.of_case(case))[GateName.PATHS] == []


@pytest.mark.parametrize(
    ("rule", "kind"),
    [
        ("_needs_no_spec", DefectType.SPEC_DELTA_WRONG),
        ("form_problems", DefectType.VERIFY_FORM),
    ],
)
def test_a_rule_of_the_check_that_stops_refusing_fails_the_replay_of_its_defects(
    cases: list[StageCase], monkeypatch: pytest.MonkeyPatch, rule: str, kind: DefectType
) -> None:
    caught = {d.gate for c in cases for d in c.defects if d.type is kind}
    monkeypatch.setattr(stage_change, rule, lambda *_: [] if rule == "form_problems" else False)

    report = replay_all(cases)

    assert GateName.PATHS in caught
    assert any(f"no longer refuses the {kind} defect" in failure for failure in report.failures)
    assert next(t.missed for t in report.by_type() if t.type is kind) > 0


def test_a_defect_that_the_replay_cannot_show_is_not_a_miss_of_a_gate(
    cases: list[StageCase],
) -> None:
    """A defect in the code that exists, or in the order of the work, has the gate `none`: the
    check of the job cannot see it in a recorded plan, and the replay does not fail it."""
    case = next(c for c in cases if DefectType.IGNORES_EXISTING_CODE in c.defect_types())
    defect = next(d for d in case.defects if d.type is DefectType.IGNORES_EXISTING_CODE)

    replay = replay_case(case.model_copy(update={"defects": (defect,)}))

    assert (defect.gate, bool(defect.reason)) == (GateName.NONE, True)
    assert replay.outcomes[0].status is DefectStatus.UNJUDGED
    assert replay.failures == []


def test_the_content_gate_catches_the_other_type_and_run_gates_holds_its_key() -> None:
    assert gate_for(DefectType.OTHER) is GateName.CONTENT
    assert GateName.CONTENT in {gate.name for gate in GATES}


def _placeholder_case(cases: list[StageCase]) -> StageCase:
    return next(c for c in cases if c.pull == 3167)


def test_the_replay_catches_a_placeholder_in_why_through_the_content_gate(
    cases: list[StageCase],
) -> None:
    case = _placeholder_case(cases)
    defect = next(d for d in case.defects if d.gate is GateName.CONTENT)

    replay = replay_case(case)

    assert case.plan["why"] == "x"
    assert defect.type is DefectType.OTHER
    assert run_gates(PlanUnderTest.of_case(case)).keys() >= {GateName.CONTENT}
    assert next(o.status for o in replay.outcomes if o.defect is defect) is DefectStatus.CAUGHT
    assert replay.failures == []


def test_the_replay_catches_a_verify_command_of_true_through_the_paths_gate(
    cases: list[StageCase],
) -> None:
    case = _placeholder_case(cases)
    defect = next(d for d in case.defects if d.type is DefectType.VERIFY_FORM)

    replay = replay_case(case)

    assert [g["verify"] for g in case.groups] == ["true"]
    assert next(o.status for o in replay.outcomes if o.defect is defect) is DefectStatus.CAUGHT


def test_a_content_gate_that_stops_refusing_a_plan_fails_the_replay(
    cases: list[StageCase],
) -> None:
    case = _placeholder_case(cases)
    real = "The job plans a real change here."
    group = {**case.groups[0], "implementation": real}
    written = case.model_copy(
        update={
            "plan": {
                **case.plan,
                "why": real,
                "existing_tool": real,
                "feasibility": [real],
                "groups": [group],
            }
        }
    )

    replay = replay_case(written)

    assert replay.problems[GateName.CONTENT] == []
    assert [o.status for o in replay.outcomes if o.defect.gate is GateName.CONTENT] == [
        DefectStatus.MISSED
    ]
    assert any("no longer refuses" in failure for failure in replay.failures)


def test_the_replay_passes_recorded_constants(cases: list[StageCase]) -> None:
    good_case = next(case for case in cases if case.verdict is Verdict.GOOD)
    replay = replay_case(good_case)
    assert not replay.refused

    specs = list(good_case.plan["specs"])
    spec = specs[0]
    bad_spec = {
        **spec,
        "added": [
            {
                "name": "Summary bound",
                "text": "The summary SHALL be bounded.",
                "scenarios": [
                    {
                        "name": "Mismatch",
                        "when": "A spec scenario says `SUMMARY_MAX_CHARS` is 40.",
                        "then": "Refuse.",
                    }
                ],
            }
        ],
    }
    facts_with_constants = good_case.facts.model_copy(
        update={"constants": (("SUMMARY_MAX_CHARS", 60),)}
    )
    case_with_constants = good_case.model_copy(
        update={
            "facts": facts_with_constants,
            "plan": {**good_case.plan, "specs": [bad_spec]},
        }
    )
    replay_constants = replay_case(case_with_constants)
    assert any(
        "SUMMARY_MAX_CHARS is 60 in the staged tree, but the plan says 40." in p
        for p in replay_constants.problems[GateName.PATHS]
    )

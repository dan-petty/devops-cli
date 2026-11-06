"""The golden set holds a plan with a group that changes only test files and delivers its
criterion, and the same plan without the group that gives it the code to test (#3448).

The first plan is the merged plan of #3410. Its group that adds the case of a move of the stage
modules changes fixture files and a test file, and an earlier group adds the field that the case
needs. The second plan lacks that earlier group, so the group of the case delivers nothing. No gate
judges the difference: the verification pass reads it. The replay lists the defect with the gate
`none`, and the finding of a model about it keeps the plan in draft.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.roadmap.stage_eval_cases import (
    CASES_DIRECTORY,
    DefectType,
    GateName,
    StageCase,
    Verdict,
    load_cases,
)
from devops_cli.roadmap.stage_eval_gates import DefectStatus, replay_case
from devops_cli.roadmap.stage_verify import Finding, VerificationInput, open_findings
from tests.support.paths import REPO_ROOT

DROPPED = "3410-the-eval-field-group-is-dropped"
DELIVERED = "good-3410-the-stage-gate-proves-a-negative"
FIELD_FILE = "src/devops_cli/roadmap/stage_eval_cases.py"
CRITERION = (
    "The stage eval replay MUST read the negative-search evidence from the eval case "
    "and MUST run no `git` command."
)


@pytest.fixture(scope="module")
def cases() -> dict[str, StageCase]:
    return {case.name: case for case in load_cases(REPO_ROOT / CASES_DIRECTORY)}


def _only_tests(group: dict[str, Any]) -> bool:
    return all(path.startswith("tests/") for path in group["changes"])


def test_the_dropped_case_has_one_defect_that_no_gate_judges(cases: dict[str, StageCase]) -> None:
    replay = replay_case(cases[DROPPED])

    (defect,) = cases[DROPPED].defects
    assert (defect.type, defect.gate, defect.reason.strip() != "") == (
        DefectType.CRITERION_DROPPED,
        GateName.NONE,
        True,
    )
    assert [outcome.status for outcome in replay.outcomes] == [DefectStatus.UNJUDGED]
    assert replay.failures == []


def test_no_gate_refuses_the_plan_of_the_dropped_case(cases: dict[str, StageCase]) -> None:
    replay = replay_case(cases[DROPPED])

    assert not replay.refused


def test_the_good_case_is_the_twin_of_the_dropped_case_and_every_gate_accepts_it(
    cases: dict[str, StageCase],
) -> None:
    good = cases[DELIVERED]

    replay = replay_case(good)

    assert (good.verdict, good.twin_of, good.defects) == (Verdict.GOOD, DROPPED, ())
    assert not replay.refused
    assert replay.failures == []


def test_the_group_that_adds_the_case_changes_only_test_files_in_both_plans(
    cases: dict[str, StageCase],
) -> None:
    for name in (DROPPED, DELIVERED):
        groups = cases[name].groups
        case_group = next(g for g in groups if "move of the stage modules" in g["title"])

        assert _only_tests(case_group), name


def test_only_the_good_plan_has_a_group_that_changes_the_case_model(
    cases: dict[str, StageCase],
) -> None:
    changing = {
        name: [g["title"] for g in cases[name].groups if FIELD_FILE in g["changes"]]
        for name in (DROPPED, DELIVERED)
    }

    assert changing == {
        DROPPED: [],
        DELIVERED: ["Read the evidence from the eval case in the replay"],
    }


def test_the_dropped_plan_is_the_good_plan_without_that_group(cases: dict[str, StageCase]) -> None:
    kept = [g for g in cases[DELIVERED].groups if FIELD_FILE not in g["changes"]]

    assert cases[DROPPED].groups == kept


def test_a_quoted_dropped_criterion_finding_on_the_dropped_case_keeps_the_plan_in_draft(
    cases: dict[str, StageCase],
) -> None:
    case = cases[DROPPED]
    given = VerificationInput.of(
        number=case.issue,
        title=case.title,
        body=case.issue_body,
        plan=case.plan,
        source=Path("/nonexistent"),
    )
    finding = Finding(
        type=DefectType.CRITERION_DROPPED,
        where="group 3",
        problem="The group writes only a fixture and a test, and no group adds the field.",
        quote=CRITERION,
    )

    assert open_findings([finding], given) == [finding]

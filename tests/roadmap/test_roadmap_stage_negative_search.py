"""The stage gate refuses a negative search that proves nothing or that a created module keeps
(#3410).

The case holds the move plan of #3378 and the paths that each literal matched before the change.
The replay reads that record and runs no git, so the test runs offline.
"""

from __future__ import annotations

from devops_cli.roadmap.stage_eval_cases import CASES_DIRECTORY, StageCase, load_cases
from devops_cli.roadmap.stage_eval_gates import GateName, PlanUnderTest, run_gates
from tests.support.paths import REPO_ROOT

CASE = "3372-the-stage-plan-of-a-module"
NO_HIT = "! git grep -n -F devops_cli.roadmap.stage_missing src/ tests/"
BARE = "! git grep -n -F devops_cli.roadmap.stage src/ tests/"
DOTTED = "! git grep -n -F devops_cli.roadmap.stage_ src/ tests/"


def _case() -> StageCase:
    return next(case for case in load_cases(REPO_ROOT / CASES_DIRECTORY) if case.name == CASE)


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


def _problems(case: StageCase) -> list[str]:
    return run_gates(PlanUnderTest.of_case(case))[GateName.PATHS]


def test_the_case_records_the_hits_of_every_negative_search() -> None:
    case = _case()

    assert case.facts.search_evidence["devops_cli.roadmap.stage_missing"] == ()
    assert case.facts.search_evidence["devops_cli.roadmap.stage"] == (
        "src/devops_cli/roadmap/stage.py",
    )
    assert (
        "src/devops_cli/roadmap/stage_ready.py"
        in case.facts.search_evidence["devops_cli.roadmap.stage_"]
    )


def test_a_negative_search_with_no_recorded_hit_is_refused() -> None:
    problems = _problems(_with_verify(_case(), NO_HIT))

    assert any("already passes before the change and proves nothing" in p for p in problems)


def test_a_negative_search_that_a_created_module_keeps_is_refused() -> None:
    problems = _problems(_with_verify(_case(), BARE))

    assert any("can never pass on the produced tree" in p for p in problems)
    assert any("src/devops_cli/roadmap/stage/__init__.py" in p for p in problems)


def test_a_negative_search_whose_recorded_hit_survives_is_accepted() -> None:
    assert _problems(_with_verify(_case(), DOTTED)) == []

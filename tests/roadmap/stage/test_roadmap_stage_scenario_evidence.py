"""`devops roadmap stage`: refuse a spec scenario that names code with no behavior test (#3321)."""

from __future__ import annotations

from devops_cli.roadmap.stage.stage_change import (
    StageGroup,
    StageScenario,
    StageSpec,
    check_proposal,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

TREE = StagedTree(
    [
        "src/devops_cli/sample.py",
        "tests/test_sample.py",
    ]
)


def _spec_with(scenarios: list[StageScenario]) -> StageSpec:
    return StageSpec.model_validate(
        {
            "capability": "comment-thread",
            "purpose": "Defines how the job reads comments, so none is lost.",
            "added": [
                {
                    "name": "The job keeps every comment",
                    "text": "The job SHALL keep every comment of a thread.",
                    "scenarios": [s.model_dump() for s in scenarios],
                }
            ],
        }
    )


def _group(test: str = "Write `test_x` in `tests/test_sample.py`") -> StageGroup:
    return StageGroup.model_construct(
        title="A behavior group",
        kind="behavior",
        reads=["src/devops_cli/sample.py"],
        changes=["src/devops_cli/sample.py"],
        creates=[],
        creates_lines={},
        test=test,
        implementation="Do x in `src/devops_cli/sample.py`",
        documentation=None,
        verify="uv run devops ci test tests/test_sample.py",
    )


def test_a_scenario_that_names_code_with_no_behavior_test_is_refused() -> None:
    scenario = StageScenario(
        name="The loki mode",
        when="single binary is configured",
        then="`_loki_mode` raises a failure",
    )
    spec = _spec_with([scenario])
    proposal = make_stage_proposal(specs=[spec], groups=[_group()])

    problems = check_proposal(proposal, ["comment-thread"], TREE)

    matching = [p for p in problems if "The loki mode" in p and "_loki_mode" in p]
    assert len(matching) == 1


def test_a_scenario_that_names_a_command_has_no_scenario_problem() -> None:
    scenario = StageScenario(
        name="The loki mode",
        when="single binary is configured",
        then="`_loki_mode` runs `helm template`",
    )
    spec = _spec_with([scenario])
    proposal = make_stage_proposal(specs=[spec], groups=[_group()])

    problems = check_proposal(proposal, ["comment-thread"], TREE)

    assert not any("The loki mode" in p or "_loki_mode" in p for p in problems)


def test_a_behavior_group_that_names_the_code_in_test_has_no_scenario_problem() -> None:
    scenario = StageScenario(
        name="The loki mode",
        when="single binary is configured",
        then="`_loki_mode` raises a failure",
    )
    spec = _spec_with([scenario])
    group = _group(test="Write `test_loki` testing `_loki_mode` in `tests/test_sample.py`")
    proposal = make_stage_proposal(specs=[spec], groups=[group])

    problems = check_proposal(proposal, ["comment-thread"], TREE)

    assert not any("The loki mode" in p or "_loki_mode" in p for p in problems)

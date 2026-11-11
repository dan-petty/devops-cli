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

    problems = check_proposal(proposal, ["comment-thread"], TREE, registry=())

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

    problems = check_proposal(proposal, ["comment-thread"], TREE, registry=())

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

    problems = check_proposal(proposal, ["comment-thread"], TREE, registry=())

    assert not any("The loki mode" in p or "_loki_mode" in p for p in problems)


# ── A data file in the `when` of a scenario (#4316) ───────────────────────────

DATA_FILE = ".github/labels.yml"
DATA_TREE = StagedTree(["src/devops_cli/sample.py", "tests/test_sample.py", DATA_FILE])
FIXTURE_WHEN = (
    "the title of the issue is `fix(floor): the job drops a comment` and "
    f"`{DATA_FILE}` declares no `scope/floor`"
)


def _scenario_problems_of(
    when: str, then: str, group: StageGroup | None = None, tree: StagedTree = DATA_TREE
) -> list[str]:
    scenario = StageScenario(name="A scope that no label declares", when=when, then=then)
    proposal = make_stage_proposal(specs=[_spec_with([scenario])], groups=[group or _group()])
    return [
        p
        for p in check_proposal(proposal, ["comment-thread"], tree, registry=())
        if "no behavior" in p
    ]


def test_a_data_file_in_the_when_that_no_group_touches_needs_no_test_text() -> None:
    problems = _scenario_problems_of(FIXTURE_WHEN, "the job refuses the title")

    assert problems == []


def test_a_data_file_in_the_when_with_a_code_name_in_the_then_needs_the_code_tested() -> None:
    problems = _scenario_problems_of(FIXTURE_WHEN, "`_scope_check` raises a failure")

    assert len(problems) == 1
    assert "_scope_check" in problems[0]


def test_a_path_in_the_then_is_judged_also_when_it_is_a_data_file() -> None:
    problems = _scenario_problems_of("a scope is checked", f"the job reads `{DATA_FILE}`")

    assert len(problems) == 1
    assert DATA_FILE in problems[0]


def test_a_path_in_the_then_that_no_test_names_is_refused() -> None:
    problems = _scenario_problems_of("the job runs", "`src/devops_cli/sample.py` holds the fix")

    assert len(problems) == 1
    assert "src/devops_cli/sample.py" in problems[0]


def test_a_path_in_the_when_that_a_behavior_group_changes_needs_a_test_that_names_it() -> None:
    problems = _scenario_problems_of(
        "`src/devops_cli/sample.py` holds a bad line", "the job refuses the plan"
    )

    assert len(problems) == 1
    assert "src/devops_cli/sample.py" in problems[0]


def test_a_path_in_the_when_that_a_behavior_group_reads_needs_a_test_that_names_it() -> None:
    group = _group()
    group.reads = [DATA_FILE]

    problems = _scenario_problems_of(FIXTURE_WHEN, "the job refuses the title", group)

    assert len(problems) == 1
    assert DATA_FILE in problems[0]


def test_a_path_in_the_when_that_the_test_names_passes() -> None:
    group = _group(test=f"Write `test_x` in `tests/test_sample.py` for `{DATA_FILE}`")
    group.reads = [DATA_FILE]

    assert _scenario_problems_of(FIXTURE_WHEN, "the job refuses the title", group) == []

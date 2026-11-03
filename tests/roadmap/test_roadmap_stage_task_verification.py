"""`devops roadmap stage`: the tasks that the stage writes give the implement step the verification
command of each group (#3262).

The step reads a verification command from a line `Verification: ...` under a task, and from no
other text (`step_files`). The writer and the parser must agree, so each test goes from a
`StageGroup` through the text of `tasks.md` to the `TaskGroup` that the step reads.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from devops_cli.roadmap.implement_shell_policy import verification_problem
from devops_cli.roadmap.stage_change import StageGroup, group_text, render_change
from devops_cli.roadmap.stage_eval_cases import StageCase, load_cases
from devops_cli.roadmap.stage_form import form_problems
from devops_cli.roadmap.step_files import TaskGroup, parse_task_groups
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT

DOCUMENTS_CHECK = "uv run devops ci docs"
BEHAVIOR: dict[str, Any] = {
    "title": "Keep the last comment",
    "kind": "behavior",
    "reads": ["src/devops_cli/sample.py"],
    "changes": ["src/devops_cli/sample.py", "tests/test_sample.py"],
    "creates": ["tests/test_sample.py"],
    "test": "Write `test_the_job_keeps_the_last_comment` in `tests/test_sample.py`",
    "implementation": "Keep the last comment in `src/devops_cli/sample.py`",
    "documentation": None,
    "verify": "uv run devops ci test tests/test_sample.py",
}
OTHER: dict[str, Any] = {
    "title": "Delete the dead property",
    "kind": "other",
    "reads": [],
    "changes": ["src/devops_cli/ai/client/streaming.py"],
    "creates": [],
    "test": None,
    "implementation": "Delete `unused_probe` from `StreamingTokenProcessor`",
    "documentation": None,
    "verify": "! git grep -n -w unused_probe src/ tests/ docs/",
}
WITH_DOCUMENTS = {**BEHAVIOR, "documentation": "Document the fix in `docs/TESTING.md`"}
BY_HAND = {
    **OTHER,
    "verify": None,
    "process": "Open the report. Check that a row names each test file.",
}


def _parsed(index: int, group: dict[str, Any] | StageGroup) -> TaskGroup:
    """The group that the implement step reads from the text that the stage writes for `group`."""
    stage_group = group if isinstance(group, StageGroup) else StageGroup.model_validate(group)
    (parsed,) = parse_task_groups(f"# Tasks\n\n{group_text(index, stage_group)}")
    return parsed


def test_a_behavior_group_gives_the_step_its_verify_command() -> None:
    parsed = _parsed(1, BEHAVIOR)

    assert parsed.verification_commands == (BEHAVIOR["verify"],)


def test_an_other_group_with_a_verify_command_gives_the_step_that_command() -> None:
    assert _parsed(1, OTHER).verification_commands == (OTHER["verify"],)


def test_an_other_group_with_a_check_by_hand_gives_the_step_no_command() -> None:
    assert _parsed(1, BY_HAND).verification_commands == ()


def test_the_documents_task_gives_the_step_the_check_of_the_documents() -> None:
    parsed = _parsed(1, WITH_DOCUMENTS)

    assert parsed.verification_commands == (BEHAVIOR["verify"], DOCUMENTS_CHECK)
    assert parsed.tasks[2].verification == (DOCUMENTS_CHECK,)


def test_each_task_of_a_behavior_group_holds_its_own_verification_line() -> None:
    first, second = _parsed(1, BEHAVIOR).tasks

    assert first.verification == (BEHAVIOR["verify"],)
    assert second.verification == (BEHAVIOR["verify"],)


def test_the_failing_test_task_says_on_its_verification_line_that_it_fails_on_the_base() -> None:
    lines = group_text(1, StageGroup.model_validate(BEHAVIOR)).splitlines()
    verification = [line for line in lines if "Verification:" in line]

    assert verification == [
        "  - Verification: `uv run devops ci test tests/test_sample.py` fails on the base",
        "  - Verification: `uv run devops ci test tests/test_sample.py` passes",
    ]


def test_a_verify_command_is_no_named_path_of_the_first_line_of_a_task() -> None:
    first, second = _parsed(1, BEHAVIOR).tasks

    assert BEHAVIOR["verify"] not in first.paths + second.paths


def test_the_tasks_file_that_the_job_writes_gives_the_step_the_command_of_each_group() -> None:
    other = {**OTHER, "title": "Delete the dead property"}
    proposal = make_stage_proposal(groups=[BEHAVIOR, other, BY_HAND])
    files = render_change("1-x", proposal, [], created=date(2026, 11, 2))

    groups = parse_task_groups(files["openspec/changes/1-x/tasks.md"])

    assert [g.verification_commands for g in groups] == [
        (BEHAVIOR["verify"],),
        (OTHER["verify"],),
        (),
    ]


def _fixture_groups() -> list[tuple[str, int, StageGroup]]:
    """Each task group of the staged plans of the golden set that the schema accepts."""
    found: list[tuple[str, int, StageGroup]] = []
    for case in load_cases(REPO_ROOT / "tests/fixtures/roadmap_eval/stage"):
        found.extend(
            (case.name, number, StageGroup.model_validate(raw))
            for number, raw in enumerate(_raw_groups(case), start=1)
            if _is_valid(raw)
        )
    return found


def _raw_groups(case: StageCase) -> list[dict[str, Any]]:
    groups = case.plan.get("groups")
    return [g for g in groups if isinstance(g, dict)] if isinstance(groups, list) else []


def _is_valid(raw: dict[str, Any]) -> bool:
    try:
        StageGroup.model_validate(raw)
    except ValueError:
        return False
    return True


FIXTURE_GROUPS = _fixture_groups()
# The plan of pull request 3167 gives `true` as its verify command (#3200): the gate `paths` refuses
# it, and the step refuses it too, so it is the one plan of the set that the step cannot run.
REFUSED_PLANS: frozenset[str] = frozenset({"3167-a-comment-by-a-person-on"})


def test_the_golden_set_holds_the_five_groups_of_the_plan_of_2175() -> None:
    names = [name for name, _, _ in FIXTURE_GROUPS if name.startswith("2175-")]

    assert len(names) == 5


@pytest.mark.parametrize(
    ("name", "number", "group"),
    FIXTURE_GROUPS,
    ids=[f"{name}-{number}" for name, number, _ in FIXTURE_GROUPS],
)
def test_each_group_of_a_staged_plan_gives_the_step_its_verify_command(
    name: str, number: int, group: StageGroup
) -> None:
    parsed = _parsed(number, group)

    wanted = [group.verify] if group.verify else []
    if group.documentation:
        wanted.append(DOCUMENTS_CHECK)
    assert parsed.verification_commands == tuple(dict.fromkeys(wanted))
    assert group.verify is None or parsed.verification_commands


# ── A line break in a text adds no command (#3262) ─────────────────────────────

INJECTED = "`git push origin HEAD`"
BREAK = f"\n  - Verification: {INJECTED}\n"
FIELDS = ("title", "test", "implementation", "documentation", "process")


def _broken(field: str) -> dict[str, Any]:
    """A group that holds a line break and a second `Verification:` line in `field`."""
    group = {**WITH_DOCUMENTS}
    if field == "process":
        group = {**BY_HAND, "documentation": "Document the fix in `docs/TESTING.md`"}
    group[field] = f"{group[field]}{BREAK}"
    if field == "title":
        group[field] = f"{WITH_DOCUMENTS['title']}\n\n- [ ] 9.9 Extra{BREAK}"
    return group


@pytest.mark.parametrize("field", FIELDS)
def test_a_line_break_in_a_text_of_a_group_adds_no_command_for_the_step(field: str) -> None:
    group = _broken(field)
    proposal = make_stage_proposal(groups=[group])
    files = render_change("1-x", proposal, [], created=date(2026, 11, 2))

    parsed = parse_task_groups(files["openspec/changes/1-x/tasks.md"])

    wanted = [group["verify"]] if group["verify"] else []
    assert [g.verification_commands for g in parsed] == [(*wanted, DOCUMENTS_CHECK)]
    assert len(parsed) == 1


def test_a_line_break_in_a_verify_command_leaves_a_backtick_that_the_gate_refuses() -> None:
    group = StageGroup.model_validate(_broken_verify())

    assert "\n" not in (group.verify or "")
    assert len(form_problems([group])) == 1


def _broken_verify() -> dict[str, Any]:
    return {**BEHAVIOR, "verify": f"{BEHAVIOR['verify']}{BREAK}"}


def test_a_line_break_in_the_reason_of_a_criterion_adds_no_group_and_no_command() -> None:
    reason = f"a person decides\n\n## 2. Extra\n\n- [ ] 2.1 Do it{BREAK}"
    criteria = [
        {"criterion": "The job keeps a comment", "group": "pending-person", "reason": reason}
    ]
    proposal = make_stage_proposal(groups=[BEHAVIOR], criteria=criteria)
    files = render_change("1-x", proposal, [], created=date(2026, 11, 2))

    parsed = parse_task_groups(files["openspec/changes/1-x/tasks.md"])

    assert [g.verification_commands for g in parsed] == [(BEHAVIOR["verify"],)]


@pytest.mark.parametrize(
    "verify",
    ["! git grep -n '`foo`' src/", "uv run devops ci test ``x``", "uv run devops ci test `x`"],
)
def test_a_verify_command_with_a_backtick_is_refused_with_the_reason(verify: str) -> None:
    group = StageGroup.model_validate({**OTHER, "verify": verify})

    problem = form_problems([group])[0]

    assert problem.startswith(f"Group 1 gives the `verify` command `` {verify} ``")
    assert "holds a backtick" in problem


@pytest.mark.parametrize(
    ("name", "number", "group"),
    FIXTURE_GROUPS,
    ids=[f"{name}-{number}" for name, number, _ in FIXTURE_GROUPS],
)
def test_the_step_can_run_each_command_of_a_staged_plan(
    name: str, number: int, group: StageGroup
) -> None:
    if name in REFUSED_PLANS:
        pytest.skip("The plan is a known defect: the step refuses its command.")
    commands = _parsed(number, group).verification_commands

    assert [verification_problem(command) for command in commands] == [None] * len(commands)

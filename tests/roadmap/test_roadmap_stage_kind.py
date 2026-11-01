"""`devops roadmap stage`: a task group has a kind, and the kind decides its tasks (#3005)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.roadmap.stage_change import StageGroup, group_text

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
    "implementation": "Delete `thinking_detected` from `StreamingTokenProcessor`",
    "documentation": None,
    "verify": "! git grep -n -w thinking_detected src/ tests/ docs/",
}


def _problem(group: dict[str, Any]) -> str:
    """The text that the schema gives back to the model for `group`."""
    with pytest.raises(ValidationError) as raised:
        StageGroup.model_validate(group)
    return str(raised.value)


def test_a_behavior_group_with_a_test_and_a_source_path_is_valid() -> None:
    assert StageGroup.model_validate(BEHAVIOR).kind == "behavior"


def test_an_other_group_with_a_verify_and_no_test_is_valid() -> None:
    group = StageGroup.model_validate(OTHER)

    assert (group.kind, group.test, group.process) == ("other", None, None)


def test_an_other_group_with_a_process_and_no_command_is_valid() -> None:
    steps = "Open the report. Check that each file has a row."
    group = StageGroup.model_validate({**OTHER, "verify": None, "process": steps})

    assert group.process == steps


@pytest.mark.parametrize(
    ("update", "fragment"),
    [
        ({"test": None}, "has the kind behavior, and it has no test"),
        ({"verify": None}, "has the kind behavior, and it has no verify"),
        ({"process": "Look at the output."}, "has a process"),
        ({"changes": ["docs/TESTING.md"], "creates": []}, "changes no path under src/"),
        ({"kind": "mixed"}, "Input should be 'behavior' or 'other'"),
    ],
)
def test_a_behavior_group_that_breaks_a_rule_is_refused_with_the_problem(
    update: dict[str, Any], fragment: str
) -> None:
    assert fragment in _problem({**BEHAVIOR, **update})


@pytest.mark.parametrize(
    ("update", "fragment"),
    [
        ({"test": "Write a test"}, "has the kind other, and it has a test"),
        ({"verify": None}, "has neither verify nor process"),
        ({"process": "Look at the output."}, "has both verify and process"),
    ],
)
def test_an_other_group_that_breaks_a_rule_is_refused_with_the_problem(
    update: dict[str, Any], fragment: str
) -> None:
    assert fragment in _problem({**OTHER, **update})


def test_a_group_that_breaks_two_rules_names_both_in_one_problem() -> None:
    problem = _problem({**OTHER, "test": "Write a test", "verify": None})

    assert "has a test" in problem
    assert "has neither verify nor process" in problem


# ── The tasks of a kind ───────────────────────────────────────────────────────

# The plans of #2162 (a report, a deletion of test files, a run of CI) as the new kinds hold them.
REPORT: dict[str, Any] = {
    **OTHER,
    "title": "Write the mutation report",
    "changes": ["openspec/changes/2162-x/mutation-report.md"],
    "creates": ["openspec/changes/2162-x/mutation-report.md"],
    "implementation": "Run `uv run devops ci mutate` and write one row for each test file",
    "verify": None,
    "process": "Open the report.\nCheck that a row names each of the 18 test files.",
}
DELETION_OF_FILES: dict[str, Any] = {
    **OTHER,
    "title": "Delete the files with no unique mutant",
    "changes": ["tests/test_review_history.py"],
    "implementation": "Delete each test file with no unique mutant in the report",
    "verify": "uv run devops ci test tests/commands",
}


def _task_lines(*groups: dict[str, Any]) -> list[str]:
    """The task lines that `group_text` writes for `groups`, numbered from group 1."""
    text = "\n".join(
        group_text(index, StageGroup.model_validate(group))
        for index, group in enumerate(groups, start=1)
    )
    return [line for line in text.splitlines() if line.startswith("- [ ] ")]


def test_a_deletion_that_keeps_behavior_renders_one_task_with_its_command_and_no_test() -> None:
    assert _task_lines(OTHER) == [
        "- [ ] 1.1 Delete `thinking_detected` from `StreamingTokenProcessor`, and verify that "
        "`! git grep -n -w thinking_detected src/ tests/ docs/` passes"
    ]


def test_the_groups_of_the_mutation_report_plan_render_with_no_contrived_test() -> None:
    lines = _task_lines(REPORT, DELETION_OF_FILES)

    assert lines == [
        "- [ ] 1.1 Run `uv run devops ci mutate` and write one row for each test file, and run "
        "this check by hand: Open the report. Check that a row names each of the 18 test files.",
        "- [ ] 2.1 Delete each test file with no unique mutant in the report, and verify that "
        "`uv run devops ci test tests/commands` passes",
    ]


@pytest.mark.parametrize("group", [OTHER, REPORT, DELETION_OF_FILES])
def test_an_other_group_renders_no_test_and_no_failure_on_the_base(group: dict[str, Any]) -> None:
    text = group_text(1, StageGroup.model_validate(group))

    assert "fails on the base" not in text
    assert "test that" not in text


def test_a_behavior_group_renders_its_failing_test_first_and_then_its_implementation() -> None:
    assert _task_lines(BEHAVIOR) == [
        "- [ ] 1.1 Write `test_the_job_keeps_the_last_comment` in `tests/test_sample.py`, and "
        "verify that `uv run devops ci test tests/test_sample.py` fails on the base",
        "- [ ] 1.2 Keep the last comment in `src/devops_cli/sample.py`, and verify that "
        "`uv run devops ci test tests/test_sample.py` passes",
    ]


def test_a_group_with_no_documentation_renders_no_documentation_task() -> None:
    text = group_text(1, StageGroup.model_validate(BEHAVIOR))

    assert "docs generate" not in text
    assert "Change no document" not in text


@pytest.mark.parametrize(
    ("group", "number"), [(BEHAVIOR, 3), (OTHER, 2)], ids=["behavior", "other"]
)
def test_a_group_with_documentation_renders_the_documentation_task_after_its_work(
    group: dict[str, Any], number: int
) -> None:
    documented = {**group, "documentation": "Document the change in `docs/TESTING.md`"}

    lines = _task_lines(documented)

    assert len(lines) == number
    assert lines[-1] == (
        f"- [ ] 1.{number} Document the change in `docs/TESTING.md`, run "
        "`uv run devops docs generate --sync-readme`, and verify that "
        "`uv run devops ci docs` passes"
    )

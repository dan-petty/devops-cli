"""The code spans of a `Verification:` line that the implement step reads as commands (#3596).

Only a code span that starts with `$ ` is a command. Every other code span of the line is prose and
gives the group no command.
"""

from __future__ import annotations

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_shell_policy import verification_problem
from devops_cli.roadmap.step_files import TaskGroup, _task_of, adds_problem, parse_task_groups

TEST_COMMAND = "uv run devops ci test tests/roadmap/test_roadmap_step_files.py"


def _group(verification: str) -> TaskGroup:
    """The group of a plan whose one task has the `Verification:` line `verification`."""
    tasks = f"## 1. A group\n\n- [ ] 1.1 Change the file\n  - Verification: {verification}\n"
    [group] = parse_task_groups(tasks)
    return group


def test_a_prose_code_span_beside_a_marked_command_is_no_command() -> None:
    group = _group(f"`tagged_image` splits the reference, and `$ {TEST_COMMAND}` passes")

    assert group.verification_commands == (TEST_COMMAND,)
    assert group.tasks[0].verification == (TEST_COMMAND,)


def test_the_mark_is_removed_before_the_step_reads_the_program() -> None:
    [command] = _group("`$ uv run devops ci docs` passes").verification_commands

    assert command == "uv run devops ci docs"
    assert verification_problem(command) is None


def test_a_marked_command_of_a_program_that_is_not_allowed_is_refused_with_the_reason() -> None:
    [command] = _group("`$ nosuchprogram --version` passes").verification_commands

    reason = verification_problem(command)

    assert command == "nosuchprogram --version"
    assert reason is not None
    assert "nosuchprogram" in reason


def test_a_line_with_no_marked_code_span_gives_the_group_no_command() -> None:
    group = _group(f"`{TEST_COMMAND}` passes")

    assert group.verification_commands == ()


def test_each_marked_command_of_a_line_is_read() -> None:
    group = _group("`$ uv run devops ci docs` and `$ uv run devops openspec check` pass")

    assert group.verification_commands == ("uv run devops ci docs", "uv run devops openspec check")


def test_the_line_that_the_stage_template_writes_gives_its_command() -> None:
    for template in (MESSAGES.roadmap.stage_task_test, MESSAGES.roadmap.stage_task_pass):
        text = template.partition("\n")[2].format(verify=TEST_COMMAND)
        group = _group(text.removeprefix("  - Verification: "))

        assert group.verification_commands == (TEST_COMMAND,)


def test_the_documents_task_of_the_stage_template_gives_its_command() -> None:
    text = MESSAGES.roadmap.stage_task_documents.partition("\n")[2]
    group = _group(text.removeprefix("  - Verification: "))

    assert group.verification_commands == ("uv run devops ci docs",)


def test_the_docstring_of_the_task_reader_states_the_rule() -> None:
    doc = _task_of.__doc__ or ""

    assert "$ " in doc
    assert "prose" in doc


def _plan_group(adds: str) -> TaskGroup:
    """The group of a plan whose line under the heading is `adds`."""
    tasks = (
        "## 1. A group\n\n"
        "Kind: behavior. Reads: `a.py`. Changes: `b.py`.\n"
        f"{adds}\n\n"
        f"- [ ] 1.1 Change the file\n  - Verification: `$ {TEST_COMMAND}` fails on the base\n"
    )
    [group] = parse_task_groups(tasks)
    return group


def test_the_added_names_of_a_group_come_from_its_adds_line() -> None:
    group = _plan_group("Adds: `_delivery_title`, `_publish`.")

    assert group.added_names == ("_delivery_title", "_publish")


def test_a_group_with_no_adds_line_adds_no_name() -> None:
    group = _plan_group("Reads: `a.py`.")

    assert group.added_names == ()


def test_an_adds_line_that_names_no_code_span_is_a_problem() -> None:
    group = _plan_group("Adds: _delivery_title.")

    problem = adds_problem(group.text)

    assert problem is not None
    assert "_delivery_title" in problem


def test_a_well_formed_adds_line_is_no_problem() -> None:
    group = _plan_group("Adds: `_delivery_title`, `_publish`.")

    assert adds_problem(group.text) is None


def test_an_adds_line_that_names_a_word_outside_a_code_span_is_a_problem() -> None:
    group = _plan_group("Adds: `_delivery_title`, _publish.")

    problem = adds_problem(group.text)

    assert problem is not None
    assert "_publish" in problem

"""`load_task_prompt` raises for a prompt that is not a file of `ai/tasks/` (#950, #4630).

An empty string for a missing file sent a model nothing at all: the benchmark suite sent empty
system and user prompts, because `benchmark_suite_system.md` and `benchmark_suite_user.md` were in
a folder that the loader does not read. The `test-tree` row of `devops ci` checks that each prompt
name the code gives to the loader exists (`tests/gate/tree_checks/task_prompts.py`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import UndefinedError

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.exceptions.base import DevOpsCLIError


def test_a_prompt_of_the_tasks_folder_loads_with_its_text() -> None:
    """Verify a prompt file of the folder loads stripped, with content."""
    prompt = load_task_prompt("style_ste100.md")

    assert (bool(prompt), prompt == prompt.strip()) == (True, True)


@pytest.mark.parametrize(
    "name",
    ["missing.md", "../personas/devsecops/role.md"],
    ids=["missing", "outside-the-folder"],
)
def test_a_name_that_is_not_a_prompt_of_the_folder_raises(name: str) -> None:
    """Verify a missing name, and a name outside the tasks folder, raise
    `TaskPromptNotFoundError` that names the prompt."""
    with pytest.raises(DevOpsCLIError, match=r"missing\.md|role\.md") as raised:
        load_task_prompt(name)

    assert raised.value.error_code == "TASK_PROMPT_NOT_FOUND"


def _tasks_dir() -> Path:
    import devops_cli.ai.task_loader as task_loader

    return Path(task_loader.__file__).resolve().parent / "tasks"


def test_a_prompt_renders_a_context_value() -> None:
    """#4633: a caller that passes a context renders the prompt as a Jinja2 template."""
    rendered = load_task_prompt(
        "roadmap_implement_step.md",
        tools="TOOLS-MARK",
        shell_programs="PROGRAMS-MARK",
        local_commands="COMMANDS-MARK",
        shell_refusals="REFUSALS-MARK",
    )

    assert "TOOLS-MARK" in rendered
    assert "{{tools}}" not in rendered
    assert "PROGRAMS-MARK" in rendered
    assert "{{shell_programs}}" not in rendered


def test_a_missing_context_value_raises() -> None:
    """#4633: `StrictUndefined` raises when the context does not hold a value that the template
    names."""
    with pytest.raises(UndefinedError, match="undefined"):
        load_task_prompt("roadmap_implement_step.md", shell_programs="PROGRAMS-MARK")


def test_a_prompt_with_no_context_keeps_its_text() -> None:
    """#4633: a prompt with no variables returns the text that the loader returned before."""
    text = (_tasks_dir() / "style_ste100.md").read_text(encoding="utf-8")

    assert load_task_prompt("style_ste100.md") == text.strip()


def test_a_prompt_with_no_context_keeps_its_markers() -> None:
    """#4633: a prompt with no context keeps its markers, so a caller that fills its own markers,
    and a benchmark prompt with a GitHub expression, keep working."""
    assert "{{plan_calls_advised}}" in load_task_prompt("roadmap_stage_tools.md")
    assert "${{ github.workflow }}-${{ github.ref }}" in load_task_prompt(
        "benchmark_embedding_eval_pairs.md"
    )


def test_the_implement_prompt_gets_its_three_tables() -> None:
    """#4633: the implement step prompt gets its three tables through context."""
    from devops_cli.roadmap.implement.implement_shell_policy import (
        local_commands_table,
        programs_table,
        refusals_table,
    )
    from devops_cli.roadmap.implement.implement_step import step_instructions

    prompt = step_instructions()

    assert (
        programs_table() in prompt,
        local_commands_table() in prompt,
        refusals_table() in prompt,
        "{{" in prompt,
    ) == (True, True, True, False)


def test_the_implement_prompt_equals_today_s_fill_prompt_output() -> None:
    """#4633: the rendered implement prompt equals the output of the `str.replace` filling of
    today."""
    from devops_cli.roadmap.implement.implement_shell_policy import (
        local_commands_table,
        programs_table,
        refusals_table,
        tools_table,
    )
    from devops_cli.roadmap.implement.implement_step import step_instructions

    raw = load_task_prompt("roadmap_implement_step.md")
    today = (
        raw.replace("{{tools}}", tools_table())
        .replace("{{shell_programs}}", programs_table())
        .replace("{{local_commands}}", local_commands_table())
        .replace("{{shell_refusals}}", refusals_table())
    )

    assert step_instructions() == today


def test_the_source_holds_no_fill_prompt_or_programs_placeholder() -> None:
    """#4633: the `str.replace` filling is gone."""
    import devops_cli.roadmap.implement.implement_shell_policy as policy

    assert not hasattr(policy, "fill_prompt")
    assert not hasattr(policy, "PROGRAMS_PLACEHOLDER")


def test_prompt_version_covers_the_context() -> None:
    """#4633: the prompt version hashes the raw templates and the context values, and a call with
    no context does not raise."""
    from devops_cli.roadmap.stage.stage_plan_record import prompt_version

    plain = prompt_version("extended")

    assert plain == prompt_version("extended")
    assert plain != prompt_version("extended", context={"tool": "a"})
    assert plain != prompt_version("extended", context={"tool": "b"})

"""`load_task_prompt` raises for a prompt that is not a file of `ai/tasks/` (#950, #4630).

An empty string for a missing file sent a model nothing at all: the benchmark suite sent empty
system and user prompts, because `benchmark_suite_system.md` and `benchmark_suite_user.md` were in
a folder that the loader does not read. The `test-tree` row of `devops ci` checks that each prompt
name the code gives to the loader exists (`tests/gate/tree_checks/task_prompts.py`).
"""

from __future__ import annotations

import pytest

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

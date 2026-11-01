"""The refusal of the shell tool names the replacement, and the prompt of the step agrees with
the table of replacements (#2773).

The model is a pydantic-ai `FunctionModel` that a script answers, so no test reaches a model. The
agent is the real agent of a step, with the real shell of the harness.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS,
    CONST_ROADMAP_RUN_ERROR_CHARS,
)
from devops_cli.roadmap.implement_shell_policy import (
    IMPLEMENT_SHELL_PROGRAMS,
    IMPLEMENT_SHELL_REPLACEMENTS,
    fill_prompt,
)
from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessFake
from tests.support.implement_step import WINDOW, git, is_clean_at
from tests.support.model_script import ModelScript, say, tool_call

pytestmark = pytest.mark.usefixtures("keyring_store")

ALLOWED = (
    "These programs are allowed: "
    + ", ".join(f"`{program}`" for program in IMPLEMENT_SHELL_PROGRAMS)
    + "."
)
UV_RUN_PYTHON = "`uv run python`. Do not run `python -m pip`: the lockfile gives the dependencies."
UV_RUN = (
    "Run the commands of the project with `uv run`, for example `uv run devops ci test <file>`."
)


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _step(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def _refusal(
    command: str, store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> str:
    """The text that the model reads after the shell refuses `command`."""
    script = ModelScript(tool_call("shell", command=command), say("Done."))
    _step(store, checkout, script)
    (answer,) = script.tool_answers()
    return answer


@pytest.mark.parametrize(
    ("command", "text"),
    [
        (
            "python -m pytest",
            f"Command 'python' is not in the allowed list. Instead of `python`: {UV_RUN_PYTHON}",
        ),
        (
            "pytest tests/test_sample.py",
            "Command 'pytest' is not in the allowed list. Instead of `pytest`: `uv run pytest`.",
        ),
        (
            "rg shout src",
            "Command 'rg' is not in the allowed list. "
            "Instead of `rg`: the tool `grep`, or `grep` in the shell.",
        ),
        (
            "cd src",
            "Command 'cd' is not in the allowed list. "
            "Instead of `cd`: nothing. Every command runs in the checkout.",
        ),
        (
            "python -m pip install x",
            f"Command 'python' is not in the allowed list. Instead of `python`: {UV_RUN_PYTHON}",
        ),
        (
            "pip install x",
            "Command 'pip' is not in the allowed list. "
            "Instead of `pip`: nothing. The lockfile gives the dependencies.",
        ),
    ],
)
def test_the_refusal_of_a_known_habit_names_the_replacement_after_the_original_text(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    command: str,
    text: str,
) -> None:
    assert _refusal(command, store, checkout, programs) == text


def test_the_refusal_of_an_unknown_program_lists_the_allowed_programs_and_the_uv_run_form(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    assert _refusal("curl http://example.com", store, checkout, programs) == (
        f"Command 'curl' is not in the allowed list. {ALLOWED} {UV_RUN}"
    )


def test_the_refusal_of_an_operator_states_the_rule_of_one_command_in_each_call(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    assert _refusal("git status; git log", store, checkout, programs) == (
        "Shell operator ';' is not allowed. Run one command in each call. "
        "Do not chain commands. Do not use `cd`: every command runs in the checkout."
    )


def test_the_text_of_the_shell_is_cut_so_a_long_word_does_not_fill_the_context(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The shell echoes the first word of the command, and so does an interactive refusal."""
    for command in ("A" * 5000, "vim " + "B" * 5000):
        answer = _refusal(command, store, checkout, programs)

        assert len(answer) <= CONST_ROADMAP_RUN_ERROR_CHARS + len(ALLOWED) + len(UV_RUN) + 2


def test_the_hint_adds_no_word_of_the_command(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The text of the shell echoes the first word. The hint adds nothing from the command."""
    answer = _refusal("API_KEY=hunter2 run --flag=sentinel", store, checkout, programs)

    assert answer == f"Command 'API_KEY=hunter2' is not in the allowed list. {ALLOWED} {UV_RUN}"


def test_a_refusal_of_a_file_tool_gets_no_hint(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_call("read_file", path="/etc/passwd"), say("Done."))

    _step(store, checkout, script)

    (answer,) = script.tool_answers()
    assert "Instead of" not in answer
    assert "uv run" not in answer


def test_the_model_gets_five_refusals_with_a_hint_and_the_sixth_call_ends_the_run(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(tool_call("shell", command="python -V"))

    outcome = _step(store, checkout, script)

    answers = script.tool_answers()
    assert (outcome.status, outcome.requests, len(answers), is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        6,
        5,
        True,
    )
    assert all(answer.endswith(f"Instead of `python`: {UV_RUN_PYTHON}") for answer in answers)
    assert outcome.reason.endswith("\nRefused commands: python 6. Other retries: 0.")


# ── The prompt agrees with the table ──────────────────────────────────────────────────────


def _prompt() -> str:
    return fill_prompt(load_task_prompt("roadmap_implement_step.md"))


def test_each_shell_example_of_the_prompt_passes_the_shell_policy() -> None:
    """The prompt teaches the model what to run. A command of the prompt that the shell refuses
    sends the model into the loop that the table is there to end. The shell refuses a command that
    holds a denied operator anywhere, also inside quotes, so the check is a plain text match."""
    examples = [
        code
        for code in re.findall(r"`([^`\n]+)`", _prompt())
        if code.split()[0] in IMPLEMENT_SHELL_PROGRAMS
    ]

    assert len(examples) >= 2
    for example in examples:
        assert [op for op in CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS if op in example] == [], (
            example
        )


def test_no_program_of_the_table_is_a_program_that_the_shell_allows() -> None:
    assert set(IMPLEMENT_SHELL_REPLACEMENTS).isdisjoint(IMPLEMENT_SHELL_PROGRAMS)


def test_each_replacement_names_an_allowed_program_or_a_tool_that_the_agent_has(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(say("Done."))
    _step(store, checkout, script)
    names = {*IMPLEMENT_SHELL_PROGRAMS, *script.tools_offered[0]}

    named = [
        code.split()[0]
        for replacement in IMPLEMENT_SHELL_REPLACEMENTS.values()
        for code in re.findall(r"`([^`]+)`", replacement.split(". ")[0])
    ]

    assert named
    assert set(named) <= names

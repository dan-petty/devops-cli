"""The shell policy of an implement step is one table (#3072).

`SHELL_PROGRAMS` and `SHELL_REFUSALS` give the allowlist of the shell, the hint of a refusal, the
prompt of the step and `docs/ROADMAP_WORKFLOW.md`. The model is a pydantic-ai `FunctionModel` that
a script answers, so no test reaches a model.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic_ai.workspaces import CommandResult
from pydantic_ai.workspaces.local import LocalWorkspaceBackend

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS
from devops_cli.roadmap.implement_shell_policy import (
    IMPLEMENT_ALLOWED_PROGRAMS,
    IMPLEMENT_SHELL_PROGRAMS,
    IMPLEMENT_SHELL_REPLACEMENTS,
    PROGRAMS_PLACEHOLDER,
    REFUSALS_PLACEHOLDER,
    SHELL_PROGRAMS,
    SHELL_REFUSALS,
    ShellAccess,
    fill_prompt,
    programs_table,
    refusals_table,
    refused_argument,
)
from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessFake
from tests.support.implement_step import WINDOW, git, is_clean_at
from tests.support.model_script import ModelScript, say, tool_call
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.usefixtures("keyring_store")

READ_ONLY = ("grep", "cat", "ls", "head", "tail", "find")
FIND_ARGUMENTS = (
    "-exec",
    "-execdir",
    "-ok",
    "-okdir",
    "-delete",
    "-fprint",
    "-fprint0",
    "-fprintf",
    "-fls",
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


# ── The table ─────────────────────────────────────────────────────────────────────────────


def test_the_table_holds_the_project_programs_and_the_read_only_programs() -> None:
    assert IMPLEMENT_SHELL_PROGRAMS == ("git", "uv", "ruff", "mypy", *READ_ONLY)


def test_each_read_only_program_has_the_access_read_and_no_other_program_has_it() -> None:
    read = tuple(p.name for p in SHELL_PROGRAMS if p.access is ShellAccess.READ)

    assert read == READ_ONLY


def test_the_verification_commands_may_also_start_openspec_and_devops() -> None:
    assert IMPLEMENT_ALLOWED_PROGRAMS == (*IMPLEMENT_SHELL_PROGRAMS, "openspec", "devops")


def test_a_refused_program_is_not_an_allowed_program() -> None:
    assert set(IMPLEMENT_SHELL_REPLACEMENTS).isdisjoint(IMPLEMENT_ALLOWED_PROGRAMS)
    assert tuple(IMPLEMENT_SHELL_REPLACEMENTS) == tuple(r.program for r in SHELL_REFUSALS)


def test_only_find_refuses_arguments() -> None:
    assert {p.name: p.refused_arguments for p in SHELL_PROGRAMS if p.refused_arguments} == {
        "find": FIND_ARGUMENTS
    }


@pytest.mark.parametrize("argument", FIND_ARGUMENTS)
def test_find_with_a_refused_argument_is_refused(argument: str) -> None:
    found = refused_argument(f"find src -name '*.py' {argument} echo")

    assert found is not None
    assert (found[0].name, found[1]) == ("find", argument)


@pytest.mark.parametrize(
    "command",
    [
        "find src -name '*.py'",
        "find . -type f -name '*exec*'",
        "find . -path './-delete'",
        "grep -rn -- -exec src",
        "git branch --delete topic",
        "ls -exec",
        "",
        "find 'unclosed",
        "python -m pytest",
    ],
)
def test_a_command_with_no_refused_argument_passes_the_argument_check(command: str) -> None:
    assert refused_argument(command) is None


# ── The guard ─────────────────────────────────────────────────────────────────────────────


def test_the_refusal_of_a_find_that_runs_a_program_names_the_argument_and_the_way_to_go(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_call("shell", command="find . -name '*.py' -exec rm {} +"), say("Done.")
    )

    _step(store, checkout, script)

    assert script.tool_answers() == [
        "Command 'find' has the argument '-exec', which the shell does not allow. "
        "Use `find` to list paths only. To change a file, use the tools `write_file` and "
        "`edit_file`."
    ]


def test_a_refused_argument_counts_as_a_refused_command_of_its_program(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(tool_call("shell", command="find . -delete"))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.requests, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        6,
        True,
    )
    assert outcome.reason.endswith("\nRefused commands: find 6. Other retries: 0.")


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The commands that reach the process edge of the workspace. The fake answers each one with
    the text `ran`, so a test sees a command that the policy let through."""
    commands: list[str] = []

    async def run(self: object, command: str, **_options: object) -> CommandResult:
        commands.append(command)
        return CommandResult(exit_code=0, stdout="ran", stderr="")

    monkeypatch.setattr(LocalWorkspaceBackend, "run", run)
    return commands


@pytest.mark.parametrize(
    "command",
    [
        "grep -rn OTHER src",
        "cat docs/SAMPLE.md",
        "ls src",
        "head -n 5 README.md",
        "tail -n 5 README.md",
        "find src -name other.py",
    ],
)
def test_a_read_only_program_reaches_the_process_edge_and_returns_its_output(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    started: list[str],
    command: str,
) -> None:
    script = ModelScript(tool_call("shell", command=command), say("Done."))

    _step(store, checkout, script)

    (answer,) = script.tool_answers()
    assert "not in the allowed list" not in answer
    assert [text for text in started if command in text] != []


# ── The prompt and the documents read the table ───────────────────────────────────────────


def _prompt() -> str:
    return fill_prompt(load_task_prompt("roadmap_implement_step.md"))


def test_the_prompt_file_holds_the_two_placeholders_and_no_copy_of_the_table() -> None:
    raw = load_task_prompt("roadmap_implement_step.md")

    assert (
        raw.count(PROGRAMS_PLACEHOLDER),
        raw.count(REFUSALS_PLACEHOLDER),
        [line for line in raw.splitlines() if line.startswith("| `")],
    ) == (1, 1, [])


def test_the_prompt_of_the_step_holds_both_tables_and_no_placeholder() -> None:
    prompt = _prompt()

    assert (programs_table() in prompt, refusals_table() in prompt, "{{" in prompt) == (
        True,
        True,
        False,
    )


def test_the_table_of_programs_has_a_row_for_each_program_in_the_order_of_the_table() -> None:
    rows = [line for line in programs_table().splitlines() if line.startswith("| `")]

    assert [row.split("`")[1] for row in rows] == list(IMPLEMENT_SHELL_PROGRAMS)


def test_the_table_of_refusals_has_a_row_for_each_refusal_in_the_order_of_the_table() -> None:
    assert [line for line in refusals_table().splitlines() if line.startswith("| `")] == [
        f"| `{refusal.program}` | {refusal.instead} |" for refusal in SHELL_REFUSALS
    ]


def test_each_shell_example_of_the_prompt_passes_the_shell_policy() -> None:
    """A command of the prompt that the shell refuses sends the model into the loop that the
    table is there to end. The shell refuses a command that holds a denied operator anywhere, also
    inside quotes, so the check is a plain text match."""
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
        assert refused_argument(example) is None, example


def test_the_document_of_the_workflow_holds_the_same_tables() -> None:
    text = (REPO_ROOT / "docs" / "ROADMAP_WORKFLOW.md").read_text(encoding="utf-8")

    assert (programs_table() in text, refusals_table() in text) == (True, True)

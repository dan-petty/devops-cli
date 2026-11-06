"""The shell of an implement step admits a read pipe and the checkout prefix (#3520).

`pipe_refusal` and `without_checkout_prefix` are the policy. The model is a pydantic-ai
`FunctionModel` that a script answers, and the real shell tool of the harness runs the command up to
the process edge, so no test reaches a model or starts a process.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.workspaces import CommandResult
from pydantic_ai.workspaces.local import LocalWorkspaceBackend

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS,
    CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS,
)
from devops_cli.roadmap.implement_shell_policy import (
    SHELL_PROGRAMS,
    ShellAccess,
    pipe_refusal,
    without_checkout_prefix,
)
from devops_cli.roadmap.implement_step import StepOutcome, run_step
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessFake
from tests.support.implement_step import WINDOW
from tests.support.model_script import ModelScript, say, tool_call

pytestmark = pytest.mark.usefixtures("keyring_store")

ALLOWED_PIPE = "A pipe may end in `head`, `tail`, `grep` or `wc`."


# ── The table ─────────────────────────────────────────────────────────────────────────────


def test_the_pipe_stays_a_denied_operator_and_the_table_holds_only_read_programs() -> None:
    read = {p.name for p in SHELL_PROGRAMS if p.access is ShellAccess.READ}

    assert "|" in CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS
    assert set(CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS) == {"head", "tail", "grep", "wc"}
    assert set(CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS) <= read


# ── The policy ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git status | head",
        "git status | head -n 5 | wc -l",
        "git show HEAD:README.md | head -100",
        "head -n 170 README.md | tail -n 20",
        "ls|head",
        "git grep -n x src | grep -v y | wc -l",
        "uv run devops ci test tests/a.py 2>&1 | tail -20",
        "grep -n 'shutil\\|subprocess' README.md",
        "grep -n shutil\\|subprocess README.md",
        'grep -n "a|b" README.md | head',
        "git log --format='%h|%s' | head",
    ],
)
def test_a_command_with_no_pipe_or_with_a_read_pipe_has_no_pipe_refusal(command: str) -> None:
    assert pipe_refusal(command) is None


@pytest.mark.parametrize(
    ("command", "program"),
    [
        ("git status | sh", "sh"),
        ("git status|sh", "sh"),
        ("ls | head | sh", "sh"),
        ("ls | python -c x", "python"),
        ("ls | $SHELL", "$SHELL"),
        ("ls | FOO=1 head", "FOO=1"),
        ("ls # x | sh", "sh"),
        ("ls | sort -o out.txt", "sort"),
        ("ls |", ""),
        ("ls | | head", ""),
    ],
)
def test_a_pipe_to_a_program_outside_the_table_is_refused_with_the_program_and_the_table(
    command: str, program: str
) -> None:
    refusal = pipe_refusal(command)

    assert refusal is not None
    assert refusal.startswith("Shell operator '|' is not allowed")
    assert (f"before `{program}`" in refusal) is bool(program)
    assert refusal.endswith(ALLOWED_PIPE)


@pytest.mark.parametrize("command", ["ls |& head", "ls ||| head", "(ls)| head"])
def test_a_pipe_operator_that_is_no_plain_pipe_is_refused(command: str) -> None:
    refusal = pipe_refusal(command)

    assert refusal is not None
    assert refusal.endswith(ALLOWED_PIPE)


@pytest.mark.parametrize(
    ("command", "redirect"),
    [
        ("git status | head > out.txt", ">"),
        ("git status | grep x >> out.txt", ">>"),
        ("git status | wc -l >f", ">"),
    ],
)
def test_a_stage_that_redirects_to_a_file_is_refused_with_its_redirect(
    command: str, redirect: str
) -> None:
    refusal = pipe_refusal(command)

    assert refusal is not None
    assert f"has the argument '{redirect}'" in refusal


@pytest.mark.parametrize("command", ["ls | head 2>&1", "ls | wc -l >/dev/null"])
def test_a_stage_may_copy_a_stream(command: str) -> None:
    assert pipe_refusal(command) is None


def test_a_command_that_cannot_be_read_and_holds_a_pipe_is_refused() -> None:
    assert pipe_refusal("ls 'x | head") is not None
    assert pipe_refusal("ls 'x") is None


def test_the_refused_program_is_shown_escaped_and_cut() -> None:
    refusal = pipe_refusal("ls | " + "a" * 500 + "\u202e")

    assert refusal is not None
    assert len(refusal) < 200
    assert "\u202e" not in refusal


@pytest.mark.parametrize(
    ("command", "rest"),
    [
        ("cd /work/w-1 && git status | head", "git status | head"),
        ("cd '/work/w-1' && git status", "git status"),
        ('cd "/work/w-1"  &&   git status', "git status"),
        ("cd /work/w-1 && git status && ls", "git status && ls"),
        ("cd /work/w-2 && git status", "cd /work/w-2 && git status"),
        ("cd /work/w-1/src && git status", "cd /work/w-1/src && git status"),
        ("cd /work/w-10 && git status", "cd /work/w-10 && git status"),
        ("cd && git status", "cd && git status"),
        ("git status && cd /work/w-1 && ls", "git status && cd /work/w-1 && ls"),
        ("git status", "git status"),
    ],
)
def test_only_the_exact_prefix_cd_checkout_is_removed(command: str, rest: str) -> None:
    assert without_checkout_prefix(command, Path("/work/w-1")) == rest


# ── The shell of the step ─────────────────────────────────────────────────────────────────


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The commands that reach the process edge of the workspace."""
    commands: list[str] = []

    async def run(self: object, command: str, **_options: object) -> CommandResult:
        commands.append(command)
        return CommandResult(exit_code=0, stdout="ran", stderr="")

    monkeypatch.setattr(LocalWorkspaceBackend, "run", run)
    return commands


def _step(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


@pytest.mark.parametrize(
    "command",
    [
        "git status | head -n 5",
        "git show HEAD:README.md | head -100",
        "head -n 170 README.md | tail -n 20",
        "git status | head | wc -l",
        "grep -n 'shutil\\|subprocess' README.md",
        "grep -n shutil\\|subprocess README.md",
    ],
)
def test_a_read_pipe_reaches_the_process_edge_and_returns_its_output(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    started: list[str],
    command: str,
) -> None:
    script = ModelScript(tool_call("shell", command=command), say("Done."))

    _step(store, checkout, script)

    (answer,) = script.tool_answers()
    assert not answer.startswith(("Shell operator", "Command "))
    assert started != []


@pytest.mark.parametrize("command", ["git status | sh", "git status | head | sh", "ls |& head"])
def test_a_pipe_to_another_program_gives_a_refusal_and_starts_no_process(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    started: list[str],
    command: str,
) -> None:
    script = ModelScript(tool_call("shell", command=command), say("Done."))

    _step(store, checkout, script)

    (answer,) = script.tool_answers()
    assert (answer.startswith("Shell operator '|' is not allowed"), started) == (True, [])
    assert answer.endswith(ALLOWED_PIPE)


def test_a_refused_pipe_counts_as_a_refused_command_of_its_first_program(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    started: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_call("shell", command="git status | sh"), say("Done."))

    _step(store, checkout, script)

    assert "Tool call: shell, program git, refused." in capsys.readouterr().err


def test_a_denied_operator_after_a_read_pipe_is_refused_for_that_operator(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    started: list[str],
) -> None:
    script = ModelScript(tool_call("shell", command="git status | head; ls"), say("Done."))

    _step(store, checkout, script)

    (answer,) = script.tool_answers()
    assert (answer.startswith("Shell operator ';' is not allowed."), started) == (True, [])


def test_the_prefix_cd_checkout_is_dropped_before_the_command_runs(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    started: list[str],
) -> None:
    script = ModelScript(
        tool_call("shell", command=f"cd {checkout} && git status | head"), say("Done.")
    )

    _step(store, checkout, script)

    (answer,) = script.tool_answers()
    assert not answer.startswith(("Shell operator", "Command "))
    (text,) = [text for text in started if "git status | head" in text]
    assert f"cd {checkout} && git status" not in text


@pytest.mark.parametrize("suffix", ["git status && ls", "git status; ls"])
def test_a_chain_after_the_checkout_prefix_is_refused(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    started: list[str],
    suffix: str,
) -> None:
    script = ModelScript(tool_call("shell", command=f"cd {checkout} && {suffix}"), say("Done."))

    _step(store, checkout, script)

    (answer,) = script.tool_answers()
    assert (answer.startswith("Shell operator"), started) == (True, [])


def test_a_change_to_another_directory_is_still_refused(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    started: list[str],
) -> None:
    script = ModelScript(tool_call("shell", command="cd src && ls"), say("Done."))

    _step(store, checkout, script)

    (answer,) = script.tool_answers()
    assert (answer.startswith("Shell operator '&&' is not allowed."), started) == (True, [])

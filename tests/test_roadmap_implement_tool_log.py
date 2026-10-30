"""The log line of each tool call of an implement step (#2758).

The model is a pydantic-ai `FunctionModel` that a script answers, so no test reaches a model. The
line goes to the standard error stream, which `capsys` reads.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, ToolFailed

from devops_cli.roadmap.implement_step import StepOutcome, run_step
from devops_cli.roadmap.implement_tool_log import ToolCallLog
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessFake
from tests.support.implement_step import TEST_BODY, WINDOW, write_call
from tests.support.model_script import ModelScript, say, tool_call, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


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


def _lines(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return capsys.readouterr().err.splitlines()


def test_a_refused_program_is_logged_as_other_with_no_argument(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(
        tool_call("shell", command="pytest tests/test_sample.py --flag=sentinel-value"),
        say("Done."),
    )

    _step(store, checkout, script)

    assert _lines(capsys) == ["Tool call: shell, program other, refused."]


def _program_line(command: str, capsys: pytest.CaptureFixture[str]) -> str:
    """The line of one call of a tool that has a `command` argument and takes any command."""

    def shell(command: str) -> str:
        return "the output"

    Agent(
        ModelScript(tool_call("shell", command=command), say("Done.")).model(),
        tools=[shell],
        capabilities=[ToolCallLog().hooks()],
    ).run_sync("go")
    return capsys.readouterr().err.strip()


@pytest.mark.parametrize("program", ["git", "uv", "ruff", "mypy", "openspec", "devops"])
def test_a_program_of_the_allowlist_is_logged_by_name(
    capsys: pytest.CaptureFixture[str], program: str
) -> None:
    assert _program_line(f"{program} --flag=x 'a b'", capsys) == (
        f"Tool call: shell, program {program}, ok."
    )


@pytest.mark.parametrize(
    "command",
    [
        "API_KEY=hunter2 uv run x",
        "PASSWORD=hunter2 git status",
        f"{TOKEN} run",
        "/home/user/secret-dir/tool run",
        "\x1b[31mred git",
        "'unclosed quote",
        "pytest tests/test_sample.py",
        "'git status'",
        "''",
    ],
)
def test_a_first_word_that_is_no_allowed_program_is_logged_as_other(
    capsys: pytest.CaptureFixture[str], command: str
) -> None:
    assert _program_line(command, capsys) == "Tool call: shell, program other, ok."


@pytest.mark.parametrize("command", ["", "   "])
def test_a_command_with_no_program_is_logged_with_no_program(
    capsys: pytest.CaptureFixture[str], command: str
) -> None:
    assert _program_line(command, capsys) == "Tool call: shell, ok."


def test_a_secret_as_the_first_word_never_reaches_the_log_of_a_step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_call("shell", command="API_KEY=hunter2 uv run x"), say("Done."))

    _step(store, checkout, script)

    assert _lines(capsys) == ["Tool call: shell, program other, refused."]


def test_a_call_that_returns_is_logged_with_neither_its_path_nor_its_content(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(
        tool_calls(write_call("tests/test_sample.py", TEST_BODY + "# sentinel-content\n")),
        say("Done."),
    )

    _step(store, checkout, script)

    assert _lines(capsys) == ["Tool call: write_file, ok."]


def test_a_call_that_fails_validation_is_logged_as_a_retry_with_no_program(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_call("read_file"), say("Done."))

    _step(store, checkout, script)

    assert _lines(capsys) == ["Tool call: read_file, retry."]


def test_a_refused_path_is_a_retry_and_not_a_refused_command(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The file tools raise `PermissionError` for a path outside the root. That is no refused
    shell command, so it counts as another retry and its line has no program."""
    script = ModelScript(tool_call("read_file", path="/etc/passwd"), say("Done."))

    _step(store, checkout, script)

    err = capsys.readouterr().err
    assert err.splitlines() == ["Tool call: read_file, retry."]
    assert "passwd" not in err


def test_every_outcome_of_a_tool_call_has_its_line_and_its_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fine() -> str:
        return "the output"

    def forbidden(command: str) -> str:
        raise ModelRetry("not here") from PermissionError("not here")

    def outside(path: str) -> str:
        raise ModelRetry("not here") from PermissionError("not here")

    def again() -> str:
        raise ModelRetry("try again")

    def broken() -> str:
        raise ToolFailed("the workspace is read-only")

    script = ModelScript(
        tool_calls(
            ("fine", {}),
            ("forbidden", {"command": "x"}),
            ("outside", {"path": "/y"}),
            ("again", {}),
            ("broken", {}),
        ),
        say("Done."),
    )
    log = ToolCallLog()
    agent = Agent(
        script.model(), tools=[fine, forbidden, outside, again, broken], capabilities=[log.hooks()]
    )

    agent.run_sync("go")

    assert (sorted(_lines(capsys)), log.refused, log.retried) == (
        [
            "Tool call: again, retry.",
            "Tool call: broken, failed.",
            "Tool call: fine, ok.",
            "Tool call: forbidden, program other, refused.",
            "Tool call: outside, retry.",
        ],
        1,
        2,
    )

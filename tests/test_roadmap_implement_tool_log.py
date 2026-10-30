"""The log line of each tool call of an implement step (#2758).

The model is a pydantic-ai `FunctionModel` that a script answers, so no test reaches a model. The
line goes to the standard error stream, which `capsys` reads.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, ToolFailed

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_PROGRAM_CHARS
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


def test_a_refused_program_is_logged_with_its_first_word_and_no_argument(
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

    assert _lines(capsys) == ["Tool call: shell, program pytest, refused."]


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


def test_a_secret_as_the_first_word_is_masked_in_the_line(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_call("shell", command=f"{TOKEN} run"), say("Done."))

    _step(store, checkout, script)

    err = capsys.readouterr().err
    assert TOKEN not in err
    assert err.splitlines() == ["Tool call: shell, program <masked-github-token>, refused."]


def test_a_long_first_word_is_cut_in_the_line(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    word = "a" * (3 * CONST_ROADMAP_IMPLEMENT_PROGRAM_CHARS)
    script = ModelScript(tool_call("shell", command=f"{word} run"), say("Done."))

    _step(store, checkout, script)

    assert _lines(capsys) == [
        f"Tool call: shell, program {'a' * CONST_ROADMAP_IMPLEMENT_PROGRAM_CHARS}, refused."
    ]


def test_every_outcome_of_a_tool_call_has_its_line_and_its_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fine() -> str:
        return "the output"

    def forbidden() -> str:
        raise ModelRetry("not here") from PermissionError("not here")

    def again() -> str:
        raise ModelRetry("try again")

    def broken() -> str:
        raise ToolFailed("the workspace is read-only")

    script = ModelScript(
        tool_calls(("fine", {}), ("forbidden", {}), ("again", {}), ("broken", {})), say("Done.")
    )
    log = ToolCallLog()
    agent = Agent(
        script.model(), tools=[fine, forbidden, again, broken], capabilities=[log.hooks()]
    )

    agent.run_sync("go")

    assert (sorted(_lines(capsys)), log.refused, log.retried) == (
        [
            "Tool call: again, retry.",
            "Tool call: broken, failed.",
            "Tool call: fine, ok.",
            "Tool call: forbidden, refused.",
        ],
        1,
        1,
    )

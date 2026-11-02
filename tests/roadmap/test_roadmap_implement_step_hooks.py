"""The hooks of the repository as an exit check of a step, and the bounded repair rounds (#3043).

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`. The `pre-commit` stage reads the files of the checkout through `process_fake`: a test
file that holds `pytest.raises(ValueError)` with no `match` fails the stage, as the ast-grep rule
does, and a file that holds `import os` fails `ruff check`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse

from devops_cli.config.settings import load_settings
from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    command_text,
    git,
    is_clean_at,
    programs_run,
    tool_reads,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE = "uv run pre-commit run --hook-stage pre-commit"
RAISES = (
    "def test_shout() -> None:\n    with pytest.raises(ValueError):\n        raise ValueError\n"
)
RAISES_MATCH = RAISES.replace("ValueError):", 'ValueError, match="x"):').replace(
    "raise ValueError", 'raise ValueError("x")'
)
HOOK_REPORT = (
    "ast-grep scan....Failed\nerror: pytest.raises without match\n --> tests/test_sample.py"
)
BAD_TEST = "import os\n\n" + TEST_BODY
TICK = write_call(TASKS_PATH, TICKED)
CODE = write_call("src/sample.py", SHOUT_CODE)
LINT = "uv run ruff check -- src/sample.py tests/test_sample.py"


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    """A checkout whose repository has hooks: `_trusted` names their configuration."""
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _stage_runs(programs: ProcessFake) -> list[str]:
    return [text for text in programs_run(programs, "uv") if text.startswith(STAGE)]


def _trusted(checkout: Path) -> Path:
    """The trusted configuration of the hooks: the job writes it from the default branch. The
    stage is answered by `process_fake`, so the file need not exist."""
    return checkout.parent / "pre-commit-trusted-config.yaml"


def _step(
    store: InMemoryRoadmapStore, checkout: Path, script: ModelScript, *, hooks: bool = True
) -> StepOutcome:
    return run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        hooks=_trusted(checkout) if hooks else None,
    )


def _prompt(script: ModelScript, request: int) -> str:
    return [str(getattr(part, "content", "")) for part in script.seen[request][-1].parts][-1]


def _hook_reads(
    word: str, report: str
) -> Callable[[ProcessCall], subprocess.CompletedProcess[str]]:
    """A stage that fails when the test file holds `word`, and prints `report`."""

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        failed = word in (call.cwd / "tests" / "test_sample.py").read_text(encoding="utf-8")
        return subprocess.CompletedProcess(
            call.argv, 1 if failed else 0, stdout=f"{report}\n" if failed else "", stderr=""
        )

    return answer


def _stage_fails_on(programs: ProcessFake, word: str, report: str = HOOK_REPORT) -> None:
    programs.answer(
        lambda call: command_text(call).startswith(STAGE),
        ProcessAnswer(side_effect=_hook_reads(word, report)),
    )


def _lint_fails_on_an_unused_import(programs: ProcessFake) -> None:
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=tool_reads("import os", "F401 unused")),
    )


def _work(test_body: str) -> ModelResponse:
    return tool_calls(write_call("tests/test_sample.py", test_body), CODE, TICK)


def test_the_default_number_of_repair_rounds_is_three() -> None:
    assert load_settings().roadmap.implement.repair_rounds == 3


def test_a_hook_failure_goes_to_the_agent_and_a_repair_ends_the_step_done(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """An ast-grep violation: `pytest.raises` with no `match`."""
    _stage_fails_on(programs, "pytest.raises(ValueError)")
    repair = write_call("tests/test_sample.py", RAISES_MATCH)
    script = ModelScript(_work(RAISES), say("Done."), tool_calls(repair), say("Added the match."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.repair_rounds, outcome.requests) == (
        StepStatus.DONE,
        "",
        1,
        4,
    )
    assert git(checkout, "show", "HEAD:tests/test_sample.py") + "\n" == RAISES_MATCH
    assert _prompt(script, 2).startswith(
        "A hook of the project failed on your changes:\n\n"
        "The hooks of the stage pre-commit failed with the exit status 1.\n"
        f"{HOOK_REPORT}\n\nThe hooks of the project check each commit."
    )
    assert len(_stage_runs(programs)) == 2


def test_a_hook_failure_that_the_agent_cannot_fix_uses_every_round_and_stops_with_the_output(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _stage_fails_on(programs, "pytest.raises(ValueError)")
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(_work(RAISES), say("Done."), say("I changed nothing."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.commit, outcome.repair_rounds, len(script.seen)) == (
        StepStatus.STOPPED,
        "",
        3,
        5,
    )
    assert outcome.reason == (
        f"The hooks of the stage pre-commit failed with the exit status 1.\n{HOOK_REPORT}"
    )
    assert is_clean_at(checkout, head)


def test_an_error_of_the_hook_tool_stops_the_step_with_no_extra_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call).startswith(STAGE),
        ProcessAnswer(returncode=3, stderr="An unexpected error has occurred"),
    )
    script = ModelScript(_work(TEST_BODY), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.repair_rounds, len(script.seen)) == (StepStatus.STOPPED, 0, 2)
    assert outcome.reason == (
        "The hooks of the stage pre-commit failed with the exit status 3.\n"
        "An unexpected error has occurred"
    )


def test_no_repair_round_leaves_a_hook_failure_to_stop_the_step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"repair_rounds": 0}})
    _stage_fails_on(programs, "pytest.raises(ValueError)")
    script = ModelScript(_work(RAISES), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.repair_rounds, len(script.seen)) == (StepStatus.STOPPED, 0, 2)


def test_a_repair_that_breaks_ruff_gets_the_next_round(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _stage_fails_on(programs, "pytest.raises(ValueError)")
    _lint_fails_on_an_unused_import(programs)
    spoil = write_call("tests/test_sample.py", BAD_TEST)
    fix = write_call("tests/test_sample.py", TEST_BODY)
    script = ModelScript(
        _work(RAISES), say("Done."), tool_calls(spoil), say("Changed."), tool_calls(fix), say("Ok.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.repair_rounds, programs_run(programs, "uv").count(LINT)) == (
        StepStatus.DONE,
        2,
        3,
    )
    assert _prompt(script, 4).startswith("A static check of your group failed:")


def test_the_turn_for_the_ticks_counts_as_a_round(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    work = tool_calls(write_call("tests/test_sample.py", TEST_BODY), CODE)
    script = ModelScript(work, say("Done."), tool_calls(TICK), say("Ticked."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.repair_rounds) == (StepStatus.DONE, 1)


def test_the_table_of_a_step_shows_the_repair_rounds(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from devops_cli.roadmap.implement_step import render_outcome

    work = tool_calls(write_call("tests/test_sample.py", TEST_BODY), CODE)
    script = ModelScript(work, say("Done."), tool_calls(TICK), say("Ticked."))
    outcome = _step(store, checkout, script)

    render_outcome(outcome, "example/roadmap", "table")

    assert "Repair rounds" in capsys.readouterr().out


def test_a_repository_with_no_hook_configuration_runs_no_hook(
    store: InMemoryRoadmapStore, implement_checkout: Path, programs: ProcessFake
) -> None:
    """A hook that does not exist is not run. The agent cannot make the file go away: the
    commit of the step decides."""
    work = tool_calls(write_call("tests/test_sample.py", TEST_BODY), CODE, TICK)
    script = ModelScript(work, say("Done."))

    outcome = _step(store, implement_checkout, script, hooks=False)

    assert (outcome.status, outcome.repair_rounds) == (StepStatus.DONE, 0)
    assert _stage_runs(programs) == []


def test_an_edit_of_the_configuration_by_the_agent_changes_no_hook_run(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The stage reads the trusted copy with `--config`, so a configuration of `repos: []` in the
    checkout skips no hook."""
    skip = write_call(".pre-commit-config.yaml", "repos: []\n")
    work = tool_calls(write_call("tests/test_sample.py", TEST_BODY), CODE, TICK, skip)
    script = ModelScript(work, say("Done."))

    _step(store, checkout, script)

    stages = _stage_runs(programs)
    assert stages
    assert all(text.endswith(f"--config {_trusted(checkout)}") for text in stages)


def test_a_stage_that_runs_out_of_time_stops_the_step_with_the_reason(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    def hang(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(call.argv, 1)

    programs.answer(
        lambda call: command_text(call).startswith(STAGE), ProcessAnswer(side_effect=hang)
    )
    work = tool_calls(write_call("tests/test_sample.py", TEST_BODY), CODE, TICK)
    script = ModelScript(work, say("Done."))
    start = git(checkout, "rev-parse", "HEAD")

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.repair_rounds, "ran out of time" in outcome.reason) == (
        StepStatus.STOPPED,
        0,
        True,
    )
    assert is_clean_at(checkout, start)

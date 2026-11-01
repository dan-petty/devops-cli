"""The extra turn for a failed static check (#2795): a step whose `ruff check` or `mypy --strict`
fails gets one more turn with the text of the failure, may change only the files it changed, and
stops with the first failure of the checks that run again after the turn.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`. `ruff check` and `mypy` read the files of the checkout through `process_fake`, so a
file that holds `import os` fails the lint and a file that holds `BAD_TYPE` fails the type check.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
    CONST_ROADMAP_IMPLEMENT_REASON_CHARS,
)
from devops_cli.roadmap.implement_step import (
    FixRequest,
    StepOutcome,
    StepStatus,
    build_step_inputs,
    run_fix_step,
    run_step,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.security.sanitizer import mask_secrets
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
    the_whole_group,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_call, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

BAD_TEST = "import os\n\n" + TEST_BODY
BAD_TYPE_CODE = SHOUT_CODE + "\nBAD_TYPE = 1\n"
LINT = "uv run ruff check -- src/sample.py tests/test_sample.py"
TYPES = "uv run mypy --strict -- src/sample.py tests/test_sample.py"
UNUSED = "F401 `os` imported but unused\n --> tests/test_sample.py:1:8"
BAD_TYPE = "src/sample.py:9: error: bad type"
NOT_TICKED = (write_call("tests/test_sample.py", BAD_TEST), write_call("src/sample.py", SHOUT_CODE))


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _tool_reads(
    word: str, report: str
) -> Callable[[ProcessCall], subprocess.CompletedProcess[str]]:
    """A static tool that fails when a file after `--` holds `word`, and prints `report`."""

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        names = call.argv[call.argv.index("--") + 1 :]
        failed = any(word in (call.cwd / name).read_text(encoding="utf-8") for name in names)
        return subprocess.CompletedProcess(
            call.argv, 1 if failed else 0, stdout=f"{report}\n" if failed else "", stderr=""
        )

    return answer


def _lint_fails_on_an_unused_import(programs: ProcessFake) -> None:
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=_tool_reads("import os", UNUSED)),
    )


def _step(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def _prompt(script: ModelScript, request: int) -> str:
    return [str(getattr(part, "content", "")) for part in script.seen[request][-1].parts][-1]


REPAIR = write_call("tests/test_sample.py", TEST_BODY)
TICK = write_call(TASKS_PATH, TICKED)
ASK = (
    "A static check of your group failed:\n\n"
    f"{LINT} exited with status 1.\n{UNUSED}\n\n"
    "Fix what the check reports. Change only the files that you changed."
)
ASK_TICKS = (
    f" The file `{TASKS_PATH}` also holds these tasks of your group unticked:\n\n"
    "- [ ] Add the failing test `tests/test_sample.py` for `src/sample.py`\n"
    "- [ ] Add `shout` to `src/sample.py`\n\n"
    "Change `- [ ]` to `- [x]` in front of each task whose work is done. Change nothing else "
    "in that file."
)
END = " Then reply with one short message."


def test_a_step_with_an_unused_import_ends_done_after_the_extra_turn_removes_it(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    before = git(checkout, "rev-parse", "HEAD")
    first = tool_calls(
        write_call("tests/test_sample.py", BAD_TEST),
        write_call("src/sample.py", SHOUT_CODE),
        TICK,
    )
    script = ModelScript(first, say("Done."), tool_calls(REPAIR), say("Removed the import."))

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        outcome.requests,
        git(checkout, "rev-parse", "HEAD~1"),
        git(checkout, "show", "HEAD:tests/test_sample.py") + "\n",
        programs_run(programs, "uv").count(LINT),
        git(checkout, "status", "--porcelain"),
    ) == (StepStatus.DONE, "", 4, before, TEST_BODY, 2, "")
    assert _prompt(script, 2) == ASK + END


def test_a_step_that_still_fails_after_the_extra_turn_stops_and_the_model_gets_no_third_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    head = git(checkout, "rev-parse", "HEAD")
    work = tool_calls(*NOT_TICKED, TICK)
    script = ModelScript(work, say("Done."), say("I changed nothing."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.commit, len(script.seen), outcome.requests) == (
        StepStatus.STOPPED,
        f"{LINT} exited with status 1.\n{UNUSED}",
        "",
        3,
        3,
    )
    assert is_clean_at(checkout, head)


def test_a_failed_type_check_gets_the_extra_turn_with_its_text(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call).startswith("uv run mypy"),
        ProcessAnswer(side_effect=_tool_reads("BAD_TYPE", BAD_TYPE)),
    )
    work = tool_calls(
        write_call("tests/test_sample.py", TEST_BODY),
        write_call("src/sample.py", BAD_TYPE_CODE),
        TICK,
    )
    script = ModelScript(
        work, say("Done."), tool_calls(write_call("src/sample.py", SHOUT_CODE)), say("Fixed.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.requests, programs_run(programs, "uv").count(TYPES)) == (
        StepStatus.DONE,
        4,
        2,
    )
    assert _prompt(script, 2).startswith(
        f"A static check of your group failed:\n\n{TYPES} exited with status 1.\n{BAD_TYPE}"
    )


def test_an_extra_turn_that_changes_a_file_the_step_did_not_change_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    head = git(checkout, "rev-parse", "HEAD")
    other = write_call("src/other.py", "OTHER = 2\n")
    script = ModelScript(
        tool_calls(*NOT_TICKED, TICK), say("Done."), tool_calls(REPAIR, other), say("Fixed.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.commit, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "The extra turn for the static check changed files that the step had not changed: "
        "src/other.py.",
        "",
        True,
    )


def test_an_extra_turn_that_writes_a_new_file_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    new = write_call("tests/test_sample_more.py", TEST_BODY)
    script = ModelScript(
        tool_calls(*NOT_TICKED, TICK), say("Done."), tool_calls(REPAIR, new), say("Fixed.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        "The extra turn for the static check changed files that the step had not changed: "
        "tests/test_sample_more.py.",
    )


def test_a_failure_and_an_unticked_task_get_one_extra_turn_that_holds_both(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    script = ModelScript(
        tool_calls(*NOT_TICKED),
        say("Done."),
        tool_calls(REPAIR, TICK),
        say("Fixed and ticked."),
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.requests) == (StepStatus.DONE, "", 4)
    assert _prompt(script, 2) == ASK + ASK_TICKS + END
    assert git(checkout, "show", f"HEAD:{TASKS_PATH}") + "\n" == TICKED


def test_the_ticks_that_stay_missing_after_the_extra_turn_stop_the_step_with_no_third_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    script = ModelScript(
        tool_calls(*NOT_TICKED), say("Done."), tool_calls(REPAIR), say("Fixed, no ticks.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, len(script.seen)) == (StepStatus.STOPPED, 4)
    assert outcome.reason == (
        "A task of the group is not ticked: [ ] Add the failing test `tests/test_sample.py` for "
        "`src/sample.py`"
    )


def test_a_failed_verification_command_gets_no_extra_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call) == "uv run devops docs check",
        ProcessAnswer(returncode=1, stdout="no docs\n"),
    )
    _lint_fails_on_an_unused_import(programs)
    script = ModelScript(tool_calls(*NOT_TICKED, TICK), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, len(script.seen), programs_run(programs, "uv").count(LINT)) == (
        StepStatus.STOPPED,
        2,
        0,
    )


def test_a_static_failure_after_the_extra_turn_for_the_ticks_gets_no_second_extra_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The checks pass after the first turn. The turn for the ticks makes `ruff check` fail."""
    _lint_fails_on_an_unused_import(programs)
    clean = (write_call("tests/test_sample.py", TEST_BODY), write_call("src/sample.py", SHOUT_CODE))
    spoil = write_call("tests/test_sample.py", BAD_TEST)
    script = ModelScript(
        tool_calls(*clean), say("Done."), tool_calls(TICK, spoil), say("Ticked."), say("Third.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, len(script.seen)) == (StepStatus.STOPPED, 4)


def test_a_fix_step_gets_the_extra_turn_with_the_failure_and_no_list_of_ticks(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    script = ModelScript(tool_calls(*NOT_TICKED), say("Done."), tool_calls(REPAIR), say("Fixed."))

    outcome = run_fix_step(
        store,
        item=1,
        fix=FixRequest(check="Static Analysis", log="E501"),
        source=checkout,
        model=script.model(),
        window=WINDOW,
    )

    assert (outcome.status, outcome.requests) == (StepStatus.DONE, 4)
    assert _prompt(script, 2) == ASK + END


def test_the_extra_turn_counts_against_the_request_limit_of_the_first_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The first turn uses all requests but one. A second budget would let the step end done."""
    _lint_fails_on_an_unused_import(programs)
    reads = [tool_call("read_file", path="docs/SAMPLE.md")] * (
        CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS - 3
    )
    script = ModelScript(
        tool_calls(*NOT_TICKED, TICK), *reads, say("Done."), tool_calls(REPAIR), say("Fixed.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.requests) == (
        StepStatus.STOPPED,
        CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
    )
    assert outcome.reason.startswith("UsageLimitExceeded: ")


def test_the_failure_text_in_the_message_is_cut_to_the_reason_limit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    long_report = "x" * (2 * CONST_ROADMAP_IMPLEMENT_REASON_CHARS)
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(returncode=1, stdout=long_report),
    )
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), say("Cannot."))

    _step(store, checkout, script)

    prompt = _prompt(script, 2)
    shown = prompt.split("A static check of your group failed:\n\n")[1].split("\n\nFix what")[0]
    assert len(shown) == CONST_ROADMAP_IMPLEMENT_REASON_CHARS


def test_the_instructions_say_that_a_failed_static_check_gets_one_turn(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert "you get one more turn with the text of the error" in inputs.instructions


def test_the_failure_text_in_the_message_is_masked(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    assert mask_secrets(token) != token
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(returncode=1, stdout=f"token {token}\n"),
    )
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), say("Cannot."))

    _step(store, checkout, script)

    assert token not in _prompt(script, 2)


def test_an_extra_turn_that_commits_stops_the_step_and_the_checkout_returns_to_its_start(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    head = git(checkout, "rev-parse", "HEAD")
    moved: list[str] = []

    def agent_commits() -> None:
        git(checkout, "add", "-A")
        git(checkout, "commit", "-q", "-m", "own commit")
        moved.append(git(checkout, "rev-parse", "HEAD"))

    script = ModelScript(
        tool_calls(*NOT_TICKED, TICK),
        say("Done."),
        tool_calls(REPAIR),
        say("Fixed."),
        effects={4: agent_commits},
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.commit, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        f"The agent moved HEAD from {head} to {moved[0]}. A step makes the only commit.",
        "",
        True,
    )


def test_an_extra_turn_that_changes_the_verification_command_leaves_the_tasks_file_as_it_was(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    changed = TICKED.replace("`uv run devops ci test tests/test_sample.py`", "`true`")
    assert changed != TICKED
    script = ModelScript(
        tool_calls(*NOT_TICKED, TICK),
        say("Done."),
        tool_calls(REPAIR, write_call(TASKS_PATH, changed)),
        say("Fixed."),
    )

    outcome = _step(store, checkout, script)

    assert outcome.status == StepStatus.DONE
    assert git(checkout, "show", f"HEAD:{TASKS_PATH}") + "\n" == TICKED

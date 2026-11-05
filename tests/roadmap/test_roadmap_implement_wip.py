"""A step keeps its green tasks as work in progress, and the next attempt resumes from them (#3054).

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`, and every other program is answered by `process_fake`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.implement_wip import WipCommit, kept_commits, wip_base
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import (
    CHECK,
    DOCS,
    SHOUT_CODE,
    TASKS,
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

TICK_FIRST = TASKS.replace("- [ ] Add the failing test", "- [x] Add the failing test")
TEST_FILE = write_call("tests/test_sample.py", TEST_BODY)
CODE_FILE = write_call("src/sample.py", SHOUT_CODE)


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    script: ModelScript,
    kept: list[WipCommit] | None = None,
) -> StepOutcome:
    return run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        on_wip=kept.append if kept is not None else None,
    )


def _docs_check_fails_once(programs: ProcessFake) -> None:
    """The first run of the verification `uv run devops docs check` fails, and the later runs pass.
    The job ticks a group only when its checks pass (#3488), so this check stops the first step."""
    pending = [1]

    def docs(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        code = pending.pop() if pending else 0
        return subprocess.CompletedProcess(call.argv, code, stdout="", stderr="")

    programs.answer(lambda call: command_text(call) == DOCS, ProcessAnswer(side_effect=docs))


def _first_task_then_a_stop(programs: ProcessFake) -> ModelScript:
    """An agent that does the first task and ticks it, and writes the code of the second task. The
    check of the group fails at the exit, so the step stops with the first task kept (#3054)."""
    _docs_check_fails_once(programs)
    return ModelScript(
        tool_calls(TEST_FILE),
        tool_calls(write_call(TASKS_PATH, TICK_FIRST)),
        tool_calls(CODE_FILE),
        say("The code is written."),
        say("I could not tick the second task."),
    )


def test_a_stopped_step_keeps_the_task_that_passed_its_verification(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    start = git(checkout, "rev-parse", "HEAD")
    kept: list[WipCommit] = []

    outcome = _step(store, checkout, _first_task_then_a_stop(programs), kept)

    tip = git(checkout, "rev-parse", "HEAD")
    assert outcome.status is StepStatus.STOPPED
    assert kept == [WipCommit(group=1, done=1, total=2, sha=tip)]
    assert git(checkout, "rev-list", "--count", f"{start}..HEAD") == "1"
    assert git(checkout, "log", "-1", "--format=%s") == (
        "wip: 1 of 2 tasks of group 1, The first group (#1)"
    )
    assert git(checkout, "show", f"HEAD:{TASKS_PATH}") == TICK_FIRST.strip()
    assert git(checkout, "show", "HEAD:tests/test_sample.py") == TEST_BODY.strip()
    assert git(checkout, "status", "--porcelain") == ""
    assert "shout" not in (checkout / "src/sample.py").read_text(encoding="utf-8")
    assert CHECK in programs_run(programs, "uv")


def test_the_diff_of_a_stopped_step_holds_only_the_work_after_the_last_kept_task(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    outcome = _step(store, checkout, _first_task_then_a_stop(programs))

    assert "+def shout(" in outcome.diff
    assert "test_shout" not in outcome.diff


def test_a_second_attempt_starts_from_the_kept_task_and_ends_done_in_one_commit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    start = git(checkout, "rev-parse", "HEAD")
    _step(store, checkout, _first_task_then_a_stop(programs))
    second = ModelScript(tool_calls(CODE_FILE, write_call(TASKS_PATH, TICKED)), say("Done."))

    outcome = _step(store, checkout, second)

    group = [str(getattr(part, "content", "")) for part in second.seen[0][-1].parts][-1]
    assert outcome.status is StepStatus.DONE
    assert "- [x] Add the failing test `tests/test_sample.py`" in group
    assert "- [ ] Add `shout` to `src/sample.py`" in group
    assert git(checkout, "rev-list", "--count", f"{start}..HEAD") == "1"
    assert not git(checkout, "log", "-1", "--format=%s").startswith("wip:")
    assert git(checkout, "show", f"HEAD:{TASKS_PATH}") == TICKED.strip()
    assert git(checkout, "show", "HEAD:tests/test_sample.py") == TEST_BODY.strip()
    assert kept_commits(lambda *args: git(checkout, *args), start) == []


def test_a_task_that_fails_its_verification_is_not_kept(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    start = git(checkout, "rev-parse", "HEAD")
    programs.answer(
        lambda call: command_text(call) == CHECK, ProcessAnswer(returncode=1, stdout="red\n")
    )
    kept: list[WipCommit] = []

    outcome = _step(store, checkout, _first_task_then_a_stop(programs), kept)

    assert (outcome.status, kept) == (StepStatus.STOPPED, [])
    assert is_clean_at(checkout, start)


def test_a_failed_static_check_after_the_last_tick_keeps_the_ticked_work(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The case of #2175: every task is done and ticked, one lint error stops the step, and the
    exit checks still judge the work that the `wip:` commit holds."""
    start = git(checkout, "rev-parse", "HEAD")
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=tool_reads("upper()", "E501 too long")),
    )
    script = ModelScript(
        tool_calls(TEST_FILE, CODE_FILE),
        tool_calls(write_call(TASKS_PATH, TICKED)),
        say("Done."),
    )
    kept: list[WipCommit] = []

    outcome = _step(store, checkout, script, kept)

    assert outcome.status is StepStatus.STOPPED
    assert "E501 too long" in outcome.reason
    assert [(commit.done, commit.total) for commit in kept] == [(2, 2)]
    assert git(checkout, "rev-list", "--count", f"{start}..HEAD") == "1"
    assert git(checkout, "status", "--porcelain") == ""
    assert wip_base(lambda *args: git(checkout, *args)) == start


def test_a_stray_file_stays_out_of_the_wip_commit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(TEST_FILE, write_call("scratch.txt", "a note\n")),
        tool_calls(write_call(TASKS_PATH, TICK_FIRST)),
        say("The code is not written."),
    )

    _step(store, checkout, script)

    assert git(checkout, "ls-tree", "-r", "--name-only", "HEAD").count("scratch.txt") == 0

"""Every push of the implement job sends a branch that holds the default branch (#4380).

Git runs for real on a clone with an `origin`. The model is scripted, so the steps are real. GitHub's
REST API and `gh` are faked at their edges. `main` of `origin` moves while a step runs, as it does
in the 20 minutes of a real run, and an effect of the script reads `origin` at the next request.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

import pytest
from pydantic_ai.exceptions import ModelAPIError

from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.implement_step import command_text
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    TASKS_PATH,
    JobWorld,
    advance_main,
    archive_effect,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

FILES = 5
FILES_AND_TESTS = ", ".join(
    f"`{path}` (new)"
    for i in range(1, FILES + 1)
    for path in (f"src/devops_cli/f{i}.py", f"tests/test_f{i}.py")
)
TASKS_OF_FIVE = (
    "# Tasks\n\n## 1. The five files\n\n"
    f"Reads: `CONTEXT.md`. Changes: {FILES_AND_TESTS}.\n\n"
    + "".join(
        f"- [ ] 1.{i} Add `src/devops_cli/f{i}.py`\n  - Verification: `$ uv run devops ci test tests/test_f{i}.py`\n"
        for i in range(1, FILES + 1)
    )
    + "\n## Criteria\n\n- Group 1: The job keeps every comment.\n"
)
BEHIND = "0"


@pytest.fixture
def staged_tasks() -> str:
    return TASKS_OF_FIVE


@pytest.fixture
def planned_tasks() -> str:
    return TASKS_OF_FIVE


def _ticked(count: int) -> str:
    return TASKS_OF_FIVE.replace("- [ ]", "- [x]", count)


def _file(number: int) -> tuple[str, dict[str, str]]:
    return "write_file", {"path": f"src/devops_cli/f{number}.py", "content": f"VALUE = {number}\n"}


def _tick(count: int) -> tuple[str, dict[str, str]]:
    return "write_file", {"path": TASKS_PATH, "content": _ticked(count)}


def _task(number: int) -> list[object]:
    """The two replies of an agent that does task `number`: the file, then the tick."""
    return [tool_calls(_file(number)), tool_calls(_tick(number))]


def _commits_behind(world: JobWorld) -> str:
    """The count of the commits of `main` that the item branch of `origin` lacks."""
    return world.repo.origin_git("rev-list", "--count", f"{BRANCH}..main")


def _watch(world: JobWorld, seen: list[str]) -> Callable[[], None]:
    return lambda: seen.append(_commits_behind(world))


def test_the_first_wip_push_of_a_planned_item_holds_the_commit_that_main_gained(
    planned_world: JobWorld,
) -> None:
    seen: list[str] = []
    script = ModelScript(
        *_task(1),
        ModelAPIError("example-model", "The pod died."),
        effects={1: lambda: advance_main(planned_world), 3: _watch(planned_world, seen)},
    )

    planned_world.run(script)

    assert seen == [BEHIND]


def test_a_later_wip_push_holds_the_commit_that_main_gained(planned_world: JobWorld) -> None:
    seen: list[str] = []
    script = ModelScript(
        *_task(1),
        *_task(2),
        ModelAPIError("example-model", "The pod died."),
        effects={
            3: lambda: advance_main(planned_world),
            5: _watch(planned_world, seen),
        },
    )

    planned_world.run(script)

    assert seen == [BEHIND]


def test_a_wip_push_of_a_staged_item_holds_the_commit_that_main_gained(
    job_world: JobWorld,
) -> None:
    seen: list[str] = []
    script = ModelScript(
        *_task(1),
        ModelAPIError("example-model", "The pod died."),
        effects={1: lambda: advance_main(job_world), 3: _watch(job_world, seen)},
    )

    job_world.run(script)

    assert seen == [BEHIND]


def test_the_wip_push_leaves_the_checkout_of_the_step_alone(planned_world: JobWorld) -> None:
    """The step holds the sha of its last `wip:` commit, so the push of a rebased copy must not
    move the branch of the checkout. The step that follows the push still ticks its tasks."""
    script = ModelScript(
        *_task(1),
        *_task(2),
        *_task(3),
        *_task(4),
        *_task(5),
        say("Group 1 is done."),
        effects={3: lambda: advance_main(planned_world)},
    )

    applied = planned_world.run(script)

    subjects = planned_world.origin_log()
    assert applied.ready == (1,)
    assert not [subject for subject in subjects if subject.startswith("wip:")]
    assert _commits_behind(planned_world) == BEHIND


def test_a_stop_pushes_a_branch_that_holds_the_commit_that_main_gained(
    planned_world: JobWorld,
) -> None:
    script = ModelScript(
        *_task(1),
        ModelAPIError("example-model", "The pod died."),
        effects={3: lambda: advance_main(planned_world)},
    )

    applied = planned_world.run(script)

    assert applied.stopped == (1,)
    assert _commits_behind(planned_world) == BEHIND
    held = planned_world.store.item(1)
    assert held is not None
    sha = planned_world.repo.origin_git("rev-parse", BRANCH)
    assert f"The last is `{sha}`." in planned_world.issue_comments()[0]


def test_a_conflict_at_a_wip_push_and_at_the_stop_pushes_nothing(
    planned_world: JobWorld, capsys: pytest.CaptureFixture[str]
) -> None:
    """A head that does not hold `main` never goes to `origin` (#4670)."""
    script = ModelScript(
        *_task(1),
        ModelAPIError("example-model", "The pod died."),
        effects={
            1: lambda: advance_main(planned_world, "src/devops_cli/f1.py", "VALUE = 99\n"),
        },
    )

    applied = planned_world.run(script)

    assert applied.stopped == (1,)
    assert planned_world.repo.origin_git("branch", "--list", BRANCH) == ""
    assert "The rebase onto origin/main stopped." in capsys.readouterr().err
    status = planned_world.repo.git("worktree", "list")
    assert status.count("\n") == 0


def _archive_applied_then_refused(world: JobWorld) -> None:
    """`main` gains a commit, then `uv run devops openspec archive` moves the change folder and
    exits 1, as it does when the strict validation of the specs fails after the move."""

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        advance_main(world)
        archive_effect(call)
        return subprocess.CompletedProcess(
            call.argv, 1, stdout="The archive is applied.\nTotals: 2 passed, 1 failed\n", stderr=""
        )

    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(side_effect=answer),
    )


def test_a_stop_after_an_archive_that_failed_pushes_a_branch_that_holds_the_commit_that_main_gained(
    planned_world: JobWorld, capsys: pytest.CaptureFixture[str]
) -> None:
    """The files that the failed archive wrote are in no commit, so the stop drops them, and the
    rebase of the stop finds a clean checkout."""
    _archive_applied_then_refused(planned_world)
    script = ModelScript(*(reply for n in range(1, FILES + 1) for reply in _task(n)), say("Done."))

    applied = planned_world.run(script)

    assert applied.stopped == (1,)
    assert planned_world.origin_log() == [
        "fix(roadmap): The five files (#1)",
        "docs: regenerate the documentation (#1)",
    ]
    assert _commits_behind(planned_world) == BEHIND
    assert "cannot rebase" not in capsys.readouterr().err

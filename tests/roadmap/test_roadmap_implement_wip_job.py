"""The implement job keeps the work of a stopped step on the branch, and a second Job resumes from
it (#3054).

Git runs for real on a clone with an `origin`. The model is scripted, so the steps are real. GitHub's
REST API and `gh` are faked at their edges.
"""

from __future__ import annotations

import json

import pytest
from pydantic_ai.exceptions import ModelAPIError

from devops_cli.roadmap.store import ItemField
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import BRANCH, TASKS_PATH, JobWorld

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
        f"- [ ] 1.{i} Add `src/devops_cli/f{i}.py`\n  - Verification: `uv run devops ci test tests/test_f{i}.py`\n"
        for i in range(1, FILES + 1)
    )
    + "\n## Criteria\n\n- Group 1: The job keeps every comment.\n"
)
PLAN = "fix(roadmap): plan"


@pytest.fixture
def staged_tasks() -> str:
    return TASKS_OF_FIVE


def _ticked(count: int) -> str:
    return TASKS_OF_FIVE.replace("- [ ]", "- [x]", count)


def _file(number: int) -> tuple[str, dict[str, str]]:
    return "write_file", {"path": f"src/devops_cli/f{number}.py", "content": f"VALUE = {number}\n"}


def _tick(count: int) -> tuple[str, dict[str, str]]:
    return "write_file", {"path": TASKS_PATH, "content": _ticked(count)}


def _first_job(seen_on_origin: list[list[str]], job_world: JobWorld) -> ModelScript:
    """An agent that does three of the five tasks and ticks each, starts the fourth, and dies.
    The effect reads `origin` at the request after the last tick."""
    replies = [
        tool_calls(call) for number in range(1, 4) for call in (_file(number), _tick(number))
    ]
    return ModelScript(
        *replies,
        tool_calls(_file(4)),
        ModelAPIError("example-model", "The pod died."),
        effects={len(replies) + 1: lambda: seen_on_origin.append(job_world.origin_log())},
    )


def test_the_work_of_a_killed_step_is_on_origin_before_the_step_ends(job_world: JobWorld) -> None:
    on_origin: list[list[str]] = []

    applied = job_world.run(_first_job(on_origin, job_world))

    assert applied.stopped == (1,)
    subjects = on_origin[0]
    assert subjects[0] == PLAN
    assert [s.split(" of ")[0] for s in subjects[1:]] == ["wip: 1", "wip: 2", "wip: 3"]


def test_a_stop_keeps_three_of_five_tasks_on_the_branch_and_says_so(job_world: JobWorld) -> None:
    job_world.run(_first_job([], job_world))

    log = job_world.origin_log()
    tip = job_world.repo.origin_git("rev-parse", BRANCH)
    tasks = job_world.repo.origin_git("show", f"{BRANCH}:{TASKS_PATH}")
    comment = job_world.issue_comments()[0]
    held = job_world.store.item(1)
    assert held is not None
    record = json.loads(held.job_record["implement.wip"] or "{}")
    assert (len(log), tasks.count("- [x]"), tasks.count("- [ ]")) == (4, 3, 2)
    assert f"The job kept 3 work-in-progress commits on the branch `{BRANCH}` on origin." in comment
    assert f"The last is `{tip}`." in comment
    assert record == {"group": 1, "done": 3, "of": 5, "sha": tip}
    assert "f4.py" not in job_world.repo.origin_git("ls-tree", "-r", "--name-only", BRANCH)


def test_a_second_job_does_only_the_remaining_tasks_and_folds_the_kept_work(
    job_world: JobWorld,
) -> None:
    job_world.run(_first_job([], job_world))
    job_world.store.seed_comment(1, "implement: retry", author_association="OWNER")
    held = job_world.store.item(1)
    assert held is not None
    # The Service clears the stop and puts the item back to Ready (`clear_stops`).
    job_world.store.set_field(held, ItemField.STATUS, "Ready")
    second = ModelScript(
        tool_calls(_file(4)),
        tool_calls(_tick(4)),
        tool_calls(_file(5)),
        tool_calls(_tick(5)),
        say("Group 1 is done."),
    )

    applied = job_world.run(second)

    message = [str(getattr(part, "content", "")) for part in second.seen[0][-1].parts][-1]
    held = job_world.store.item(1)
    assert held is not None
    assert applied.ready == (1,)
    group = message.split("# Your group")[1].split("# The tasks file")[0]
    assert group.count("- [x] 1.") == 3
    assert group.count("- [ ] 1.") == 2
    subjects = job_world.origin_log()
    assert not [subject for subject in subjects if subject.startswith("wip:")]
    assert "implement.wip" not in {k for k, v in held.job_record.items() if v}
    for number in range(1, FILES + 1):
        assert f"f{number}.py" in job_world.repo.origin_git("ls-tree", "-r", "--name-only", BRANCH)


def test_the_commit_that_ticks_the_last_task_waits_for_the_push_of_the_stop(
    job_world: JobWorld,
) -> None:
    """The exit checks follow the last tick at once, so the job pushes that commit with the stop."""
    on_origin: list[list[str]] = []
    replies = [
        tool_calls(call)
        for number in range(1, FILES + 1)
        for call in (_file(number), _tick(number))
    ]
    script = ModelScript(
        *replies,
        ModelAPIError("example-model", "The provider broke."),
        effects={len(replies) + 1: lambda: on_origin.append(job_world.origin_log())},
    )

    applied = job_world.run(script)

    assert applied.stopped == (1,)
    assert len(on_origin[0]) == FILES  # the plan and four `wip:` commits
    assert len(job_world.origin_log()) == FILES + 1

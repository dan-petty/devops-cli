"""`devops roadmap implement` as a job: the watch of the checks, the bounded repair rounds, and the
stops that follow the push (#2665, #3043). The checks of the pull request are scripted for each
head."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse

from tests.support.fakes.process import ProcessAnswer
from tests.support.model_script import say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    FAIL,
    OPEN_THREAD,
    PASS,
    PULL,
    RUNNING,
    SHOUT,
    JobWorld,
    a_fix,
    move_main_when,
    two_groups,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

MARKER = "<!-- devops roadmap implement -->"
CHECK = "Tests & Coverage"


def _fix(round_number: int) -> tuple[ModelResponse, ModelResponse]:
    """A fix that changes the code in a way that no earlier fix did."""
    changed = SHOUT + "".join(f"\n\nVALUE_{k} = {k}\n" for k in range(round_number))
    path = "src/devops_cli/shout.py"
    return (
        tool_calls(("write_file", {"path": path, "content": changed})),
        say(f"Fixed round {round_number}."),
    )


def _comments(world: JobWorld) -> list[str]:
    return [str(sent["body"]) for sent in world.sent("POST", f"issues/{PULL}/comments")]


def _item(world: JobWorld) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(1)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


def test_a_check_that_fails_once_gets_a_fix_step_with_its_log_and_then_passes(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[FAIL], [PASS]]
    script = two_groups(*a_fix())

    applied = job_world.run(script)

    assert (applied.ready, applied.stopped) == ((1,), ())
    assert job_world.origin_log()[-1] == f"Make check {CHECK} pass (#1)"
    first_fix_request = script.seen[4]
    prompt = " ".join(
        str(getattr(part, "content", "")) for m in first_fix_request for part in m.parts
    )
    assert "FAILED tests/test_shout.py::test_shout" in prompt
    assert job_world.pull.run_view_calls == [
        ("run", "view", "101", "--log-failed", "--job", "202", "--repo", "example/roadmap")
    ]
    assert job_world.pull.ready_calls == [("pr", "ready", str(PULL), "--repo", "example/roadmap")]
    assert _item(job_world)[0] == "In Review"


def test_a_conflict_on_the_rebase_after_the_fix_pushes_the_fix_commit(job_world: JobWorld) -> None:
    job_world.pull.runs = [[FAIL], [PASS]]
    move_main_when(
        job_world,
        lambda call: call.argv[1:3] == ("run", "view"),
        lambda call: subprocess.CompletedProcess(call.argv, 0, stdout=job_world.pull.log),
    )

    applied = job_world.run(two_groups(*a_fix()))

    status, record = _item(job_world)
    assert (applied.ready, applied.stopped, status, record.get("implement.stopped")) == (
        (),
        (1,),
        "Blocked",
        "push",
    )
    assert job_world.origin_log()[-1] == f"Make check {CHECK} pass (#1)"
    assert job_world.pull.ready_calls == []


def test_a_check_that_fails_in_the_last_round_stops_the_item_and_leaves_the_draft(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"repair_rounds": 1}})
    job_world.pull.runs = [[FAIL], [FAIL]]
    script = two_groups(*a_fix(), *a_fix())

    applied = job_world.run(script)

    status, record = _item(job_world)
    assert (applied.ready, applied.stopped, status, record.get("implement.stopped")) == (
        (),
        (1,),
        "Blocked",
        "checks",
    )
    assert len(script.seen) == 6
    assert job_world.pull.ready_calls == []
    assert f"The check {CHECK} failed." in job_world.issue_comments()[0]
    assert job_world.origin_log()[-1] == f"Make check {CHECK} pass (#1)"


def test_a_fix_step_that_stops_stops_the_item_at_the_fix(job_world: JobWorld) -> None:
    job_world.pull.runs = [[FAIL], [PASS]]
    script = two_groups(say("I cannot find the cause."))

    applied = job_world.run(script)

    _, record = _item(job_world)
    assert (applied.stopped, record.get("implement.stopped")) == ((1,), "fix")
    assert "I cannot find the cause." in job_world.issue_comments()[0]


def test_a_read_that_still_shows_the_old_head_is_read_again_until_the_new_head_has_checks(
    job_world: JobWorld,
) -> None:
    job_world.pull.stale = 2

    applied = job_world.run(two_groups())

    assert (applied.ready, job_world.clock.waits) == ((1,), [30.0, 30.0])


def test_a_head_that_holds_no_check_is_waited_for_until_the_checks_time_out(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[]]

    applied = job_world.run(two_groups())

    _, record = _item(job_world)
    assert (applied.stopped, record.get("implement.stopped"), len(job_world.clock.waits)) == (
        (1,),
        "checks",
        60,
    )
    assert "did not finish in 1800 s" in job_world.issue_comments()[0]
    assert job_world.pull.ready_calls == []


def test_a_pull_request_that_never_shows_the_pushed_head_stops_the_item_after_the_reads(
    job_world: JobWorld,
) -> None:
    job_world.pull.stale = 100

    applied = job_world.run(two_groups())

    _, record = _item(job_world)
    assert (applied.stopped, record.get("implement.stopped"), len(job_world.clock.waits)) == (
        (1,),
        "checks",
        20,
    )
    assert "did not show the commit" in job_world.issue_comments()[0]


def test_a_check_that_does_not_settle_in_time_stops_the_item_with_no_fix_step(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[RUNNING]]
    script = two_groups(*a_fix())

    applied = job_world.run(script)

    assert (applied.stopped, len(script.seen)) == ((1,), 4)
    assert "did not finish in 1800 s" in job_world.issue_comments()[0]
    assert job_world.pull.ready_calls == []


def test_an_unresolved_review_thread_stops_the_item_with_no_fix_step(job_world: JobWorld) -> None:
    job_world.pull.threads(OPEN_THREAD)
    script = two_groups(*a_fix())

    applied = job_world.run(script)

    assert (applied.stopped, len(script.seen)) == ((1,), 4)
    assert "1 unresolved review thread(s)" in job_world.issue_comments()[0]
    assert job_world.pull.ready_calls == []


def test_a_merge_conflict_stops_the_item_with_no_fix_step(job_world: JobWorld) -> None:
    job_world.pull.conflict = True
    script = two_groups(*a_fix())

    applied = job_world.run(script)

    assert (applied.stopped, len(script.seen)) == ((1,), 4)
    assert "merge conflict" in job_world.issue_comments()[0]


def test_a_failed_ready_call_stops_the_item_at_ready_and_the_pull_request_stays_a_draft(
    job_world: JobWorld,
) -> None:
    job_world.programs.answer(
        lambda call: call.argv[1:3] == ("pr", "ready"),
        ProcessAnswer(returncode=1, stderr="GraphQL: resource not accessible\n"),
    )

    applied = job_world.run(two_groups())

    _, record = _item(job_world)
    assert (applied.stopped, record.get("implement.stopped")) == ((1,), "ready")
    assert "resource not accessible" in job_world.issue_comments()[0]
    assert job_world.repo.origin_git("log", "-1", "--format=%s", BRANCH) == (
        "docs(openspec): archive the change (#1)"
    )


def test_a_check_that_fails_twice_gets_two_fix_steps_and_then_passes(job_world: JobWorld) -> None:
    job_world.pull.runs = [[FAIL], [FAIL], [PASS]]
    script = two_groups(*_fix(1), *_fix(2))

    applied = job_world.run(script)

    assert (applied.ready, applied.stopped) == ((1,), ())
    assert job_world.origin_log()[-2:] == [f"Make check {CHECK} pass (#1)"] * 2
    assert len(script.seen) == 8


def test_each_repair_round_after_the_push_is_in_a_comment_on_the_pull_request(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[FAIL], [FAIL], [PASS]]

    job_world.run(two_groups(*_fix(1), *_fix(2)))

    comments = _comments(job_world)
    assert len(comments) == 3
    assert "- fix (" not in comments[0]
    for comment in comments[1:]:
        assert f"- fix (Make check {CHECK} pass): done" in comment
        assert "0 repair rounds" in comment
        assert "scoped check static: passed" in comment


def test_a_check_that_fails_in_every_round_stops_the_item_after_the_rounds(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[FAIL]]
    script = two_groups(*_fix(1), *_fix(2), *_fix(3))

    applied = job_world.run(script)

    status, record = _item(job_world)
    assert (applied.ready, applied.stopped, status, record.get("implement.stopped")) == (
        (),
        (1,),
        "Blocked",
        "checks",
    )
    assert len(script.seen) == 10
    assert job_world.pull.ready_calls == []
    assert f"The check {CHECK} failed." in job_world.issue_comments()[0]


def test_the_rounds_after_the_push_come_from_the_setting(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"repair_rounds": 0}})
    job_world.pull.runs = [[FAIL]]
    script = two_groups()

    applied = job_world.run(script)

    assert (applied.stopped, len(script.seen)) == ((1,), 4)
    assert job_world.origin_log()[-1] != f"Make check {CHECK} pass (#1)"

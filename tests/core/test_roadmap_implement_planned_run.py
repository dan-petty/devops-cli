"""`devops roadmap implement` runs a Planned item (#2714): the plan of its change is on `main`,
and its branch is gone. The job makes the branch at `main`, opens the draft pull request when the
branch first holds a commit, and then goes on as for a Staged item.

Git runs for real on a clone with an `origin`. The model is scripted. GitHub's REST API and `gh`
are faked at their edges.
"""

from __future__ import annotations

import subprocess

import pytest

from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stop_clear import clear_stops
from tests.support.fakes.github import github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.implement_step import command_text
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    ARCHIVE_COMMIT,
    BRANCH,
    CHANGE,
    PULL,
    TASKS_PATH,
    TICKED_FIRST,
    WORK_COMMIT,
    JobWorld,
    archive_effect,
    group_one_calls,
    group_two_calls,
    two_groups,
)
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

MARKER = "<!-- devops roadmap implement -->"


def _item(world: JobWorld, number: int = 1) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(number)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


def _on_origin(world: JobWorld) -> list[str]:
    return world.repo.origin_git("branch", "--format=%(refname:short)").split()


DELIVERY_TITLE = "fix(roadmap): The job keeps every comment."


def test_two_groups_make_a_new_branch_a_draft_and_a_closing_body(
    planned_world: JobWorld,
) -> None:
    applied = planned_world.run(two_groups())

    assert (applied.drafted, applied.stopped, applied.failed) == ((1,), (), ())
    assert planned_world.origin_log() == [WORK_COMMIT, ARCHIVE_COMMIT]
    (created,) = planned_world.sent("POST", "pulls")
    assert (created["draft"], created["head"], created["base"], created["title"]) == (
        True,
        BRANCH,
        "main",
        DELIVERY_TITLE,
    )
    assert created["body"].startswith("Closes #1")
    assert planned_world.sent("PATCH", f"pulls/{PULL}") == [
        {
            "title": DELIVERY_TITLE,
            "body": "The job drops the last comment of a thread (#1). It must keep it."
            f"\n\nCloses #1\n\nChange: `openspec/changes/archive/2026-10-29-{CHANGE}/`",
        }
    ]
    assert planned_world.pull.ready_calls == []
    status, record = _item(planned_world)
    assert (status, record["implement.branch"], record["implement.pr"]) == (
        "In Review",
        BRANCH,
        str(PULL),
    )


def _pushes(world: JobWorld) -> list[tuple[str, ...]]:
    """The words after `push` of each push of the job, which runs in the new repository of
    `publish` (#3702)."""
    return [
        call.argv[call.argv.index("push") + 1 :]
        for call in world.programs.calls
        if "push" in call.argv
    ]


def test_the_branch_is_published_once_and_the_clone_keeps_no_branch_or_worktree(
    planned_world: JobWorld,
) -> None:
    planned_world.run(two_groups())

    ref = f"refs/heads/{BRANCH}"
    # `publish` makes the branch with one push, with an empty lease: the branch must not exist.
    assert _pushes(planned_world) == [
        ("--quiet", f"--force-with-lease={ref}:", "origin", f"HEAD:{ref}")
    ]
    assert planned_world.repo.git("worktree", "list").count("\n") == 0
    assert planned_world.repo.git("branch", "--format=%(refname:short)") == "main"


def test_the_final_push_of_the_new_branch_carries_a_lease(planned_world: JobWorld) -> None:
    applied = planned_world.run(two_groups())

    pushes = _pushes(planned_world)
    ref = f"refs/heads/{BRANCH}"
    # One push, with a lease that says the branch must not exist yet (#3702).
    assert (applied.drafted, len(pushes)) == ((1,), 1)
    assert pushes[0][1] == f"--force-with-lease={ref}:"
    assert len(planned_world.sent("POST", "pulls")) == 1


def test_a_group_that_is_ticked_on_main_is_not_run_again(planned_world: JobWorld) -> None:
    (planned_world.repo.clone / TASKS_PATH).write_text(TICKED_FIRST, encoding="utf-8")
    planned_world.repo.git("add", "-A")
    planned_world.repo.git("commit", "-q", "-m", "main ticks group 1")
    planned_world.repo.git("push", "-q", "origin", "main")
    script = ModelScript(tool_calls(*group_two_calls()), say("Group 2 is done."))

    applied = planned_world.run(script)

    assert (applied.drafted, len(script.seen)) == ((1,), 2)
    assert planned_world.origin_log() == [WORK_COMMIT, ARCHIVE_COMMIT]


def test_a_stop_before_the_first_commit_pushes_nothing_and_opens_no_pull_request(
    planned_world: JobWorld,
) -> None:
    applied = planned_world.run(ModelScript(say("I could not do group 1.")))

    status, record = _item(planned_world)
    assert (applied.stopped, status, record.get("implement.stopped")) == (
        (1,),
        "Blocked",
        "group 1",
    )
    assert _on_origin(planned_world) == ["main"]
    assert planned_world.sent("POST", "pulls") == []
    assert record.get("implement.pr") is None
    assert "Stopped at group 1." in planned_world.issue_comments()[-1]


def test_a_stop_after_a_commit_pushes_the_branch_and_opens_a_draft_that_closes_its_issue(
    planned_world: JobWorld,
) -> None:
    script = ModelScript(tool_calls(*group_one_calls()), say("Done."), say("Stuck."))

    planned_world.run(script)

    (created,) = planned_world.sent("POST", "pulls")
    status, record = _item(planned_world)
    assert planned_world.origin_log() == [WORK_COMMIT]
    assert (created["draft"], created["body"].startswith("Closes #1")) == (True, True)
    assert (status, record["implement.stopped"], record["implement.pr"]) == (
        "Blocked",
        "group 2",
        str(PULL),
    )
    assert planned_world.sent("PATCH", f"pulls/{PULL}") == []
    assert planned_world.pull.ready_calls == []


def test_a_retry_takes_over_the_branch_and_the_draft_that_the_stop_left(
    planned_world: JobWorld,
) -> None:
    planned_world.run(ModelScript(tool_calls(*group_one_calls()), say("Done."), say("Stuck.")))
    planned_world.store.seed_comment(1, "implement: retry", author_association="OWNER")
    cleared = clear_stops(
        planned_world.store, planned=PlannedChanges("main", {}, {}), digest=lambda: None
    )
    script = ModelScript(tool_calls(*group_two_calls()), say("Group 2 is done."))

    applied = planned_world.run(script)

    status, record = _item(planned_world)
    assert (cleared.cleared, applied.drafted, status, record.get("implement.stopped")) == (
        (1,),
        (1,),
        "In Review",
        None,
    )
    assert planned_world.origin_log() == [WORK_COMMIT, ARCHIVE_COMMIT]
    assert len(planned_world.sent("POST", "pulls")) == 1
    assert len(script.seen) == 2


def test_a_draft_that_github_refuses_takes_the_branch_off_origin_and_stops_the_item(
    planned_world: JobWorld,
) -> None:
    planned_world.api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json({"message": "Validation Failed"}, status=422),
    )

    applied = planned_world.run(two_groups())

    status, record = _item(planned_world)
    assert (applied.stopped, status, record.get("implement.stopped")) == ((1,), "Blocked", "push")
    assert _on_origin(planned_world) == ["main"]
    assert record.get("implement.pr") is None
    assert "did not open the draft pull request" in planned_world.issue_comments()[0]
    assert planned_world.repo.git("worktree", "list").count("\n") == 0


def test_a_failed_archive_stops_a_planned_item_and_pushes_what_passed(
    planned_world: JobWorld,
) -> None:
    planned_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(returncode=1, stderr="openspec: the change has no delta\n"),
    )

    applied = planned_world.run(two_groups())

    _, record = _item(planned_world)
    assert (applied.stopped, record.get("implement.stopped")) == ((1,), "archive")
    assert len(planned_world.sent("POST", "pulls")) == 1
    # The work commit holds the groups and the documents, and no archive commit follows (#3702).
    assert planned_world.origin_log() == [WORK_COMMIT]


def test_the_plan_alone_runs_nothing_for_a_planned_item(planned_world: JobWorld) -> None:
    plan = planned_world.plan()

    assert [(t.item.number, t.branch, t.pull) for t in plan.selected] == [(1, BRANCH, None)]
    assert _on_origin(planned_world) == ["main"]
    assert planned_world.sent("POST", "pulls") == []
    assert _item(planned_world)[0] == "Ready"


def test_a_why_of_the_whole_body_limit_is_kept(planned_world: JobWorld) -> None:
    why = "A reason that is kept. " * 43
    assert len(why) == 989

    def archive_with_why(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        done = archive_effect(call)
        assert call.cwd is not None
        change = command_text(call).split()[-1]
        proposal = call.cwd / "openspec/changes/archive" / f"2026-10-29-{change}" / "proposal.md"
        text = proposal.read_text(encoding="utf-8")
        proposal.write_text(
            text.replace("The job drops the last comment of a thread (#1). It must keep it.", why),
            encoding="utf-8",
        )
        return done

    planned_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(side_effect=archive_with_why),
    )
    planned_world.run(two_groups())

    (patched,) = planned_world.sent("PATCH", f"pulls/{PULL}")
    assert patched["body"].startswith(f"{why.strip()}\n\nCloses #1")

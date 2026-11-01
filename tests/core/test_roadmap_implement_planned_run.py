"""`devops roadmap implement` runs a Planned item (#2714): the plan of its change is on `main`,
and its branch is gone. The job makes the branch at `main`, opens the draft pull request when the
branch first holds a commit, and then goes on as for a Staged item.

Git runs for real on a clone with an `origin`. The model is scripted. GitHub's REST API and `gh`
are faked at their edges.
"""

from __future__ import annotations

import pytest

from tests.support.fakes.github import github_json
from tests.support.fakes.process import ProcessAnswer
from tests.support.implement_step import command_text
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    CHANGE,
    FAIL,
    PASS,
    PULL,
    TASKS_PATH,
    TICKED_FIRST,
    TITLE,
    JobWorld,
    a_fix,
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


def test_two_groups_make_a_new_branch_a_draft_a_closing_body_and_a_ready_pull_request(
    planned_world: JobWorld,
) -> None:
    applied = planned_world.run(two_groups())

    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    assert planned_world.origin_log() == [
        "The first group (#1)",
        "The second group (#1)",
        "docs: regenerate the documentation (#1)",
        "docs(openspec): archive the change (#1)",
    ]
    (created,) = planned_world.sent("POST", "pulls")
    assert (created["draft"], created["head"], created["base"], created["title"]) == (
        True,
        BRANCH,
        "main",
        TITLE,
    )
    assert "Closes" not in created["body"]
    assert planned_world.sent("PATCH", f"pulls/{PULL}") == [
        {
            "title": TITLE,
            "body": "Closes #1\n\nThe job drops the last comment of a thread (#1). It must keep it."
            f"\n\nChange: `openspec/changes/archive/2026-10-29-{CHANGE}/`",
        }
    ]
    assert planned_world.pull.ready_calls == [("pr", "ready", str(PULL), "--repo", STAGE_REPO)]
    status, record = _item(planned_world)
    assert (status, record["implement.branch"], record["implement.pr"]) == (
        "In Review",
        BRANCH,
        str(PULL),
    )


def test_the_branch_is_pushed_once_with_upstream_and_the_clone_keeps_no_branch_or_worktree(
    planned_world: JobWorld,
) -> None:
    planned_world.run(two_groups())

    pushes = [call.argv[4:] for call in planned_world.programs.calls if call.argv[3:4] == ("push",)]
    assert pushes == [("-u", "origin", BRANCH)]
    assert planned_world.repo.git("worktree", "list").count("\n") == 0
    assert planned_world.repo.git("branch", "--format=%(refname:short)") == "main"


def test_a_check_that_fails_once_gets_a_fix_step_and_a_push_with_a_lease_on_the_new_branch(
    planned_world: JobWorld,
) -> None:
    planned_world.pull.runs = [[FAIL], [PASS]]

    applied = planned_world.run(two_groups(*a_fix()))

    pushes = [call.argv[4:] for call in planned_world.programs.calls if call.argv[3:4] == ("push",)]
    first_tip = planned_world.repo.origin_git("rev-parse", f"{BRANCH}~1")
    assert (applied.ready, len(pushes)) == ((1,), 2)
    assert pushes[0] == ("-u", "origin", BRANCH)
    assert pushes[1] == (f"--force-with-lease={BRANCH}:{first_tip}", "origin", BRANCH)
    assert len(planned_world.sent("POST", "pulls")) == 1


def test_a_group_that_is_ticked_on_main_is_not_run_again(planned_world: JobWorld) -> None:
    (planned_world.repo.clone / TASKS_PATH).write_text(TICKED_FIRST, encoding="utf-8")
    planned_world.repo.git("add", "-A")
    planned_world.repo.git("commit", "-q", "-m", "main ticks group 1")
    planned_world.repo.git("push", "-q", "origin", "main")
    script = ModelScript(tool_calls(*group_two_calls()), say("Group 2 is done."))

    applied = planned_world.run(script)

    assert (applied.ready, len(script.seen)) == ((1,), 2)
    assert planned_world.origin_log()[0] == "The second group (#1)"


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
    assert "Stopped at group 1." in planned_world.issue_comments()[0]


def test_a_stop_after_a_commit_pushes_the_branch_and_opens_a_draft_that_closes_nothing(
    planned_world: JobWorld,
) -> None:
    script = ModelScript(tool_calls(*group_one_calls()), say("Done."), say("Stuck."))

    planned_world.run(script)

    (created,) = planned_world.sent("POST", "pulls")
    status, record = _item(planned_world)
    assert planned_world.origin_log() == ["The first group (#1)"]
    assert (created["draft"], "Closes" in created["body"]) == (True, False)
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
    script = ModelScript(tool_calls(*group_two_calls()), say("Group 2 is done."))

    applied = planned_world.run(script)

    status, record = _item(planned_world)
    assert (applied.ready, status, record.get("implement.stopped")) == ((1,), "In Review", None)
    assert planned_world.origin_log() == [
        "The first group (#1)",
        "The second group (#1)",
        "docs: regenerate the documentation (#1)",
        "docs(openspec): archive the change (#1)",
    ]
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
    assert planned_world.origin_log() == [
        "The first group (#1)",
        "The second group (#1)",
        "docs: regenerate the documentation (#1)",
    ]


def test_the_plan_alone_runs_nothing_for_a_planned_item(planned_world: JobWorld) -> None:
    plan = planned_world.plan()

    assert [(t.item.number, t.branch, t.pull) for t in plan.selected] == [(1, BRANCH, None)]
    assert _on_origin(planned_world) == ["main"]
    assert planned_world.sent("POST", "pulls") == []
    assert _item(planned_world)[0] == "Ready"

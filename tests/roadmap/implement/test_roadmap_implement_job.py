"""`devops roadmap implement` as a job: the run of a Staged item from the first group to a ready
pull request, and every way it stops (#2665).

Git runs for real on a clone with an `origin`. The model is scripted, so the steps are real: they
write files in the worktree, and their exit checks run through the process edge. GitHub's REST API
and `gh` are faked at their edges.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from markdown_it import MarkdownIt
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.config import constants
from devops_cli.exceptions import RoadmapImplementError
from devops_cli.git.worktree_add import worktree_directory
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.roadmap.implement.implement import (
    ImplementPlan,
    parse_implement_filters,
    plan_implement,
)
from devops_cli.roadmap.implement.implement_run import apply_implement, raise_for_failed
from devops_cli.roadmap.pull_form import body_problems
from devops_cli.roadmap.stage.stage_change import closing_keyword_in
from devops_cli.roadmap.stores.store import ImplementRecordKey
from tests.support.base_replay import (
    BEHAVIOR_FIRST_TICKED,
    BEHAVIOR_TASKS,
    BEHAVIOR_TICKED,
    SHOUT_TEST_ID,
    answer_pytest_on_base,
    junit,
)
from tests.support.fakes.github import GitHubApiFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import TEST_BODY, WINDOW, command_text, write_call
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    CHANGE,
    PULL,
    SHOUT,
    TASKS,
    TASKS_PATH,
    TICKED_FIRST,
    JobWorld,
    archive_effect,
    branch_of,
    docs_effect,
    group_one_calls,
    group_two_calls,
    merge_plan,
    move_main_when,
    push_staged_branch,
    route_pull_status,
    seed_staged,
    two_groups,
)
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

MARKER = "<!-- devops roadmap implement -->"


def _item(world: JobWorld, number: int = 1) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(number)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


# ── The refusal ───────────────────────────────────────────────────────────────────────────


def test_the_job_runs_no_step_unless_it_is_in_a_runner(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"in_runner": False}})
    script = two_groups()
    plan = job_world.plan()
    calls_before = len(job_world.programs.calls)
    requests_before = list(job_world.api.requested)

    with pytest.raises(RoadmapImplementError) as raised:
        apply_implement(
            job_world.store,
            plan,
            source=job_world.repo.clone,
            model=script.model(),
            window=WINDOW,
        )

    assert "roadmap.implement.in_runner" in str(raised.value)
    assert (
        script.seen,
        len(job_world.programs.calls) - calls_before,
        job_world.api.requested,
        _item(job_world),
    )[0:3] == ([], 0, requests_before)
    assert job_world.origin_log() == ["fix(roadmap): plan"]


def test_the_job_refuses_a_token_that_is_not_scoped_to_the_repository_of_the_plan(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    """A Job made by `devops k8s run-job` sets no token repository, so its installation token
    would cover every repository of the App: the job runs no step then (#2667)."""
    config(service={"github_app": {"token_repository": "example/other"}})
    plan = job_world.plan()
    requests_before = list(job_world.api.requested)
    script = two_groups()

    with pytest.raises(RoadmapImplementError) as raised:
        apply_implement(
            job_world.store,
            plan,
            source=job_world.repo.clone,
            model=script.model(),
            window=WINDOW,
        )

    assert "example/other" in str(raised.value)
    assert (script.seen, job_world.api.requested) == ([], requests_before)
    assert job_world.origin_log() == ["fix(roadmap): plan"]


def test_the_job_refuses_a_token_with_no_repository_scope(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(service={"github_app": {"token_repository": None}})

    with pytest.raises(RoadmapImplementError) as raised:
        job_world.run(two_groups())

    assert "service.github_app.token_repository" in str(raised.value)


def test_the_job_refuses_to_run_when_it_does_not_act_as_the_app(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the App's key the token is the person's `gh` login, which no setting can scope."""
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_run.acts_as_github_app", lambda: False
    )

    with pytest.raises(RoadmapImplementError) as raised:
        job_world.run(two_groups())

    assert "GitHub App" in str(raised.value)


def test_the_job_checks_the_token_scope_before_it_clears_its_dumpable_flag(
    job_world: JobWorld, config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config(service={"github_app": {"token_repository": None}})
    seen: list[str] = []
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_run.deny_environment_reads",
        lambda: seen.append("called"),
    )

    with pytest.raises(RoadmapImplementError) as raised:
        job_world.run(two_groups())
    assert raised.value.error_code == "ROADMAP_IMPLEMENT_REFUSED"

    assert seen == []


# ── The run to a ready pull request ───────────────────────────────────────────────────────


def test_the_job_makes_its_process_unreadable_before_it_does_any_work(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A step runs as the same user as the job, so the job clears its dumpable flag first, and
    only in a runner (#2667). The spy replaces the kernel call, which would change the test run."""
    seen: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_run.deny_environment_reads",
        lambda: seen.append((len(job_world.api.requested), len(job_world.programs.calls))),
    )
    plan = job_world.plan()
    before = (len(job_world.api.requested), len(job_world.programs.calls))

    applied = apply_implement(
        job_world.store,
        plan,
        source=job_world.repo.clone,
        model=two_groups().model(),
        window=WINDOW,
    )

    assert (seen, applied.ready) == ([before], (1,))


def test_the_job_runs_no_step_when_the_kernel_refuses_to_clear_the_flag(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`apply_implement` itself refuses, not only the function it calls: a step that could read
    the environment of the job must never start (#2667)."""
    monkeypatch.setattr("devops_cli.core.process_hardening._prctl", lambda *_args: -1)
    script = two_groups()
    plan = job_world.plan()
    calls_before = len(job_world.programs.calls)

    with pytest.raises(RoadmapImplementError, match="PR_SET_DUMPABLE"):
        apply_implement(
            job_world.store,
            plan,
            source=job_world.repo.clone,
            model=script.model(),
            window=WINDOW,
        )

    assert (script.seen, len(job_world.programs.calls) - calls_before) == ([], 0)
    assert job_world.origin_log() == ["fix(roadmap): plan"]


def test_a_job_outside_a_runner_does_not_touch_its_process(
    job_world: JobWorld, config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config(roadmap={"implement": {"in_runner": False}})
    seen: list[str] = []
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_run.deny_environment_reads",
        lambda: seen.append("called"),
    )

    with pytest.raises(RoadmapImplementError) as raised:
        job_world.run(two_groups())
    assert raised.value.error_code == "ROADMAP_IMPLEMENT_REFUSED"

    assert seen == []


def test_two_groups_end_in_commits_a_pushed_branch_a_closing_body_and_a_ready_pull_request(
    job_world: JobWorld,
) -> None:
    applied = job_world.run(two_groups())

    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    assert job_world.origin_log() == [
        "fix(roadmap): plan",
        "fix(roadmap): The first group (#1)",
        "fix(roadmap): The second group (#1)",
        "docs: regenerate the documentation (#1)",
        "docs(openspec): archive the change (#1)",
    ]
    assert job_world.sent("PATCH", f"pulls/{PULL}") == [
        {
            "title": "fix(roadmap): the job drops a comment",
            "body": "The job drops the last comment of a thread (#1). It must keep it."
            f"\n\nCloses #1\n\nChange: `openspec/changes/archive/2026-10-29-{CHANGE}/`",
        }
    ]
    assert job_world.pull.ready_calls == [("pr", "ready", str(PULL), "--repo", STAGE_REPO)]
    status, record = _item(job_world)
    assert (status, record["implement.pr"], record.get("implement.stopped")) == (
        "In Review",
        str(PULL),
        None,
    )


def _rewrite_why(job_world: JobWorld, why: str) -> None:
    """Make the archive step leave `why` as the "Why" of the archived proposal."""

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

    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(side_effect=archive_with_why),
    )


def test_the_body_of_the_pull_request_passes_the_form_check(job_world: JobWorld) -> None:
    """The body is the text, `Closes`, then the `Change:` line (#3215)."""
    job_world.run(two_groups())

    (patched,) = job_world.sent("PATCH", f"pulls/{PULL}")
    assert body_problems(patched["body"]) == []
    assert patched["body"].index("Closes #1") < patched["body"].index("Change:")


def test_a_why_that_does_not_fit_the_body_limit_gives_way_to_the_issue_title_and_is_not_cut(
    job_world: JobWorld,
) -> None:
    _rewrite_why(job_world, "The job keeps a long reason. " * 60)

    job_world.run(two_groups())

    (patched,) = job_world.sent("PATCH", f"pulls/{PULL}")
    assert patched["body"].startswith("fix(roadmap): the job drops a comment\n\nCloses #1")
    assert "..." not in patched["body"]
    assert body_problems(patched["body"]) == []


def test_a_body_that_the_form_check_refuses_stops_the_item_before_the_job_writes_it(
    job_world: JobWorld,
) -> None:
    """A why that holds a closing keyword gives way to the title of the issue. A title that is a
    placeholder then fails `build_body`, and the job writes no body."""
    _rewrite_why(job_world, "This work closes #9 when it merges.")
    issue = job_world.store._roadmap.issues[1]
    job_world.store._roadmap.issues[1] = issue.model_copy(update={"title": "fix(roadmap): x"})

    applied = job_world.run(two_groups())

    status, record = _item(job_world)
    assert (applied.stopped, status, record.get("implement.stopped")) == (
        (1,),
        "Blocked",
        "pull request",
    )
    assert job_world.sent("PATCH", f"pulls/{PULL}") == []
    assert "does not pass the form check" in job_world.issue_comments()[0]


def test_the_title_of_the_pull_request_has_no_scope_that_the_labels_file_lacks(
    job_world: JobWorld,
) -> None:
    """The `Semantic PR title` check refuses an undeclared scope (#2800), and the title of the
    issue may hold one."""
    job_world.store.seed_file(".github/labels.yml", "- name: type/bug\n  color: D73A4A\n")

    job_world.run(two_groups())

    (patched,) = job_world.sent("PATCH", f"pulls/{PULL}")
    assert patched["title"] == "fix: the job drops a comment"


def test_a_title_that_the_check_refuses_stops_the_item_before_the_job_writes_it(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The job keeps the whole summary of the issue (#3200), and the check limits the summary to
    60 UTF-16 units (#3292). A long summary stops the item, so no title reaches the check."""
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_run.delivery_title", lambda *_args: "Add a flag: "
    )

    applied = job_world.run(two_groups())

    status, record = _item(job_world)
    assert (applied.stopped, status, record.get("implement.stopped")) == (
        (1,),
        "Blocked",
        "pull request",
    )
    assert job_world.sent("PATCH", f"pulls/{PULL}") == []
    assert "not in the form" in job_world.issue_comments()[0]


def test_a_title_with_a_type_that_the_project_does_not_declare_stops_the_item(
    job_world: JobWorld,
) -> None:
    """A person may edit the issue title after staging (#3368). The implement job reads the title
    again when it publishes, and a type the project does not declare fails the check
    `Semantic PR title`, so the job stops before it writes the title."""
    issue = job_world.store._roadmap.issues[1]
    job_world.store._roadmap.issues[1] = issue.model_copy(update={"title": "wip(cli): add a flag"})

    applied = job_world.run(two_groups())

    status, record = _item(job_world)
    assert (applied.stopped, status, record.get("implement.stopped")) == (
        (1,),
        "Blocked",
        "pull request",
    )
    assert job_world.sent("PATCH", f"pulls/{PULL}") == []
    comment = job_world.issue_comments()[0]
    assert "The type `wip` is not a type of the project" in comment
    assert "The title is `wip(cli): add a flag`." in comment


def test_a_planned_item_with_a_title_that_has_no_type_stops_before_the_first_push(
    planned_world: JobWorld,
) -> None:
    """A person may edit the issue title after the plan reads it (#3368). The delivery title of a
    Planned item must pass the check before the first push, so a title with no Conventional Commit
    type stops the item before any branch reaches `origin` and no draft pull request exists."""
    plan = planned_world.plan()
    (target,) = plan.selected
    edited = replace(
        plan,
        selected=(replace(target, item=target.item.model_copy(update={"title": "Add a flag"})),),
    )

    applied = apply_implement(
        planned_world.store,
        edited,
        source=planned_world.repo.clone,
        model=two_groups().model(),
        window=WINDOW,
    )

    status, record = _item(planned_world)
    assert (applied.stopped, status, record.get("implement.stopped")) == (
        (1,),
        "Blocked",
        "push",
    )
    assert planned_world.repo.origin_git("branch", "--list", BRANCH) == ""
    assert not any(request.method == "POST" for request in planned_world.api.sent)
    comment = planned_world.issue_comments()[0]
    assert "not in the form" in comment
    assert "The title is `Add a flag: `." in comment


def test_the_changes_of_the_archive_and_the_documents_are_in_the_pushed_tree(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    tree = job_world.repo.origin_git("ls-tree", "-r", "--name-only", BRANCH).split()
    context = job_world.repo.origin_git("show", f"{BRANCH}:CONTEXT.md")
    assert "upper-cases" in context
    assert [
        name for name in tree if name.startswith("openspec/changes") or name.startswith("docs/")
    ] == [
        "docs/GENERATED.md",
        f"openspec/changes/archive/2026-10-29-{CHANGE}/.openspec.yaml",
        f"openspec/changes/archive/2026-10-29-{CHANGE}/design.md",
        f"openspec/changes/archive/2026-10-29-{CHANGE}/proposal.md",
        f"openspec/changes/archive/2026-10-29-{CHANGE}/tasks.md",
    ]


def test_the_outcome_of_each_step_is_one_comment_on_the_pull_request_and_not_in_its_body(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    comments = job_world.sent("POST", f"issues/{PULL}/comments")
    assert len(comments) == 1
    body = comments[0]["body"]
    assert body.startswith(MARKER)
    assert "| group 1 | done |" in body
    assert "| group 2 | done |" in body
    assert "Group 1 is done" not in job_world.sent("PATCH", f"pulls/{PULL}")[0]["body"]


def test_the_issue_gets_one_comment_with_the_pull_request_and_the_spend(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    comments = job_world.issue_comments()
    assert len(comments) == 1
    assert comments[0].startswith(MARKER)
    assert f"Pull request #{PULL} is ready for review." in comments[0]
    assert "4 model requests" in comments[0]


def test_the_record_keeps_the_last_group_the_last_commit_and_the_spend_of_every_step(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    _, record = _item(job_world)
    tip = job_world.repo.origin_git("rev-parse", BRANCH)
    spend = json.loads(record["implement.spend"] or "{}")
    assert (record["implement.group"], record["implement.sha"], spend["requests"]) == (
        "2",
        tip,
        4,
    )
    assert spend["input_tokens"] > 0


def test_the_record_of_a_staged_item_keeps_its_branch_and_its_pull_request(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    _, record = _item(job_world)
    assert (record["implement.branch"], record["implement.pr"]) == (BRANCH, str(PULL))


def test_the_push_runs_in_the_worktree_with_a_lease_and_leaves_no_worktree_behind(
    job_world: JobWorld,
) -> None:
    before = job_world.repo.origin_git("rev-parse", BRANCH)
    job_world.run(two_groups())

    pushes = [call for call in job_world.programs.calls if call.argv[3:4] == ("push",)]
    tip = job_world.repo.origin_git("rev-parse", BRANCH)
    assert len(pushes) == 1
    assert pushes[0].argv[1] == "-C"
    assert pushes[0].argv[2] != str(job_world.repo.clone)
    assert pushes[0].argv[4:] == (f"--force-with-lease={BRANCH}:{before}", "origin", BRANCH)
    assert tip != before
    assert job_world.repo.git("branch", "--show-current") == "main"
    assert job_world.repo.git("worktree", "list").count("\n") == 0
    assert job_world.repo.git("branch", "--format=%(refname:short)") == "main"


def test_a_group_whose_tasks_are_ticked_on_the_branch_is_not_run_again(
    job_world: JobWorld,
) -> None:
    job_world.repo.git("fetch", "-q", "origin", BRANCH)
    job_world.repo.git("switch", "-q", "-c", "tmp", f"origin/{BRANCH}")
    (job_world.repo.clone / TASKS_PATH).write_text(TICKED_FIRST, encoding="utf-8")
    job_world.repo.git("add", "-A")
    job_world.repo.git(
        "-c",
        "user.name=devops-roadmap[bot]",
        "commit",
        "-q",
        "-m",
        "fix(roadmap): The first group (#1)",
    )
    job_world.repo.git("push", "-q", "origin", f"tmp:{BRANCH}")
    job_world.repo.git("switch", "-q", "main")
    job_world.repo.git("branch", "-q", "-D", "tmp")
    script = ModelScript(tool_calls(*group_two_calls()), say("Group 2 is done."))

    applied = job_world.run(script)

    assert (applied.ready, len(script.seen)) == ((1,), 2)
    assert job_world.origin_log()[:3] == [
        "fix(roadmap): plan",
        "fix(roadmap): The first group (#1)",
        "fix(roadmap): The second group (#1)",
    ]


def test_the_documentation_commit_is_skipped_when_the_generator_changes_nothing(
    job_world: JobWorld,
) -> None:
    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        ProcessAnswer(),
    )

    job_world.run(two_groups())

    assert "docs: regenerate the documentation (#1)" not in job_world.origin_log()


def test_the_documentation_and_the_archive_run_in_the_worktree_after_the_last_group(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    uv = [call for call in job_world.programs.calls if call.argv[0] == "uv"]
    commands = [command_text(call) for call in uv]
    docs = commands.index("uv run devops docs generate --sync-readme")
    archive = commands.index(f"uv run devops openspec archive {CHANGE}")
    assert (
        docs < archive,
        uv[docs].cwd == uv[archive].cwd,
        uv[docs].cwd != job_world.repo.clone,
    ) == (
        True,
        True,
        True,
    )


def test_a_retry_clears_the_stop_before_the_first_step(job_world: JobWorld) -> None:
    item = job_world.store.item(1)
    assert item is not None
    job_world.store.set_marks(item, {ImplementRecordKey.STOPPED: "group 2"})
    job_world.store.comment(1, f"{MARKER}\nStopped at group 2.")
    job_world.store.seed_comment(1, "implement: retry", author_association="OWNER")

    applied = job_world.run(two_groups())

    status, record = _item(job_world)
    assert (applied.ready, status, record.get("implement.stopped")) == ((1,), "In Review", None)


# ── The stops ─────────────────────────────────────────────────────────────────────────────


def test_a_step_that_stops_blocks_the_item_with_a_comment_and_a_record(
    job_world: JobWorld,
) -> None:
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        say("I could not do group 2."),
    )

    applied = job_world.run(script)

    status, record = _item(job_world)
    comments = job_world.issue_comments()
    assert (applied.ready, applied.stopped, status, record.get("implement.stopped")) == (
        (),
        (1,),
        "Blocked",
        "group 2",
    )
    assert len(comments) == 1
    assert comments[0].startswith(MARKER)
    assert "Stopped at group 2." in comments[0]
    assert "The agent changed no file." in comments[0]
    assert "I could not do group 2." in comments[0]
    assert "The job discarded" not in comments[0]
    assert "implement: retry" in comments[0]


def test_the_stop_comment_names_the_failure_class_the_action_taken_and_the_action_left(
    job_world: JobWorld,
) -> None:
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        say("I could not do group 2."),
    )

    job_world.run(script)

    (comment,) = job_world.issue_comments()
    _, record = _item(job_world)
    assert "Failure class: `plan_defect`.\nAction taken: none.\nAction left: `amend`:" in comment
    assert comment.index("Failure class") < comment.index("Reason:")
    assert record.get("implement.failure") == "plan_defect"


def test_the_trace_holds_the_class_and_the_action_left_of_a_stop(
    job_world: JobWorld, capsys: pytest.CaptureFixture[str]
) -> None:
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        say("I could not do group 2."),
    )

    job_world.run(script)

    captured = capsys.readouterr()
    assert "Failure class plan_defect. Action left: amend." in captured.out + captured.err


def test_a_retry_clears_the_failure_class_with_the_stop(job_world: JobWorld) -> None:
    item = job_world.store.item(1)
    assert item is not None
    job_world.store.set_marks(
        item, {ImplementRecordKey.STOPPED: "group 2", ImplementRecordKey.FAILURE: "types"}
    )
    job_world.store.comment(1, f"{MARKER}\nStopped at group 2.")
    job_world.store.seed_comment(1, "implement: retry", author_association="OWNER")

    job_world.run(two_groups())

    _, record = _item(job_world)
    assert record.get("implement.failure") is None


TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
DIFF_TEXT = f"A note with a secret {TOKEN}\n```\nand a line that tries to close the block\n```\n"


def _stop_with_a_dangerous_diff(job_world: JobWorld) -> str:
    """Run the job to the stop of group 2, which writes `DIFF_TEXT` and ticks nothing."""
    write = ("write_file", {"path": "CONTEXT.md", "content": DIFF_TEXT})
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(write),
        ModelAPIError("example-model", "The provider broke."),
    )
    job_world.run(script)
    comments = job_world.issue_comments()
    assert len(comments) == 1
    return comments[0]


def test_the_stop_comment_holds_the_masked_diff_of_the_discarded_work_in_one_fenced_block(
    job_world: JobWorld,
) -> None:
    comment = _stop_with_a_dangerous_diff(job_world)

    tokens = MarkdownIt("commonmark").parse(comment)
    fences = [token for token in tokens if token.type == "fence"]
    text_after = [
        token.content
        for token in tokens[tokens.index(fences[0]) :]
        if token.type == "inline" and "The item is Blocked" in token.content
    ]
    assert (TOKEN in comment, len(fences), text_after != []) == (False, 1, True)
    assert fences[0].info == "diff"
    assert fences[0].markup == "````"
    assert "+A note with a secret <masked-github-token>\n+```\n" in fences[0].content
    assert "+and a line that tries to close the block\n+```\n" in fences[0].content
    assert "diff --git a/CONTEXT.md b/CONTEXT.md" in fences[0].content


def test_the_stop_comment_says_that_the_job_discarded_the_work_and_how_much_it_shows(
    job_world: JobWorld,
) -> None:
    comment = _stop_with_a_dangerous_diff(job_world)

    assert "The job discarded this work. Read it before you retry:" in comment


def test_the_stop_comment_of_a_cut_diff_says_that_it_is_cut(job_world: JobWorld) -> None:
    cut = constants.CONST_ROADMAP_IMPLEMENT_DIFF_CHARS
    long_note = ("write_file", {"path": "CONTEXT.md", "content": "y" * 3 * cut + "\n"})
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(long_note),
        ModelAPIError("example-model", "The provider broke."),
    )

    job_world.run(script)

    comment = job_world.issue_comments()[0]
    assert f"The job discarded this work. The diff is cut to {cut} characters. Read it" in comment
    assert len(comment) < 2 * cut


def test_the_stop_comment_of_a_failed_model_call_holds_the_diff_of_the_discarded_work(
    job_world: JobWorld,
) -> None:
    write = ("write_file", {"path": "CONTEXT.md", "content": "A note.\n"})
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(write),
        ModelAPIError("example-model", "The provider broke."),
    )

    applied = job_world.run(script)

    comment = job_world.issue_comments()[0]
    assert (applied.stopped, applied.failed) == ((1,), ())
    assert "Stopped at group 2." in comment
    assert "ModelAPIError: model example-model" in comment
    assert "+A note." in comment
    assert "The job discarded this work." in comment


def test_a_refused_key_stops_the_whole_run_and_not_only_the_item(job_world: JobWorld) -> None:
    script = ModelScript(
        tool_calls(*group_one_calls()), ModelHTTPError(401, "example-model", {"error": "no"})
    )

    with pytest.raises(AICredentialsError) as raised:
        job_world.run(script)
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"

    assert job_world.issue_comments() == []


def test_the_stop_comment_cuts_a_reason_that_is_too_long(job_world: JobWorld) -> None:
    """GitHub refuses a comment of more than 65,536 characters, and the comment would be lost."""
    long_output = "E" * (2 * constants.CONST_ROADMAP_IMPLEMENT_REASON_CHARS)
    job_world.programs.answer(
        lambda call: command_text(call) == "uv run devops docs check",
        ProcessAnswer(returncode=1, stdout=long_output),
    )
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(*group_two_calls(TICKED_FIRST)),
        say("Wrote the note."),
    )

    job_world.run(script)

    comment = job_world.issue_comments()[0]
    reason = comment.partition("Reason:\n\n")[2].partition("\n\nLast message")[0]
    assert reason.strip().startswith("uv run devops docs check exited with status 1.")
    assert reason.count("E") < 2 * constants.CONST_ROADMAP_IMPLEMENT_REASON_CHARS
    assert len(comment) < 65_536


def test_a_stop_pushes_the_commits_of_the_steps_that_passed_and_leaves_the_draft(
    job_world: JobWorld,
) -> None:
    script = ModelScript(tool_calls(*group_one_calls()), say("Done."), say("Stuck."))

    job_world.run(script)

    assert job_world.origin_log() == ["fix(roadmap): plan", "fix(roadmap): The first group (#1)"]
    assert job_world.pull.ready_calls == []
    assert job_world.sent("PATCH", f"pulls/{PULL}") == []
    _, record = _item(job_world)
    assert record["implement.group"] == "1"


def test_a_stop_after_the_first_group_of_a_planned_item_leaves_a_draft_that_closes_its_issue(
    planned_world: JobWorld,
) -> None:
    """The draft that `_publish` opens carries the closing keyword of the delivered issue (#3273).
    The stop never reaches the body of the final step, so the draft body is the last body, and
    `devops pr check-readiness` must not call the pull request ungrounded."""
    script = ModelScript(tool_calls(*group_one_calls()), say("Done."), say("Stuck."))

    planned_world.run(script)

    (opened,) = planned_world.sent("POST", "pulls")
    assert closing_keyword_in(opened["body"]) == "closes"
    assert opened["body"].count(f"#{planned_world.number}") == 1
    assert planned_world.sent("PATCH", f"pulls/{PULL}") == []


def test_a_conflict_on_the_rebase_stops_the_item_before_any_step(job_world: JobWorld) -> None:
    clone = job_world.repo.clone
    folder = clone / "openspec" / "changes" / CHANGE
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "tasks.md").write_text("A different file.\n", encoding="utf-8")
    job_world.repo.git("add", "-A")
    job_world.repo.git("commit", "-q", "-m", "main also adds the tasks")
    job_world.repo.git("push", "-q", "origin", "main")
    script = two_groups()

    applied = job_world.run(script)

    status, record = _item(job_world)
    assert (applied.stopped, status, record.get("implement.stopped"), script.seen) == (
        (1,),
        "Blocked",
        "rebase",
        [],
    )
    assert "conflict" in job_world.issue_comments()[0].lower()
    assert "The job discarded" not in job_world.issue_comments()[0]
    assert job_world.repo.git("worktree", "list").count("\n") == 0
    assert job_world.origin_log() == ["fix(roadmap): plan"]


def test_a_conflict_on_the_rebase_before_the_push_pushes_the_commits_that_passed(
    job_world: JobWorld,
) -> None:
    move_main_when(
        job_world,
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        docs_effect,
    )

    applied = job_world.run(two_groups())

    status, record = _item(job_world)
    assert (applied.stopped, status, record.get("implement.stopped")) == ((1,), "Blocked", "push")
    assert job_world.origin_log() == [
        "fix(roadmap): plan",
        "fix(roadmap): The first group (#1)",
        "fix(roadmap): The second group (#1)",
        "docs: regenerate the documentation (#1)",
        "docs(openspec): archive the change (#1)",
    ]
    assert job_world.pull.ready_calls == []
    assert "conflict" in job_world.issue_comments()[0].lower()


def _conflict_on_main(world: JobWorld, names: list[str]) -> None:
    """Make the staged branch and `main` both add each file of `names` with other text, so a rebase
    of the branch onto `main` stops on one conflict for each file."""
    repo = world.repo
    repo.git("fetch", "-q", "origin", BRANCH)
    repo.git("switch", "-q", "-c", "stage-side", f"origin/{BRANCH}")
    for name in names:
        (repo.clone / name).parent.mkdir(parents=True, exist_ok=True)
        (repo.clone / name).write_text("The branch.\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("-c", "user.name=devops-roadmap[bot]", "commit", "-q", "-m", "fix(roadmap): more")
    repo.git("push", "-q", "--force", "origin", f"stage-side:{BRANCH}")
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", "stage-side")
    for name in names:
        (repo.clone / name).parent.mkdir(parents=True, exist_ok=True)
        (repo.clone / name).write_text("Main.\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "main adds the same files")
    repo.git("push", "-q", "origin", "main")


def test_a_conflict_on_the_rebase_at_the_start_names_the_conflicted_files(
    job_world: JobWorld,
) -> None:
    _conflict_on_main(job_world, ["docs/a.md", "docs/b.md"])

    job_world.run(two_groups())

    comment = job_world.issue_comments()[0]
    _, record = _item(job_world)
    assert (
        "Failure class: `conflict`" in comment,
        "- docs/a.md" in comment and "- docs/b.md" in comment,
        json.loads(record["implement.conflict"] or "[]"),
    ) == (True, True, ["docs/a.md", "docs/b.md"])


def test_a_conflict_on_the_rebase_before_the_push_names_the_conflicted_files(
    job_world: JobWorld,
) -> None:
    move_main_when(
        job_world,
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        docs_effect,
    )

    job_world.run(two_groups())

    comment = job_world.issue_comments()[0]
    _, record = _item(job_world)
    assert (
        "Failure class: `conflict`" in comment,
        "- src/devops_cli/shout.py" in comment,
        json.loads(record["implement.conflict"] or "[]"),
    ) == (True, True, ["src/devops_cli/shout.py"])


def test_a_retry_clears_the_conflicted_files_with_the_stop(job_world: JobWorld) -> None:
    item = job_world.store.item(1)
    assert item is not None
    job_world.store.set_marks(
        item,
        {ImplementRecordKey.STOPPED: "rebase", ImplementRecordKey.CONFLICT: '["docs/a.md"]'},
    )
    job_world.store.comment(1, f"{MARKER}\nStopped at rebase.")
    job_world.store.seed_comment(1, "implement: retry", author_association="OWNER")

    job_world.run(two_groups())

    _, record = _item(job_world)
    assert record.get("implement.conflict") is None


def test_a_list_of_conflicted_files_above_the_limit_is_cut_and_the_comment_counts_the_rest(
    job_world: JobWorld,
) -> None:
    limit = constants.CONST_ROADMAP_IMPLEMENT_REASON_PATHS
    names = [f"docs/file-{number:03d}.md" for number in range(limit + 3)]
    _conflict_on_main(job_world, names)

    job_world.run(two_groups())

    comment = job_world.issue_comments()[0]
    _, record = _item(job_world)
    assert (
        f"- {names[limit - 1]}" in comment,
        f"- {names[limit]}" in comment,
        "and 3 more" in comment,
        json.loads(record["implement.conflict"] or "[]"),
    ) == (True, False, True, names[:limit])


def test_a_secret_in_the_path_of_a_conflicted_file_reaches_neither_comment_nor_record(
    job_world: JobWorld,
) -> None:
    _conflict_on_main(job_world, [f"docs/{TOKEN}.md"])

    job_world.run(two_groups())

    _, record = _item(job_world)
    recorded = record["implement.conflict"] or ""
    assert (TOKEN in job_world.issue_comments()[0], TOKEN in recorded, "docs/" in recorded) == (
        False,
        False,
        True,
    )


def test_a_step_that_stops_does_not_stop_the_next_item(job_world: JobWorld) -> None:
    second = seed_staged(job_world.store, pull=6)
    push_staged_branch(job_world.repo, number=second)
    route_pull_status(job_world.api, pull=6)
    script = ModelScript(say("Stuck."))

    applied = job_world.run(script, limit=2)

    assert (second, applied.stopped, applied.failed) == (second, (1, second), ())
    assert [_item(job_world, n)[0] for n in (1, second)] == ["Blocked", "Blocked"]


def test_a_commit_the_agent_cannot_make_without_a_change_stops_at_the_group(
    job_world: JobWorld,
) -> None:
    script = ModelScript(say("Nothing to do."))

    applied = job_world.run(script)

    _, record = _item(job_world)
    assert (applied.stopped, record.get("implement.stopped")) == ((1,), "group 1")


def test_a_failed_archive_stops_the_item_at_the_archive(job_world: JobWorld) -> None:
    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(returncode=1, stderr="openspec: the change has no delta\n"),
    )

    applied = job_world.run(two_groups())

    _, record = _item(job_world)
    assert (applied.stopped, record.get("implement.stopped")) == ((1,), "archive")
    assert "the change has no delta" in job_world.issue_comments()[0]
    assert job_world.pull.ready_calls == []


def test_the_plan_alone_runs_nothing(job_world: JobWorld) -> None:
    plan = plan_implement(
        job_world.store,
        repo=STAGE_REPO,
        source=job_world.repo.clone,
        filters=parse_implement_filters(()),
    )

    assert [t.item.number for t in plan.selected] == [1]
    assert job_world.pull.ready_calls == []
    assert job_world.origin_log() == ["fix(roadmap): plan"]
    assert _item(job_world)[0] == "Ready"


def test_an_item_whose_worktree_cannot_be_made_is_reported_and_left_alone(
    job_world: JobWorld,
) -> None:
    plan = job_world.plan()
    worktree_directory(1, job_world.repo.clone).mkdir(parents=True)
    script = two_groups()

    applied = apply_implement(
        job_world.store, plan, source=job_world.repo.clone, model=script.model(), window=WINDOW
    )

    assert (applied.ready, applied.stopped, [f.number for f in applied.failed]) == ((), (), [1])
    assert applied.failed[0].error == "GitOperationError"
    assert (script.seen, _item(job_world)[0]) == ([], "Ready")
    with pytest.raises(RoadmapImplementError) as raised:
        raise_for_failed(applied.failed)
    assert "1 item(s) failed: #1 (GitOperationError" in str(raised.value)


def test_a_run_with_no_failure_raises_nothing() -> None:
    assert raise_for_failed(()) is None


# ── A claim of an agent or a person ends the run at a group boundary (#2910) ──────────────


def _claim(world: JobWorld, label: str) -> Callable[[], None]:
    """What a person does on GitHub: label the item."""
    return lambda: world.store.as_actor("alice").add_label(1, label)


def _owner(world: JobWorld) -> list[str]:
    held = world.store.item(1)
    assert held is not None
    return [label for label in held.labels if label.startswith("owner/")]


def _docs_ran(world: JobWorld) -> bool:
    return any(
        command_text(call).startswith("uv run devops docs generate")
        for call in world.programs.calls
    )


def test_a_person_who_claims_while_group_one_runs_ends_the_job_before_group_two(
    job_world: JobWorld,
) -> None:
    script = two_groups()
    script.effects[2] = _claim(job_world, "owner/human")

    applied = job_world.run(script)

    (comment,) = job_world.issue_comments()
    status, record = _item(job_world)
    assert (applied.yielded, applied.ready, applied.stopped, applied.failed) == ((1,), (), (), ())
    assert (len(script.seen), job_world.origin_log(), _docs_ran(job_world)) == (
        2,
        ["fix(roadmap): plan"],
        False,
    )
    assert (job_world.sent("PATCH", f"pulls/{PULL}"), job_world.pull.ready_calls) == ([], [])
    assert (status, record.get("implement.stopped"), record["implement.group"]) == (
        "In Progress",
        None,
        "1",
    )
    assert (_owner(job_world), comment.startswith(MARKER)) == (["owner/human"], True)
    assert "human claimed the item" in comment
    assert "start of group 2" in comment
    assert "opened no pull request" in comment


def test_a_claim_made_before_the_first_group_ends_the_job_before_any_step(
    job_world: JobWorld,
) -> None:
    plan = job_world.plan()
    _claim(job_world, "owner/agent")()
    script = two_groups()

    applied = apply_implement(
        job_world.store, plan, source=job_world.repo.clone, model=script.model(), window=WINDOW
    )

    (comment,) = job_world.issue_comments()
    assert (applied.yielded, applied.ready, script.seen, job_world.origin_log()) == (
        (1,),
        (),
        [],
        ["fix(roadmap): plan"],
    )
    assert ("agent claimed the item" in comment, "start of group 1" in comment) == (True, True)
    assert (_item(job_world)[0], _owner(job_world)) == ("In Progress", ["owner/agent"])


def test_a_claim_made_while_the_last_group_runs_ends_the_job_before_the_push(
    job_world: JobWorld,
) -> None:
    script = two_groups()
    script.effects[4] = _claim(job_world, "owner/human")

    applied = job_world.run(script)

    (comment,) = job_world.issue_comments()
    assert (applied.yielded, applied.ready, len(script.seen)) == ((1,), (), 4)
    assert (job_world.origin_log(), job_world.pull.ready_calls) == (["fix(roadmap): plan"], [])
    assert "end of the last group" in comment


def test_a_planned_item_that_a_person_claims_gets_no_branch_and_no_pull_request(
    planned_world: JobWorld,
) -> None:
    script = two_groups()
    script.effects[2] = _claim(planned_world, "owner/human")

    applied = planned_world.run(script)

    assert (applied.yielded, applied.ready) == ((1,), ())
    assert planned_world.repo.origin_git("branch", "--list", BRANCH) == ""
    assert not any(request.method == "POST" for request in planned_world.api.sent)


def test_the_claim_of_the_service_does_not_end_the_job(job_world: JobWorld) -> None:
    job_world.store.as_actor("alice").add_label(1, "owner/service")

    applied = job_world.run(two_groups())

    assert (applied.ready, applied.yielded) == ((1,), ())


def test_a_claim_made_while_the_docs_are_generated_ends_the_job_before_the_push(
    job_world: JobWorld,
) -> None:
    claim = _claim(job_world, "owner/human")

    def claim_then_generate(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        claim()
        return docs_effect(call)

    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        ProcessAnswer(side_effect=claim_then_generate),
    )

    applied = job_world.run(two_groups())

    (comment,) = job_world.issue_comments()
    assert (applied.yielded, applied.ready, job_world.pull.ready_calls) == ((1,), (), [])
    assert job_world.origin_log() == ["fix(roadmap): plan"]
    assert "the end of the last group" in comment


@pytest.mark.parametrize("world_name", ["job_world", "planned_world"])
def test_a_claim_made_while_a_group_runs_beats_the_stop_of_that_group(
    world_name: str, request: pytest.FixtureRequest
) -> None:
    world: JobWorld = request.getfixturevalue(world_name)
    script = ModelScript(tool_calls(*group_one_calls()), say("Done."), say("Stuck."))
    script.effects[3] = _claim(world, "owner/human")

    applied = world.run(script)

    (comment,) = world.issue_comments()
    status, record = _item(world)
    assert (applied.yielded, applied.stopped, applied.failed) == ((1,), (), ())
    if world_name == "job_world":
        assert world.origin_log() == ["fix(roadmap): plan"]
    else:
        assert world.repo.origin_git("branch", "--list", BRANCH) == ""
    assert not any(r.method == "POST" for r in world.api.sent)
    assert (record.get("implement.stopped"), _owner(world)) == (None, ["owner/human"])
    assert status != "Ready"
    assert "human claimed the item" in comment


# ── The model tier ladder (#3060) ─────────────────────────────────────────────────────────


def test_the_record_itemizes_the_spend_under_the_tier_that_served_it(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"ladder": {"edit": ["devops-coder", "devops-reasoning"]}}})
    script = ModelScript(
        ModelAPIError("example-model", "The provider broke."), *two_groups().replies
    )

    job_world.run(script)

    _, record = _item(job_world)
    spend = json.loads(record["implement.spend"] or "{}")
    assert (set(spend["tiers"]), spend["tiers"]["devops-reasoning"]["input_tokens"] > 0) == (
        {"devops-coder", "devops-reasoning"},
        True,
    )
    assert spend["requests"] == sum(tier["requests"] for tier in spend["tiers"].values())


def test_the_stop_comment_of_a_tier_change_names_the_tier_move(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"ladder": {"edit": ["devops-coder", "devops-reasoning"]}}})
    script = ModelScript(
        ModelAPIError("example-model", "The provider broke."),
        ModelHTTPError(
            400, "example-model", {"message": "Ollama_chatException: failed to parse the reply"}
        ),
    )

    applied = job_world.run(script)

    comment = job_world.issue_comments()[0]
    assert (applied.stopped, applied.failed) == ((1,), ())
    assert "Action taken: `change_tier`, 1 tier move(s)." in comment
    assert "Action left: `wait`" in comment


def test_unticked_task_in_archived_change_stops_at_ready(job_world: JobWorld) -> None:
    def unticked_archive(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        res = archive_effect(call)
        assert call.cwd is not None
        change = command_text(call).split()[-1]
        target_tasks = (
            call.cwd / "openspec" / "changes" / "archive" / f"2026-10-29-{change}" / "tasks.md"
        )
        content = target_tasks.read_text(encoding="utf-8")
        target_tasks.write_text(
            content.replace("- [x] 2.1 Document", "- [ ] 2.1 Document"), encoding="utf-8"
        )
        return res

    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(side_effect=unticked_archive),
    )

    applied = job_world.run(two_groups())

    assert (applied.stopped, job_world.pull.ready_calls) == ((1,), [])
    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.stopped") == "ready"
    (comment,) = job_world.issue_comments()
    assert "2" in comment
    assert "Failure class: `plan_defect`" in comment


def test_running_check_at_ready_stops_the_job(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_run.read_check_runs",
        lambda *_args, **_kwargs: CheckVerdictSummary(
            items=[PRCheckItem(name="Lint", bucket=CheckBucket.PENDING)]
        ),
    )

    applied = job_world.run(two_groups())

    assert (applied.stopped, job_world.pull.ready_calls) == ((1,), [])
    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.stopped") == "ready"
    (comment,) = job_world.issue_comments()
    assert "a check runs" in comment.lower()


def test_unarchived_active_change_stops_at_ready(job_world: JobWorld) -> None:
    """When the change folder was not archived and remains under openspec/changes/, ready refuses."""
    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(stdout="skipped archive\n"),
    )
    applied = job_world.run(two_groups())
    assert (applied.stopped, job_world.pull.ready_calls) == ((1,), [])
    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.stopped") == "ready"
    (comment,) = job_world.issue_comments()
    assert "not archived" in comment.lower()


def test_missing_change_folder_stops_at_ready(job_world: JobWorld) -> None:
    """When neither archive nor active change folder exists, ready refuses with change missing."""

    def remove_change(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        change = command_text(call).split()[-1]
        source = call.cwd / "openspec" / "changes" / change
        if source.exists():
            shutil.rmtree(source)
        return subprocess.CompletedProcess(call.argv, 0, stdout="removed\n")

    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(side_effect=remove_change),
    )
    applied = job_world.run(two_groups())
    assert (applied.stopped, job_world.pull.ready_calls) == ((1,), [])
    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.stopped") == "ready"
    (comment,) = job_world.issue_comments()
    assert "missing" in comment.lower()


def test_implement_replaces_staging_labels_with_new_title_labels(job_world: JobWorld) -> None:
    status = {
        "state": "open",
        "draft": True,
        "merged": False,
        "title": "docs(openspec): plan #1 Stop the job dropping a comment",
        "head": {"ref": BRANCH, "sha": ""},
        "base": {"ref": "main", "sha": "basesha"},
        "labels": [
            {"name": "type/docs"},
            {"name": "scope/openspec"},
            {"name": "scope/ai"},
        ],
    }
    route_pull_status(job_world.api, status)
    pr_issue = job_world.store._roadmap.issues[PULL]
    job_world.store._roadmap.issues[PULL] = pr_issue.model_copy(
        update={"labels": ("type/docs", "scope/openspec", "scope/ai")}
    )

    applied = job_world.run(two_groups())

    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    assert set(job_world.store._roadmap.issues[PULL].labels) == {
        "type/bug",
        "scope/roadmap",
        "scope/ai",
    }
    unlabels = [w for w in job_world.store._roadmap.job_writes if w.operation == "unlabel_issue"]
    assert len(unlabels) == 2


def test_implement_with_no_labels_held_sends_no_delete(job_world: JobWorld) -> None:
    status = {
        "state": "open",
        "draft": True,
        "merged": False,
        "title": "docs(openspec): plan #1 Stop the job dropping a comment",
        "head": {"ref": BRANCH, "sha": ""},
        "base": {"ref": "main", "sha": "basesha"},
        "labels": [],
    }
    route_pull_status(job_world.api, status)
    pr_issue = job_world.store._roadmap.issues[PULL]
    job_world.store._roadmap.issues[PULL] = pr_issue.model_copy(update={"labels": ()})

    applied = job_world.run(two_groups())

    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    unlabels = [w for w in job_world.store._roadmap.job_writes if w.operation == "unlabel_issue"]
    assert unlabels == []


def test_implement_refused_label_comments_on_pull_and_marks_ready(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.exceptions.git import GitHubOperationError

    status = {
        "state": "open",
        "draft": True,
        "merged": False,
        "title": "docs(openspec): plan #1 Stop the job dropping a comment",
        "head": {"ref": BRANCH, "sha": ""},
        "base": {"ref": "main", "sha": "basesha"},
        "labels": [{"name": "type/docs"}],
    }
    route_pull_status(job_world.api, status)

    def fail_label(number: int, label: str) -> None:
        raise GitHubOperationError("refused label write", operation="label_issue")

    monkeypatch.setattr(job_world.store, "label_issue", fail_label)

    applied = job_world.run(two_groups())

    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    assert len(job_world.pull.ready_calls) == 1
    comments = job_world.sent("POST", f"issues/{PULL}/comments")
    assert any(
        "refused label write" in c.get("body", "") or "type/bug" in c.get("body", "")
        for c in comments
    )


def test_implement_unauthenticated_label_error_stops_item(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.exceptions.git import GitHubUnauthenticatedError

    def unauth_label(number: int, label: str) -> None:
        raise GitHubUnauthenticatedError("bad token", operation="label_issue")

    monkeypatch.setattr(job_world.store, "label_issue", unauth_label)

    with pytest.raises(GitHubUnauthenticatedError, match="bad token"):
        job_world.run(two_groups())


def test_planned_item_holds_labels_and_removes_none(planned_world: JobWorld) -> None:
    applied = planned_world.run(two_groups())

    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    assert set(planned_world.store._roadmap.issues[PULL].labels) == {"type/bug", "scope/roadmap"}
    unlabels = [
        w for w in planned_world.store._roadmap.job_writes if w.operation == "unlabel_issue"
    ]
    assert unlabels == []


class TestFailToPassOfABehaviorGroup:
    """The job of a group whose staged tasks name a test that fails on base (#3042)."""

    @pytest.fixture
    def staged_tasks(self) -> str:
        return BEHAVIOR_TASKS

    @pytest.fixture
    def staged_files(self) -> dict[str, str]:
        return {"tests/conftest.py": '"""The tests."""\n'}

    def test_the_pr_comment_shows_the_fail_to_pass_result_of_each_behavior_group(
        self, job_world: JobWorld
    ) -> None:
        answer_pytest_on_base(job_world.programs, junit((SHOUT_TEST_ID, "failed")))
        group_one = (
            write_call("tests/test_shout.py", TEST_BODY),
            write_call("src/devops_cli/shout.py", SHOUT),
            write_call(TASKS_PATH, BEHAVIOR_FIRST_TICKED),
        )
        script = ModelScript(
            tool_calls(*group_one),
            say("Group 1 is done."),
            tool_calls(*group_two_calls(BEHAVIOR_TICKED)),
            say("Group 2 is done."),
        )

        applied = job_world.run(script)

        assert (applied.ready, applied.stopped) == ((1,), ())
        (comment,) = job_world.sent("POST", f"issues/{PULL}/comments")
        assert (
            "- fail-to-pass of group 1: fails on the base commit. "
            "Tests that fail on the base commit: tests.test_shout::test_shout."
        ) in comment["body"]


TWO_BEHAVIOR_TASKS = """\
# Tasks

## 1. The first group

Reads: `CONTEXT.md`. Changes: `tests/test_shout.py` (new), `src/devops_cli/shout.py` (new).

- [ ] 1.1 Add the failing test `tests/test_shout.py` for `src/devops_cli/shout.py`
  - Verification: `$ uv run devops ci test tests/test_shout.py` fails on the base
- [ ] 1.2 Add `shout` to `src/devops_cli/shout.py`
  - Verification: `$ uv run devops ci test tests/test_shout.py`

## 2. The second group

Reads: `CONTEXT.md`. Changes: `tests/test_whisper.py` (new), `src/devops_cli/whisper.py` (new).

- [ ] 2.1 Add the failing test `tests/test_whisper.py` for `src/devops_cli/whisper.py`
  - Verification: `$ uv run devops ci test tests/test_whisper.py` fails on the base
- [ ] 2.2 Add `whisper` to `src/devops_cli/whisper.py`
  - Verification: `$ uv run devops ci test tests/test_whisper.py`

## Criteria

- Group 1: The job keeps every comment.
"""
TWO_FIRST_TICKED = TWO_BEHAVIOR_TASKS.replace("- [ ] 1.", "- [x] 1.")
TWO_TICKED = TWO_BEHAVIOR_TASKS.replace("- [ ] 1.", "- [x] 1.").replace("- [ ] 2.", "- [x] 2.")
WHISPER = '"""Whisper."""\n\n\ndef whisper(text: str) -> str:\n    return text.lower()\n'
WHISPER_TEST_BODY = "def test_whisper() -> None:\n    assert True\n"
WHISPER_TEST_ID = "tests.test_whisper::test_whisper"


class TestFailToPassOfTwoBehaviorGroups:
    """The job of a change whose two groups are behavior groups: the PR comment shows a fail-to-pass
    line for each of them (#3042)."""

    @pytest.fixture
    def staged_tasks(self) -> str:
        return TWO_BEHAVIOR_TASKS

    @pytest.fixture
    def staged_files(self) -> dict[str, str]:
        return {"tests/conftest.py": '"""The tests."""\n'}

    def test_the_pr_comment_shows_a_fail_to_pass_line_for_each_behavior_group(
        self, job_world: JobWorld
    ) -> None:
        answer_pytest_on_base(
            job_world.programs,
            junit((SHOUT_TEST_ID, "failed")),
            junit((WHISPER_TEST_ID, "failed")),
        )
        script = ModelScript(
            tool_calls(
                write_call("tests/test_shout.py", TEST_BODY),
                write_call("src/devops_cli/shout.py", SHOUT),
                write_call(TASKS_PATH, TWO_FIRST_TICKED),
            ),
            say("Group 1 is done."),
            tool_calls(
                write_call("tests/test_whisper.py", WHISPER_TEST_BODY),
                write_call("src/devops_cli/whisper.py", WHISPER),
                write_call(TASKS_PATH, TWO_TICKED),
            ),
            say("Group 2 is done."),
        )

        applied = job_world.run(script)

        assert (applied.ready, applied.stopped) == ((1,), ())
        (comment,) = job_world.sent("POST", f"issues/{PULL}/comments")
        assert (
            "- fail-to-pass of group 1: fails on the base commit. "
            "Tests that fail on the base commit: tests.test_shout::test_shout."
        ) in comment["body"]
        assert (
            "- fail-to-pass of group 2: fails on the base commit. "
            "Tests that fail on the base commit: tests.test_whisper::test_whisper."
        ) in comment["body"]


# ── The premise of a behavior group (#3417) ───────────────────────────────────────────────

TITLES = '"""The titles."""\n\n\ndef _delivery_title(text: str) -> str:\n    return text.strip()\n'
TITLES_PATH = "src/devops_cli/titles.py"
TITLES_LINE = f"{TITLES_PATH}:4:def _delivery_title(text: str) -> str:"


def _guard_tasks(name: str, *, behavior: bool) -> str:
    """A change of two groups whose first group adds the guard `name`. With `behavior`, the first
    group is a behavior group: a failing test, then the guard. Otherwise it is a group of kind
    `other` with one task that adds the guard."""
    if behavior:
        first = (
            "Reads: `CONTEXT.md`. Changes: `tests/test_shout.py` (new), "
            "`src/devops_cli/shout.py` (new).\n\n"
            "- [ ] 1.1 Add the failing test `tests/test_shout.py` for `src/devops_cli/shout.py`\n"
            "  - Verification: `$ uv run devops ci test tests/test_shout.py` fails on the base\n"
            f"- [ ] 1.2 Add the guard `{name}` to `src/devops_cli/shout.py`\n"
            "  - Verification: `$ uv run devops ci test tests/test_shout.py`\n"
        )
    else:
        first = (
            "Reads: `CONTEXT.md`. Changes: `src/devops_cli/shout.py` (new), `tests/test_shout.py` (new).\n\n"
            f"- [ ] 1.1 Add the guard `{name}` to `src/devops_cli/shout.py`\n"
            "  - Verification: `$ uv run devops ci test tests/test_shout.py`\n"
        )
    return (
        f"# Tasks\n\n## 1. The first group\n\n{first}\n"
        "## 2. The second group\n\n"
        "Reads: `CONTEXT.md`. Changes: `CONTEXT.md`.\n\n"
        "- [ ] 2.1 Document the function in `CONTEXT.md`\n"
        "  - Verification: `$ uv run devops docs check`\n\n"
        "## Criteria\n\n- Group 1: The job keeps every comment.\n"
    )


def _ticked(tasks: str) -> tuple[str, str]:
    """The tasks with group 1 ticked, and with both groups ticked."""
    first = tasks.replace("- [ ] 1.", "- [x] 1.")
    return first, first.replace("- [ ] 2.", "- [x] 2.")


class _PremiseWorld:
    """A staged branch whose base defines `_delivery_title` in `src/devops_cli/titles.py`."""

    @pytest.fixture
    def staged_files(self) -> dict[str, str]:
        return {"tests/conftest.py": '"""The tests."""\n', TITLES_PATH: TITLES}


class TestAFalsePremiseOfABehaviorGroup(_PremiseWorld):
    """A task of a behavior group adds a guard that the branch tip defines (#3417)."""

    @pytest.fixture
    def staged_tasks(self) -> str:
        return _guard_tasks("_delivery_title", behavior=True)

    def test_a_behavior_group_that_adds_a_guard_the_base_already_runs_returns_the_item(
        self, job_world: JobWorld
    ) -> None:
        tip = job_world.repo.origin_git("rev-parse", BRANCH)
        script = two_groups()

        applied = job_world.run(script)

        assert (applied.ready, applied.stopped, applied.failed) == ((), (), ())
        status, record = _item(job_world)
        assert (status, record.get("implement.group"), record.get("implement.branch")) == (
            "New",
            None,
            None,
        )
        (comment,) = job_world.issue_comments()
        assert TITLES_LINE in comment
        assert "`_delivery_title`" in comment
        assert script.seen == []
        assert job_world.repo.origin_git("rev-parse", BRANCH) == tip


class TestATruePremiseOfABehaviorGroup(_PremiseWorld):
    """A task of a behavior group adds a guard that the branch tip lacks (#3417)."""

    @pytest.fixture
    def staged_tasks(self) -> str:
        return _guard_tasks("_missing_guard", behavior=True)

    def test_a_behavior_group_whose_guard_the_base_lacks_runs(self, job_world: JobWorld) -> None:
        answer_pytest_on_base(job_world.programs, junit((SHOUT_TEST_ID, "failed")))
        first, both = _ticked(_guard_tasks("_missing_guard", behavior=True))
        script = ModelScript(
            tool_calls(
                write_call("tests/test_shout.py", TEST_BODY),
                write_call("src/devops_cli/shout.py", SHOUT),
                write_call(TASKS_PATH, first),
            ),
            say("Group 1 is done."),
            tool_calls(*group_two_calls(both)),
            say("Group 2 is done."),
        )

        applied = job_world.run(script)

        assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
        assert "src/devops_cli/shout.py" in job_world.repo.origin_git(
            "diff", "--name-only", f"main..{BRANCH}"
        )


class TestAGuardOfAGroupThatIsNotBehavior(_PremiseWorld):
    """A group of kind `other` names a defined guard: the check does not apply to it (#3417)."""

    @pytest.fixture
    def staged_tasks(self) -> str:
        return _guard_tasks("_delivery_title", behavior=False)

    def test_a_group_that_is_not_behavior_runs_though_the_base_defines_the_name(
        self, job_world: JobWorld
    ) -> None:
        _, both = _ticked(_guard_tasks("_delivery_title", behavior=False))
        script = ModelScript(
            tool_calls(
                write_call("src/devops_cli/shout.py", SHOUT),
                write_call(TASKS_PATH, both.replace("- [x] 2.", "- [ ] 2.")),
            ),
            say("Group 1 is done."),
            tool_calls(*group_two_calls(both)),
            say("Group 2 is done."),
        )

        applied = job_world.run(script)

        assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())


class TestVerifyOutputOfAnOtherGroup:
    """The job of a group of kind `other`: its verify command prints a line (#3042)."""

    def test_the_pr_comment_shows_the_exit_status_and_the_output_of_the_verify_command(
        self, job_world: JobWorld
    ) -> None:
        job_world.programs.answer(
            lambda call: "devops" in call.argv and "test" in call.argv,
            ProcessAnswer(stdout="shout ran\n"),
        )

        applied = job_world.run(two_groups())

        assert (applied.ready, applied.stopped) == ((1,), ())
        (comment,) = job_world.sent("POST", f"issues/{PULL}/comments")
        assert (
            "- verify of group 1: `uv run devops ci test tests/test_shout.py` exits 0.\n\n"
            "```\nshout ran\n```"
        ) in comment["body"]
        assert "- fail-to-pass of group 1" not in comment["body"]


def test_a_passing_group_without_a_model_tick_is_ticked_by_the_job_and_pushed(
    job_world: JobWorld,
) -> None:
    """The model writes the code of group 1 and no tick. The job ticks the group when its exit
    checks pass, and the commit of the group on origin holds the tick (#3488)."""
    script = ModelScript(
        tool_calls(("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT})),
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
    )

    applied = job_world.run(script)

    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    lines = job_world.repo.origin_git(
        "log", "--reverse", "--format=%H %s", f"main..{BRANCH}"
    ).splitlines()
    (first,) = [
        line.split(" ", 1)[0]
        for line in lines
        if line.endswith(" fix(roadmap): The first group (#1)")
    ]
    tasks = job_world.repo.origin_git("show", f"{first}:{TASKS_PATH}")
    assert "- [x] 1.1 Add `src/devops_cli/shout.py`" in tasks


# ── The plan check of the selection (#3393) ───────────────────────────────────────────────

PLACEHOLDER_TASKS = TASKS.replace("1.1 Add `src/devops_cli/shout.py`", "1.1 x")
FIRST_PROBLEM = (
    "The text of implementation of group 1 has 1 characters, and the least is 10. "
    "Write a real sentence."
)
SECOND_PROBLEM = "is the placeholder `x`"


def _select(store: InMemoryRoadmapStore, repo: StageRepo, number: int) -> ImplementPlan:
    """The selection of item `number`: the plan of a run that names it."""
    return plan_implement(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_implement_filters(()),
        item_number=number,
    )


def test_a_staged_item_whose_branch_plan_holds_task_x_is_left_out_with_the_first_problem(
    stage_repo: StageRepo,
    app_slug: None,
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
) -> None:
    push_staged_branch(stage_repo, tasks=PLACEHOLDER_TASKS)
    route_pull_status(github_api)
    number = seed_staged(roadmap_store)

    plan = _select(roadmap_store, stage_repo, number)

    assert plan.selected == ()
    (left,) = plan.left_out
    assert (left.number, FIRST_PROBLEM in left.reason) == (number, True)


def test_a_planned_item_whose_default_branch_plan_holds_task_x_gets_no_target_and_no_branch(
    stage_repo: StageRepo,
    app_slug: None,
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
) -> None:
    number = seed_staged(roadmap_store, record=False)
    merge_plan(stage_repo, number, tasks=PLACEHOLDER_TASKS)

    plan = _select(roadmap_store, stage_repo, number)

    assert plan.selected == ()
    (left,) = plan.left_out
    assert FIRST_PROBLEM in left.reason
    assert branch_of(number) not in stage_repo.origin_git(
        "for-each-ref", "--format=%(refname:short)", "refs/heads"
    )


def test_a_plan_with_two_problems_reports_only_the_first_problem(
    stage_repo: StageRepo,
    app_slug: None,
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
) -> None:
    push_staged_branch(stage_repo, tasks=PLACEHOLDER_TASKS)
    route_pull_status(github_api)
    number = seed_staged(roadmap_store)

    plan = _select(roadmap_store, stage_repo, number)

    (left,) = plan.left_out
    assert (FIRST_PROBLEM in left.reason, SECOND_PROBLEM in left.reason) == (True, False)


def test_a_plan_that_passes_the_check_selects_a_staged_item(
    stage_repo: StageRepo,
    app_slug: None,
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
) -> None:
    push_staged_branch(stage_repo)
    route_pull_status(github_api)
    number = seed_staged(roadmap_store)

    plan = _select(roadmap_store, stage_repo, number)

    assert [(t.item.number, t.branch, t.pull) for t in plan.selected] == [(number, BRANCH, PULL)]


def test_a_plan_that_passes_the_check_selects_a_planned_item(
    stage_repo: StageRepo,
    app_slug: None,
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
) -> None:
    number = seed_staged(roadmap_store, record=False)
    merge_plan(stage_repo, number)

    plan = _select(roadmap_store, stage_repo, number)

    assert [t.branch for t in plan.selected] == [branch_of(number)]


def test_a_plan_the_reader_cannot_parse_is_left_out_and_names_its_file(
    stage_repo: StageRepo,
    app_slug: None,
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
) -> None:
    unreadable = TASKS.replace("Reads: `CONTEXT.md`. Changes: `CONTEXT.md`.\n\n", "")
    push_staged_branch(stage_repo, tasks=unreadable)
    route_pull_status(github_api)
    number = seed_staged(roadmap_store)

    plan = _select(roadmap_store, stage_repo, number)

    assert plan.selected == ()
    (left,) = plan.left_out
    assert "tasks.md" in left.reason


def test_a_plan_whose_test_path_no_file_holds_is_left_out_and_names_the_path(
    stage_repo: StageRepo,
    app_slug: None,
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
) -> None:
    missing = TASKS.replace(
        "uv run devops ci test tests/test_shout.py",
        "uv run devops ci test tests/commands/test_shout.py",
    )
    push_staged_branch(stage_repo, tasks=missing)
    route_pull_status(github_api)
    number = seed_staged(roadmap_store)

    plan = _select(roadmap_store, stage_repo, number)

    assert plan.selected == ()
    (left,) = plan.left_out
    assert "tests/commands/test_shout.py" in left.reason


# ── The reads of the plan check for a run (#3430) ─────────────────────────────────────────

DEFAULT_REV = "origin/main"
BASE_SPEC = f"{DEFAULT_REV}:openspec/specs/roadmap-refine/spec.md"


def _git_calls(world: JobWorld, since: int) -> list[tuple[str, ...]]:
    """The git commands that the process edge saw after call number `since`, without `git -C
    <path>`."""
    return [call.argv[3:] for call in world.programs.calls[since:] if call.argv[0] == "git"]


def _listings(commands: list[tuple[str, ...]], rev: str) -> int:
    """How many commands list the files of `rev` with `git ls-tree -r`."""
    return sum(1 for command in commands if command[:2] == ("ls-tree", "-r") and command[-1] == rev)


def _plan_two_planned_items(world: JobWorld) -> tuple[int, list[tuple[str, ...]]]:
    """Add a second Planned item to the world, and plan a run over both. Return the number of
    the second item and the git commands of the run."""
    second = seed_staged(world.store, record=False)
    merge_plan(world.repo, second, slug="the-second-plan")
    since = len(world.programs.calls)
    plan = world.plan(limit=2)
    assert sorted(target.item.number for target in plan.selected) == [world.number, second]
    return second, _git_calls(world, since)


def test_a_run_over_two_planned_items_lists_the_default_tree_once(planned_world: JobWorld) -> None:
    _, commands = _plan_two_planned_items(planned_world)

    assert _listings(commands, DEFAULT_REV) == 1


def test_a_run_over_two_planned_items_reads_each_base_spec_once(planned_world: JobWorld) -> None:
    _, commands = _plan_two_planned_items(planned_world)

    assert commands.count(("show", BASE_SPEC)) == 1


def test_a_run_over_two_staged_items_lists_the_branch_of_each_item(job_world: JobWorld) -> None:
    second = seed_staged(job_world.store)
    push_staged_branch(job_world.repo, number=second)
    since = len(job_world.programs.calls)

    plan = job_world.plan(limit=2)

    commands = _git_calls(job_world, since)
    assert sorted(target.item.number for target in plan.selected) == [job_world.number, second]
    assert [_listings(commands, f"origin/{branch_of(n)}") for n in (job_world.number, second)] == [
        1,
        1,
    ]
    assert _listings(commands, DEFAULT_REV) == 1


def test_a_run_gives_each_item_the_target_or_reason_of_a_run_over_that_item_alone(
    planned_world: JobWorld,
) -> None:
    """The run over three items (a Planned plan that passes, a Planned plan with a placeholder task,
    and a Staged plan that passes) decides each item as a run that names the item does."""
    bad = seed_staged(planned_world.store, record=False)
    merge_plan(planned_world.repo, bad, tasks=PLACEHOLDER_TASKS, slug="the-bad-plan")
    staged = seed_staged(planned_world.store)
    push_staged_branch(planned_world.repo, number=staged)
    numbers = [planned_world.number, bad, staged]

    together = planned_world.plan(limit=len(numbers))
    alone = [planned_world.plan(item=number) for number in numbers]

    assert {t.item.number: t.branch for t in together.selected} == {
        t.item.number: t.branch for plan in alone for t in plan.selected
    }
    assert {x.number: x.reason for x in together.left_out} == {
        x.number: x.reason for plan in alone for x in plan.left_out
    }
    assert FIRST_PROBLEM in {x.number: x.reason for x in together.left_out}[bad]


def test_a_default_tree_that_git_cannot_list_leaves_each_planned_item_out_and_ends_no_run(
    planned_world: JobWorld,
) -> None:
    second = seed_staged(planned_world.store, record=False)
    merge_plan(planned_world.repo, second, slug="the-second-plan")
    planned_world.programs.answer(
        lambda call: call.argv[3:5] == ("ls-tree", "-r") and call.argv[-1] == DEFAULT_REV,
        ProcessAnswer(returncode=128, stderr="fatal: not a tree object"),
    )

    plan = planned_world.plan(limit=2)

    assert plan.selected == ()
    assert {x.number: "cannot be read from git" in x.reason for x in plan.left_out} == {
        planned_world.number: True,
        second: True,
    }

"""`devops roadmap implement` as a job: the run of a Staged item from the first group to a ready
pull request, and every way it stops (#2665).

Git runs for real on a clone with an `origin`. The model is scripted, so the steps are real: they
write files in the worktree, and their exit checks run through the process edge. GitHub's REST API
and `gh` are faked at their edges.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from markdown_it import MarkdownIt
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.config import constants
from devops_cli.exceptions import RoadmapImplementError
from devops_cli.git.worktree_add import worktree_directory
from devops_cli.roadmap.implement import parse_implement_filters, plan_implement
from devops_cli.roadmap.implement_run import apply_implement, raise_for_failed
from devops_cli.roadmap.store import ImplementRecordKey
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.implement_step import WINDOW, command_text
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    CHANGE,
    PULL,
    TASKS_PATH,
    TICKED_FIRST,
    JobWorld,
    docs_effect,
    group_one_calls,
    group_two_calls,
    move_main_when,
    push_staged_branch,
    route_pull_status,
    seed_staged,
    two_groups,
)
from tests.support.roadmap_stage import STAGE_REPO

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
    monkeypatch.setattr("devops_cli.roadmap.implement_run.acts_as_github_app", lambda: False)

    with pytest.raises(RoadmapImplementError) as raised:
        job_world.run(two_groups())

    assert "GitHub App" in str(raised.value)


def test_the_job_checks_the_token_scope_before_it_clears_its_dumpable_flag(
    job_world: JobWorld, config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config(service={"github_app": {"token_repository": None}})
    seen: list[str] = []
    monkeypatch.setattr(
        "devops_cli.roadmap.implement_run.deny_environment_reads", lambda: seen.append("called")
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
        "devops_cli.roadmap.implement_run.deny_environment_reads",
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
        "devops_cli.roadmap.implement_run.deny_environment_reads", lambda: seen.append("called")
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
        "The first group (#1)",
        "The second group (#1)",
        "docs: regenerate the documentation (#1)",
        "docs(openspec): archive the change (#1)",
    ]
    assert job_world.sent("PATCH", f"pulls/{PULL}") == [
        {
            "title": "fix(roadmap): the job drops a comment",
            "body": "Closes #1\n\nThe job drops the last comment of a thread (#1). It must keep it."
            f"\n\nChange: `openspec/changes/archive/2026-10-29-{CHANGE}/`",
        }
    ]
    assert job_world.pull.ready_calls == [("pr", "ready", str(PULL), "--repo", STAGE_REPO)]
    status, record = _item(job_world)
    assert (status, record["implement.pr"], record.get("implement.stopped")) == (
        "In Review",
        str(PULL),
        None,
    )


def test_the_title_of_the_pull_request_has_no_scope_that_the_labels_file_lacks(
    job_world: JobWorld,
) -> None:
    """The `Semantic PR title` check refuses an undeclared scope (#2800), and the title of the
    issue may hold one."""
    job_world.store.seed_file(".github/labels.yml", "- name: type/bug\n  color: D73A4A\n")

    job_world.run(two_groups())

    (patched,) = job_world.sent("PATCH", f"pulls/{PULL}")
    assert patched["title"] == "fix: the job drops a comment"


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
    assert "The first group" in body
    assert "The second group" in body
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
        "-c", "user.name=devops-roadmap[bot]", "commit", "-q", "-m", "The first group (#1)"
    )
    job_world.repo.git("push", "-q", "origin", f"tmp:{BRANCH}")
    job_world.repo.git("switch", "-q", "main")
    job_world.repo.git("branch", "-q", "-D", "tmp")
    script = ModelScript(tool_calls(*group_two_calls()), say("Group 2 is done."))

    applied = job_world.run(script)

    assert (applied.ready, len(script.seen)) == ((1,), 2)
    assert job_world.origin_log()[:3] == [
        "fix(roadmap): plan",
        "The first group (#1)",
        "The second group (#1)",
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


TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
DIFF_TEXT = f"A note with a secret {TOKEN}\n```\nand a line that tries to close the block\n```\n"


def _stop_with_a_dangerous_diff(job_world: JobWorld) -> str:
    """Run the job to the stop of group 2, which writes `DIFF_TEXT` and ticks nothing."""
    write = ("write_file", {"path": "CONTEXT.md", "content": DIFF_TEXT})
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(write),
        say("Wrote the note."),
        say("I did not tick."),
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
        say("Wrote the note."),
        say("I did not tick."),
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
    names = [f"{'f' * 240}{number:02d}.md" for number in range(30)]
    many = tuple(("write_file", {"path": name, "content": "x\n"}) for name in names)
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(*group_two_calls(TICKED_FIRST)),
        say("Wrote the note."),
        tool_calls(*many),
        say("Ticked."),
    )

    job_world.run(script)

    comment = job_world.issue_comments()[0]
    reason = comment.partition("Reason:\n\n")[2].partition("\n\nLast message")[0]
    assert reason.strip().startswith("The extra turn for the ticks changed files")
    assert len(reason.strip()) == constants.CONST_ROADMAP_IMPLEMENT_REASON_CHARS


def test_a_stop_pushes_the_commits_of_the_steps_that_passed_and_leaves_the_draft(
    job_world: JobWorld,
) -> None:
    script = ModelScript(tool_calls(*group_one_calls()), say("Done."), say("Stuck."))

    job_world.run(script)

    assert job_world.origin_log() == ["fix(roadmap): plan", "The first group (#1)"]
    assert job_world.pull.ready_calls == []
    assert job_world.sent("PATCH", f"pulls/{PULL}") == []
    _, record = _item(job_world)
    assert record["implement.group"] == "1"


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
        "The first group (#1)",
        "The second group (#1)",
        "docs: regenerate the documentation (#1)",
        "docs(openspec): archive the change (#1)",
    ]
    assert job_world.pull.ready_calls == []
    assert "conflict" in job_world.issue_comments()[0].lower()


def test_a_step_that_stops_does_not_stop_the_next_item(job_world: JobWorld) -> None:
    push_staged_branch(job_world.repo, number=2)
    second = seed_staged(job_world.store, pull=6)
    route_pull_status(job_world.api, pull=6)
    script = ModelScript(say("Stuck."))

    applied = job_world.run(script, limit=2)

    assert (second, applied.stopped, applied.failed) == (2, (1, 2), ())
    assert [_item(job_world, n)[0] for n in (1, 2)] == ["Blocked", "Blocked"]


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

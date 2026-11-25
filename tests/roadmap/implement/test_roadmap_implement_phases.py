"""The implement job on the phases `prepare`, `agent` and `publish` (#3702).

Git runs for real on a clone with an `origin`. The model is scripted, so the steps are real. GitHub's
REST API and `gh` are faked at their edges. Each phase runs on its own call here, as #3700 runs it in
its own container: `prepare` clones and records the base and the lease, the agent phase writes the
patches and the outcome and makes no GitHub call, and `publish` reads them as data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.github.client import GitHubClient
from devops_cli.roadmap.implement import implement_report
from devops_cli.roadmap.implement.implement_phases import (
    AgentTools,
    ImplementState,
    agent_implement,
    prepare_implement,
    publish_phase,
)
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.phases.rebase import skips_archive_commit
from devops_cli.roadmap.stores.store import ImplementRecordKey, ImplementResult, ItemField
from tests.support.fakes.github import github_json
from tests.support.fakes.process import ProcessAnswer
from tests.support.implement_step import WINDOW
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    ARCHIVE_COMMIT,
    BRANCH,
    OPEN_DRAFT,
    PULL,
    WORK_COMMIT,
    JobWorld,
    group_one_calls,
    route_pull_status,
    two_groups,
)
from tests.support.roadmap_stage import STAGE_NAME, STAGE_REPO
from tests.support.run_folders import read_only_run

pytestmark = pytest.mark.usefixtures("keyring_store")

SECRET = "ghp_" + "a" * 36


class _Killed(BaseException):
    """The end of a Job that the kernel kills: no handler of the job catches it."""


def _prepare(world: JobWorld, folders: RunFolders, *, rebase: bool = True) -> ImplementState:
    (target,) = world.plan().selected
    state = prepare_implement(world.store, STAGE_REPO, target, folders, rebase=rebase)
    assert isinstance(state, ImplementState)
    return state


def _pushes(world: JobWorld) -> int:
    return sum("push" in call.argv for call in world.programs.calls)


def test_the_phases_in_separate_calls_take_the_item_to_the_draft(
    job_world: JobWorld, tmp_path: Path
) -> None:
    """`prepare` records the tip of `main` as the base and the tip of the branch as the lease, the
    agent phase makes no GitHub call, and `publish` pushes the work and the archive as two commits
    of the bot on the base."""
    folders = RunFolders(tmp_path / "run")
    lease = job_world.repo.origin_git("rev-parse", BRANCH)
    state = _prepare(job_world, folders)
    requested = list(job_world.api.requested)

    agent_implement(folders, AgentTools(two_groups().model(), WINDOW))

    assert job_world.api.requested == requested
    assert (state.base, state.lease) == (job_world.repo.origin_git("rev-parse", "main"), lease)
    assert publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1) is (
        ImplementResult.DRAFTED
    )
    assert job_world.origin_log() == [WORK_COMMIT, ARCHIVE_COMMIT]


def test_publish_pushes_from_a_run_folder_that_it_cannot_write(
    job_world: JobWorld, tmp_path: Path
) -> None:
    """The container `publish` mounts the run folder read-only (#3700), so its new repository
    goes to a temporary folder of its own."""
    folders = RunFolders(tmp_path / "run")
    _prepare(job_world, folders)
    agent_implement(folders, AgentTools(two_groups().model(), WINDOW))

    with read_only_run(folders):
        result = publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1)

    assert (result, job_world.origin_log()) == (
        ImplementResult.DRAFTED,
        [WORK_COMMIT, ARCHIVE_COMMIT],
    )


def test_a_second_publish_of_the_same_run_pushes_and_comments_nothing(
    job_world: JobWorld, tmp_path: Path
) -> None:
    folders = RunFolders(tmp_path / "run")
    _prepare(job_world, folders)
    agent_implement(folders, AgentTools(two_groups().model(), WINDOW))
    publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1)
    pushes, comments = _pushes(job_world), len(job_world.issue_comments())
    pull_comments = job_world.sent("POST", f"issues/{PULL}/comments")

    again = publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1)

    assert again is ImplementResult.DRAFTED
    assert (_pushes(job_world), len(job_world.issue_comments())) == (pushes, comments)
    assert job_world.sent("POST", f"issues/{PULL}/comments") == pull_comments


def test_publish_masks_each_text_of_the_outcome(job_world: JobWorld, tmp_path: Path) -> None:
    """The agent wrote `outcome.json`, so `publish` masks a secret in any of its texts before the
    stop comment and the record take it."""
    folders = RunFolders(tmp_path / "run")
    _prepare(job_world, folders)
    agent_implement(folders, AgentTools(ModelScript(say(f"Stuck on {SECRET}.")).model(), WINDOW))
    outcome = json.loads((folders.out / "outcome.json").read_text(encoding="utf-8"))
    outcome["stop"]["reason"] = f"The token is {SECRET}."
    (folders.out / "outcome.json").write_text(json.dumps(outcome), encoding="utf-8")

    result = publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1)

    assert result is ImplementResult.STOPPED
    comments = job_world.issue_comments()
    assert comments
    assert [comment for comment in comments if SECRET in comment] == []
    assert SECRET not in json.dumps(dict(job_world.store.item(1).job_record))  # type: ignore[union-attr]


def test_publish_refuses_a_state_that_names_another_branch(
    job_world: JobWorld, tmp_path: Path
) -> None:
    """A separate `publish` takes the state file as data: its branch must be the branch that
    `prepare` recorded on the item."""
    folders = RunFolders(tmp_path / "run")
    _prepare(job_world, folders)
    state = json.loads((folders.state / "state.json").read_text(encoding="utf-8"))
    state["branch"] = "fix/1-another-branch"
    (folders.state / "state.json").write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(PhaseOutputError, match="another branch"):
        publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1)


def test_the_agent_phase_writes_its_outputs_into_a_new_folder(
    job_world: JobWorld, tmp_path: Path
) -> None:
    """The agent can write the run folder, so a link that it leaves at `out/outcome.json` would turn
    the write of the job to another file. The agent phase makes `out/` after the sweep, and
    refuses an `out/` that is there already (#6655, #3702)."""
    folders = RunFolders(tmp_path / "run")
    _prepare(job_world, folders)
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text("untouched", encoding="utf-8")
    folders.out.mkdir()
    (folders.out / "outcome.json").symlink_to(elsewhere)

    with pytest.raises(PhaseOutputError, match="output folder"):
        agent_implement(folders, AgentTools(two_groups().model(), WINDOW))

    assert elsewhere.read_text(encoding="utf-8") == "untouched"


class TestPrepareRunsGitOnly:
    @pytest.fixture
    def staged_files(self) -> dict[str, str]:
        """A branch whose build hook would run with a build of the project."""
        return {
            "pyproject.toml": (
                "[build-system]\nrequires = ['hatchling']\nbuild-backend = 'hatchling.build'\n\n"
                "[tool.hatch.build.hooks.custom]\npath = 'hook.py'\n"
            ),
            "hook.py": "raise SystemExit('the hook ran')\n",
        }

    def test_prepare_starts_no_child_but_git(self, job_world: JobWorld, tmp_path: Path) -> None:
        """`prepare` holds the App token and runs no code of the pull request: no `uv`, no hook and
        no build, only git."""
        before = len(job_world.programs.calls)

        _prepare(job_world, RunFolders(tmp_path / "run"))

        calls = job_world.programs.calls[before:]
        assert {Path(call.argv[0]).name for call in calls} == {"git"}
        # The read of the plan title gets a home folder of the run, as `publish` does (#6655).
        (log,) = [call for call in calls if "log" in call.argv and "--format=%s" in call.argv]
        assert (log.env or {}).get("HOME", "").startswith(str(tmp_path))


ARCHIVE_MOVE = (
    "R100\0openspec/changes/1-x/tasks.md\0openspec/changes/archive/2026-11-21-1-x/tasks.md\0"
)


@pytest.mark.parametrize(
    ("listed", "skip"),
    [
        (ARCHIVE_MOVE + "M\0openspec/specs/roadmap/spec.md\0", True),
        ("D\0openspec/changes/1-x/tasks.md\0M\0docs/CLI_REFERENCE.md\0", True),
        ("A\0openspec/changes/1-x/tasks.md\0A\0openspec/changes/1-x/proposal.md\0", False),
        ("M\0openspec/specs/roadmap/spec.md\0", False),
        ("D\0openspec/changes/2-y/tasks.md\0", False),
        (ARCHIVE_MOVE + "M\0src/devops_cli/shout.py\0", False),
    ],
    ids=["archive", "archive-by-delete", "plan", "spec-only", "other-item", "mixed"],
)
def test_a_rebase_skips_only_the_archive_commit_of_the_item(listed: str, skip: bool) -> None:
    """The archive commit moves the change folder of the item and merges the specs, so the run
    archives again after a skip. The plan commit adds the change folder, so a skip would lose the
    plan, and a commit that changes other files goes to a stop (#3702)."""
    assert skips_archive_commit(listed, 1) is skip


# ── The review of #6670 ───────────────────────────────────────────────────────────────────

PREMISE = (
    "```plan-request\n"
    '{"kind": "premise", "group": 2, "defect": "the premise is false", '
    '"evidence": "upstream removed the API"}\n'
    "```"
)


def _stop_after_group_one() -> ModelScript:
    return ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."), say("Stuck."))


def _record(world: JobWorld) -> dict[str, str | None]:
    held = world.store.item(1)
    assert held is not None
    return {str(key): value for key, value in held.job_record.items()}


def _continue(world: JobWorld) -> None:
    """What the Service does after a stop: it clears the stop and puts the item back to Ready."""
    held = world.store.item(1)
    assert held is not None
    world.store.set_marks(
        held, {ImplementRecordKey.STOPPED: None, ImplementRecordKey.FAILURE: None}
    )
    held = world.store.item(1)
    assert held is not None
    world.store.set_field(held, ItemField.STATUS, "Ready")


def _branch_changes_a_doc_that_main_deletes(world: JobWorld, name: str) -> None:
    """The staged branch changes the generated document `name`, and `main` deletes it, so the
    rebase stops on a modify/delete conflict whose file has no side of `main`."""
    repo = world.repo
    (repo.clone / name).parent.mkdir(parents=True, exist_ok=True)
    (repo.clone / name).write_text("Main.\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "main adds the document")
    repo.git("push", "-q", "origin", "main")
    repo.git("fetch", "-q", "origin", BRANCH)
    repo.git("switch", "-q", "-c", "stage-side", f"origin/{BRANCH}")
    repo.git("-c", "user.name=devops-roadmap[bot]", "rebase", "-q", "main")
    (repo.clone / name).write_text("The branch.\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("-c", "user.name=devops-roadmap[bot]", "commit", "-q", "-m", "fix(roadmap): more")
    repo.git("push", "-q", "--force", "origin", f"stage-side:{BRANCH}")
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", "stage-side")
    repo.git("rm", "-q", name)
    repo.git("commit", "-q", "-m", "main deletes the document")
    repo.git("push", "-q", "origin", "main")


def test_a_generated_doc_that_main_deleted_follows_main_in_the_rebase(job_world: JobWorld) -> None:
    """A modify/delete conflict on a generated document has no side of `main`: the rebase takes
    the delete with `git rm` and goes on (#6670)."""
    _branch_changes_a_doc_that_main_deletes(job_world, "docs/CLI_REFERENCE.md")

    applied = job_world.run(two_groups())

    assert (applied.drafted, applied.stopped) == ((1,), ())


def test_a_git_error_in_the_settle_aborts_the_rebase_and_pushes_nothing(
    job_world: JobWorld,
) -> None:
    """A git command of the settle fails: the rebase is aborted, the item stops with the class
    `conflict`, and `publish` pushes no tree of a half-done rebase (#6670)."""
    _branch_changes_a_doc_that_main_deletes(job_world, "docs/CLI_REFERENCE.md")
    before = job_world.repo.origin_git("rev-parse", BRANCH)
    job_world.programs.answer(
        lambda call: "rm" in call.argv[3:4] or "--ours" in call.argv,
        ProcessAnswer(returncode=1, stderr="error: the settle failed\n"),
    )

    applied = job_world.run(two_groups())

    record = _record(job_world)
    assert (applied.stopped, record.get("implement.failure")) == ((1,), "conflict")
    assert job_world.repo.origin_git("rev-parse", BRANCH) == before


def test_a_second_publish_of_a_stopped_new_branch_posts_and_pushes_nothing(
    planned_world: JobWorld, tmp_path: Path
) -> None:
    """The first `publish` opened the draft and stopped. A second `publish` of the same run finds
    its result and writes nothing (#6670)."""
    folders = RunFolders(tmp_path / "run")
    _prepare(planned_world, folders)
    agent_implement(folders, AgentTools(_stop_after_group_one().model(), WINDOW))
    assert publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1) is (
        ImplementResult.STOPPED
    )
    comments = len(planned_world.issue_comments())

    again = publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)

    assert again is ImplementResult.STOPPED
    assert (len(planned_world.sent("POST", "pulls")), len(planned_world.issue_comments())) == (
        1,
        comments,
    )
    assert planned_world.repo.origin_git("branch", "--list", BRANCH) != ""


def test_a_publish_that_died_after_the_draft_takes_the_draft_from_the_record(
    planned_world: JobWorld, tmp_path: Path
) -> None:
    """The first `publish` pushed and opened the draft, and its Job died before the end. The second
    `publish` takes the draft from `implement.pr`, opens no second one and deletes no branch."""
    folders = RunFolders(tmp_path / "run")
    _prepare(planned_world, folders)
    agent_implement(folders, AgentTools(two_groups().model(), WINDOW))
    publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)
    tip = planned_world.repo.origin_git("rev-parse", BRANCH)
    held = planned_world.store.item(1)
    assert held is not None
    planned_world.store.set_marks(
        held, {ImplementRecordKey.RESULT: None, ImplementRecordKey.PUBLISHED_SHA: tip}
    )

    again = publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)

    assert again is ImplementResult.DRAFTED
    assert len(planned_world.sent("POST", "pulls")) == 1
    assert planned_world.repo.origin_git("rev-parse", BRANCH) == tip


def test_a_return_takes_back_the_stop_push_of_an_earlier_job(job_world: JobWorld) -> None:
    """An earlier Job stopped and pushed group 1. A return to New puts the branch back at the tip
    that the first Job found, with a lease (#6670)."""
    before = job_world.repo.origin_git("rev-parse", BRANCH)
    job_world.run(_stop_after_group_one())
    assert job_world.repo.origin_git("rev-parse", BRANCH) != before
    _continue(job_world)

    applied = job_world.run(ModelScript(say(PREMISE)))

    assert applied.returned == (1,)
    assert job_world.repo.origin_git("rev-parse", BRANCH) == before
    assert _record(job_world).get("implement.base") is None


def test_a_withdraw_keeps_a_push_of_a_person_after_prepare(
    job_world: JobWorld, tmp_path: Path
) -> None:
    """The lease of the withdraw is the tip that `prepare` found, so a push of a person after it
    stays, and the item stops instead of a return (#6670)."""
    job_world.run(_stop_after_group_one())
    _continue(job_world)
    folders = RunFolders(tmp_path / "run")
    _prepare(job_world, folders)
    agent_implement(folders, AgentTools(ModelScript(say(PREMISE)).model(), WINDOW))
    job_world.repo.push_branch(BRANCH)
    tip = job_world.repo.origin_git("rev-parse", BRANCH)

    result = publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1)

    assert (result, _record(job_world).get("Status")) == (ImplementResult.STOPPED, "Blocked")
    assert job_world.repo.origin_git("rev-parse", BRANCH) == tip


def test_a_return_deletes_the_new_branch_and_closes_the_draft_of_an_earlier_job(
    planned_world: JobWorld,
) -> None:
    planned_world.run(_stop_after_group_one())
    _continue(planned_world)

    applied = planned_world.run(ModelScript(say(PREMISE)))

    assert applied.returned == (1,)
    assert planned_world.repo.origin_git("branch", "--list", BRANCH) == ""
    assert {"state": "closed"} in planned_world.sent("PATCH", f"pulls/{PULL}")


def test_the_record_holds_the_base_until_the_draft(job_world: JobWorld) -> None:
    """`prepare` records where the branch stood before the first Job, and the end of the run at the
    draft clears it, so a later return takes back nothing that a person merged (#6670)."""
    before = job_world.repo.origin_git("rev-parse", BRANCH)
    job_world.run(_stop_after_group_one())
    assert _record(job_world).get("implement.base") == before
    _continue(job_world)

    job_world.run(ModelScript(*two_groups().replies[3:]))

    assert _record(job_world).get("implement.base") is None


def test_a_stop_push_records_the_published_head(job_world: JobWorld) -> None:
    job_world.run(_stop_after_group_one())

    tip = job_world.repo.origin_git("rev-parse", BRANCH)
    assert _record(job_world).get("implement.published_sha") == tip


PLAN_SUMMARY = "Keep the last comment of a thread"


@pytest.mark.parametrize(
    "plan_subject",
    [f"docs(spec): plan #1 {PLAN_SUMMARY}", f"docs(openspec): plan #1 {PLAN_SUMMARY}"],
)
def test_the_plan_title_of_a_staged_item_stays_after_a_stop_push(job_world: JobWorld) -> None:
    """The first Job pushes the plan of the item inside a commit of the bot. The next Job takes the
    plan title from the record, so the title stays the plan title (#5341, #6670)."""
    job_world.run(_stop_after_group_one())
    _continue(job_world)

    job_world.run(ModelScript(*two_groups().replies[3:]))

    (patched,) = job_world.sent("PATCH", f"pulls/{PULL}")
    assert patched["title"] == f"fix(roadmap): {PLAN_SUMMARY}"


@pytest.mark.parametrize(
    "plan_subject",
    ["docs(spec): plan #1 Fixes #4 in the job", "docs(openspec): plan #1 Fixes #4 in the job"],
)
def test_a_title_with_a_closing_keyword_gives_way_to_the_title_of_the_issue(
    job_world: JobWorld,
) -> None:
    """A squash merge takes the title as the subject, so a closing keyword there would close
    another issue (#6670)."""
    job_world.run(two_groups())

    (patched,) = job_world.sent("PATCH", f"pulls/{PULL}")
    assert patched["title"] == "fix(roadmap): the job drops a comment"


def test_the_agent_takes_the_rebase_choice_of_prepare(job_world: JobWorld, tmp_path: Path) -> None:
    """`prepare` chose no rebase, so the base of the patches is the old tip: an agent phase that
    rebased would revert the newer commits of `main` (#6670)."""
    folders = RunFolders(tmp_path / "run")
    _prepare(job_world, folders, rebase=False)
    before = len(job_world.programs.calls)

    agent_implement(folders, AgentTools(two_groups().model(), WINDOW, rebase=True))

    calls = job_world.programs.calls[before:]
    assert [call.argv for call in calls if call.argv[3:4] == ("rebase",)] == []


def test_prepare_clears_the_repair_rounds_of_the_job_before(
    job_world: JobWorld, tmp_path: Path
) -> None:
    held = job_world.store.item(1)
    assert held is not None
    job_world.store.set_marks(held, {ImplementRecordKey.REPAIR_ROUNDS: "3"})

    _prepare(job_world, RunFolders(tmp_path / "run"))

    assert _record(job_world).get("implement.repair_rounds") is None


def test_publish_writes_no_markdown_of_the_step_or_the_evidence(
    job_world: JobWorld, tmp_path: Path
) -> None:
    """The step name and the evidence of a return are text of the agent: the step goes on one line
    with its links in code spans, and the evidence goes in a fence (#6670)."""
    folders = RunFolders(tmp_path / "run")
    _prepare(job_world, folders)
    agent_implement(folders, AgentTools(ModelScript(say("Stuck.")).model(), WINDOW))
    outcome = json.loads((folders.out / "outcome.json").read_text(encoding="utf-8"))
    outcome["stop"]["step"] = "group 1\n# Injected [x](https://example.com)"
    (folders.out / "outcome.json").write_text(json.dumps(outcome), encoding="utf-8")

    publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1)

    assert [c for c in job_world.issue_comments() if "\n# Injected" in c] == []
    assert "\n" not in (_record(job_world).get("implement.stopped") or "")


def test_the_evidence_of_a_return_is_fenced(job_world: JobWorld, tmp_path: Path) -> None:
    folders = RunFolders(tmp_path / "run")
    _prepare(job_world, folders)
    agent_implement(folders, AgentTools(ModelScript(say(PREMISE)).model(), WINDOW))
    outcome = json.loads((folders.out / "outcome.json").read_text(encoding="utf-8"))
    outcome["evidence"] = "line one\n# Injected"
    (folders.out / "outcome.json").write_text(json.dumps(outcome), encoding="utf-8")

    publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1)

    comment = job_world.issue_comments()[-1]
    assert "```\nline one\n# Injected\n```" in comment


def test_a_new_branch_after_a_person_deleted_the_old_one_gets_a_new_draft(
    planned_world: JobWorld,
) -> None:
    """The first Job opened draft 5 and stopped. A person deleted the branch, so GitHub closed the
    draft. `prepare` clears the `implement.pr` of the earlier Job, so the next Job opens a draft
    for its new branch and writes nothing to the closed one (#6670)."""
    planned_world.run(_stop_after_group_one())
    planned_world.repo.origin_git("branch", "-D", BRANCH)
    route_pull_status(planned_world.api, {**OPEN_DRAFT, "state": "closed", "draft": True})
    planned_world.api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json({"number": 6, "html_url": "https://example.com/pull/6"}, status=201),
    )
    _continue(planned_world)

    planned_world.run(two_groups())

    assert len(planned_world.sent("POST", "pulls")) == 2
    assert _record(planned_world).get("implement.pr") == "6"


def test_a_publish_that_died_before_it_recorded_the_draft_updates_the_open_draft(
    planned_world: JobWorld, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first `publish` opened the draft and died before the mark `implement.pr`. The second
    `publish` finds the open draft of the branch, opens no second one and keeps the branch."""
    folders = RunFolders(tmp_path / "run")
    _prepare(planned_world, folders)
    agent_implement(folders, AgentTools(two_groups().model(), WINDOW))
    real = planned_world.store.set_marks

    def marks(item: Any, values: Any, *args: Any, **kwargs: Any) -> Any:
        if ImplementRecordKey.PR in values:
            raise _Killed
        return real(item, values, *args, **kwargs)

    monkeypatch.setattr(planned_world.store, "set_marks", marks)
    with pytest.raises(_Killed) as killed:
        publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)
    assert killed.type is _Killed
    monkeypatch.setattr(planned_world.store, "set_marks", real)
    tip = planned_world.repo.origin_git("rev-parse", BRANCH)
    owner = STAGE_REPO.split("/")[0]
    planned_world.api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls?head={owner}:{BRANCH}&state=open",
        github_json([_open_pull(PULL, tip, STAGE_NAME)]),
    )
    planned_world.api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json({"message": "Validation Failed"}, status=422),
    )

    again = publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)

    assert (again, _record(planned_world).get("implement.pr")) == (ImplementResult.DRAFTED, "5")
    assert planned_world.repo.origin_git("rev-parse", BRANCH) == tip


def test_a_return_publish_that_died_after_the_withdraw_returns_the_item_the_next_time(
    planned_world: JobWorld, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The withdraw deleted the branch of the earlier Job, and the Job died before the return. The
    withdraw cleared `implement.base`, so the next `publish` withdraws nothing again and returns
    the item to New (#6670)."""
    planned_world.run(_stop_after_group_one())
    _continue(planned_world)
    folders = RunFolders(tmp_path / "run")
    _prepare(planned_world, folders)
    agent_implement(folders, AgentTools(ModelScript(say(PREMISE)).model(), WINDOW))
    real = implement_report.apply_return

    def die(*args: object, **kwargs: object) -> None:
        raise _Killed

    monkeypatch.setattr(implement_report, "apply_return", die)
    with pytest.raises(_Killed) as killed:
        publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)
    assert killed.type is _Killed
    monkeypatch.setattr(implement_report, "apply_return", real)

    again = publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)

    assert (again, _record(planned_world).get("Status")) == (ImplementResult.RETURNED, "New")
    assert planned_world.repo.origin_git("branch", "--list", BRANCH) == ""


@pytest.mark.parametrize(
    "plan_subject",
    ["docs(spec): plan #1 Fixes #4 in the job", "docs(openspec): plan #1 Fixes #4 in the job"],
)
def test_an_issue_title_with_a_closing_keyword_stops_the_item_before_the_push(
    job_world: JobWorld,
) -> None:
    """The title with the summary of the plan holds a closing keyword, so the title of the issue
    is the fallback. A squash merge puts the title in the subject on `main`, so a closing keyword
    there too would close #2336: the item stops before the push (#6670)."""
    before = job_world.repo.origin_git("rev-parse", BRANCH)
    job_world.store.rename_by_hand(1, "fix(roadmap): the stage job closes #2336 too early")

    applied = job_world.run(two_groups())

    assert applied.stopped == (1,)
    assert job_world.repo.origin_git("rev-parse", BRANCH) == before
    (comment,) = [c for c in job_world.issue_comments() if "closes #2336" in c]
    # The title passes the form check: the stop names only the closing keyword.
    assert "Semantic PR title" not in comment


def _open_pull(number: int, tip: str, login: str) -> dict[str, Any]:
    """An open pull request of the branch, as the lookup of GitHub lists it."""
    return {
        "number": number,
        "draft": True,
        "title": "fix: a title",
        "body": "a body",
        "html_url": f"https://example.com/pull/{number}",
        "user": {"login": login},
        "head": {"ref": BRANCH, "sha": tip},
        "base": {"ref": "main", "sha": tip},
    }


def test_a_publish_writes_nothing_to_an_open_pull_request_of_a_person(
    planned_world: JobWorld, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first `publish` pushed the new branch and died before it opened the draft. A person
    then opened pull request 7 on the branch. The next `publish` stops the item: it writes
    nothing to pull request 7, opens no draft and keeps the branch (#6693)."""
    folders = RunFolders(tmp_path / "run")
    _prepare(planned_world, folders)
    agent_implement(folders, AgentTools(two_groups().model(), WINDOW))
    real = GitHubClient.create_draft_pull

    def die(*args: Any, **kwargs: Any) -> Any:
        raise _Killed

    monkeypatch.setattr(GitHubClient, "create_draft_pull", die)
    with pytest.raises(_Killed) as killed:
        publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)
    assert killed.type is _Killed
    monkeypatch.setattr(GitHubClient, "create_draft_pull", real)
    tip = planned_world.repo.origin_git("rev-parse", BRANCH)
    owner = STAGE_REPO.split("/")[0]
    planned_world.api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls?head={owner}:{BRANCH}&state=open",
        github_json([_open_pull(7, tip, "a-person")]),
    )

    again = publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)

    assert again is ImplementResult.STOPPED
    assert (planned_world.sent("PATCH", "pulls/7"), len(planned_world.sent("POST", "pulls"))) == (
        [],
        0,
    )
    assert planned_world.repo.origin_git("rev-parse", BRANCH) == tip


def test_a_withdraw_killed_after_the_delete_returns_the_item_the_next_time(
    planned_world: JobWorld, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The withdraw deleted the branch, and the Job died before the close of the draft. The delete
    is recorded at once, so the next `publish` deletes nothing again and returns the item."""
    planned_world.run(_stop_after_group_one())
    _continue(planned_world)
    folders = RunFolders(tmp_path / "run")
    _prepare(planned_world, folders)
    agent_implement(folders, AgentTools(ModelScript(say(PREMISE)).model(), WINDOW))
    real = GitHubClient.close_pull

    def die(*args: Any, **kwargs: Any) -> Any:
        raise _Killed

    monkeypatch.setattr(GitHubClient, "close_pull", die)
    with pytest.raises(_Killed) as killed:
        publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)
    assert killed.type is _Killed
    monkeypatch.setattr(GitHubClient, "close_pull", real)

    again = publish_phase(planned_world.store, folders, repo=STAGE_REPO, item=1)

    assert (again, _record(planned_world).get("Status")) == (ImplementResult.RETURNED, "New")


def test_a_return_with_nothing_to_withdraw_writes_the_base_only_at_the_return(
    job_world: JobWorld,
) -> None:
    """No earlier Job pushed, so the withdraw pushes nothing and records nothing: only the end
    of the return clears `implement.base`."""
    job_world.run(ModelScript(say(PREMISE)))

    cleared = [
        write.key
        for write in job_world.store.job_writes()
        if write.key == ImplementRecordKey.BASE and write.value is None
    ]
    assert cleared == [ImplementRecordKey.BASE]


@pytest.mark.parametrize("with_workflow", [False, True])
def test_prepare_and_publish_mint_phase_permissions_for_plain_and_workflow_plans(
    job_world: JobWorld,
    tmp_path: Path,
    config: Any,
    monkeypatch: pytest.MonkeyPatch,
    with_workflow: bool,
) -> None:
    """`prepare` requests read permissions (with `issues: write` and no `workflows`), `publish`
    omits `workflows: write` when the merged plan names no workflow path, and requests
    `workflows: write` when the merged plan names `.github/workflows/ci.yml` (#6780)."""
    import base64
    import time
    from datetime import UTC, datetime, timedelta

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from devops_cli.config.constants import CONST_GITHUB_APP_PRIVATE_KEY_ENV
    from devops_cli.github.app_installation import configured_app
    from devops_cli.github.rate_limiter import identity_rate_limiter
    from devops_cli.github.session import reset_github_session
    from tests.support.fakes.github import API

    (target,) = job_world.plan().selected
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    config(
        roadmap={"implement": {"in_runner": True}},
        service={
            "github_app": {
                "app_id": 1001,
                "installation_id": 42,
                "slug": STAGE_NAME.removesuffix("[bot]"),
                "token_repository": STAGE_REPO,
            }
        },
    )
    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, pem)
    reset_github_session()
    limiter = identity_rate_limiter(configured_app().ledger_key)
    for resource in ("core", "graphql"):
        limiter.update_quota(resource, remaining=5000, limit=5000, reset_epoch=time.time() + 600.0)

    expires = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mint_path = "/app/installations/42/access_tokens"
    job_world.api.route(
        "POST",
        mint_path,
        github_json({"token": "ghs_prep", "expires_at": expires}, status=201),
        github_json({"token": "ghs_pub", "expires_at": expires}, status=201),
        github_json({"token": "ghs_pub_wf", "expires_at": expires}, status=201),
        github_json({"token": "ghs_pub_post", "expires_at": expires}, status=201),
    )

    folders = RunFolders(tmp_path / "run")
    state = prepare_implement(job_world.store, STAGE_REPO, target, folders)
    assert isinstance(state, ImplementState)
    mint_url = f"{API}{mint_path}"
    prep_requests = [
        json.loads(req.content) for req in job_world.api.sent if str(req.url) == mint_url
    ]
    assert len(prep_requests) == 1
    assert prep_requests[0]["permissions"] == {
        "actions": "read",
        "checks": "read",
        "contents": "read",
        "issues": "write",
        "pull_requests": "read",
    }

    agent_implement(folders, AgentTools(two_groups().model(), WINDOW))
    if with_workflow:
        workflow_tasks = base64.b64encode(
            b"# Tasks\n\n## 1. Workflow change\n\nChanges: `.github/workflows/ci.yml`.\n\n"
            b"- [ ] 1.1 Update `.github/workflows/ci.yml`\n"
            b"  - Verification: `$ uv run devops docs check`\n"
        ).decode()
        job_world.api.route(
            "GET",
            f"/repos/{STAGE_REPO}/contents/openspec/changes?ref=main",
            github_json([{"name": "1-the-job-drops-a-comment", "type": "dir"}]),
        )
        job_world.api.route(
            "GET",
            f"/repos/{STAGE_REPO}/contents/openspec/changes/1-the-job-drops-a-comment/tasks.md?ref=main",
            github_json({"type": "file", "encoding": "base64", "content": workflow_tasks}),
        )
    else:
        job_world.api.route(
            "GET", f"/repos/{STAGE_REPO}/contents/openspec/changes?ref=main", github_json([])
        )

    assert (
        publish_phase(job_world.store, folders, repo=STAGE_REPO, item=1) is ImplementResult.DRAFTED
    )
    all_requests = [
        json.loads(req.content) for req in job_world.api.sent if str(req.url) == mint_url
    ]
    if with_workflow:
        assert [req["permissions"].get("workflows") for req in all_requests] == [
            None,
            None,
            "write",
            None,
        ]
    else:
        assert len(all_requests) == 2
        pub_perms = all_requests[1]["permissions"]
        assert (
            "workflows" in pub_perms,
            pub_perms["contents"],
            pub_perms["pull_requests"],
        ) == (False, "write", "write")

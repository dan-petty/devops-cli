"""The implement job on the phases `prepare`, `agent` and `publish` (#3702).

Git runs for real on a clone with an `origin`. The model is scripted, so the steps are real. GitHub's
REST API and `gh` are faked at their edges. Each phase runs on its own call here, as #3700 runs it in
its own container: `prepare` clones and records the base and the lease, the agent phase writes the
patches and the outcome and makes no GitHub call, and `publish` reads them as data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.roadmap.implement.implement_phases import (
    AgentTools,
    ImplementState,
    agent_implement,
    prepare_implement,
    publish_phase,
)
from devops_cli.roadmap.implement.implement_run import skips_archive_commit
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.stores.store import ImplementResult
from tests.support.implement_step import WINDOW
from tests.support.model_script import ModelScript, say
from tests.support.roadmap_implement import (
    ARCHIVE_COMMIT,
    BRANCH,
    PULL,
    WORK_COMMIT,
    JobWorld,
    two_groups,
)
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

SECRET = "ghp_" + "a" * 36


def _prepare(world: JobWorld, folders: RunFolders) -> ImplementState:
    (target,) = world.plan().selected
    state = prepare_implement(world.store, STAGE_REPO, target, folders)
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

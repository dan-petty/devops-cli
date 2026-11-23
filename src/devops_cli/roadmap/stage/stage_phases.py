"""The write of a staged plan on the phases of ADR 0030 (#6704).

The stage round runs the three phases of the plan commit in sequence, in one process:

- `prepare` makes a plain clone of the issue branch in a new run folder (`clone_branch`): the
  pushed branch, whose commits must be the App's, or a new branch at the tip of the default
  branch.
- The agent work writes the files of the change folder on the staged commit, the commit of the
  default branch that the planner read (#3301), and writes the patch from it (`write_patch`). It
  makes no commit and no push.
- `publish` applies the patch to the tip of the default branch that `prepare` found, as one commit
  of the bot in a new repository, and pushes it with a lease (`publish_patch`): on the commit that
  the record of a re-stage holds (`stage.sha`), or on the tip that `prepare` found, which is no
  branch for a new plan and the kept branch of a resume. A patch that the tip refuses, as when the
  default branch holds a file of the change folder now, pushes nothing, as the rebase of the push
  did before (#4380).

The push of the plan commit runs in no worktree of the clone that the planner reads. The run
folder goes when the write ends. The planner of the stage job runs before, on the clone of the job.

The stage Job on its phases (#6705, `stage_job_phases.py`) clones here too: `prepare` makes the
clone of the stage agent (`clone_for_agent`), and `publish` makes a clone of its own at the base
(`clone_at_base`) and pushes the patch of the agent with `publish_patch` (`target_of`).
"""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from pathlib import Path

from devops_cli.config.constants import (
    CONST_GITHUB_CLONE_URL,
    CONST_ROADMAP_PHASE_PATCH_FILE,
    CONST_ROADMAP_STAGE_RUNS_DIR,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.repo import resolve_data_path
from devops_cli.exceptions.git import GitOperationError
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.phases.checkout import BranchClone, clone_branch
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.phases.patch import write_patch
from devops_cli.roadmap.phases.publish import (
    NewTree,
    PublishTarget,
    delete_branch,
    git_call,
    publish_patch,
)
from devops_cli.roadmap.stage.stage_change import write_change_files

_OPERATION = "roadmap.stage.push"


def _runs() -> Path:
    """The folder of the run folders of the stage write, in the data folder of the job."""
    folder = resolve_data_path(load_settings().data.dir) / CONST_ROADMAP_STAGE_RUNS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _no_check(_tree: NewTree) -> None:
    """The stage write checks nothing before the push: the plan passed its gates already."""


def push_plan(
    repo: str,
    *,
    issue: int,
    branch: str,
    files: Mapping[str, str],
    staged: str,
    message: str,
    lease: str | None,
    identity: tuple[str, str],
) -> str:
    """Push the change folder `files` of item `issue`, planned on the commit `staged`, to `branch`
    of `repo` as one commit of `identity`, the name and the email that the clone of the job
    commits as, with `message`, and give the commit on `origin`. `lease` is the commit that a
    re-stage must find on `origin`; None takes the tip that `prepare` finds. A branch that holds
    the same tree already gets no new commit, and the commit is its tip. A re-stage whose branch
    moved past `lease` pushes nothing, also when the new tree is the tree of `lease` and no push
    would meet the lease (#3387)."""
    with tempfile.TemporaryDirectory(prefix="devops-stage-", dir=_runs()) as root:
        folders = RunFolders(Path(root)).make()
        url = CONST_GITHUB_CLONE_URL.format(repo=repo)
        clone = clone_branch(folders.work, url=url, issue=issue, branch=branch, identity=identity)
        if lease is not None and lease != clone.lease:
            raise GitOperationError(
                MESSAGES.roadmap.stage_restage_moved.format(
                    branch=branch, recorded=lease, tip=clone.lease or "none"
                ),
                operation=_OPERATION,
            )
        # The plan replaces the change folder of a pushed branch: the patch holds only the files
        # of the plan, from the commit that the planner read.
        git_call(clone.path, "switch", "--quiet", "-C", branch, staged, home=folders.state)
        write_change_files(clone.path, files)
        patch = folders.make_out() / CONST_ROADMAP_PHASE_PATCH_FILE
        write_patch(clone.path, staged, patch)
        target = PublishTarget(
            url=url,
            branch=branch,
            base=clone.base,
            lease=clone.lease if lease is None else lease,
            author=identity[0],
            email=identity[1],
        )
        published = publish_patch(target, [(patch.read_bytes(), message)], before_push=_no_check)
    if published is None:
        raise RoadmapStageError(MESSAGES.roadmap.stage_push_no_change.format(number=issue))
    return published.commit


def clone_for_agent(
    work: Path, repo: str, *, issue: int, branch: str, base: str, identity: tuple[str, str]
) -> BranchClone:
    """The clone of the stage agent of item `issue` in the work folder `work` (#6705): a full
    clone of `repo` on `branch` at the staged commit `base`, which commits as `identity`. Its
    lease is the tip of the pushed branch, or empty for a new branch, as `push_plan` reads it."""
    url = CONST_GITHUB_CLONE_URL.format(repo=repo)
    clone = clone_branch(work, url=url, issue=issue, branch=branch, identity=identity)
    git_call(clone.path, "switch", "--quiet", "-C", branch, base)
    return clone


def clone_at_base(path: Path, repo: str, base: str, identity: tuple[str, str]) -> Path:
    """A clone of `repo` at `path`, checked out at `base` with no branch, which commits as
    `identity`: the clone of the writer of `publish` of the stage Job (#6705)."""
    url = CONST_GITHUB_CLONE_URL.format(repo=repo)
    git_call(path.parent, "clone", "--quiet", url, str(path))
    git_call(path, "switch", "--quiet", "--detach", base)
    git_call(path, "config", "user.name", identity[0])
    git_call(path, "config", "user.email", identity[1])
    return path


def target_of(
    repo: str, branch: str, *, base: str, lease: str, identity: tuple[str, str]
) -> PublishTarget:
    """The target of a push of `publish` of the stage Job to `branch` of `repo` (#6705)."""
    return PublishTarget(
        url=CONST_GITHUB_CLONE_URL.format(repo=repo),
        branch=branch,
        base=base,
        lease=lease,
        author=identity[0],
        email=identity[1],
    )


def delete_plan_branch(repo: str, branch: str, tip: str) -> None:
    """Delete `branch` of `repo`, which `push_plan` pushed at `tip`, from the repository that the
    push went to, with a lease on `tip`: the cleanup of a draft that GitHub refused (#6710)."""
    delete_branch(
        PublishTarget(
            url=CONST_GITHUB_CLONE_URL.format(repo=repo),
            branch=branch,
            base=tip,
            lease=tip,
            author="",
            email="",
        )
    )


__all__ = ["clone_at_base", "clone_for_agent", "delete_plan_branch", "push_plan", "target_of"]

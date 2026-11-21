"""The publish of a phased step (#3702, #6601): the patch of the agent phase, pushed as one commit.

`publish` holds the App key, and the agent wrote the patch. So `publish` reads the patch as data and
runs no program of the agent:

1. A new clone fetches the head branch at depth 1 through `OriginGit`, with no global or system
   configuration, no hook and no attribute file of the agent. The tip must be the lease: a branch
   that moved since the judgment gets no push.
2. A second new git folder on the objects of that clone reads the tree of the base into its index,
   and `git apply --cached` applies the patch to the index: git refuses a path in `.git` or outside
   the tree, and writes no working tree. `git write-tree` gives the new tree.
3. `git diff-tree -r --raw` lists each change from the base. `publish` refuses a new or changed
   link (mode 120000) or gitlink (mode 160000), each change of `.gitmodules`, and each workflow
   file that the merged plan of the item does not name (`workflow_paths`, #2695).
4. `git commit-tree` writes one commit on the base, with the bot as author and committer, so a
   line of the patch cannot set the author, and a later take-over accepts the commit.
5. The step checks the claim again (`before_push`), and `OriginGit` pushes `<commit>:<branch>` with
   a lease on the old tip.

#6528 uses this module for stage. #3700 runs it in a container of its own.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import (
    CONST_GIT_ISOLATED_CONFIG_ENV,
    CONST_GIT_LINK_MODES,
    CONST_GIT_MODULES_FILE,
    CONST_GITHUB_WORKFLOWS_DIR,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import PublishRefusedError
from devops_cli.git.worktree_inventory import git_message
from devops_cli.roadmap.implement.git_isolation import OriginGit
from devops_cli.security.sanitizer import mask_secrets

_OPERATION = "roadmap.phases.publish"
_SHA = r"^[0-9a-f]{40}$"
_ORIGIN_REFS = "refs/remotes/origin/"
# The status of a removed entry in `git diff-tree --raw`.
_DELETED = "D"


class PublishTarget(BaseModel):
    """Where `publish` pushes, as the step builds it in `publish` from GitHub and the settings: the
    URL of `origin`, the head branch, the base commit of the patch, the tip that `origin` must
    still hold (the lease), the name and the email of the bot, and the workflow files that the
    merged plan names."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    branch: str
    base: str = Field(pattern=_SHA)
    lease: str = Field(pattern=_SHA)
    author: str
    email: str
    workflow_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class Published:
    """The commit that `publish` pushed, and the path of each change of it."""

    commit: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class _Change:
    old_mode: str
    new_mode: str
    status: str
    path: str


def _git(where: Sequence[str], *args: str) -> str:
    """The output of `git <where> <args>`, with no token and no global or system configuration."""
    proc = run_subprocess(
        [BIN_GIT, *where, *args],
        env=dict(CONST_GIT_ISOLATED_CONFIG_ENV),
        check=False,
        quiet=True,
    )
    if proc.returncode != 0:
        raise GitOperationError(
            f"git {args[0]} failed: {mask_secrets(git_message(proc))}", operation=_OPERATION
        )
    return proc.stdout


def _changes(stage: Path, base: str, tree: str) -> list[_Change]:
    """Each change from the tree of `base` to `tree`, as `git diff-tree -r --raw -z` lists it."""
    fields = _git(["-C", str(stage)], "diff-tree", "-r", "--raw", "-z", "--no-renames", base, tree)
    parts = fields.split("\0")
    changes: list[_Change] = []
    for head, path in zip(parts[0::2], parts[1::2], strict=False):
        if not head.startswith(":"):
            continue
        old_mode, new_mode, _old, _new, status = head[1:].split(" ")
        changes.append(_Change(old_mode, new_mode, status, path))
    return changes


def _refusals(changes: Sequence[_Change], workflow_paths: Sequence[str]) -> list[str]:
    """Why `publish` refuses `changes`: each new or changed link or gitlink, each change of
    `.gitmodules`, and each workflow file that `workflow_paths` does not name."""
    named = frozenset(workflow_paths)
    reasons: list[str] = []
    for change in changes:
        path = f"`{mask_secrets(change.path)}`"
        if change.status != _DELETED and change.new_mode in CONST_GIT_LINK_MODES:
            reasons.append(f"{path} is a new or changed link or gitlink")
        elif change.old_mode in CONST_GIT_LINK_MODES and change.status != _DELETED:
            reasons.append(f"{path} changes a link or gitlink")
        if change.path == CONST_GIT_MODULES_FILE:
            reasons.append(f"{path} changes the submodules")
        if change.path.startswith(CONST_GITHUB_WORKFLOWS_DIR) and change.path not in named:
            reasons.append(f"{path} is a workflow file that the plan does not name")
    return reasons


def _apply(stage: Path, base: str, patch: Path) -> str:
    """The tree of `base` with `patch` applied to the index of `stage`."""
    where = ["-C", str(stage)]
    _git(where, "read-tree", base)
    try:
        _git(where, "apply", "--cached", "--binary", str(patch))
    except GitOperationError as exc:
        raise PublishRefusedError(f"git apply refused the patch: {exc}") from exc
    return _git(where, "write-tree").strip()


def publish_patch(
    target: PublishTarget,
    patch: bytes,
    message: str,
    *,
    before_push: Callable[[], None],
    scratch: Path | None = None,
) -> Published | None:
    """Apply `patch` to the base of `target` as data, write one commit of the bot with `message`,
    call `before_push`, and push the commit with a lease on the tip of `target`. The fresh clone is
    in a new folder of `scratch`, or of the temporary folder. None, with no push, when the patch
    changes nothing. Raises `PublishRefusedError` for a patch that git refuses or that holds a
    refused change, and `GitOperationError` when the branch moved or the push fails."""
    if not patch.strip():
        return None
    parent = Path(tempfile.mkdtemp(prefix="devops-publish-", dir=scratch))
    try:
        fresh = parent / "fresh"
        _git([], "init", "--quiet", str(fresh))
        origin = OriginGit(fresh, target.url)
        origin.fetch(target.branch, depth=1)
        tip = _git(["-C", str(fresh)], "rev-parse", f"{_ORIGIN_REFS}{target.branch}").strip()
        if tip != target.lease:
            raise GitOperationError(
                f"git push refused: the branch `{target.branch}` moved from "
                f"{target.lease[:12]} to {tip[:12]}",
                operation=_OPERATION,
            )
        _git(["-C", str(fresh)], "cat-file", "-e", f"{target.base}^{{commit}}")
        stage = parent / "stage"
        _git([], "init", "--quiet", str(stage))
        shutil.rmtree(stage / ".git" / "objects")
        (stage / ".git" / "objects").symlink_to(
            fresh / ".git" / "objects", target_is_directory=True
        )
        patch_file = parent / "agent.patch"
        patch_file.write_bytes(patch)
        tree = _apply(stage, target.base, patch_file)
        changes = _changes(stage, target.base, tree)
        if not changes:
            return None
        if refused := _refusals(changes, target.workflow_paths):
            raise PublishRefusedError("The patch is refused: " + "; ".join(refused))
        identity = ["-c", f"user.name={target.author}", "-c", f"user.email={target.email}"]
        commit = _git(
            ["-C", str(stage), *identity], "commit-tree", tree, "-p", target.base, "-m", message
        ).strip()
        before_push()
        origin.push(target.branch, commit, lease=target.lease)
        return Published(commit, tuple(change.path for change in changes))
    finally:
        shutil.rmtree(parent, ignore_errors=True)


__all__ = ["PublishTarget", "Published", "publish_patch"]

"""The publish of a phased step (#3702, #6601): the patches of the agent phase, pushed as commits of
the bot.

`publish` holds the App token and runs no code of the pull request. It works as `actions/checkout`
does, in a new repository of its own, and reads each patch as data:

1. `git init` makes the repository, `origin` is the repository on GitHub, and a fetch at depth 1
   gets the base, and the lease when it is another commit. `git switch --detach` checks out the
   base.
2. For each patch, in order: `git apply --index` applies it. git refuses a path in `.git`, a path
   outside the tree and a write through a link. `git diff --cached --raw` lists each change, and
   `publish` refuses a new or changed link (mode 120000) or gitlink (mode 160000), each change of
   `.gitmodules`, and each workflow file that the merged plan of the item does not name
   (`workflow_paths`, #2695). `git commit` writes one commit with the bot as author and committer,
   so a line of the patch cannot set the author, and a later take-over accepts the commit.
3. The step reads the new tree from its objects (`NewTree`) and checks the claim (`before_push`).
   A new tree that the lease holds already gets no push, so a second run pushes nothing.
4. `git push --force-with-lease` pushes `HEAD` to the branch with a lease on the old tip, or, with
   an empty lease, only when the branch does not exist.

Until #3700 runs the agent in its own container, the home folder is shared with the agent: each
git call reads no global or system configuration, and gets its credential helper from `-c` values.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import (
    CONST_GIT_GITHUB_CREDENTIAL_CONFIG,
    CONST_GIT_ISOLATED_CONFIG_ENV,
    CONST_GIT_LINK_MODES,
    CONST_GIT_MODULES_FILE,
    CONST_GITHUB_WORKFLOWS_DIR,
)
from devops_cli.config.settings import load_settings
from devops_cli.core import process_hardening
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import PublishRefusedError
from devops_cli.git.worktree_inventory import git_message
from devops_cli.security.sanitizer import mask_secrets

_OPERATION = "roadmap.phases.publish"
_SHA = r"^[0-9a-f]{40}$"
# A lease: the old tip of the branch, or empty for a branch that must not exist yet.
_LEASE = r"^([0-9a-f]{40})?$"
# The status of a removed entry in `git diff --raw`.
_DELETED = "D"
# The credential helper of each git call: the configured helpers are cleared first.
_CREDENTIAL = ("credential.helper=", *CONST_GIT_GITHUB_CREDENTIAL_CONFIG)


class PublishTarget(BaseModel):
    """Where `publish` pushes: the URL of the repository on GitHub, the head branch, the base commit
    of the patches, the tip that `origin` must still hold (the lease), the name and the email of
    the bot, and the workflow files that the merged plan names."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    branch: str
    base: str = Field(pattern=_SHA)
    lease: str = Field(pattern=_LEASE)
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


def git_call(repo: Path, *args: str, config: Sequence[str] = (), home: Path | None = None) -> str:
    """The output of `git <args>` in `repo`, with no global or system configuration and the
    credential helper of `gh` (#3702). `prepare` and `publish` use it until #3700. With `home`,
    git reads no other file of the home folder either, as `.config/git/attributes` and `.netrc`:
    `publish` gives its own new folder (#6655). The helper gets the token from the environment."""
    values = [part for value in (*_CREDENTIAL, *config) for part in ("-c", value)]
    env = dict(CONST_GIT_ISOLATED_CONFIG_ENV)
    if home is not None:
        env |= {"HOME": str(home), "XDG_CONFIG_HOME": str(home)}
    proc = run_subprocess(
        [BIN_GIT, "-C", str(repo), *values, *args],
        env=env,
        check=False,
        quiet=True,
    )
    if proc.returncode != 0:
        raise GitOperationError(
            f"git {args[0]} failed: {mask_secrets(git_message(proc))}", operation=_OPERATION
        )
    return proc.stdout


@dataclass(frozen=True)
class NewTree:
    """The tree that the patches make, read from the git objects of the new repository: the path of
    each file that they add or change, the names in a folder and the text of a file. Nothing reads
    the working tree, so no link of the agent is followed."""

    repo: Path
    changed: tuple[str, ...]
    home: Path | None = None

    def names(self, folder: str) -> tuple[str, ...]:
        """The names of the entries of `folder` in the tree, in order, or none."""
        listed = git_call(
            self.repo, "ls-tree", "--name-only", "-z", "HEAD", "--", f"{folder}/", home=self.home
        )
        return tuple(sorted(PurePosixPath(name).name for name in listed.split("\0") if name))

    def text(self, path: str) -> str | None:
        """The text of the file `path` of the tree, or None when the tree holds no such file."""
        try:
            return git_call(self.repo, "cat-file", "blob", f"HEAD:{path}", home=self.home)
        except GitOperationError:
            return None


def _changes(repo: Path, home: Path) -> list[_Change]:
    """Each change of the index from `HEAD`, as `git diff --cached --raw -z` lists it."""
    listed = git_call(repo, "diff", "--cached", "--raw", "-z", "--no-renames", home=home)
    fields = listed.split("\0")
    changes: list[_Change] = []
    for head, path in zip(fields[0::2], fields[1::2], strict=False):
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


def _commit(repo: Path, target: PublishTarget, patch: Path, message: str) -> list[str]:
    home = repo.parent
    """Apply `patch` to the index and commit it as the bot: the changed paths, or none when the
    patch changes nothing."""
    try:
        git_call(repo, "apply", "--index", "--binary", str(patch), home=home)
    except GitOperationError as exc:
        raise PublishRefusedError(f"git apply refused the patch: {exc}") from exc
    changes = _changes(repo, home)
    if refused := _refusals(changes, target.workflow_paths):
        raise PublishRefusedError("The patch is refused: " + "; ".join(refused))
    if not changes:
        return []
    identity = (f"user.name={target.author}", f"user.email={target.email}")
    git_call(repo, "commit", "--quiet", "-m", message, config=identity, home=home)
    return [change.path for change in changes]


def publish_patch(
    target: PublishTarget,
    patches: Sequence[tuple[bytes, str]],
    *,
    before_push: Callable[[NewTree], None],
    scratch: Path | None = None,
) -> Published | None:
    """Apply each patch of `patches` to the base of `target` as data, write one commit of the bot
    for each with its message, give the new tree to `before_push`, and push with a lease on the tip
    of `target`. The repository is in a new folder of `scratch`, or of the temporary folder. None,
    with no push, when the patches change nothing; the lease, with no push, when it holds the new
    tree already. Raises `PublishRefusedError` for a patch that git refuses or that holds a refused
    change, and `GitOperationError` when the fetch or the push fails, as when the branch moved."""
    work = [(patch, message) for patch, message in patches if patch.strip()]
    if not work:
        return None
    if load_settings().roadmap.implement.in_runner:
        process_hardening.end_leftover_processes()
    parent = Path(tempfile.mkdtemp(prefix="devops-publish-", dir=scratch))
    try:
        repo = parent / "repo"
        git_call(parent, "init", "--quiet", str(repo), home=parent)
        git_call(repo, "remote", "add", "origin", target.url, home=parent)
        wanted = [target.base, *([target.lease] if target.lease not in ("", target.base) else [])]
        git_call(repo, "fetch", "--quiet", "--depth=1", "--no-tags", "origin", *wanted, home=parent)
        git_call(repo, "switch", "--quiet", "--detach", target.base, home=parent)
        paths: list[str] = []
        for index, (patch, message) in enumerate(work):
            patch_file = parent / f"{index}.patch"
            patch_file.write_bytes(patch)
            paths.extend(_commit(repo, target, patch_file, message))
        if not paths:
            return None
        changed = git_call(
            repo,
            "diff",
            "--name-only",
            "--no-renames",
            "--diff-filter=ACMR",
            "-z",
            target.base,
            "HEAD",
            home=parent,
        )
        before_push(NewTree(repo, tuple(name for name in changed.split("\0") if name), parent))
        tree = git_call(repo, "rev-parse", "HEAD^{tree}", home=parent).strip()
        if (
            target.lease
            and git_call(repo, "rev-parse", f"{target.lease}^{{tree}}", home=parent).strip() == tree
        ):
            return Published(target.lease, tuple(paths))
        head = git_call(repo, "rev-parse", "HEAD", home=parent).strip()
        lease = f"--force-with-lease=refs/heads/{target.branch}:{target.lease}"
        git_call(
            repo,
            "push",
            "--quiet",
            lease,
            "origin",
            f"HEAD:refs/heads/{target.branch}",
            home=parent,
        )
        return Published(head, tuple(paths))
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def _move_branch(target: PublishTarget, tip: str) -> None:
    """Push `tip`, or a delete when `tip` is empty, to the branch of `target` on `origin`, with a
    lease on its tip `target.lease`. The fetch of `tip` takes its full history: after a rebase no
    branch of `origin` holds `tip`, and `origin` refuses a shallow commit that no branch holds."""
    parent = Path(tempfile.mkdtemp(prefix="devops-publish-"))
    try:
        repo = parent / "repo"
        git_call(parent, "init", "--quiet", str(repo), home=parent)
        git_call(repo, "remote", "add", "origin", target.url, home=parent)
        if tip:
            git_call(repo, "fetch", "--quiet", "--no-tags", "origin", tip, home=parent)
        lease = f"--force-with-lease=refs/heads/{target.branch}:{target.lease}"
        git_call(
            repo,
            "push",
            "--quiet",
            lease,
            "origin",
            f"{tip}:refs/heads/{target.branch}",
            home=parent,
        )
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def delete_branch(target: PublishTarget) -> None:
    """Delete the branch of `target` on `origin`, with a lease on its tip `target.lease`: a branch
    that `publish` made, whose draft pull request GitHub refused, or a branch that an earlier Job
    made, at a return to New (#3677)."""
    _move_branch(target, "")


def reset_branch(target: PublishTarget) -> None:
    """Move the branch of `target` on `origin` back to `target.base`, with a lease on its tip
    `target.lease`: at a return to New, the withdraw of the commits that earlier Jobs pushed
    (#3677)."""
    _move_branch(target, target.base)


__all__ = [
    "NewTree",
    "PublishTarget",
    "Published",
    "delete_branch",
    "git_call",
    "publish_patch",
    "reset_branch",
]

"""The git commands that the roadmap jobs run in a clone or in a worktree of it (#2654, #2665).

Each runs through the process runner in the process of the job, never in the shell of an agent,
so a job's credential (the helper of its git configuration) is the job's alone.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from devops_cli.config.constants import CONST_GIT_CLI
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
from devops_cli.git.branch_authors import LOG_FORMAT, person_authors
from devops_cli.git.worktree_inventory import git_message
from devops_cli.lang import MESSAGES
from devops_cli.security.sanitizer import mask_secrets


def git(cwd: Path, *args: str, operation: str) -> str:
    """The output of `git <args>` in `cwd`, stripped. A failure raises `GitOperationError` for
    `operation` with git's reason, credentials masked."""
    proc = run_subprocess([CONST_GIT_CLI, "-C", str(cwd), *args], check=False, quiet=True)
    if proc.returncode != 0:
        raise GitOperationError(
            MESSAGES.roadmap.git_failed.format(
                command=" ".join(args), reason=mask_secrets(git_message(proc))
            ),
            operation=operation,
        )
    return proc.stdout.strip()


@contextmanager
def checkout_at(repository: Path, commit: str, *, operation: str) -> Iterator[Path]:
    """The tracked files of `commit` in a new detached worktree of `repository`, removed after.
    A commit the repository lacks raises `GitOperationError` for `operation`."""
    parent = Path(tempfile.mkdtemp(prefix="roadmap-checkout-"))
    tree = parent / "tree"
    try:
        git(repository, "worktree", "add", "--detach", str(tree), commit, operation=operation)
        try:
            yield tree
        finally:
            git(repository, "worktree", "remove", "--force", str(tree), operation=operation)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def default_branch(source: Path, *, operation: str) -> str:
    """The default branch of the clone, from `refs/remotes/origin/HEAD`."""
    ref = git(source, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", operation=operation)
    return ref.removeprefix("origin/")


def branch_authors(source: Path, branch: str, *, operation: str) -> list[str]:
    """The author name of each commit that `origin/<branch>` holds past the default branch, after
    a fetch of the branch, except a clean merge (#3392). The name is what `worktrees add` reads
    when it takes a branch over."""
    git(source, "fetch", "-q", "origin", branch, operation=operation)
    default = default_branch(source, operation=operation)
    log = git(source, "log", LOG_FORMAT, f"origin/{default}..origin/{branch}", operation=operation)
    return person_authors([CONST_GIT_CLI, "-C", str(source)], log)

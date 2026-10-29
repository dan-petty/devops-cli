"""The git commands that the roadmap jobs run in a clone or in a worktree of it (#2654, #2665).

Each runs through the process runner in the process of the job, never in the shell of an agent,
so a job's credential (the helper of its git configuration) is the job's alone.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.constants import CONST_GIT_CLI
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
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


def default_branch(source: Path, *, operation: str) -> str:
    """The default branch of the clone, from `refs/remotes/origin/HEAD`."""
    ref = git(source, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", operation=operation)
    return ref.removeprefix("origin/")


def branch_authors(source: Path, branch: str, *, operation: str) -> list[str]:
    """The author name of each commit that `origin/<branch>` holds past the default branch, after
    a fetch of the branch. The name is what `worktrees add` reads when it takes a branch over."""
    git(source, "fetch", "-q", "origin", branch, operation=operation)
    default = default_branch(source, operation=operation)
    log = git(
        source, "log", "--format=%an", f"origin/{default}..origin/{branch}", operation=operation
    )
    return log.splitlines()

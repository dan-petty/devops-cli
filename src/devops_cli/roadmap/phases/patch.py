"""The patch of the agent phase (#6601): what the agent changed in the checkout, from the base.

The agent controls the checkout and the git settings of its clone: a clean filter, a
`core.fsmonitor` program or a hook there runs as a child of git. So the patch comes from a new git
folder, as `OriginGit` makes one for a network call (`git_isolation.py`): its objects are the
objects of the clone, it has its own index and configuration, and git reads no global or system
configuration. `git add -A` in it stages every file of the checkout over the tree of the base, so a
commit of a fixer and a file that no commit holds are both in the patch. The leftover processes of
the agent end first (`end_leftover_processes`, in a runner), so none changes the checkout during
the read (#3702).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import CONST_GIT_ISOLATED_CONFIG_ENV
from devops_cli.config.settings import load_settings
from devops_cli.core import process_hardening
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
from devops_cli.git.worktree_inventory import git_message
from devops_cli.security.sanitizer import mask_secrets

_OPERATION = "roadmap.phases.patch"


def _git(git_dir: Path, checkout: Path, *args: str) -> str:
    """`git <args>` in the new git folder `git_dir` on the work tree `checkout`, with no token."""
    proc = run_subprocess(
        [BIN_GIT, f"--git-dir={git_dir}", f"--work-tree={checkout}", *args],
        cwd=checkout,
        env=dict(CONST_GIT_ISOLATED_CONFIG_ENV),
        check=False,
        quiet=True,
    )
    if proc.returncode != 0:
        raise GitOperationError(
            f"git {' '.join(args[:2])} failed: {mask_secrets(git_message(proc))}",
            operation=_OPERATION,
        )
    return proc.stdout


def _objects(checkout: Path) -> Path:
    """The object folder of the clone of `checkout`, which each of its worktrees shares."""
    proc = run_subprocess(
        [BIN_GIT, "-C", str(checkout), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        env=dict(CONST_GIT_ISOLATED_CONFIG_ENV),
        check=False,
        quiet=True,
    )
    if proc.returncode != 0:
        raise GitOperationError(
            f"git rev-parse failed: {mask_secrets(git_message(proc))}", operation=_OPERATION
        )
    return Path(proc.stdout.strip()) / "objects"


def write_patch(checkout: Path, base: str, path: Path) -> None:
    """Write to `path` the binary patch of every file of `checkout` from the commit `base`, made in
    a new git folder. A checkout with no change gives an empty file."""
    if load_settings().roadmap.implement.in_runner:
        process_hardening.end_leftover_processes()
    parent = Path(tempfile.mkdtemp(prefix="devops-patch-"))
    try:
        git_dir = parent / "repo.git"
        run_subprocess(
            [BIN_GIT, "init", "--quiet", "--bare", str(git_dir)],
            env=dict(CONST_GIT_ISOLATED_CONFIG_ENV),
            check=True,
            quiet=True,
        )
        shutil.rmtree(git_dir / "objects")
        (git_dir / "objects").symlink_to(_objects(checkout), target_is_directory=True)
        _git(git_dir, checkout, "read-tree", base)
        _git(git_dir, checkout, "add", "-A")
        # git writes the bytes of the patch to the file itself, so text that is not UTF-8 stays.
        _git(
            git_dir,
            checkout,
            "diff",
            "--cached",
            "--binary",
            "--full-index",
            f"--output={path}",
            base,
        )
    finally:
        shutil.rmtree(parent, ignore_errors=True)
    path.chmod(0o600)


__all__ = ["write_patch"]

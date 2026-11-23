"""The patch of the agent phase (#6601, #3702): what the agent changed in its clone, from the base.

The agent phase works in its own clone, as a developer does, and holds no GitHub credential. The
patch is the only data that goes from it to `publish`, so its format does not depend on a setting
of the clone or of the home folder: the flags turn off an external diff program, a textconv
driver and color, and fix the context lines to 3 and the path prefixes. `git add -A` stages every
file of the checkout, so a commit of a fixer and a file that no commit holds are both in the
patch.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.commands import BIN_GIT
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
from devops_cli.git.worktree_inventory import git_message
from devops_cli.security.sanitizer import mask_secrets

_OPERATION = "roadmap.phases.patch"
# The format of the patch: binary, with full object names, and no setting that changes the text.
_FORMAT = (
    "--binary",
    "--full-index",
    "--unified=3",
    "--no-color",
    "--no-ext-diff",
    "--no-textconv",
    "--src-prefix=a/",
    "--dst-prefix=b/",
)


def _git(checkout: Path, *args: str) -> None:
    proc = run_subprocess([BIN_GIT, "-C", str(checkout), *args], check=False, quiet=True)
    if proc.returncode != 0:
        raise GitOperationError(
            f"git {' '.join(args[:2])} failed: {mask_secrets(git_message(proc))}",
            operation=_OPERATION,
        )


def write_patch(
    checkout: Path, base: str, path: Path, *, head: str | None = None, only: str | None = None
) -> None:
    """Write to `path` the binary patch from the commit `base` to the commit `head`, or to every
    file of `checkout` when `head` is None. With `only`, a path of the checkout, the patch holds
    the changes under that path alone, as the stage agent hands over its change folder (#6705).
    A checkout with no change gives an empty file."""
    paths = ["--", only] if only is not None else []
    if head is None:
        _git(checkout, "add", "-A", *paths)
        target = ["--cached", base]
    else:
        target = [base, head]
    # git writes the bytes of the patch to the file itself, so text that is not UTF-8 stays.
    _git(checkout, "diff", *_FORMAT, f"--output={path}", *target, *paths)
    path.chmod(0o600)


__all__ = ["write_patch"]

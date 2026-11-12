"""The commit of an infra repo that `devops infra` reads: the head of its default branch at
`origin` (#5162).

A command reads an infra repo at one commit, never in the working tree of the checkout. The working
tree can be on another branch, behind `origin`, or hold changes that nobody committed, and the
profile of a repo is read at its default branch, the trusted ref (#4627). The reader fetches
`origin`, takes the commit of the default branch that `refs/remotes/origin/HEAD` names, and exports
the tracked files of that commit with `git archive` into a new private folder, which it removes
after. It changes no file and no branch of the checkout; only the fetch moves its remote-tracking
branches. Each git command goes through the process runner, and the dry run lists the same
commands (`read_commands`).
"""

from __future__ import annotations

import shutil
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devops_cli.config.constants import (
    CONST_GIT_GITHUB_CREDENTIAL_CONFIG,
    CONST_GIT_NONINTERACTIVE_ENV,
)
from devops_cli.config.defaults import DEFAULT_INFRA_GIT_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.infra import InfraReadError
from devops_cli.git.operations import git_argv
from devops_cli.git.worktree_inventory import git_message
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.models.infra import ReadCommit
from devops_cli.security.sanitizer import mask_secrets

_REMOTE: Final[str] = "origin"
_REMOTE_HEAD: Final[str] = f"refs/remotes/{_REMOTE}/HEAD"
_DETACHED: Final[str] = "HEAD"
_ARCHIVE: Final[str] = "tree.tar"
_TREE: Final[str] = "tree"
_PRIVATE: Final[int] = 0o700
_EXPORT_PREFIX: Final[str] = "devops-infra-"

_FETCH: Final[tuple[str, ...]] = ("fetch", "--quiet", _REMOTE)
# The fetch, with the credential of the GitHub session and no prompt: git fails instead of asking.
FETCH_ARGS: Final[tuple[str, ...]] = (
    *(word for value in CONST_GIT_GITHUB_CREDENTIAL_CONFIG for word in ("-c", value)),
    *_FETCH,
)
# The commit of the default branch at origin, then its name (`origin/<branch>`).
DEFAULT_BRANCH_ARGS: Final[tuple[str, ...]] = (
    "rev-parse",
    _REMOTE_HEAD,
    "--abbrev-ref",
    _REMOTE_HEAD,
)
# The commit of the checkout, then its branch (`HEAD` when it is detached).
CHECKOUT_ARGS: Final[tuple[str, ...]] = ("rev-parse", "HEAD", "--abbrev-ref", "HEAD")


def archive_args(commit: str, output: Path) -> tuple[str, ...]:
    """The export of the tracked files of `commit` as a tar file at `output`."""
    return ("archive", "--format=tar", f"--output={output}", commit)


@dataclass(frozen=True)
class RepoTree:
    """The files of one commit of an infra repo in a private folder, and what was read."""

    root: Path
    read: ReadCommit


@contextmanager
def default_branch_tree(checkout: Path) -> Iterator[RepoTree]:
    """The files of the head of the default branch at `origin`, after a fetch, in a private
    folder that is removed after the block.

    Raises:
        InfraReadError: a git command fails, the checkout records no default branch of
            `origin`, or the export does not unpack.
    """
    _git(checkout, FETCH_ARGS, shown=_FETCH)
    commit, ref = _two_lines(checkout, DEFAULT_BRANCH_ARGS, _no_default_branch(checkout))
    checkout_commit, checkout_branch = _checkout_state(checkout)
    read = ReadCommit(
        ref=ref, commit=commit, checkout_branch=checkout_branch, checkout_commit=checkout_commit
    )
    parent = Path(tempfile.mkdtemp(prefix=_EXPORT_PREFIX))
    try:
        archive = parent / _ARCHIVE
        _git(checkout, archive_args(commit, archive))
        root = parent / _TREE
        root.mkdir(mode=_PRIVATE)
        _unpack(archive, root, commit)
        archive.unlink()
        yield RepoTree(root=root, read=read)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def _git(checkout: Path, args: tuple[str, ...], *, shown: tuple[str, ...] = ()) -> str:
    """The standard output of `git -C <checkout> <args>`, run with no prompt. An error names the
    command as `git <shown>`, by default `git <args>`.

    Raises:
        InfraReadError: git exits with a status other than 0; the message holds git's reason with
            credentials masked.
    """
    result = run_subprocess(
        git_argv(checkout, *args),
        env=dict(CONST_GIT_NONINTERACTIVE_ENV),
        quiet=True,
        timeout=DEFAULT_INFRA_GIT_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise InfraReadError(
            ERRORS.infra.read_failed.format(
                command=" ".join(("git", *(shown or args))),
                code=result.returncode,
                detail=mask_secrets(git_message(result)),
            )
        )
    return result.stdout


def _two_lines(checkout: Path, args: tuple[str, ...], error: InfraReadError) -> tuple[str, str]:
    """The two lines that `git rev-parse <rev> --abbrev-ref <rev>` prints, or `error` when git
    finds no such revision."""
    try:
        lines = _git(checkout, args).split()
    except InfraReadError as exc:
        raise error from exc
    if len(lines) != 2:
        raise error
    return lines[0], lines[1]


def _no_default_branch(checkout: Path) -> InfraReadError:
    return InfraReadError(ERRORS.infra.no_default_branch.format(path=checkout, ref=_REMOTE_HEAD))


def _checkout_state(checkout: Path) -> tuple[str | None, str | None]:
    """The commit and the branch of the checkout. A detached HEAD has no branch, and a checkout
    with no commit has neither."""
    result = run_subprocess(
        git_argv(checkout, *CHECKOUT_ARGS),
        env=dict(CONST_GIT_NONINTERACTIVE_ENV),
        quiet=True,
        timeout=DEFAULT_INFRA_GIT_TIMEOUT_SECONDS,
    )
    lines = result.stdout.split() if result.returncode == 0 else []
    if len(lines) != 2:
        return None, None
    commit, branch = lines
    return commit, None if branch == _DETACHED else branch


def _unpack(archive: Path, root: Path, commit: str) -> None:
    """Unpack the export into `root` with the `data` filter: no link out of `root`, no device,
    and no write bit for the group or others.

    Raises:
        InfraReadError: the tar file does not read or holds a member that the filter refuses.
    """
    try:
        with tarfile.open(archive) as tar:
            tar.extractall(root, filter="data")
    except (tarfile.TarError, OSError) as exc:
        raise InfraReadError(ERRORS.infra.export_failed.format(commit=commit, reason=exc)) from exc


def read_commands(checkout: Path) -> list[PlannedRequest]:
    """The git commands of `default_branch_tree`, in order, for a dry run."""
    export = Path("<private temporary folder>")
    commit = "<commit of the default branch>"
    return [
        PlannedRequest(
            method="EXEC",
            target=f"the fetch of {_REMOTE} into {checkout}",
            argv=tuple(git_argv(checkout, *FETCH_ARGS)),
        ),
        PlannedRequest(
            method="EXEC",
            target=f"the default branch of {_REMOTE} and its commit",
            argv=tuple(git_argv(checkout, *DEFAULT_BRANCH_ARGS)),
        ),
        PlannedRequest(
            method="EXEC",
            target="the branch and the commit of the checkout",
            argv=tuple(git_argv(checkout, *CHECKOUT_ARGS)),
        ),
        PlannedRequest(
            method="EXEC",
            target="the export of the default branch, unpacked and removed after the read",
            argv=tuple(git_argv(checkout, *archive_args(commit, export / _ARCHIVE))),
        ),
    ]


def render_read(read: ReadCommit) -> list[str]:
    """The line that names the commit that a command read, and a line when the checkout is not
    at that commit."""
    texts = MESSAGES.infra
    lines = [texts.read_commit.format(ref=read.ref, commit=read.commit)]
    if read.checkout_commit is None:
        lines.append(texts.checkout_no_commit)
    elif read.checkout_differs:
        where = (
            texts.checkout_on_branch.format(branch=read.checkout_branch)
            if read.checkout_branch
            else texts.checkout_detached
        )
        lines.append(
            texts.checkout_differs.format(where=where, commit=read.checkout_commit, ref=read.ref)
        )
    return lines


__all__ = [
    "CHECKOUT_ARGS",
    "DEFAULT_BRANCH_ARGS",
    "FETCH_ARGS",
    "RepoTree",
    "archive_args",
    "default_branch_tree",
    "read_commands",
    "render_read",
]

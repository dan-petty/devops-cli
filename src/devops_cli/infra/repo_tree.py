"""The commit of an infra repo that `devops infra` reads: the head of its default branch at
`origin` (#5162), or another ref that `origin` holds (#5124).

A command reads an infra repo at one commit, never in the working tree of the checkout. The working
tree can be on another branch, behind `origin`, or hold changes that nobody committed, and the
profile of a repo is read at its default branch, the trusted ref (#4627). The reader fetches
`origin`, takes the commit of the default branch that `refs/remotes/origin/HEAD` names, and exports
the tracked files of that commit with `git archive` into a new private folder, which it removes
after. `devops infra plan --ref` reads a branch of `origin` (`refs/remotes/origin/<branch>`, a name
that `git check-ref-format --branch` accepts) or the head of a pull request (`pull/<number>/head`,
fetched from `origin` into `FETCH_HEAD`), and exports it into the plan folder. The reader changes
no file and no branch of the checkout; only the fetch moves its remote-tracking branches and
`FETCH_HEAD`. Each git command goes through the process runner, and the dry run lists the same
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


def _credential(args: tuple[str, ...]) -> tuple[str, ...]:
    """`args` with the `-c` values that give git the credential of the GitHub session."""
    return (
        *(word for value in CONST_GIT_GITHUB_CREDENTIAL_CONFIG for word in ("-c", value)),
        *args,
    )


# The fetch, with the credential of the GitHub session and no prompt: git fails instead of asking.
FETCH_ARGS: Final[tuple[str, ...]] = _credential(_FETCH)
# The commit of the default branch at origin, then its name (`origin/<branch>`).
DEFAULT_BRANCH_ARGS: Final[tuple[str, ...]] = (
    "rev-parse",
    _REMOTE_HEAD,
    "--abbrev-ref",
    _REMOTE_HEAD,
)
# The commit of the checkout, then its branch (`HEAD` when it is detached).
CHECKOUT_ARGS: Final[tuple[str, ...]] = ("rev-parse", "HEAD", "--abbrev-ref", "HEAD")
# The ref of the head of a pull request: `pull/<number>/head`.
_PULL: Final[str] = "pull"
_PULL_HEAD: Final[str] = "head"
_FETCH_HEAD: Final[str] = "FETCH_HEAD"


def pull_number(ref: str) -> int | None:
    """The number of the pull request whose head `ref` names (`pull/<number>/head`), else none."""
    parts = ref.split("/")
    if len(parts) == 3 and parts[0] == _PULL and parts[1].isdecimal() and parts[2] == _PULL_HEAD:
        return int(parts[1])
    return None


def _pull_fetch(number: int) -> tuple[str, ...]:
    return ("fetch", "--quiet", _REMOTE, f"refs/{_PULL}/{number}/{_PULL_HEAD}")


def _verify(rev: str) -> tuple[str, ...]:
    """The commit that `rev` names: `git rev-parse --verify` prints it, or fails."""
    return ("rev-parse", "--verify", "--end-of-options", f"{rev}^{{commit}}")


def ref_steps(ref: str) -> list[tuple[str, tuple[str, ...]]]:
    """The git commands, after the fetch of `origin`, that give the commit of `ref`, each with
    what it does: the fetch of the head of a pull request and its commit, or the check of a branch
    name and the commit of that branch at `origin`. Each fetch takes the credential of the GitHub
    session."""
    number = pull_number(ref)
    if number is not None:
        return [
            (f"the fetch of {ref} from {_REMOTE}", _credential(_pull_fetch(number))),
            (f"the commit of {ref}", _verify(_FETCH_HEAD)),
        ]
    return [
        (f"the check of the branch name {ref}", ("check-ref-format", "--branch", ref)),
        (f"the commit of {_REMOTE}/{ref}", _verify(f"refs/remotes/{_REMOTE}/{ref}")),
    ]


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
    parent = Path(tempfile.mkdtemp(prefix=_EXPORT_PREFIX))
    try:
        root = parent / _TREE
        read = export_commit(checkout, root)
        yield RepoTree(root=root, read=read)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def export_commit(checkout: Path, root: Path, *, ref: str | None = None) -> ReadCommit:
    """Fetch `origin`, and export the tracked files of the commit of `ref` at `origin` into the
    new private folder `root`. With no `ref`, the commit is the head of the default branch. The
    tar file of the export goes beside `root` and is removed after it unpacks.

    Raises:
        InfraReadError: a git command fails, the checkout records no default branch of
            `origin`, `origin` holds no such ref, or the export does not unpack.
    """
    _git(checkout, FETCH_ARGS, shown=_FETCH)
    if ref is None:
        commit, name = _two_lines(checkout, DEFAULT_BRANCH_ARGS, _no_default_branch(checkout))
    else:
        commit, name = _ref_commit(checkout, ref), _ref_name(ref)
    checkout_commit, checkout_branch = _checkout_state(checkout)
    archive = root.parent / _ARCHIVE
    _git(checkout, archive_args(commit, archive))
    root.mkdir(mode=_PRIVATE)
    _unpack(archive, root, commit)
    archive.unlink()
    return ReadCommit(
        ref=name, commit=commit, checkout_branch=checkout_branch, checkout_commit=checkout_commit
    )


def _ref_name(ref: str) -> str:
    """How a read names `ref`: `origin/<branch>`, or `pull/<number>/head` as given."""
    return ref if pull_number(ref) is not None else f"{_REMOTE}/{ref}"


def _ref_commit(checkout: Path, ref: str) -> str:
    """The commit of `ref` at `origin`.

    Raises:
        InfraReadError: `ref` is not a branch name, or `origin` holds no such branch or pull
            request head.
    """
    *before, (_, verify) = ref_steps(ref)
    try:
        for _, args in before:
            _git(checkout, args)
        return _git(checkout, verify).strip()
    except InfraReadError as exc:
        raise InfraReadError(
            ERRORS.infra.ref_not_found.format(ref=ref, path=checkout, reason=exc.message)
        ) from exc


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


def read_commands(
    checkout: Path, *, ref: str | None = None, export: Path | None = None
) -> list[PlannedRequest]:
    """The git commands of `export_commit`, in order, for a dry run: by default the read of the
    default branch into a private temporary folder (`default_branch_tree`)."""
    archive = (export.parent if export else Path("<private temporary folder>")) / _ARCHIVE
    requests = [
        PlannedRequest(
            method="EXEC",
            target=f"the fetch of {_REMOTE} into {checkout}",
            argv=tuple(git_argv(checkout, *FETCH_ARGS)),
        )
    ]
    if ref is None:
        commit = "<commit of the default branch>"
        requests.append(
            PlannedRequest(
                method="EXEC",
                target=f"the default branch of {_REMOTE} and its commit",
                argv=tuple(git_argv(checkout, *DEFAULT_BRANCH_ARGS)),
            )
        )
    else:
        commit = f"<commit of {_ref_name(ref)}>"
        requests += [
            PlannedRequest(method="EXEC", target=target, argv=tuple(git_argv(checkout, *args)))
            for target, args in ref_steps(ref)
        ]
    requests += [
        PlannedRequest(
            method="EXEC",
            target="the branch and the commit of the checkout",
            argv=tuple(git_argv(checkout, *CHECKOUT_ARGS)),
        ),
        PlannedRequest(
            method="EXEC",
            target=(
                f"the export of {commit} into {export}"
                if export
                else "the export of the default branch, unpacked and removed after the read"
            ),
            argv=tuple(git_argv(checkout, *archive_args(commit, archive))),
        ),
    ]
    return requests


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
    "export_commit",
    "pull_number",
    "read_commands",
    "ref_steps",
    "render_read",
]

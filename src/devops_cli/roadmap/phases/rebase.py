"""The rebase of a phased step onto the tip of the default branch, as a developer makes it (#3702,
#6639).

The agent phases of implement and of fix-checks rebase the branch onto the tip of the default
branch that `prepare` recorded, and settle each stop as a developer does:

- `git rebase --skip` for the archive commit of the item, whose every path the step makes again
  (`skips_archive_commit`);
- the side of the default branch, stage 2 of the index, for a conflict only in the generated
  documents and `uv.lock`: `git checkout --ours`, or `git rm` for a file that the default branch
  deleted. Then `uv lock` and `devops docs generate` run again (`generate`).

A stop that no rule settles ends the rebase with its error, and the rebase stays in progress: the
caller aborts it and stops with the class `conflict`. The conflict fixer of #6620 holds the same
rules; #6640 makes them one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devops_cli.config.commands import BIN_DEVOPS, BIN_UV
from devops_cli.config.constants import CONST_OPENSPEC_CHANGES_DIR, CONST_OPENSPEC_DIR
from devops_cli.exceptions import GitOperationError
from devops_cli.roadmap.clone_git import git

# The subject of the archive commit of an item, which the step finds by it (`archive_commit`).
ARCHIVE_MESSAGE: Final[str] = "docs(openspec): archive the change (#{number})"

# Runs a program in the checkout, and raises when it fails or runs out of time.
Generate = Callable[[Sequence[str]], None]


@dataclass(frozen=True)
class RebaseEnd:
    """How a rebase ended. `started` is False when git refused to start it, as in a checkout that
    holds changes: no rebase is in progress then. `error` is the error of git when it refused to
    start, or of the stop that no rule settles, with the rebase still in progress. `skipped` says
    that the rebase skipped the archive commit of the item."""

    started: bool = True
    error: GitOperationError | None = None
    skipped: bool = False


def unmerged(path: Path, *, operation: str) -> list[str]:
    """The paths that a stopped rebase left unmerged in the checkout `path`."""
    listed = git(path, "diff", "--name-only", "--diff-filter=U", "-z", operation=operation)
    return [name for name in listed.split("\0") if name]


def skips_archive_commit(listed: str, number: int) -> bool:
    """Whether a rebase skips the commit that `listed` gives, the output of `git show --name-status
    -z` of `REBASE_HEAD`: the archive commit of item `number`. It removes or moves a file out of
    `openspec/changes/<number>-`, and every path is an OpenSpec path or a generated document, which
    the step makes again (#3702). The plan commit adds its change folder, so the rule keeps it."""
    from devops_cli.roadmap.steps.fix_conflict import is_generated_docs_path

    fields = listed.split("\0")
    moved, paths, index = False, [], 0
    while index < len(fields) and fields[index]:
        status = fields[index][:1]
        width = 2 if status in ("R", "C") else 1
        names = fields[index + 1 : index + 1 + width]
        moved = moved or (
            status in ("D", "R") and names[0].startswith(f"{CONST_OPENSPEC_CHANGES_DIR}/{number}-")
        )
        paths.extend(names)
        index += 1 + width
    made_again = all(
        name.startswith(f"{CONST_OPENSPEC_DIR}/") or is_generated_docs_path(name) for name in paths
    )
    return moved and made_again


def rebase_in_progress(path: Path, *, operation: str) -> bool:
    """Whether a rebase stopped in the checkout `path` and waits: git keeps the state of the rebase
    in the directory `rebase-merge`, or `rebase-apply` for the apply backend, until it ends. A
    rebase that git refused to start has neither."""
    names = git(
        path,
        "rev-parse",
        "--git-path",
        "rebase-merge",
        "--git-path",
        "rebase-apply",
        operation=operation,
    )
    return any((path / name).is_dir() for name in names.splitlines())


def settle_stop(
    path: Path, number: int, generate: Generate, *, docs: bool, operation: str
) -> tuple[str, ...] | None:
    """The git command that goes on with the rebase at its stop, or None when no rule settles the
    stop. `docs` says that the target generates its documents."""
    from devops_cli.roadmap.steps.fix_conflict import is_generated_docs_path, is_lockfile_path

    listed = git(
        path, "show", "--name-status", "-z", "--format=", "REBASE_HEAD", operation=operation
    )
    if skips_archive_commit(listed, number):
        return ("rebase", "--skip")
    stopped = unmerged(path, operation=operation)
    if not stopped or not all(is_generated_docs_path(n) or is_lockfile_path(n) for n in stopped):
        return None
    # Take the side of the default branch, stage 2 of the index: a file that the default branch
    # deleted has no stage 2, so it goes.
    staged = git(path, "ls-files", "-u", "-z", "--", *stopped, operation=operation)
    ours = {entry.split("\t", 1)[1] for entry in staged.split("\0") if " 2\t" in entry}
    if gone := [name for name in stopped if name not in ours]:
        git(path, "rm", "-q", "--", *gone, operation=operation)
    if kept := [name for name in stopped if name in ours]:
        git(path, "checkout", "--ours", "--", *kept, operation=operation)
    if any(is_lockfile_path(name) for name in stopped):
        generate([BIN_UV, "lock"])
    if docs and any(is_generated_docs_path(n) for n in stopped):
        generate([BIN_UV, "run", BIN_DEVOPS, "docs", "generate"])
    git(path, "add", "-A", operation=operation)
    return ("-c", "core.editor=true", "rebase", "--continue")


def rebase_onto(
    path: Path, onto: str, number: int, generate: Generate, *, docs: bool, operation: str
) -> RebaseEnd:
    """Rebase the checkout `path` onto the commit `onto`, and settle each stop (`settle_stop`). It
    makes no network call: the clone holds `onto`. An error of `settle_stop` or of `generate`
    propagates with the rebase still in progress, so the caller aborts it."""
    try:
        git(path, "rebase", "--quiet", onto, operation=operation)
        return RebaseEnd()
    except GitOperationError as exc:
        if not rebase_in_progress(path, operation=operation):
            return RebaseEnd(started=False, error=exc)
        stopped = exc
    skipped = False
    while rebase_in_progress(path, operation=operation):
        action = settle_stop(path, number, generate, docs=docs, operation=operation)
        if action is None:
            return RebaseEnd(error=stopped, skipped=skipped)
        skipped = skipped or action == ("rebase", "--skip")
        try:
            git(path, *action, operation=operation)
        except GitOperationError as exc:
            stopped = exc
    return RebaseEnd(skipped=skipped)


def archive_commit(path: Path, base: str, number: int, *, operation: str) -> str | None:
    """The newest archive commit of item `number` past `base`, or None when the branch holds none.
    The archive stays its own commit when `publish` pushes (#3702)."""
    subject = ARCHIVE_MESSAGE.format(number=number)
    listed = git(path, "log", "--format=%H%x1f%s", f"{base}..HEAD", operation=operation)
    for line in listed.splitlines():
        sha, _, title = line.partition("\x1f")
        if title == subject:
            return sha
    return None


def holds(path: Path, commit: str, tip: str, *, operation: str) -> bool:
    """Whether the history of `tip` holds `commit`: a branch at `tip` needs no rebase onto it."""
    try:
        git(path, "merge-base", "--is-ancestor", commit, tip, operation=operation)
    except GitOperationError:
        return False
    return True


__all__ = [
    "ARCHIVE_MESSAGE",
    "Generate",
    "RebaseEnd",
    "archive_commit",
    "holds",
    "rebase_in_progress",
    "rebase_onto",
    "settle_stop",
    "skips_archive_commit",
    "unmerged",
]

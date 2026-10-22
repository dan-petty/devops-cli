"""Archive a release's changes one at a time, in the order they merged (ADR 0010).

`openspec archive` writes `openspec/specs/<capability>/spec.md`, so two changes archived from
parallel branches conflict, and one that modifies a requirement another adds aborts, writing
nothing, when it archives first. Only the release cut archives, serially, in merge order: oldest
first by the commit that added each change folder, folders not yet committed last, and ties by the
issue number read as a number (999 before 1000). The cut and the gate's rehearsal of it both call
`archive_sequence`, so what the gate rehearses is what the cut runs.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from math import inf
from pathlib import Path, PurePosixPath

from devops_cli.config.commands import BIN_OPENSPEC, build_git_additions_log_cmd
from devops_cli.config.constants import (
    CONST_OPENSPEC_CHANGE_METADATA_FILENAME,
    CONST_OPENSPEC_CHANGE_NAME_RE,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_OPENSPEC_DIR,
    CONST_OPENSPEC_STATUS_COMPLETE,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import OpenSpecArchiveError, ToolExecutionError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool, output_of

# The commit lines of `git log --format=<prefix>%H`, told apart from the paths `--name-only` lists.
_COMMIT_LINE_PREFIX = "commit "


def active_changes(tool: OpenSpecTool, directory: Path) -> dict[str, str]:
    """The status OpenSpec gives each active change under `directory`, by name."""
    listing = tool.read_json(["list", "--json"], directory)
    return {change["name"]: change["status"] for change in listing["changes"]}


def _commit_ranks(root: Path) -> dict[str, int]:
    """The rank, from 1, of the commit that added each change folder's `.openspec.yaml`, oldest
    first and parents before children. A folder added again by a later commit takes that rank, and
    a rename counts as an addition, so a renamed folder merges when it was renamed."""
    log = run_subprocess(
        build_git_additions_log_cmd(
            CONST_OPENSPEC_CHANGES_DIR, CONST_OPENSPEC_CHANGE_METADATA_FILENAME, _COMMIT_LINE_PREFIX
        ),
        cwd=root,
        quiet=True,
    )
    if log.returncode != 0:
        raise ToolExecutionError(output_of(log)[:256], tool_name="git")
    ranks: dict[str, int] = {}
    rank = 0
    for line in log.stdout.splitlines():
        if line.startswith(_COMMIT_LINE_PREFIX):
            rank += 1
        elif line.strip():
            ranks[PurePosixPath(line).parts[2]] = rank
    return ranks


def _issue_number(name: str) -> float:
    """The issue a change folder is named for, read as a number; `inf` for a name that is not
    `<issue>-<slug>`."""
    named = re.fullmatch(CONST_OPENSPEC_CHANGE_NAME_RE, name)
    return int(named["issue"]) if named else inf


def merge_order(root: Path, names: Iterable[str]) -> list[str]:
    """`names` in the order their folders merged into the checkout at `root`."""
    names = list(names)
    ranks = _commit_ranks(root) if names else {}
    return sorted(names, key=lambda name: (ranks.get(name, inf), _issue_number(name), name))


def _refusal(run_stdout: str, fallback: str) -> str:
    """Why `openspec archive --json` refused: the messages of its error statuses, else `fallback`."""
    try:
        statuses = json.loads(run_stdout).get("status", [])
    except ValueError, AttributeError:
        return fallback
    return (
        "; ".join(status["message"] for status in statuses if status["severity"] == "error")
        or fallback
    )


def archive_sequence(tool: OpenSpecTool, directory: Path, names: Iterable[str]) -> list[str]:
    """Archive each of `names` under `directory`, in order, and stop at the first the tool
    refuses.

    Raises `OpenSpecArchiveError` naming that change and why; the changes before it stay archived.
    """
    archived = []
    for name in names:
        run = tool.run(["archive", name, "--yes", "--json"], directory)
        if run.returncode != 0:
            raise OpenSpecArchiveError(name, _refusal(run.stdout, output_of(run)))
        archived.append(name)
    return archived


def symlink_refusal(root: Path) -> str | None:
    """Why `root`'s `openspec/` folder cannot be copied: it holds a symbolic link, which a copy
    would follow out of the folder, and an archive in the copy could write through; None when it
    holds none."""
    linked = sorted(
        path.relative_to(root).as_posix()
        for path in (root / CONST_OPENSPEC_DIR).rglob("*")
        if path.is_symlink()
    )
    return MESSAGES.openspec.symlink_refused.format(paths=", ".join(linked)) if linked else None


@contextmanager
def scratch_copy(root: Path) -> Iterator[Path]:
    """A copy of `root`'s `openspec/` folder in a scratch directory that goes when the block ends,
    for a run that must write nothing in the tree.

    Raises `ToolExecutionError` naming each symbolic link in the folder, and copies nothing.
    """
    if refusal := symlink_refusal(root):
        raise ToolExecutionError(refusal, tool_name=BIN_OPENSPEC)
    with tempfile.TemporaryDirectory(prefix="openspec-copy-") as scratch:
        shutil.copytree(root / CONST_OPENSPEC_DIR, Path(scratch) / CONST_OPENSPEC_DIR)
        yield Path(scratch)


def archive_complete_changes(tool: OpenSpecTool, root: Path) -> list[str]:
    """Archive every change whose tasks are all ticked, in merge order, leaving the others active.

    The sequence runs first in a scratch copy of `openspec/`, so a change the tool refuses writes
    nothing; it runs in `root` only once the whole sequence has archived there.

    Raises `OpenSpecArchiveError` naming the change the tool refused.
    """
    complete = [
        name
        for name, status in active_changes(tool, root).items()
        if status == CONST_OPENSPEC_STATUS_COMPLETE
    ]
    names = merge_order(root, complete)
    with scratch_copy(root) as plan:
        archive_sequence(tool, plan, names)
    return archive_sequence(tool, root, names)

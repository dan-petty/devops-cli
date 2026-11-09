"""Archive a change into the living specs, then validate every spec and change (ADR 0010).

The pull request that closes a change archives it as its last commit. `openspec archive` applies the
deltas of the change to `openspec/specs/` and moves the folder. It can leave a spec that `validate`
rejects: a new capability gets a placeholder Purpose. So the wrapper validates after the archive.
It runs both commands under the isolated configuration (`isolated_openspec`). That configuration
keeps the telemetry and the per-user configuration of the tool out of the run. The wrapper passes no
`--skip-specs`, because a change that declares `skip_specs` archives without it.

An exit code of 0 does not prove the move (#4270): the wrapper reads the result on disk. The folder
of the change must be gone, and a folder `<date>-<change>` must be new in the archive.
"""

from __future__ import annotations

import re
from pathlib import Path

from devops_cli.config.commands import BIN_OPENSPEC, build_openspec_cmd
from devops_cli.config.constants import CONST_OPENSPEC_ARCHIVE_DIR, CONST_OPENSPEC_CHANGES_DIR
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import ToolExecutionError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool, output_of
from devops_cli.output import print_error


def archive_commands(change: str) -> list[list[str]]:
    """The arguments of the two `openspec` commands that archive `change`, in the order they run."""
    return [["archive", change, "--yes"], ["validate", "--all", "--strict"]]


def plan_archive(change: str) -> list[PlannedRequest]:
    """The two `openspec` commands that archive `change`, as a dry run lists them."""
    return [
        PlannedRequest(method="openspec", target=change, argv=tuple(build_openspec_cmd(*arguments)))
        for arguments in archive_commands(change)
    ]


def _archived_folders(root: Path, change: str) -> set[str]:
    """The names of the folders `<date>-<change>` in the archive of the checkout at `root`."""
    folder = re.compile(rf"\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(change)}")
    archive = root / CONST_OPENSPEC_ARCHIVE_DIR
    if not archive.is_dir():
        return set()
    return {
        entry.name for entry in archive.iterdir() if entry.is_dir() and folder.fullmatch(entry.name)
    }


def archive_change(tool: OpenSpecTool, root: Path, change: str) -> None:
    """Archive `change` in the checkout at `root`, then validate every spec and change.

    When a command fails, this function prints its whole output and raises `ToolExecutionError`
    that names the command and its exit code. The output of `validate` lists each passing spec
    before the failure, so a cut of the output would hide the spec that failed. A failed archive
    skips the validation. A failed validation says that the archive is already applied. A
    successful archive command that leaves the folder of the change in place, or makes no new
    archive folder, raises `ToolExecutionError` that names the change and the folder.
    """
    source = f"{CONST_OPENSPEC_CHANGES_DIR}/{change}"
    archived_before = _archived_folders(root, change)
    failures = (MESSAGES.openspec.archive_failed, MESSAGES.openspec.archive_left_invalid)
    for arguments, failure in zip(archive_commands(change), failures, strict=True):
        run = tool.run(arguments, root)
        if run.returncode != 0:
            print_error(output_of(run), prefix=False, safe=True)
            raise ToolExecutionError(
                failure.format(
                    command=" ".join(build_openspec_cmd(*arguments)), code=run.returncode
                ),
                tool_name=BIN_OPENSPEC,
            )
        if arguments[0] == "archive":
            _check_moved(
                root, change, source, archived_before, " ".join(build_openspec_cmd(*arguments))
            )


def _check_moved(
    root: Path, change: str, source: str, archived_before: set[str], command: str
) -> None:
    """Raise when the archive run left `source` in place or made no new archive folder."""
    if (root / source).exists():
        message = MESSAGES.openspec.archive_not_moved.format(
            command=command, change=change, folder=source
        )
    elif _archived_folders(root, change) <= archived_before:
        message = MESSAGES.openspec.archive_no_destination.format(
            command=command, change=change, folder=source, archive=CONST_OPENSPEC_ARCHIVE_DIR
        )
    else:
        return
    raise ToolExecutionError(message, tool_name=BIN_OPENSPEC)

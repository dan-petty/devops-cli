"""Archive a change into the living specs, then validate every spec and change (ADR 0010).

The pull request that closes a change archives it as its last commit. `openspec archive` applies the
deltas of the change to `openspec/specs/` and moves the folder. It can leave a spec that `validate`
rejects: a new capability gets a placeholder Purpose. So the wrapper validates after the archive.
It runs both commands under the isolated configuration (`isolated_openspec`). That configuration
keeps the telemetry and the per-user configuration of the tool out of the run. The wrapper passes no
`--skip-specs`, because a change that declares `skip_specs` archives without it.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.commands import BIN_OPENSPEC, build_openspec_cmd
from devops_cli.exceptions import ToolExecutionError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool, output_of
from devops_cli.output import print_error


def archive_commands(change: str) -> list[list[str]]:
    """The arguments of the two `openspec` commands that archive `change`, in the order they run."""
    return [["archive", change, "--yes"], ["validate", "--all", "--strict"]]


def archive_change(tool: OpenSpecTool, root: Path, change: str) -> None:
    """Archive `change` in the checkout at `root`, then validate every spec and change.

    When a command fails, this function prints its whole output and raises `ToolExecutionError`
    that names the command and its exit code. The output of `validate` lists each passing spec
    before the failure, so a cut of the output would hide the spec that failed. A failed archive
    skips the validation. A failed validation says that the archive is already applied.
    """
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

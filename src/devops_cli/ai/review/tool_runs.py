"""The runs of the review tools, as `review.md` shows them (#772).

A review starts many runs of the same tool. Gitleaks scans one file at a time, and a review of 300
files starts it 300 times. A run is one `ToolRun`, the record of what ran. `profile.json` keeps
every record. The report holds one row for each distinct record and counts its runs, because two
runs differ only by the files they scanned. A row shows how its runs ended: the exit code, and if
the scanner decided that the runs succeeded.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolRun

TOOL_RUNS_HEADING = "## Tool Runs"
TOOL_RUNS_COLUMNS = (
    "Tool",
    "Version",
    "Executor",
    "Binary",
    "Config",
    "Ruleset",
    "Commit",
    "Command",
    "Exit code",
    "Succeeded",
    "Runs",
)
# How many hexadecimal digits of the binary digest the report shows. `profile.json` holds all.
_BINARY_DIGEST_CHARS = 16
# The cell of the success of a record. A run that its scanner did not settle is `unknown`.
_SUCCEEDED: dict[bool | None, str] = {True: "yes", False: "no", None: "unknown"}


def tool_run_rows(runs: Iterable[ToolRun]) -> list[tuple[ToolRun, int]]:
    """Each distinct record with the number of runs that made it, in the order of the first run.

    The digest of the targets is not part of a record's identity here: it differs for every file.
    """
    counted = Counter(run.model_copy(update={"targets_digest": ""}) for run in runs)
    return list(counted.items())


def _cell(text: str) -> str:
    """`text` as the content of one table cell."""
    return " ".join(text.split()).replace("|", "\\|")


def _row(run: ToolRun, count: int) -> str:
    cells = (
        run.tool,
        run.version,
        run.executor,
        f"`{run.binary_sha256[:_BINARY_DIGEST_CHARS]}`",
        f"`{run.config_digest}`",
        f"`{run.ruleset_digest}`",
        f"`{run.commit}`" if run.commit else "none",
        f"`{' '.join(run.argv_template)}`",
        "none" if run.exit_code is None else str(run.exit_code),
        _SUCCEEDED[run.success],
        str(count),
    )
    return "| " + " | ".join(_cell(cell) for cell in cells) + " |"


def tool_runs_section(runs: Iterable[ToolRun]) -> list[str]:
    """The lines of the report section that lists the tool runs; none when no tool ran."""
    rows = tool_run_rows(runs)
    if not rows:
        return []
    header = "| " + " | ".join(TOOL_RUNS_COLUMNS) + " |"
    divider = "|" + "---|" * len(TOOL_RUNS_COLUMNS)
    return [TOOL_RUNS_HEADING, header, divider, *(_row(run, count) for run, count in rows), ""]

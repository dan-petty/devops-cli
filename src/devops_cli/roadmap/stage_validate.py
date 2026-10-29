"""The check of a planned OpenSpec change before the stage job writes it (#2654).

`validate_change` runs `openspec validate <change> --strict --json` on the files of the change in a
scratch directory. The directory also holds the base spec of each capability that the change
touches, so OpenSpec can judge a MODIFIED requirement against the real spec. OpenSpec reports a
delta that `openspec archive` would refuse as an INFO issue on a change that is valid, with exit
code 0. So every issue in the report counts as a problem: a change with an issue cannot be
archived, and the model gets one try to correct it.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ValidationError

from devops_cli.exceptions import RoadmapStageError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool, output_of
from devops_cli.roadmap.stage_change import write_change_files

# The most characters of a validation problem that goes back to the model or to a report.
_PROBLEM_CHARS = 2000


class _Issue(BaseModel):
    path: str = ""
    message: str


class _Item(BaseModel):
    issues: list[_Issue] = []


class _Report(BaseModel):
    items: list[_Item] = []


def _copy_base_specs(source: Path, scratch: Path, change: str, files: Mapping[str, str]) -> None:
    """Copy `openspec/specs/<capability>/spec.md` of the checkout for each capability that the
    change has a delta for, when the capability exists."""
    deltas = f"openspec/changes/{change}/specs/*/spec.md"
    for path in files:
        if not PurePosixPath(path).match(deltas):
            continue
        base = Path("openspec") / "specs" / PurePosixPath(path).parent.name / "spec.md"
        if (source / base).is_file():
            (scratch / base).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / base, scratch / base)


def _issues_of(stdout: str) -> list[str] | None:
    """The issues of an OpenSpec report as `path: message`, or None when the text is no report."""
    try:
        report = _Report.model_validate_json(stdout)
    except ValidationError:
        return None
    return [f"{issue.path}: {issue.message}" for item in report.items for issue in item.issues]


def validate_change(
    tool: OpenSpecTool, source: Path, change: str, files: Mapping[str, str]
) -> str | None:
    """The problems that OpenSpec finds in `files`, or None when it finds none.

    `source` is the checkout that holds the base specs. A run that exits non-zero with no report
    gives its output as it is. A run that exits zero with no report raises `RoadmapStageError`,
    as a validation that cannot be read is no pass. A timeout raises `ToolExecutionError`.
    """
    with tempfile.TemporaryDirectory(prefix="stage-") as scratch:
        root = Path(scratch)
        write_change_files(root, files)
        _copy_base_specs(source, root, change, files)
        run = tool.run(["validate", change, "--strict", "--json"], root)
    issues = _issues_of(run.stdout)
    if issues is None and run.returncode == 0:
        raise RoadmapStageError(MESSAGES.roadmap.stage_validate_unreadable)
    problem = "\n".join(issues) if issues else ""
    if not problem and run.returncode != 0:
        problem = output_of(run)
    return problem[:_PROBLEM_CHARS] or None

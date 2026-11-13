"""The check of a planned OpenSpec change before the stage job writes it (#2654).

`validate_change` runs `openspec validate <change> --strict --json` on the files of the change in a
scratch directory. The directory also holds the base spec of each capability that the change
touches, so OpenSpec can judge a MODIFIED requirement against the real spec. OpenSpec reports a
delta that `openspec archive` would refuse as an INFO issue on a change that is valid, with exit
code 0. So every issue in the report counts as a problem: a change with an issue cannot be
archived, and the model gets one try to correct it. One issue is no problem: the note that a change
sets `skip_specs` and so holds no delta (#3482). OpenSpec gives it as INFO for a valid plan.
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
from devops_cli.roadmap.stage.stage_change import (
    OmittedScenarios,
    StageProposal,
    omitted_scenarios,
    spec_file,
    spec_file_path,
    write_change_files,
)

# The most characters of a validation problem that goes back to the model or to a report.
_PROBLEM_CHARS = 2000
# The INFO message that OpenSpec 1.x gives for a change with `skip_specs: true` in its
# `.openspec.yaml`. The change is valid and archivable, so the message is no problem. Any other
# message stays a problem: it can be a delta that `openspec archive` refuses.
_SKIP_SPECS_NOTE = (
    "skip_specs is set in .openspec.yaml: change declares no spec-level behavior changes, "
    "zero deltas accepted"
)


def _base_scenarios(
    tool: OpenSpecTool, source: Path, capability: str
) -> dict[str, list[tuple[str, str]]] | None:
    """The name and the raw text of each scenario of each requirement of the base spec of
    `capability`, by requirement name, as `openspec show` gives them. None when the checkout holds
    no spec of the capability (#4310)."""
    if not (source / "openspec" / "specs" / capability / "spec.md").is_file():
        return None
    shown = tool.read_json(["show", capability, "--type", "spec", "--json"], source)
    return {
        str(requirement["name"]).strip(): [
            (str(scenario["name"]), str(scenario["rawText"]))
            for scenario in requirement["scenarios"]
        ]
        for requirement in shown["requirements"]
    }


def restore_omitted_scenarios(
    tool: OpenSpecTool,
    source: Path,
    change: str,
    proposal: StageProposal,
    files: Mapping[str, str],
) -> dict[str, str]:
    """`files` with each base scenario that a MODIFIED requirement omits added at the end of its
    block, with the raw text that OpenSpec gives (#4310). A MODIFIED block replaces the whole
    requirement, so `openspec archive` refuses a block that omits a scenario, and a scenario cannot
    be dropped on purpose. The scenarios of the reply stay as they are. The archive applies a rename
    before a MODIFIED block, so a requirement under the new name of a rename gets the scenarios of
    the old name (#5340). A requirement that the base spec lacks, and a capability with no base
    spec, are left to `validate_change`, which reports them."""
    repaired = dict(files)
    for spec in proposal.specs:
        base = _base_scenarios(tool, source, spec.capability) if spec.modified else None
        if base is None:
            continue
        base_names = spec.base_names()
        omitted: OmittedScenarios = {
            name: found
            for requirement in spec.modified
            if (name := requirement.name.strip())
            and (found := omitted_scenarios(requirement, base.get(base_names.get(name, name), ())))
        }
        if omitted:
            repaired[spec_file_path(change, spec.capability)] = spec_file(spec, omitted)
    return repaired


class _Issue(BaseModel):
    path: str = ""
    message: str


class _Item(BaseModel):
    issues: list[_Issue] = []


class _Report(BaseModel):
    items: list[_Item] = []


def _copy_base_specs(source: Path, scratch: Path, change: str, files: Mapping[str, str]) -> None:
    """Copy `openspec/specs/<capability>/spec.md` of the checkout for each capability, flat or
    nested, that the change has a delta for, when the capability exists."""
    deltas = PurePosixPath("openspec", "changes", change, "specs")
    for path in files:
        delta = PurePosixPath(path)
        if delta.name != "spec.md" or delta.parent == deltas or not delta.is_relative_to(deltas):
            continue
        base = Path("openspec", "specs", *delta.parent.relative_to(deltas).parts, "spec.md")
        if (source / base).is_file():
            (scratch / base).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / base, scratch / base)


def _issues_of(stdout: str) -> list[str] | None:
    """The issues of an OpenSpec report as `path: message`, or None when the text is no report."""
    try:
        report = _Report.model_validate_json(stdout)
    except ValidationError:
        return None
    return [
        f"{issue.path}: {issue.message}"
        for item in report.items
        for issue in item.issues
        if issue.message != _SKIP_SPECS_NOTE
    ]


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

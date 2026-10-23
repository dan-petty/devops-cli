"""The OpenSpec gate: what keeps a change folder valid and its tooling as committed (ADR 0010).

OpenSpec's own `validate` passes two changes that rewrite one requirement. Its configuration fails
quietly. So `devops openspec check` runs the pinned tool five ways and reports every problem it
finds:

1. `openspec validate --all --strict`, which fails an unknown key in a change's `.openspec.yaml`.
2. `openspec validate --archived`, a separate run because `--archived` replaces `--all`, which
   fails an archived change with unticked tasks.
3. A regeneration of the skills under the isolated profile, compared with the tree.
4. `openspec instructions` for a probe change, failing on any output to standard error, where the
   tool warns with exit 0 about a rule it ignores or a context it drops.
5. The overlap check: no requirement is rewritten by two active changes.

The gate archives nothing and reads no git history. The pull request that closes a change archives
it. The tool refuses a delta it cannot apply. Checks 1 and 2 fail what the archive leaves wrong,
such as a placeholder Purpose or an unticked task. A tree with no change and no spec passes every
check vacuously.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from devops_cli.config.constants import (
    CONST_OPENSPEC_CONFIG_FILENAME,
    CONST_OPENSPEC_DIR,
    CONST_OPENSPEC_INSTRUCTION_ARTIFACTS,
    CONST_OPENSPEC_PROBE_CHANGE,
)
from devops_cli.exceptions import ToolExecutionError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.overlap import overlapping_requirements
from devops_cli.openspec.skills import skill_drift
from devops_cli.openspec.tool import OpenSpecTool, active_changes, isolated_openspec, output_of

CONFIG_PATH = Path(CONST_OPENSPEC_DIR) / CONST_OPENSPEC_CONFIG_FILENAME


class GateCheck(StrEnum):
    """The checks the gate runs, as a finding names them."""

    CONFIGURATION = "configuration"
    VALIDATE = "validate"
    VALIDATE_ARCHIVED = "validate --archived"
    SKILLS = "skills"
    INSTRUCTIONS = "instructions"
    OVERLAP = "overlap"


@dataclass(frozen=True)
class GateFinding:
    """One problem the gate found, and the check that found it."""

    check: GateCheck
    detail: str

    def line(self) -> str:
        """The finding as one report line."""
        return MESSAGES.openspec.finding_line.format(check=self.check, detail=self.detail)


def _validation_findings(tool: OpenSpecTool, root: Path) -> list[GateFinding]:
    """Checks 1 and 2: every change, spec and archived change validates."""
    runs = {
        GateCheck.VALIDATE: ["validate", "--all", "--strict"],
        GateCheck.VALIDATE_ARCHIVED: ["validate", "--archived"],
    }
    return [
        GateFinding(check, output_of(run))
        for check, args in runs.items()
        if (run := tool.run(args, root)).returncode != 0
    ]


def _skill_findings(tool: OpenSpecTool, root: Path) -> list[GateFinding]:
    """Check 3: the committed skills are what a regeneration writes."""
    return [GateFinding(GateCheck.SKILLS, drift) for drift in skill_drift(tool, root)]


def _instruction_report(run: subprocess.CompletedProcess[str]) -> str:
    """What an `openspec instructions` run reports as wrong: its standard error, which the tool
    uses for the warnings it exits 0 after, else its output when it failed."""
    return run.stderr.strip() or (output_of(run) if run.returncode else "")


def _instruction_findings(tool: OpenSpecTool, root: Path) -> list[GateFinding]:
    """Check 4: a probe change gets the instructions of every artifact with nothing on standard
    error. Only the configuration is copied, so the probe leaves the tree alone."""
    with tempfile.TemporaryDirectory(prefix="openspec-probe-") as scratch:
        probe = Path(scratch)
        (probe / CONST_OPENSPEC_DIR).mkdir()
        (probe / CONFIG_PATH).write_bytes((root / CONFIG_PATH).read_bytes())
        tool.run_checked(["new", "change", CONST_OPENSPEC_PROBE_CHANGE], probe)
        runs = [
            tool.run(
                ["instructions", artifact, "--change", CONST_OPENSPEC_PROBE_CHANGE, "--json"], probe
            )
            for artifact in CONST_OPENSPEC_INSTRUCTION_ARTIFACTS
        ]
    reports = dict.fromkeys(line for run in runs for line in _instruction_report(run).splitlines())
    return [GateFinding(GateCheck.INSTRUCTIONS, "\n".join(reports))] if reports else []


def _overlap_findings(tool: OpenSpecTool, root: Path, changes: list[str]) -> list[GateFinding]:
    """Check 5: no requirement is rewritten by two active changes."""
    try:
        overlaps = overlapping_requirements(tool, root, changes)
    except ToolExecutionError as unreadable:
        return [GateFinding(GateCheck.OVERLAP, str(unreadable))]
    return [
        GateFinding(
            GateCheck.OVERLAP,
            MESSAGES.openspec.overlap.format(
                spec=overlap.capability,
                requirement=overlap.requirement,
                changes=", ".join(
                    f"{change} ({operation})" for change, operation in overlap.rewrites
                ),
            ),
        )
        for overlap in overlaps
    ]


def check_openspec(root: Path) -> list[GateFinding]:
    """Every problem the five checks find in the checkout at `root`; none when it is sound. A
    checkout with no `openspec/config.yaml` has nothing to check, and that is the one problem.

    Raises `DependencyError` naming the install command when `openspec` is not on PATH.
    """
    if not (root / CONFIG_PATH).is_file():
        missing = MESSAGES.openspec.config_missing.format(path=CONFIG_PATH.as_posix())
        return [GateFinding(GateCheck.CONFIGURATION, missing)]
    with isolated_openspec() as tool:
        changes = active_changes(tool, root)
        return [
            *_validation_findings(tool, root),
            *_skill_findings(tool, root),
            *_instruction_findings(tool, root),
            *_overlap_findings(tool, root, changes),
        ]

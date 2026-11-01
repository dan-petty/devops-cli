"""The golden set of the stage job: one directory of fixtures for each plan (#3028).

A case is a plan that the stage job staged, the issue it came from, the facts of the tree that the
gates need, and the defects a reviewer found in it. The files of a case directory are:

- `case.json`: the pull request and the commits, the verdict and scores of the review, and the
  defects. A defect has a type, a severity, the review text with its evidence, and the gate that
  must refuse it: `paths` (#3010), `kind` (#3005), `pending` (a gate that does not exist yet) or
  `none` (no gate judges it; a reviewer does).
- `issue.md`: the body of the issue, as the stage job read it.
- `plan.json`: the plan as a `StageProposal` holds it. The groups stay raw, as the model wrote
  them, so that a group the schema refuses is still a case.
- `facts.json`: the tracked files that the gates need, and the capabilities the plan names that
  exist. A replay cannot assume a deep clone, so it reads no git.

A case with the verdict `good` has no defect: every gate must accept it.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.core.repo import find_repo_root
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage_paths import StagedTree

# The folder of the cases, from the root of the repository.
CASES_DIRECTORY: Final[Path] = Path("tests/fixtures/roadmap_eval/stage")
_CASE_FILE: Final[str] = "case.json"
_ISSUE_FILE: Final[str] = "issue.md"
_PLAN_FILE: Final[str] = "plan.json"
_FACTS_FILE: Final[str] = "facts.json"
# The files of the change folder that the job writes, beside the spec of each capability.
_CHANGE_FILES: Final[tuple[str, ...]] = (".openspec.yaml", "proposal.md", "design.md", "tasks.md")


class DefectType(StrEnum):
    """What is wrong with a plan. Each gate catches one type."""

    MISSING_PATH = "missing_path"
    FALSE_PREMISE = "false_premise"
    SPEC_DELTA_WRONG = "spec_delta_wrong"
    VERIFY_FORM = "verify_form"
    TASK_ORDER = "task_order"
    CRITERION_DROPPED = "criterion_dropped"
    IGNORES_EXISTING_CODE = "ignores_existing_code"
    CONTRIVED_TEST = "contrived_test"
    OTHER = "other"


class GateName(StrEnum):
    """The gate that must refuse a defect: a gate that exists, a gate that does not exist yet, or
    none, when only a reviewer can judge the defect."""

    PATHS = "paths"
    KIND = "kind"
    PENDING = "pending"
    NONE = "none"


class Severity(StrEnum):
    """How much a defect costs, as the review graded it."""

    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"
    NIT = "nit"


class Verdict(StrEnum):
    """What the review decided about a plan. `good` is a plan with no known defect."""

    GOOD = "good"
    ACCEPTABLE = "acceptable"
    NEEDS_FIX = "needs-fix"
    REJECT = "reject"


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Defect(_Record):
    """One defect of a plan, with the text and the evidence of the review. `paths` lists the paths
    of a `missing_path` defect that the gate must name."""

    type: DefectType
    severity: Severity
    where: str
    problem: str
    evidence: str
    gate: GateName
    paths: tuple[str, ...] = ()


class Scores(_Record):
    """The five scores of the review, from 1 to 5."""

    premise_ok: int
    fidelity: int
    task_quality: int
    rule_compliance: int
    accuracy: int


class CaseFacts(_Record):
    """What the gates need of the tree at the staging commit: the tracked files that matter, and
    the capabilities the plan names that have a spec."""

    tracked: tuple[str, ...]
    capabilities: tuple[str, ...]


class StageCase(_Record):
    """One case of the golden set. `name` is the directory, `change` the change folder the job
    wrote, `base_commit` the commit the plan was staged on, and `twin_of` the case a `good` case
    corrects."""

    name: str
    issue: int
    pull: int
    title: str
    change: str
    merge_commit: str
    base_commit: str
    verdict: Verdict
    scores: Scores
    state: str
    summary: str
    notes: tuple[str, ...] = ()
    twin_of: str | None = None
    defects: tuple[Defect, ...] = ()
    issue_body: str
    plan: dict[str, Any]
    facts: CaseFacts

    @property
    def groups(self) -> list[dict[str, Any]]:
        """The raw task groups of the plan."""
        groups: list[dict[str, Any]] = self.plan["groups"]
        return groups

    def change_files(self) -> list[str]:
        """The files of the change folder that the job writes in the same commit."""
        root = f"openspec/changes/{self.change}"
        specs = (f"{root}/specs/{spec['capability']}/spec.md" for spec in self.plan["specs"])
        return [*(f"{root}/{name}" for name in _CHANGE_FILES), *specs]

    def tree(self) -> StagedTree:
        """The files that exist when the change is written: the facts and the change folder."""
        return StagedTree(self.facts.tracked).with_files(self.change_files())

    def defect_types(self) -> frozenset[DefectType]:
        """The types of the known defects."""
        return frozenset(defect.type for defect in self.defects)


def cases_root(directory: Path | None = None) -> Path:
    """The folder of the cases: `directory`, or the default folder of this checkout."""
    return directory or find_repo_root() / CASES_DIRECTORY


def _read_case(folder: Path) -> StageCase:
    """The case in `folder`. A file that is missing or does not match the model raises
    `ConfigurationError` that names the folder."""
    try:
        meta: dict[str, Any] = json.loads((folder / _CASE_FILE).read_text(encoding="utf-8"))
        return StageCase.model_validate(
            {
                **meta,
                "name": folder.name,
                "issue_body": (folder / _ISSUE_FILE).read_text(encoding="utf-8"),
                "plan": json.loads((folder / _PLAN_FILE).read_text(encoding="utf-8")),
                "facts": json.loads((folder / _FACTS_FILE).read_text(encoding="utf-8")),
            }
        )
    except (OSError, ValueError, ValidationError) as exc:
        raise ConfigurationError(
            MESSAGES.roadmap.stage_eval_bad_case.format(name=folder.name, reason=exc),
            details={"case": folder.name},
        ) from exc


def load_cases(directory: Path | None = None) -> list[StageCase]:
    """The cases of the golden set, sorted by name. A folder that is missing or holds no case
    raises `ConfigurationError`."""
    root = cases_root(directory)
    folders = sorted(path for path in root.glob("*") if (path / _CASE_FILE).is_file())
    if not folders:
        raise ConfigurationError(
            MESSAGES.roadmap.stage_eval_no_cases.format(path=root), details={"path": str(root)}
        )
    return [_read_case(folder) for folder in folders]


def select_cases(
    cases: list[StageCase], names: tuple[str, ...], limit: int | None
) -> list[StageCase]:
    """The cases that `names` pick, each by its directory name or its issue number, in the order of
    the set, and then the first `limit`. A name that picks no case raises `ConfigurationError`."""
    if names:
        unknown = [
            name
            for name in names
            if not any(name in (case.name, str(case.issue)) for case in cases)
        ]
        if unknown:
            raise ConfigurationError(
                MESSAGES.roadmap.stage_eval_unknown_case.format(names=", ".join(unknown)),
                details={"cases": unknown},
            )
        cases = [case for case in cases if case.name in names or str(case.issue) in names]
    return cases[:limit] if limit else cases

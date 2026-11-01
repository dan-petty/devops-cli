"""The score of a live run of the golden set (#3028).

For each type of defect that a gate catches, the score counts the cases whose recorded plan had a
defect of that type, and how the model did on them. The model *avoided* the defect when the first
reply of the model passes the gate. The gate *caught* it when the first reply fails the gate, so
the job sent the reply back. A reply that never came counts as neither. The score of the run is
the share of avoided defects over the cases of the types that a gate catches. A type with no gate
yet is listed with its count and has no rate: a reviewer judges it.

A change to the stage prompt or to the checks states this score before and after in its pull
request (docs/ROADMAP_WORKFLOW.md).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from devops_cli.roadmap.stage_eval_cases import DefectType, GateName, StageCase
from devops_cli.roadmap.stage_eval_gates import PENDING_GATES, gate_for
from devops_cli.roadmap.stage_eval_run import CaseRun, Outcome


@dataclass(frozen=True)
class DefectScore:
    """The score of one type of defect. `gate` is the gate that catches it, `pending` when the
    gate is planned, or `none`. `avoided` and `caught` are None when no gate judges the type."""

    type: DefectType
    gate: GateName
    cases: int
    avoided: int | None
    caught: int | None

    @property
    def rate(self) -> float | None:
        """The share of the cases that the model got right, or None when no gate judges the type
        or no case has the type."""
        if self.avoided is None or not self.cases:
            return None
        return self.avoided / self.cases


@dataclass(frozen=True)
class StageScore:
    """The score of a run: a row for each type of defect, and the cases by how they ended."""

    model: str
    rows: tuple[DefectScore, ...]
    ended: Mapping[Outcome, int]
    cases: int

    @property
    def scored(self) -> tuple[int, int]:
        """The defects avoided, and the cases of the scored types, over all scored rows."""
        rows = [row for row in self.rows if row.avoided is not None]
        return sum(row.avoided or 0 for row in rows), sum(row.cases for row in rows)

    @property
    def total(self) -> float | None:
        """The share of avoided defects over the scored rows, or None when no row is scored."""
        avoided, cases = self.scored
        return avoided / cases if cases else None


def _first_problems(run: CaseRun | None, gate: GateName) -> list[str] | None:
    """The problems of `gate` in the first reply of the run, or None when no reply came."""
    if run is None or run.first is None:
        return None
    return run.first.get(gate, [])


def _row(
    defect_type: DefectType, cases: Sequence[StageCase], runs: Mapping[str, CaseRun]
) -> DefectScore:
    known = [case for case in cases if defect_type in case.defect_types()]
    gate = gate_for(defect_type)
    if gate in (GateName.PENDING, GateName.NONE):
        return DefectScore(defect_type, gate, len(known), None, None)
    seen = [_first_problems(runs.get(case.name), gate) for case in known]
    return DefectScore(
        defect_type,
        gate,
        len(known),
        sum(problems == [] for problems in seen),
        sum(bool(problems) for problems in seen),
    )


def score_runs(model: str, cases: Sequence[StageCase], runs: Sequence[CaseRun]) -> StageScore:
    """The score of `runs` over `cases`, one row for each type of defect."""
    by_name = {run.name: run for run in runs}
    types = [*DefectType]
    ended = {outcome: sum(run.outcome is outcome for run in runs) for outcome in Outcome}
    return StageScore(model, tuple(_row(t, cases, by_name) for t in types), ended, len(cases))


def pending_reference(defect_type: DefectType) -> str:
    """The issue that builds the gate of the type, or an empty text when none is planned."""
    return PENDING_GATES.get(defect_type, "")

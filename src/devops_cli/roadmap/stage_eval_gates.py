"""The deterministic gates of the stage job, and the replay of a recorded plan through them (#3028).

A gate finds one type of defect in a plan with no model. `paths` is the check of the job on a plan
(`check_proposal`): the path gate (#3010), where every path a group names is a file of the staged
commit or a group creates it, and the rules of the spec delta, which use the capabilities of the
case. `kind` is the kind rule
(#3005): a group that the schema of the reply refuses. Gates that do not exist yet (#3011 to #3019)
are in `PENDING_GATES`: a defect that one of them will catch is listed, and it fails nothing.

`replay_case` runs the gates on the plan of a case, as the job runs them on a reply, and checks
each known defect against the gate that must refuse it. The replay reads no git and makes no model
call, so the test suite runs it on the whole set. It fails when a gate stops refusing a known-bad
plan, when a gate refuses a `good` plan, and when a defect waits for a gate that exists now.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from pydantic import ValidationError

from devops_cli.roadmap.stage_change import (
    GroupKind,
    StageGroup,
    StageProposal,
    StageSpec,
    check_proposal,
)
from devops_cli.roadmap.stage_eval_cases import (
    Defect,
    DefectType,
    GateName,
    StageCase,
    Verdict,
)
from devops_cli.roadmap.stage_paths import StagedTree


@dataclass(frozen=True)
class PlanUnderTest:
    """A plan as the gates judge it: the proposal, the problems the schema found in it, the names
    of the capabilities that have a spec, and the files that exist when the change is written. A
    reply that the job accepted has no schema problem, since the client sends a reply that breaks
    the schema back before the checks."""

    proposal: StageProposal
    schema_problems: tuple[str, ...]
    known: frozenset[str]
    tree: StagedTree

    @classmethod
    def of_case(cls, case: StageCase) -> PlanUnderTest:
        """The plan of a case. A raw group or spec that fails the schema is kept as it is when it
        can be, with the message of the schema as a problem, so the other gates still judge it."""
        problems: list[str] = []
        groups = [_group_of(raw, problems) for raw in case.groups]
        specs = [spec for raw in case.plan["specs"] if (spec := _spec_of(raw, problems))]
        proposal = StageProposal.model_construct(**{**case.plan, "specs": specs, "groups": groups})
        return cls(proposal, tuple(problems), frozenset(case.facts.capabilities), case.tree())

    @classmethod
    def of_reply(
        cls, proposal: StageProposal, tree: StagedTree, known: Collection[str]
    ) -> PlanUnderTest:
        """The plan of a reply that passed the schema, with the tree it was staged on."""
        return cls(proposal, (), frozenset(known), tree)


def _group_of(raw: Mapping[str, Any], problems: list[str]) -> StageGroup:
    """The group that `raw` holds. A group that fails the schema is built with no check, and the
    messages of the schema are added to `problems`."""
    try:
        return StageGroup.model_validate(raw)
    except ValidationError as exc:
        problems.extend(error["msg"] for error in exc.errors())
        return StageGroup.model_construct(**{**raw, "kind": GroupKind(raw["kind"])})


def _spec_of(raw: Mapping[str, Any], problems: list[str]) -> StageSpec | None:
    """The spec that `raw` holds, or None when it fails the schema; the messages of the schema are
    added to `problems`."""
    try:
        return StageSpec.model_validate(raw)
    except ValidationError as exc:
        problems.extend(error["msg"] for error in exc.errors())
        return None


@dataclass(frozen=True)
class Gate:
    """A check of the job: the name, the issue that built it, the type of defect it catches, and
    the function that gives the problems it finds, one sentence each."""

    name: GateName
    reference: str
    catches: DefectType
    check: Callable[[PlanUnderTest], list[str]]


def _path_gate(plan: PlanUnderTest) -> list[str]:
    """The checks of the job on a plan (`check_proposal`): the path rule and the rules of the spec
    delta. The recorded plans hold no bad spec, so these rules only refuse a good plan."""
    return check_proposal(plan.proposal, plan.known, plan.tree)


def _kind_gate(plan: PlanUnderTest) -> list[str]:
    return list(plan.schema_problems)


GATES: Final[tuple[Gate, ...]] = (
    Gate(GateName.PATHS, "#3010", DefectType.MISSING_PATH, _path_gate),
    Gate(GateName.KIND, "#3005", DefectType.CONTRIVED_TEST, _kind_gate),
)
# The gates that are not built yet, by the type of defect they will catch.
PENDING_GATES: Final[Mapping[DefectType, str]] = {
    DefectType.FALSE_PREMISE: "#3011",
    DefectType.IGNORES_EXISTING_CODE: "#3012",
    DefectType.SPEC_DELTA_WRONG: "#3013",
    DefectType.VERIFY_FORM: "#3015",
    DefectType.TASK_ORDER: "#3017",
    DefectType.CRITERION_DROPPED: "#3019",
}
_GATE_BY_TYPE: Final[Mapping[DefectType, Gate]] = {gate.catches: gate for gate in GATES}


def gate_for(defect_type: DefectType) -> GateName:
    """The gate that catches the type today: its name, `pending` when a gate is planned, else
    `none`."""
    if defect_type in _GATE_BY_TYPE:
        return _GATE_BY_TYPE[defect_type].name
    return GateName.PENDING if defect_type in PENDING_GATES else GateName.NONE


def run_gates(plan: PlanUnderTest) -> dict[GateName, list[str]]:
    """The problems each gate finds in the plan, by gate. A gate that finds none has an empty
    list."""
    return {gate.name: gate.check(plan) for gate in GATES}


class DefectStatus(StrEnum):
    """What the replay found for a known defect."""

    CAUGHT = "caught"
    MISSED = "missed"
    PENDING = "pending"
    STALE = "stale"
    UNJUDGED = "unjudged"


@dataclass(frozen=True)
class DefectOutcome:
    """A known defect and what the replay found for it."""

    defect: Defect
    status: DefectStatus


@dataclass(frozen=True)
class CaseReplay:
    """The replay of one case: the problems of each gate, and the outcome of each known defect."""

    case: StageCase
    problems: Mapping[GateName, list[str]]
    outcomes: tuple[DefectOutcome, ...]

    @property
    def refused(self) -> bool:
        """Whether any gate refuses the plan."""
        return any(self.problems.values())

    @property
    def failures(self) -> list[str]:
        """What fails the replay of this case, one sentence each."""
        found = [
            f"{self.case.name}: the gate `{o.defect.gate}` no longer refuses the {o.defect.type} "
            f"defect ({o.defect.where})."
            for o in self.outcomes
            if o.status is DefectStatus.MISSED
        ]
        found += [
            f"{self.case.name}: the {o.defect.type} defect waits for a gate, and the gate "
            f"`{gate_for(o.defect.type)}` exists now. Set its gate in case.json."
            for o in self.outcomes
            if o.status is DefectStatus.STALE
        ]
        if self.case.verdict is Verdict.GOOD and self.refused:
            refusing = ", ".join(str(name) for name, found_ in self.problems.items() if found_)
            found.append(f"{self.case.name}: a good plan is refused by the gate {refusing}.")
        return found


def _names_every_path(problems: Sequence[str], paths: Sequence[str]) -> bool:
    return all(any(f"`{path}`" in problem for problem in problems) for path in paths)


def _explains(problems: Sequence[str], defect: Defect) -> bool:
    """Whether the problems name every path of the defect and hold its message."""
    holds_message = not defect.message or any(defect.message in problem for problem in problems)
    return holds_message and _names_every_path(problems, defect.paths)


def _status(defect: Defect, problems: Mapping[GateName, list[str]]) -> DefectStatus:
    """The status of one defect against the problems the gates found."""
    if defect.gate is GateName.NONE:
        return DefectStatus.UNJUDGED
    if defect.gate is GateName.PENDING:
        stale = gate_for(defect.type) is not GateName.PENDING
        return DefectStatus.STALE if stale else DefectStatus.PENDING
    found = problems.get(defect.gate, [])
    caught = bool(found) and _explains(found, defect)
    return DefectStatus.CAUGHT if caught else DefectStatus.MISSED


def replay_case(case: StageCase) -> CaseReplay:
    """Run the gates on the recorded plan of `case` and judge each known defect."""
    problems = run_gates(PlanUnderTest.of_case(case))
    outcomes = tuple(DefectOutcome(defect, _status(defect, problems)) for defect in case.defects)
    return CaseReplay(case, problems, outcomes)


@dataclass(frozen=True)
class GateTotals:
    """What one gate did over the set: the known defects it must refuse, and how many it did."""

    gate: Gate
    known: int
    caught: int

    @property
    def missed(self) -> int:
        """The known defects the gate no longer refuses."""
        return self.known - self.caught


@dataclass(frozen=True)
class ReplayReport:
    """The replay of the whole set."""

    replays: tuple[CaseReplay, ...]

    @property
    def failures(self) -> list[str]:
        """Every failure of every case."""
        return [failure for replay in self.replays for failure in replay.failures]

    def totals(self) -> list[GateTotals]:
        """The totals of each gate, in the order of `GATES`."""
        outcomes = [o for replay in self.replays for o in replay.outcomes]
        return [
            GateTotals(
                gate,
                known=sum(o.defect.gate is gate.name for o in outcomes),
                caught=sum(
                    o.defect.gate is gate.name and o.status is DefectStatus.CAUGHT for o in outcomes
                ),
            )
            for gate in GATES
        ]

    def count(self, status: DefectStatus) -> dict[DefectType, int]:
        """The defects with `status`, by type, for the types that have some."""
        counts: dict[DefectType, int] = {}
        for replay in self.replays:
            for outcome in replay.outcomes:
                if outcome.status is status:
                    counts[outcome.defect.type] = counts.get(outcome.defect.type, 0) + 1
        return counts

    def good(self) -> tuple[int, int]:
        """The `good` plans that every gate accepts, and the `good` plans in the set."""
        good = [r for r in self.replays if r.case.verdict is Verdict.GOOD]
        return sum(not r.refused for r in good), len(good)


def replay_all(cases: Sequence[StageCase]) -> ReplayReport:
    """Replay every case."""
    return ReplayReport(tuple(replay_case(case) for case in cases))

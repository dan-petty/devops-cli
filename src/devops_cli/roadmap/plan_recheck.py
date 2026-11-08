"""The plan recheck (#3492): each change folder on the default branch, judged again.

A merged plan is judged once, when the stage job writes it. A later gate can strand an old plan, a
plan can be delivered while its issue stays open, and the folder of a closed issue stays in every
count. `devops roadmap plan-recheck` reads every numbered folder of `openspec/changes/` on
`origin/<default branch>` and gives each one result:

- `cleanup`: the issue of the folder is closed. No count holds the folder.
- `delivered`: every file that the plan marks `(new)` is on the default branch.
- `new-plan`: the plan does not read, or it fails a gate or `openspec validate`, also after the
  mechanical rewrite of `plan_rewrite`. The first problem of the rewritten plan is the reason.
- `rewrite`: the plan as it is fails the reader or lacks a file, and the mechanical rewrite fixes
  it. The pass applies the rewrite in memory and gives `rewrite` only when the rewritten plan
  reads and passes every check (#3556). `--confirm` writes the rewrite.
- `ok`: none of the above. The rewrite changes nothing in the plan.

The pass reads the same plan reader (`read_change`), the same gates (`check_gates`) and the same
OpenSpec check (`validate_change`) as `devops roadmap plan-check`. It calls no model and writes
nothing to git or to GitHub. It writes no file either: `plan_rewrite.write_rewrite` does that, for
the folders with the result `rewrite`.

Each refusal has a gate (#3498): `read` for a folder that the plan reader refuses, `openspec` for a
finding of `openspec validate`, or a name of `ProposalGate`. With a branch, the pass judges the
folders of that ref on its own tree as well, and it lists the refusals that the branch adds to the
result of the default branch. A refusal on a merged plan is a case to review: it can be a hit or a
false refusal, and only a person decides which.

The pass judges less than the stage job. It gives `check_gates` no `probes`, `overlaps`,
`search_evidence` or `plan_creates`. It records the tests that each changed manifest reaches from a
search at the ref, so a merged manifest plan gets the refusal of a staged one (#3972). It does not
measure the groups, scan the files for secrets or check the staging title, and it calls no model.
It judges the plan on the tree of the default branch or of the branch, and not on the commit that
the job staged. So a plan that it accepts can still fail the job.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from devops_cli.config.constants import CONST_OPENSPEC_CHANGES_DIR
from devops_cli.exceptions.git import GitOperationError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.plan_read import (
    PlanReadError,
    created_paths,
    files_at,
    read_change,
    specs_at,
    tree_files,
)
from devops_cli.roadmap.plan_rewrite import PlanRewrite, rewrite_plan
from devops_cli.roadmap.planned import PlannedChanges, planned_changes_at, read_planned_changes
from devops_cli.roadmap.stage.stage_change import check_gates
from devops_cli.roadmap.stage.stage_paths import StagedTree, record_test_references
from devops_cli.roadmap.stage.stage_validate import validate_change
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.stores.store import GitHubState, Item, RoadmapStore

GIT_OPERATION: Final[str] = "roadmap.plan-recheck"
# The gates of a refusal that `check_gates` does not name (#3498).
GATE_READ: Final[str] = "read"
GATE_OPENSPEC: Final[str] = "openspec"
_DESIGN: Final[str] = "design.md"
_TASKS: Final[str] = "tasks.md"


class PlanResult(StrEnum):
    """The one result of a change folder."""

    OK = "ok"
    REWRITE = "rewrite"
    NEW_PLAN = "new-plan"
    DELIVERED = "delivered"
    CLEANUP = "cleanup"


@dataclass(frozen=True)
class Refusal:
    """One problem that a gate finds in a change folder (#3498): the folder, the name of the gate
    and the message of the gate. A refusal is a case to review, not a proven false refusal."""

    folder: str
    gate: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"folder": self.folder, "gate": self.gate, "message": self.message}


@dataclass(frozen=True)
class PlanRecord:
    """The result of one change folder, the reasons for it, and the two facts that the counts
    use. `notes` explain a result that is no refusal (for `rewrite`, the edits), and `refusals`
    hold the problems of a `new-plan`. `readable` is false when the plan reader refuses the folder
    as it is on the branch. `verified` is false when no group of `tasks.md` has a `Verification:`
    line. `rewrite` holds the rewritten files of a `rewrite` folder, and is None for any other."""

    folder: str
    issue: int
    result: PlanResult
    notes: tuple[str, ...] = ()
    refusals: tuple[Refusal, ...] = ()
    readable: bool = True
    verified: bool = True
    rewrite: PlanRewrite | None = None

    def as_dict(self) -> dict[str, object]:
        report: dict[str, object] = {
            "folder": self.folder,
            "issue": self.issue,
            "result": self.result.value,
            "notes": list(self.notes),
            "refusals": [refusal.as_dict() for refusal in self.refusals],
        }
        if self.rewrite is not None:
            report["files"] = [change.path for change in self.rewrite.changes]
        return report


def _count(records: Iterable[PlanRecord], result: PlanResult) -> int:
    return sum(1 for record in records if record.result is result)


def refusals_by_gate(records: Iterable[PlanRecord]) -> dict[str, tuple[Refusal, ...]]:
    """The refusals of `records` by the name of their gate, in the order of the gate names. The
    refusals of a gate keep the order of the records."""
    found: dict[str, list[Refusal]] = {}
    for record in records:
        for refusal in record.refusals:
            found.setdefault(refusal.gate, []).append(refusal)
    return {gate: tuple(found[gate]) for gate in sorted(found)}


def _gate_counts(records: Iterable[PlanRecord]) -> dict[str, int]:
    return {gate: len(found) for gate, found in refusals_by_gate(records).items()}


@dataclass(frozen=True)
class BranchRecheck:
    """The folders of the branch `ref`, judged on the tree of the branch."""

    ref: str
    records: tuple[PlanRecord, ...]

    @property
    def unread(self) -> tuple[str, ...]:
        """The folders that the plan reader refuses: they are not read."""
        return tuple(record.folder for record in self.records if not record.readable)


@dataclass(frozen=True)
class PlanRecheck:
    """The records of the pass, by issue number. The folders of closed issues are in the records,
    and in no count: `live` holds the others. `branch` holds the folders of the ref that a person
    compares with the default branch, or None."""

    default: str
    records: tuple[PlanRecord, ...]
    branch: BranchRecheck | None = None

    @property
    def live(self) -> tuple[PlanRecord, ...]:
        """The records that every count includes: all but the folders of closed issues."""
        return tuple(r for r in self.records if r.result is not PlanResult.CLEANUP)

    def count(self, result: PlanResult) -> int:
        """How many folders got `result`."""
        return _count(self.records, result)

    @property
    def unverified(self) -> int:
        """How many live folders have no marked `Verification:` command."""
        return sum(1 for record in self.live if not record.verified)

    @property
    def unreadable(self) -> int:
        """How many live folders the plan reader refuses."""
        return sum(1 for record in self.live if not record.readable)

    @property
    def new_refusals(self) -> tuple[Refusal, ...]:
        """The refusals of the branch that the default branch does not hold for the same folder,
        gate and message. Each one is a case to review. A run with no branch has none."""
        if self.branch is None:
            return ()
        held = {refusal for record in self.records for refusal in record.refusals}
        return tuple(
            refusal
            for record in self.branch.records
            for refusal in record.refusals
            if refusal not in held
        )

    def summary(self) -> dict[str, int]:
        """The counts of the pass, by name."""
        return {
            "live": len(self.live),
            "unverified": self.unverified,
            "unreadable": self.unreadable,
            **{result.value: self.count(result) for result in PlanResult},
        }

    def as_dict(self) -> dict[str, object]:
        """The report as JSON data: the folders, the counts and the refusals for each gate, and
        with a branch, the comparison."""
        report: dict[str, object] = {
            "folders": [record.as_dict() for record in self.records],
            "summary": self.summary(),
            "gates": _gate_counts(self.records),
        }
        if self.branch is not None:
            label = MESSAGES.roadmap.plan_recheck_case
            report["branch"] = {
                "ref": self.branch.ref,
                "folders": [record.as_dict() for record in self.branch.records],
                "gates": _gate_counts(self.branch.records),
                "new_refusals": [
                    {**refusal.as_dict(), "label": label} for refusal in self.new_refusals
                ],
                "not_read": list(self.branch.unread),
            }
        return report


@dataclass(frozen=True)
class _Pass:
    """What the pass reads once for a ref and every folder of it shares. `name` is the ref as the
    messages call it."""

    source: Path
    rev: str
    name: str
    paths: Sequence[str]
    tree: StagedTree
    known: frozenset[str]
    requirements: dict[str, tuple[str, ...]]
    open_items: dict[int, Item]
    closed: frozenset[int]
    tool: OpenSpecTool
    test_search: Callable[[str], Sequence[str]]


def _refused(
    folder: str, issue: int, refusals: Iterable[Refusal], *, readable: bool = True, verified: bool
) -> PlanRecord:
    return PlanRecord(
        folder,
        issue,
        PlanResult.NEW_PLAN,
        refusals=tuple(refusals),
        readable=readable,
        verified=verified,
    )


def _test_search(source: Path, rev: str) -> Callable[[str], Sequence[str]]:
    """The search of the tests at `rev` that hold a literal: one `git grep -l -F` over `tests`. A
    literal that no test holds, and a failed read, gives no file. The record of a manifest plan
    reads it (#3972)."""
    cache: dict[str, tuple[str, ...]] = {}

    def search(literal: str) -> Sequence[str]:
        if literal not in cache:
            cache[literal] = _grep_tests(source, rev, literal)
        return cache[literal]

    return search


def _grep_tests(source: Path, rev: str, literal: str) -> tuple[str, ...]:
    """The tests at `rev` that hold `literal`, sorted."""
    try:
        listing = git(
            source,
            "grep",
            "-l",
            "-F",
            "-e",
            literal,
            rev,
            "--",
            "tests",
            operation=GIT_OPERATION,
        )
    except GitOperationError:
        return ()
    prefix = f"{rev}:"
    return tuple(sorted({line.removeprefix(prefix) for line in listing.splitlines() if line}))


def _reads(files: dict[str, str], root: str) -> bool:
    """Whether the plan reader accepts the folder as it is. A folder with no `design.md` is read
    with an empty one: the rewrite adds the file, so its absence is no reader error."""
    design = f"{root}/{_DESIGN}"
    try:
        read_change(files if design in files else {**files, design: ""})
    except PlanReadError:
        return False
    return True


def _record(shared: _Pass, issue: int, folder: str) -> PlanRecord:
    texts = MESSAGES.roadmap
    if issue in shared.closed:
        return PlanRecord(
            folder, issue, PlanResult.CLEANUP, (texts.plan_recheck_closed.format(issue=issue),)
        )
    root = f"{CONST_OPENSPEC_CHANGES_DIR}/{folder}"
    names = [path for path in shared.paths if path.startswith(f"{root}/")]
    files = files_at(shared.source, shared.rev, names, operation=GIT_OPERATION)
    tasks = files.get(f"{root}/{_TASKS}", "")
    verified = any(group.verification_commands for group in parse_task_groups(tasks))
    created = created_paths(tasks)
    if created and all(path in shared.tree.files for path in created):
        listed = ", ".join(f"`{path}`" for path in created)
        reason = texts.plan_recheck_delivered.format(paths=listed, branch=shared.name, issue=issue)
        return PlanRecord(folder, issue, PlanResult.DELIVERED, (reason,), verified=verified)
    readable = _reads(files, root)
    rewrite = rewrite_plan(root, files, shared.tree)
    judged = rewrite.files
    try:
        proposal = read_change(judged)
    except PlanReadError as exc:
        reason = texts.plan_check_read.format(path=exc.path, reason=exc.reason)
        return _refused(
            folder,
            issue,
            [Refusal(folder, GATE_READ, reason)],
            readable=readable,
            verified=verified,
        )
    held = shared.open_items.get(issue)
    found = check_gates(
        proposal,
        shared.known,
        shared.tree,
        requirements=shared.requirements,
        issue_body=held.body if held is not None else "",
        manifest_references=record_test_references(proposal.groups, shared.test_search),
    )
    refusals = [
        Refusal(folder, gate.value, problem)
        for gate, problems in found.items()
        for problem in problems
    ]
    if report := validate_change(shared.tool, shared.source, folder, judged):
        message = texts.plan_recheck_openspec.format(problem=" ".join(report.split()))
        refusals.append(Refusal(folder, GATE_OPENSPEC, message))
    if refusals:
        return _refused(folder, issue, refusals, readable=readable, verified=verified)
    if rewrite.changes:
        return PlanRecord(
            folder,
            issue,
            PlanResult.REWRITE,
            rewrite.notes,
            readable=readable,
            verified=verified,
            rewrite=rewrite,
        )
    return PlanRecord(folder, issue, PlanResult.OK, verified=verified)


def _judge(
    source: Path,
    planned: PlannedChanges,
    rev: str,
    name: str,
    *,
    open_items: dict[int, Item],
    closed: frozenset[int],
    tool: OpenSpecTool,
) -> tuple[PlanRecord, ...]:
    """The record of each active folder of `planned`, judged on the tree at `rev`."""
    paths = tree_files(source, rev, operation=GIT_OPERATION)
    known, requirements = specs_at(source, rev, operation=GIT_OPERATION)
    shared = _Pass(
        source=source,
        rev=rev,
        name=name,
        paths=paths,
        tree=StagedTree(paths),
        known=known,
        requirements=requirements,
        open_items=open_items,
        closed=closed,
        tool=tool,
        test_search=_test_search(source, rev),
    )
    return tuple(_record(shared, issue, folder) for issue, folder in sorted(planned.active.items()))


def _closed_issues(
    store: RoadmapStore, open_items: dict[int, Item], issues: Iterable[int]
) -> frozenset[int]:
    """The issues among `issues` that are closed. An issue that is not open and is no Item is not
    closed: the folder is judged as the folder of an open issue."""
    closed: set[int] = set()
    for issue in sorted(set(issues) - open_items.keys()):
        held = store.item(issue)
        if held is not None and held.state is GitHubState.CLOSED:
            closed.add(issue)
    return frozenset(closed)


def recheck_plans(
    source: Path, store: RoadmapStore, *, tool: OpenSpecTool, branch: str | None = None
) -> PlanRecheck:
    """Judge each change folder on the default branch of the clone at `source` again. `store`
    tells which issues are closed. With `branch`, a ref of the clone, the pass judges the folders
    of that ref on its own tree too (#3498). The pass reads and writes nothing else."""
    planned = read_planned_changes(source, operation=GIT_OPERATION)
    rev = f"origin/{planned.default}"
    on_branch = (
        None
        if branch is None
        else planned_changes_at(source, branch, planned.default, operation=GIT_OPERATION)
    )
    open_items = {item.number: item for item in store.open_items()}
    issues = [*planned.active, *([] if on_branch is None else on_branch.active)]
    closed = _closed_issues(store, open_items, issues)
    records = _judge(
        source, planned, rev, planned.default, open_items=open_items, closed=closed, tool=tool
    )
    if branch is None or on_branch is None:
        return PlanRecheck(planned.default, records)
    judged = _judge(
        source, on_branch, branch, branch, open_items=open_items, closed=closed, tool=tool
    )
    return PlanRecheck(planned.default, records, BranchRecheck(branch, judged))


def _joined(counts: dict[str, int]) -> str:
    texts = MESSAGES.roadmap
    return ", ".join(f"{gate} {count}" for gate, count in counts.items()) or texts.plan_recheck_none


def _render_folders(records: Iterable[PlanRecord]) -> list[str]:
    texts = MESSAGES.roadmap
    lines: list[str] = []
    for record in records:
        lines.append(
            texts.plan_recheck_line.format(result=record.result.value, folder=record.folder)
        )
        lines.extend(texts.plan_recheck_reason.format(reason=note) for note in record.notes)
        lines.extend(
            texts.plan_recheck_refusal.format(gate=refusal.gate, message=refusal.message)
            for refusal in record.refusals
        )
    return lines


def _results_line(records: Iterable[PlanRecord]) -> str:
    """The number of folders for each result."""
    found = tuple(records)
    return MESSAGES.roadmap.plan_recheck_results.format(
        ok=_count(found, PlanResult.OK),
        rewrite=_count(found, PlanResult.REWRITE),
        new_plan=_count(found, PlanResult.NEW_PLAN),
        delivered=_count(found, PlanResult.DELIVERED),
        cleanup=_count(found, PlanResult.CLEANUP),
    )


def _gate_lines(
    on_default: Iterable[Refusal], on_branch: Iterable[Refusal], default: str, ref: str
) -> list[str]:
    """One line for each refusal of a gate on either side. A refusal that both sides hold gets
    one line, with the side `both`."""
    texts = MESSAGES.roadmap
    default_held, branch_held = set(on_default), set(on_branch)
    sides = [(refusal, default) for refusal in on_default]
    sides.extend((refusal, ref) for refusal in on_branch if refusal not in default_held)
    return [
        texts.plan_recheck_gate_line.format(
            side=texts.plan_recheck_both
            if refusal in default_held and refusal in branch_held
            else side,
            folder=refusal.folder,
            message=refusal.message,
        )
        for refusal, side in sides
    ]


def _render_branch(recheck: PlanRecheck, branch: BranchRecheck) -> list[str]:
    texts = MESSAGES.roadmap
    default, ref = recheck.default, branch.ref
    lines = [
        "",
        texts.plan_recheck_branch.format(
            ref=ref,
            default=default,
            branch_folders=len(branch.records),
            default_folders=len(recheck.records),
        ),
        *(
            texts.plan_recheck_line.format(result=record.result.value, folder=record.folder)
            for record in branch.records
        ),
        _results_line(branch.records),
    ]
    on_default = refusals_by_gate(recheck.records)
    on_branch = refusals_by_gate(branch.records)
    for gate in sorted(on_default.keys() | on_branch.keys()):
        lines.append(
            texts.plan_recheck_gate.format(
                gate=gate,
                default=default,
                ref=ref,
                default_count=len(on_default.get(gate, ())),
                branch_count=len(on_branch.get(gate, ())),
            )
        )
        lines.extend(_gate_lines(on_default.get(gate, ()), on_branch.get(gate, ()), default, ref))
    added = recheck.new_refusals
    lines.append(texts.plan_recheck_new.format(ref=ref, count=len(added)))
    lines.extend(
        texts.plan_recheck_new_line.format(
            label=texts.plan_recheck_case,
            folder=refusal.folder,
            gate=refusal.gate,
            message=refusal.message,
        )
        for refusal in added
    )
    if branch.unread:
        lines.append(texts.plan_recheck_unread.format(ref=ref, folders=", ".join(branch.unread)))
    return lines


def render_recheck(recheck: PlanRecheck) -> str:
    """The report as text: one line for each folder with its reasons below it, then the counts,
    and with a branch, the result of each folder of the branch and their counts, the refusals of
    each gate on both sides, and the refusals that the branch adds."""
    texts = MESSAGES.roadmap
    lines = _render_folders(recheck.records)
    live = len(recheck.live)
    lines.extend(
        [
            "",
            texts.plan_recheck_live.format(live=live, cleanup=recheck.count(PlanResult.CLEANUP)),
            texts.plan_recheck_unverified.format(count=recheck.unverified, live=live),
            texts.plan_recheck_unreadable.format(count=recheck.unreadable, live=live),
            _results_line(recheck.records),
            texts.plan_recheck_gates.format(counts=_joined(_gate_counts(recheck.records))),
        ]
    )
    if recheck.branch is not None:
        lines.extend(_render_branch(recheck, recheck.branch))
    return "\n".join(lines)


__all__ = [
    "BranchRecheck",
    "PlanRecheck",
    "PlanRecord",
    "PlanResult",
    "Refusal",
    "recheck_plans",
    "refusals_by_gate",
    "render_recheck",
]

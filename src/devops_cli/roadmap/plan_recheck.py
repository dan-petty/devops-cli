"""The plan recheck (#3492): each change folder on the default branch, judged again.

A merged plan is judged once, when the stage job writes it. A later gate can strand an old plan, a
plan can be delivered while its issue stays open, and the folder of a closed issue stays in every
count. `devops roadmap plan-recheck` reads every numbered folder of `openspec/changes/` on
`origin/<default branch>` and gives each one result:

- `cleanup`: the issue of the folder is closed. No count holds the folder.
- `delivered`: every file that the plan marks `(new)` is on the default branch.
- `new-plan`: the plan does not read, or it fails a gate or `openspec validate`. The first problem
  is the reason.
- `rewrite`: the plan reads and passes every check, but it has no `design.md` or no `Verification:`
  line. A mechanical rewrite adds them.
- `ok`: none of the above.

The pass reads the same plan reader (`read_change`), the same gates (`check_proposal`) and the same
OpenSpec check (`validate_change`) as `devops roadmap plan-check`. It calls no model and writes
nothing to git or to GitHub.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from devops_cli.config.constants import CONST_OPENSPEC_CHANGES_DIR
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.plan_read import (
    PlanReadError,
    created_paths,
    files_at,
    read_change,
    specs_at,
    tree_files,
)
from devops_cli.roadmap.planned import read_planned_changes
from devops_cli.roadmap.stage_change import check_proposal
from devops_cli.roadmap.stage_paths import StagedTree
from devops_cli.roadmap.stage_validate import validate_change
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.store import GitHubState, Item, RoadmapStore

GIT_OPERATION: Final[str] = "roadmap.plan-recheck"
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
class PlanRecord:
    """The result of one change folder, the reasons for it, and the two facts that the counts
    use. `readable` is false when the plan reader refuses the folder. `verified` is false when
    no group of `tasks.md` has a `Verification:` line."""

    folder: str
    issue: int
    result: PlanResult
    reasons: tuple[str, ...] = ()
    readable: bool = True
    verified: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "issue": self.issue,
            "result": self.result.value,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class PlanRecheck:
    """The records of the pass, by issue number. The folders of closed issues are in the records,
    and in no count: `live` holds the others."""

    default: str
    records: tuple[PlanRecord, ...]

    @property
    def live(self) -> tuple[PlanRecord, ...]:
        """The records that every count includes: all but the folders of closed issues."""
        return tuple(r for r in self.records if r.result is not PlanResult.CLEANUP)

    def count(self, result: PlanResult) -> int:
        """How many folders got `result`."""
        return sum(1 for record in self.records if record.result is result)

    @property
    def unverified(self) -> int:
        """How many live folders have no `Verification:` line."""
        return sum(1 for record in self.live if not record.verified)

    @property
    def unreadable(self) -> int:
        """How many live folders the plan reader refuses."""
        return sum(1 for record in self.live if not record.readable)

    def summary(self) -> dict[str, int]:
        """The counts of the pass, by name."""
        return {
            "live": len(self.live),
            "unverified": self.unverified,
            "unreadable": self.unreadable,
            **{result.value: self.count(result) for result in PlanResult},
        }


@dataclass(frozen=True)
class _Pass:
    """What the pass reads once and every folder shares."""

    source: Path
    rev: str
    default: str
    paths: Sequence[str]
    tree: StagedTree
    known: frozenset[str]
    requirements: dict[str, tuple[str, ...]]
    open_items: dict[int, Item]
    store: RoadmapStore
    tool: OpenSpecTool


def _closed(shared: _Pass, issue: int) -> bool:
    """Whether the issue is closed. An issue that is not open and is no Item is not closed: the
    folder is judged as the folder of an open issue."""
    if issue in shared.open_items:
        return False
    held = shared.store.item(issue)
    return held is not None and held.state is GitHubState.CLOSED


def _record(shared: _Pass, issue: int, folder: str) -> PlanRecord:
    texts = MESSAGES.roadmap
    if _closed(shared, issue):
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
        reason = texts.plan_recheck_delivered.format(
            paths=listed, branch=shared.default, issue=issue
        )
        return PlanRecord(folder, issue, PlanResult.DELIVERED, (reason,), verified=verified)
    fixable: list[str] = []
    if f"{root}/{_DESIGN}" not in files:
        # The reader needs the file. A rewrite adds a stub, so the pass reads the folder with one.
        files[f"{root}/{_DESIGN}"] = ""
        fixable.append(texts.plan_recheck_no_design)
    if not verified:
        fixable.append(texts.plan_recheck_no_verification)
    try:
        proposal = read_change(files)
    except PlanReadError as exc:
        reason = texts.plan_check_read.format(path=exc.path, reason=exc.reason)
        return PlanRecord(
            folder, issue, PlanResult.NEW_PLAN, (reason,), readable=False, verified=verified
        )
    held = shared.open_items.get(issue)
    problems = check_proposal(
        proposal,
        shared.known,
        shared.tree,
        requirements=shared.requirements,
        issue_body=held.body if held is not None else "",
    )
    if report := validate_change(shared.tool, shared.source, folder, files):
        problems.append(texts.plan_recheck_openspec.format(problem=" ".join(report.split())))
    if problems:
        return PlanRecord(folder, issue, PlanResult.NEW_PLAN, tuple(problems), verified=verified)
    if fixable:
        return PlanRecord(folder, issue, PlanResult.REWRITE, tuple(fixable), verified=verified)
    return PlanRecord(folder, issue, PlanResult.OK, verified=verified)


def recheck_plans(source: Path, store: RoadmapStore, *, tool: OpenSpecTool) -> PlanRecheck:
    """Judge each change folder on the default branch of the clone at `source` again. `store`
    tells which issues are closed. The pass reads and writes nothing else."""
    planned = read_planned_changes(source, operation=GIT_OPERATION)
    rev = f"origin/{planned.default}"
    paths = tree_files(source, rev, operation=GIT_OPERATION)
    known, requirements = specs_at(source, rev, operation=GIT_OPERATION)
    shared = _Pass(
        source=source,
        rev=rev,
        default=planned.default,
        paths=paths,
        tree=StagedTree(paths),
        known=known,
        requirements=requirements,
        open_items={item.number: item for item in store.open_items()},
        store=store,
        tool=tool,
    )
    records = tuple(
        _record(shared, issue, folder) for issue, folder in sorted(planned.active.items())
    )
    return PlanRecheck(planned.default, records)


def render_recheck(recheck: PlanRecheck) -> str:
    """The report as text: one line for each folder with its reasons below it, then the counts."""
    texts = MESSAGES.roadmap
    lines: list[str] = []
    for record in recheck.records:
        lines.append(
            texts.plan_recheck_line.format(result=record.result.value, folder=record.folder)
        )
        lines.extend(texts.plan_recheck_reason.format(reason=reason) for reason in record.reasons)
    live = len(recheck.live)
    lines.extend(
        [
            "",
            texts.plan_recheck_live.format(live=live, cleanup=recheck.count(PlanResult.CLEANUP)),
            texts.plan_recheck_unverified.format(count=recheck.unverified, live=live),
            texts.plan_recheck_unreadable.format(count=recheck.unreadable, live=live),
            texts.plan_recheck_results.format(
                ok=recheck.count(PlanResult.OK),
                rewrite=recheck.count(PlanResult.REWRITE),
                new_plan=recheck.count(PlanResult.NEW_PLAN),
                delivered=recheck.count(PlanResult.DELIVERED),
                cleanup=recheck.count(PlanResult.CLEANUP),
            ),
        ]
    )
    return "\n".join(lines)


__all__ = [
    "PlanRecheck",
    "PlanRecord",
    "PlanResult",
    "recheck_plans",
    "render_recheck",
]

"""`devops roadmap repair`: set back the items that a placeholder reply of a model stalled (#3478).

Two jobs once took placeholder text from a model as a real result:

- **A filler return.** The stage job returned an item to New with the comment of the stage job and
  the evidence `x`, `placeholder`, "Not yet: ..." or another placeholder. The item stays New until a
  person sets it back. The pass sets it to Ready, the Status that the stage job takes.
- **A stub refine block.** Refine stored `x` as the problem statement or the existing-tool answer,
  recorded the next step `person` and asked a person to state a problem that the body already
  states. The pass writes the body without the refine section and clears the refine block of the
  record, so the next refine round reads the item as a new one.

**What the pass lists.** An open Item that a job set: its label holds Status New, its job record
holds the same Status, and no agent or person owns it and no runner Job holds it. The record names
the cause, and the newest comment confirms it: it is the comment of the job that made the block.
A comment after it, from anyone, is a reply, and the item is a person's. A refine section that a
person edited does not hash as recorded, and its item is a person's too.

**Cost.** One listing of the open issues. An item whose record names the next step `ready` or
`person` costs one more request, the listing of its comments. The pass calls no model.

**What it writes.** Only with `--confirm`, and only after it reads each item again: an item that
changed since the listing is left for the next run. An item that fails does not stop the others;
a rate limit stops the pass. The write of a stub block goes in two steps, the body first: a body
without a section reads as a new item, but a section with no recorded hash reads as a person edit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from functools import partial

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import GitHubRateLimitError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.body_hash import extract_section_and_outside, hash_text
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.pull_form import is_placeholder
from devops_cli.roadmap.refine.refine import NextStep
from devops_cli.roadmap.stage.stage import StageFailure, write_each
from devops_cli.roadmap.status_sync import job_holds
from devops_cli.roadmap.step_files import section_text
from devops_cli.roadmap.stores.store import (
    GitHubState,
    IssueComment,
    Item,
    ItemField,
    RefineRecordKey,
    RoadmapStore,
)

logger = logging.getLogger(__name__)

# The line of the comment that the stage job wrote for a return, before the evidence: the pass reads
# the comments that the removed return path left (#3478).
_EVIDENCE_LEAD = "Evidence:\n\n"
_PROBLEM_HEADING = "problem statement"
_TOOL_HEADING = "existing tool considered"
# The marks of the refine block that a stub reply made: the pass clears them, so refine reads the
# item as a new one.
_REFINE_BLOCK: tuple[RefineRecordKey, ...] = (
    RefineRecordKey.BODY_HASH,
    RefineRecordKey.SECTION_HASH,
    RefineRecordKey.FAILED_BODY_HASH,
    RefineRecordKey.NEXT_STEP,
    RefineRecordKey.BLOCKED_BY,
    RefineRecordKey.BLOCK_PATHS,
    RefineRecordKey.NEEDS_SPLIT,
    RefineRecordKey.TRIES,
    RefineRecordKey.FAILED_CHECK,
    RefineRecordKey.FAILURE,
)


class StallKind(StrEnum):
    """What stalled an item."""

    FILLER_RETURN = "filler return"
    STUB_REFINE = "stub refine block"


@dataclass(frozen=True)
class Stalled:
    """An item that a placeholder reply stalled, with the cause."""

    item: Item
    kind: StallKind


@dataclass(frozen=True)
class RepairPlan:
    """What a run does: the items it sets back. A dry run holds the requests of a run and no
    item."""

    repo: str
    stalled: tuple[Stalled, ...] = ()
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()


@dataclass(frozen=True)
class Repaired:
    """What a run wrote: the numbers of the items it set back, and the items it could not write."""

    reset: tuple[int, ...] = ()
    failed: tuple[StageFailure, ...] = ()


def _job_set_new(item: Item) -> bool:
    """Whether a job set the Status New of `item`, and no person or runner holds it."""
    return (
        item.state is GitHubState.OPEN
        and item.status == CONST_ROADMAP_STATUS_NEW
        and item.job_record.get(ItemField.STATUS) == CONST_ROADMAP_STATUS_NEW
        and claimed_by(item) is None
        and not job_holds(item)
    )


def _newest(comments: list[IssueComment]) -> str:
    return comments[-1].body if comments else ""


def _filler_return(newest: str) -> bool:
    """Whether the comment is a return of the stage job whose evidence is a placeholder."""
    if not newest.startswith(CONST_ROADMAP_STAGE_COMMENT_MARKER):
        return False
    _, found, evidence = newest.partition(_EVIDENCE_LEAD)
    return bool(found) and is_placeholder(evidence)


def _text_of(section: str, heading: str) -> str:
    """The text under the heading of the refine section, without the heading line."""
    return section_text(section, frozenset({heading})).partition("\n")[2].strip()


def _stub_section(item: Item) -> bool:
    """Whether the refine section of `item` is the one that refine recorded, and its problem
    statement or its existing-tool answer is a placeholder."""
    _, section = extract_section_and_outside(item.body)
    if section is None or item.job_record.get(RefineRecordKey.SECTION_HASH) != hash_text(section):
        return False
    return any(is_placeholder(_text_of(section, h)) for h in (_PROBLEM_HEADING, _TOOL_HEADING))


def _stall_of(store: RoadmapStore, item: Item) -> StallKind | None:
    """The cause that stalled `item`, or None. The record names the cause, and the newest comment
    confirms it: a comment after the comment of the job means a person replied."""
    if not _job_set_new(item):
        return None
    step = item.job_record.get(RefineRecordKey.NEXT_STEP)
    if step == NextStep.READY.value:
        if _filler_return(_newest(store.comments_on(item.number))):
            return StallKind.FILLER_RETURN
    elif step == NextStep.PERSON.value and _stub_section(item):
        if _newest(store.comments_on(item.number)).startswith(CONST_ROADMAP_REFINE_COMMENT_MARKER):
            return StallKind.STUB_REFINE
    return None


def plan_repair(store: RoadmapStore, *, repo: str) -> RepairPlan:
    """The items that a filler return or a stub refine block stalled. It writes nothing."""
    found: list[Stalled] = []
    for item in store.open_items():
        kind = _stall_of(store, item)
        if kind is not None:
            found.append(Stalled(item, kind))
    return RepairPlan(repo, tuple(found))


def dry_run_repair(repo: str) -> RepairPlan:
    """The plan of a dry run, having made no request: the requests of a run and its writes."""
    from devops_cli.roadmap.request_plan import repair_requests

    reads, writes = repair_requests(repo)
    return RepairPlan(repo, dry_run=True, requests=reads, write_requests=writes)


def _repair_one(store: RoadmapStore, stalled: Stalled, reset: list[int]) -> None:
    """Set `stalled` back. The issue is read again first: an item that a person or another lane
    changed since the listing, or whose cause is gone, is left for the next run."""
    current = store.item(stalled.item.number)
    if current is None or _stall_of(store, current) is not stalled.kind:
        return
    if stalled.kind is StallKind.FILLER_RETURN:
        store.set_field(current, ItemField.STATUS, CONST_ROADMAP_STATUS_READY)
    else:
        outside, _ = extract_section_and_outside(current.body)
        store.write_issue_body(current.number, outside.rstrip())
        store.set_marks(current, dict.fromkeys(_REFINE_BLOCK))
    reset.append(current.number)


def apply_repair(store: RoadmapStore, plan: RepairPlan) -> Repaired:
    """Set back each item of `plan`. An item that fails does not stop the others; a rate limit,
    rejected credentials and the stop of the Service stop the pass."""
    reset: list[int] = []
    failed: list[StageFailure] = []
    writes = [(s.item, partial(_repair_one, store, s, reset)) for s in plan.stalled]
    write_each(writes, [], failed, also_stop=(GitHubRateLimitError,))
    logger.info("The repair pass set back %d item(s) and failed for %d", len(reset), len(failed))
    return Repaired(tuple(reset), tuple(failed))


def render_repair_plan(plan: RepairPlan) -> str:
    """The items to set back, one line each with the cause."""
    texts = MESSAGES.roadmap
    lines = [texts.repair_title.format(repo=plan.repo)]
    lines += [
        texts.repair_line.format(number=s.item.number, title=s.item.title, cause=s.kind.value)
        for s in plan.stalled
    ]
    if not plan.stalled:
        lines += ["", texts.repair_nothing]
    return "\n".join(lines)


__all__ = [
    "RepairPlan",
    "Repaired",
    "StallKind",
    "Stalled",
    "apply_repair",
    "dry_run_repair",
    "plan_repair",
    "render_repair_plan",
]

"""`devops roadmap reprioritize`: the current release's admission rule, size and stall window,
and the start of each release (#740).

The current release is the open Release with the lowest version (`current_release`). Its state
comes from its release pull request (`is_release_pull_request`): it is cut from the moment one
is opened, draft or not, until that one is closed unmerged, merged once one has merged, and
shipped once GitHub Release vX.Y.Z is published too (`release_state`). Every decision about an
item reads one table, `TRANSITIONS`, which maps the state of a release and what happened to the
item (an `Event`) to a `Transition`: an action and the reason the item's comment gives. A cut
release follows the started release's rows, and a merged one the cut release's, except where
each has its own (`INHERITS`). While its release pull request is open, a cut release still
admits a critical fix, whose own pull request then merges into the release branch before the
release's does (#1294); once that pull request has merged, a critical fix goes first into the
next release, the merged release's one row.

Intake (#742) asks the same table what an item joining the current release meets: it finds the
release with `current_release`, its state with `release_state`, the item's event with
`admission_event`, and the transition with `decide(state, event)`. `ADMIT` keeps the item and
`TO_NEXT` or `TO_BACKLOG` sends it elsewhere, with the reason's text in
`MESSAGES.roadmap.reasons`.

A mark that names a Release names it by its milestone number, which GitHub keeps when a person
renames the milestone; the plan, the report and every comment use the title it has now.

The run record (the store's `run_record`, ADR 0002) names, as its `Started` mark, the Release
the job last started, or recorded at its first run, and as its `Size` mark that Release's size
then. With no run record, a run is the first: it records the admitted set of the release under
way and moves nothing. That is the current release, or, once the current release has shipped
with its milestone still open, the first release after it that has not shipped, and the shipped
milestones are closed last, so a first run records the same release whether `release.yml`
closed them or not. A first run names its Release in the run record before anything else, and
gives its size last: a run record without a size is a first run that stopped part-way, which
the next run does again. With no run record while items carry the job's marks, the job has run
before and the run record card is gone, and the job refuses to run rather than record a new
baseline.

Once the Release the run record names is closed (`release.yml` closes the milestone after it
publishes the release), the current release is newer than it, and it starts, but only when the
release before it has shipped: a milestone closed by hand starts nothing. A shipped release
whose milestone is still open starts the first release after it that has not shipped: a start
skips each open release right after it that has shipped too, as one a person cut and shipped
while no run started it, and closes all of them last, the current one first. If the run record
already names a Release newer than all of them, the run that started it, or recorded it at a
first run, stopped at those closes: while the newer Release is open and has not shipped, the run
holds it to the rules as the current release, in its own state, so an item a person added to it
since is judged now, and closes the shipped ones last; once its milestone is closed without it
shipping, the closes are all that is left. One the run record names that has shipped since, its
milestone closed or not, is skipped like the others, and the release after it starts. A release
a person cut before any run started it takes no item at its start, its pull request open or merged.
A current release older than the one the run record names, such as a hotfix milestone opened
later, never started: the job holds it to no rule and moves nothing until it ships or closes.
The run record's `Size` is the commit point of a start or a first run: written after every other
write of that run but the closes, so a run that stops part-way leaves it as it was, and the next
run starts or records that release again, finishing what the first began. Written first, it
would make that next run hold the half-started release to its admission rule and send away the
items the start had not yet marked. An empty release is recorded like any other.

The admitted set is the items the current release held when it started, or at the job's first
run, open or closed, plus each critical fix admitted since; the size counts the open ones. Each
carries the release as its `Admitted` mark in its job record. An item in the current release
without that mark joined after the start, however long ago, so a missed poll or a late run still
finds it, and an item reopened there never joined it. An item that leaves the release, open or
closed, has its mark cleared, so one reopened after a person put it back joined then; leaving it
while it carries the mark is never a job's own change, so the run that clears it is due. A first
run or a start clears the mark of an item that left the release it records since a run that
stopped part-way set it. A critical fix that joins is admitted even when the stall rule readies
or nudges it in the same run: that change carries the admission, in its `Pending` mark and its
last write, so a run that stops part-way through it leaves the admission to the run that
finishes it. A move out of the release that a person undid before its comment was posted keeps
the item's mark. When a person takes an item out of the current release it was admitted to, out
of an open release a job last placed it in, or out of the backlog where a job last placed it,
its `Left` mark names that place until a job places the item again: putting it back then sets
the value a job last set, yet is no job's change, and `is_own_change` sees that. The job reads
state, not the change feed (ADR 0003), so an item a person takes out of such a place and puts
back before any run records it out, or while a run that read it out stopped before recording it,
is where it was: still admitted, or still where a job placed it, and a start may pull it in.
That holds while a change a stopped run began to move the item waits too, unless nothing shows
that change's milestone call never landed, as below. The first run's promise covers admission: a
condition already present then, such as an item already Blocked, is judged by the next run's
descoping rules. The size binds from the start: while the release holds more than the larger of
its cap and its size at start, its lowest-ranked unstarted items that are not critical fixes are
descoped, so an item a person moves back to Ready after a fix has filled the release makes room.

Each change to an item is finished before the next begins: its `Pending` mark records the
decision first, with the item's Release and Status as it found them, what its job record held
for the fields the change writes, when its Status last changed and how many times its issue had
joined or left a Release; then come the field writes (the Release before the Status), the reason
comment, and one job-record write that sets its `Admitted` or `Nudged` mark and clears
`Pending`. On GitHub a field write is two calls, the job record first, then the milestone or the
board field. A field joins the mark's begun fields in the job-record write that records its
value, before the field call, and its written fields in a job-record write once that call has
returned, so values alone never decide who wrote one. A run that finds a `Pending` mark judges
the change again before it finishes it. Once its comment is posted, only its marks are left; one
whose move a person undid before the run that posted its comment keeps the item's admission in
its `Pending` mark (`stays`), should that run stop before its last write. A written field that
holds the change's value is the job's until it changes since: the written mark keeps the field's
event count or Status clock as the job's write left it, so a field a person set away and back,
or set to that value once a dropped change had put it back, is the person's. A field only begun
is read again: if the issue's Release events, or its Status's last change, show no change since
the change began, the field call never landed, and the field is neither the job's nor a person's
yet, so the change sets it when it is finished, and its job record goes back to what it held
when it is not. A begun field that changed since and holds the change's value may be the job's
write or a person's, which no read tells apart. Either way the change has happened, at least in
part, so the run finishes it as it stands, without judging it again: it posts the comment and
sets the marks, sets only the fields no one has set since, and never puts back, writes or
records as the job's a field someone may have set. Any other field the change writes was set by
a person once it holds anything but what it held before, even the change's value, and the Status
once it has changed since, even back to what it held, since the job writes the Status only once
it has recorded it as begun; a Release moved out and back is where it was, as above. The change
gives way to that edit, on every path: one it finishes as it stands leaves the field as the
person set it. When a person has set one, and no field holds a value nothing shows the job set,
that change stands down: the run puts back the written fields that hold the job's values, puts
back the job record of the begun ones that have not changed since, so no `Left` mark names a
Release the item never reached, and drops the change. The record of a begun Release a person has
set since is put back too when the issue's events show the item never joined the change's target
since it began: the change's milestone call never landed, so every move since is a person's, and
the record still names the last place a job set; an item a person moved out of it and back is
where a job placed it, as above. The events can't show that for a move to the backlog, which no
join shows, nor once a person has moved the item into the change's target: then that record is
dropped, since it may name the place a job last put the item in, and once the job's call may
have landed, a person who moved the item back there would read as that job, and a start would
pull in the item they had just taken out of it. When no field is a person's or unproven, and the
change is about the release this run judges, the run decides the item afresh as it was before
the change began, and finishes the change only when it decides the same again; else it puts the
item back and decides anew, so a release merged since the change began sends a fix on. Its Status
clock is the one the change found only when the change began its Status write, the job's own
write being no activity; a change that never began it leaves the clock as it is, since a person
who set the Status since, even to what the change found, worked on the item. A change about
another release, such as one that shipped since, is finished, and the item is then judged like
any other, so a start finds an item an earlier run descoped into it; once the release it moves
the item to has shipped too, cut and shipped while that run waited, the item stays there when
the start closes it, as any open item a release shipped with: the job moves no item out of a
shipped release. A start's pull-in into a release that has shipped since, whose milestone call
never landed, is dropped instead: the item was never in that release when it shipped, and the
start that runs now judges it afresh. The `Pending` mark counts the comments with the change's
text the item had before it, so the comment is posted once. One window stays, which no read
closes: a field call that landed and still reported a failure, or whose written mark then
failed, looks like a person setting that value, and the other way round. The run finishes such a
change with its comment, so a person who set that very value sees the job's comment, and drops
the field's job record, so a place it set counts as a person's from then on, as for an item no
job placed: an item sent to the backlog then is not pulled back in by a later start. Keeping the
record the field had before the change would name the place a job had put the item in, such as a
Release a start pulled it into, and the next run would read the job's own move out of it as a
person's, with a `Left` mark.

A person's placement stands: an item's Release, or its absence from one, is a person's when it
differs from the last one a job set, or when its `Left` mark says a person moved it since. An
item no job placed is a person's in a Release, and in the backlog once a person took it out of
one. A release start reads the issue events (`release_changes`) of a Ready backlog item no job
placed, and records the Release a person took it out of as its `Left` mark, as for an item a
job placed, so the next start reads them no more; one that was never in a Release is unplaced.
Release start pulls in only items no person placed, while the admission rule, the cut and the
size bind everyone. The job refuses a board #739's migrate has not finished: one whose Status
field lacks New or Blocked or still has an option migrate merges into New, or that still holds
an open release epic.

The job writes only GitHub state, never a commit (ADR 0001), and comments a one-line reason on
every item it moves, readies, admits or nudges. It never sets Priority, Value or Effort, never
closes or merges a pull request, and its only branch write creates a missing `release/vX.Y.Z`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType

from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as MalformedPendingError

from devops_cli.config.constants import (
    CONST_RELEASE_BRANCH_PREFIX,
    CONST_ROADMAP_CRITICAL_FIX_LABELS,
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_EPIC_LABEL,
    CONST_ROADMAP_LEFT_BACKLOG,
    CONST_ROADMAP_NEEDS_SPLIT_LABEL,
    CONST_ROADMAP_PREMIGRATE_STATUSES,
    CONST_ROADMAP_RUN_RECORD_TITLE,
    CONST_ROADMAP_STARTED_STATUSES,
    CONST_ROADMAP_STATUS_BLOCKED,
    CONST_ROADMAP_STATUS_DONE,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_STALL_CHECK_HOURS
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.github.issue_closure import extract_linked_issues
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.store import (
    RELEASE_CHANGE_KINDS,
    Branch,
    Change,
    ChangeKind,
    GitHubState,
    Item,
    ItemField,
    JobMark,
    JobRecord,
    PullRequest,
    PullRequestState,
    RefineRecordKey,
    Release,
    RoadmapStore,
    field_options,
    find_release,
    in_release,
    is_release_pull_request,
    is_release_title,
    with_marks,
)

# ── The table ─────────────────────────────────────────────────────────────────


class ReleaseState(StrEnum):
    """Where a release is: planned, started (the current one), cut (its release pull request
    is open), merged (that pull request merged, and the release is not published yet), or
    shipped."""

    PLANNED = "planned"
    STARTED = "started"
    CUT = "cut"
    MERGED = "merged"
    SHIPPED = "shipped"


class Event(StrEnum):
    """What happened to an item, as the rules see it; a `FIX_` event is a critical fix's."""

    # An item joined the current release after it started.
    FIX_JOINED = "fix_joined"
    PR_JOINED = "pr_joined"
    P0_FEATURE_JOINED = "p0_feature_joined"
    ITEM_JOINED = "item_joined"
    # An admitted critical fix took the release over the cap, and this item makes room.
    OVER_CAP = "over_cap"
    # The release holds more than the larger of the cap and its size at start, and this item
    # makes room: one a person moved back to Ready after a fix had joined.
    OVER_SIZE = "over_size"
    # An unstarted item's reasons to be descoped.
    BLOCKED = "blocked"
    DEPENDS_OUTSIDE = "depends_outside"
    NEEDS_SPLIT = "needs_split"
    OTHERS_DONE = "others_done"
    FIX_BLOCKED = "fix_blocked"
    FIX_DEPENDS_OUTSIDE = "fix_depends_outside"
    FIX_NEEDS_SPLIT = "fix_needs_split"
    FIX_OTHERS_DONE = "fix_others_done"
    # A started item idle for the stall window.
    STALLED = "stalled"
    FIX_STALLED = "fix_stalled"
    REVIEW_IDLE = "review_idle"
    # The current release shipped, and the next one starts.
    SHIPPED = "shipped"
    NEW_AT_START = "new_at_start"
    FIX_NEW_AT_START = "fix_new_at_start"
    BLOCKED_AT_START = "blocked_at_start"
    FIX_BLOCKED_AT_START = "fix_blocked_at_start"
    CANDIDATE = "candidate"
    OVER_CAP_AT_START = "over_cap_at_start"


class Action(StrEnum):
    """What the job does about an event."""

    KEEP = "keep"
    ADMIT = "admit"
    TO_BACKLOG = "to_backlog"
    TO_NEXT = "to_next"
    READY = "ready"
    READY_TO_NEXT = "ready_to_next"
    NUDGE = "nudge"
    PULL_IN = "pull_in"
    START_NEXT = "start_next"


class Reason(StrEnum):
    """Why, as an item's comment says it; `MESSAGES.roadmap.reasons` holds each one's text."""

    CRITICAL_FIX = "critical_fix"
    PULL_REQUEST = "pull_request"
    ADMISSION = "admission"
    P0_FEATURE = "p0_feature"
    CUT = "cut"
    MERGED = "merged"
    CAP = "cap"
    OVER_SIZE = "over_size"
    BLOCKED = "blocked"
    DEPENDENCY = "dependency"
    NEEDS_SPLIT = "needs_split"
    OTHERS_DONE = "others_done"
    FIX_STAYS = "fix_stays"
    STALLED = "stalled"
    FIX_STALLED = "fix_stalled"
    REVIEW_IDLE = "review_idle"
    SHIPPED = "shipped"
    NOT_READY_AT_START = "not_ready_at_start"
    FIX_NEW_AT_START = "fix_new_at_start"
    BLOCKED_AT_START = "blocked_at_start"
    TOP_UP = "top_up"
    TRIM = "trim"


@dataclass(frozen=True)
class Transition:
    """What the job does about an event, and why."""

    action: Action
    reason: Reason


_S, _P, _C, _M, _X = (
    ReleaseState.STARTED,
    ReleaseState.PLANNED,
    ReleaseState.CUT,
    ReleaseState.MERGED,
    ReleaseState.SHIPPED,
)

# Every decision the job makes about an item. The release state is the current release's, or
# PLANNED for the release that is starting. Descoping moves an unstarted item to the next
# planned release; an admitted critical fix leaves only when it is Blocked.
TRANSITIONS: Mapping[tuple[ReleaseState, Event], Transition] = MappingProxyType(
    {
        # Admission: after the release starts, only a critical fix or an item with a pull request joins it.
        (_S, Event.FIX_JOINED): Transition(Action.ADMIT, Reason.CRITICAL_FIX),
        (_S, Event.PR_JOINED): Transition(Action.ADMIT, Reason.PULL_REQUEST),
        (_S, Event.P0_FEATURE_JOINED): Transition(Action.TO_NEXT, Reason.P0_FEATURE),
        (_S, Event.ITEM_JOINED): Transition(Action.TO_BACKLOG, Reason.ADMISSION),
        # The cut: while the release pull request is open, a critical fix still joins, and its
        # own pull request merges into the release branch before the release's does.
        (_C, Event.FIX_JOINED): Transition(Action.ADMIT, Reason.CUT),
        (_C, Event.PR_JOINED): Transition(Action.ADMIT, Reason.PULL_REQUEST),
        # The lock: once the release pull request has merged, a critical fix goes first into
        # the next release.
        (_M, Event.FIX_JOINED): Transition(Action.TO_NEXT, Reason.MERGED),
        # The cap: an admitted critical fix that takes the release over it descopes one item.
        (_S, Event.OVER_CAP): Transition(Action.TO_NEXT, Reason.CAP),
        (_S, Event.OVER_SIZE): Transition(Action.TO_NEXT, Reason.OVER_SIZE),
        # Descoping.
        (_S, Event.BLOCKED): Transition(Action.TO_NEXT, Reason.BLOCKED),
        (_S, Event.DEPENDS_OUTSIDE): Transition(Action.TO_NEXT, Reason.DEPENDENCY),
        (_S, Event.NEEDS_SPLIT): Transition(Action.TO_NEXT, Reason.NEEDS_SPLIT),
        (_S, Event.OTHERS_DONE): Transition(Action.TO_NEXT, Reason.OTHERS_DONE),
        (_S, Event.FIX_BLOCKED): Transition(Action.TO_NEXT, Reason.BLOCKED),
        (_S, Event.FIX_DEPENDS_OUTSIDE): Transition(Action.KEEP, Reason.FIX_STAYS),
        (_S, Event.FIX_NEEDS_SPLIT): Transition(Action.KEEP, Reason.FIX_STAYS),
        (_S, Event.FIX_OTHERS_DONE): Transition(Action.KEEP, Reason.FIX_STAYS),
        # The stall window.
        (_S, Event.STALLED): Transition(Action.READY_TO_NEXT, Reason.STALLED),
        (_S, Event.FIX_STALLED): Transition(Action.READY, Reason.FIX_STALLED),
        (_S, Event.REVIEW_IDLE): Transition(Action.NUDGE, Reason.REVIEW_IDLE),
        # Ship, and the start of the next release.
        (_X, Event.SHIPPED): Transition(Action.START_NEXT, Reason.SHIPPED),
        (_P, Event.NEW_AT_START): Transition(Action.TO_BACKLOG, Reason.NOT_READY_AT_START),
        (_P, Event.FIX_NEW_AT_START): Transition(Action.KEEP, Reason.FIX_NEW_AT_START),
        (_P, Event.BLOCKED_AT_START): Transition(Action.TO_BACKLOG, Reason.BLOCKED_AT_START),
        (_P, Event.FIX_BLOCKED_AT_START): Transition(Action.TO_NEXT, Reason.BLOCKED_AT_START),
        (_P, Event.CANDIDATE): Transition(Action.PULL_IN, Reason.TOP_UP),
        (_P, Event.PR_JOINED): Transition(Action.KEEP, Reason.PULL_REQUEST),
        (_P, Event.OVER_CAP_AT_START): Transition(Action.TO_NEXT, Reason.TRIM),
    }
)
# A state without a row of its own for an event takes the row of the state it inherits from.
INHERITS: Mapping[ReleaseState, ReleaseState] = MappingProxyType({_C: _S, _M: _C})

_LEAVING = frozenset({Action.TO_BACKLOG, Action.TO_NEXT, Action.READY_TO_NEXT})
_TO_TARGET = frozenset({Action.TO_NEXT, Action.READY_TO_NEXT, Action.PULL_IN})
_SILENT = frozenset({Action.KEEP, Action.START_NEXT})


def decide(state: ReleaseState, event: Event) -> Transition:
    """The table's transition for `event` in a release in `state`, or the one it inherits."""
    found = TRANSITIONS.get((state, event))
    if found is not None:
        return found
    inherited = INHERITS.get(state)
    if inherited is None:
        raise ConfigurationError(
            f"The release rules have no row for {event.value} in a {state.value} release.",
            details={"state": state.value, "event": event.value},
        )
    return decide(inherited, event)


# ── What an item and a release are ────────────────────────────────────────────


def is_critical_fix(item: Item) -> bool:
    """Whether the item is a critical fix: Priority P0 and a `type/bug` or `type/security` label."""
    return item.priority == CONST_ROADMAP_CRITICAL_PRIORITY and not (
        CONST_ROADMAP_CRITICAL_FIX_LABELS.isdisjoint(item.labels)
    )


def is_p0_feature(item: Item) -> bool:
    """Whether the item is P0 without being a critical fix: it waits for the next release."""
    return item.priority == CONST_ROADMAP_CRITICAL_PRIORITY and not is_critical_fix(item)


def is_started(item: Item) -> bool:
    """Whether the item is in progress, in review or done."""
    return item.status in CONST_ROADMAP_STARTED_STATUSES


def admission_event(item: Item, *, has_pr: bool = False) -> Event:
    """What an item joining the current release after its start is: a critical fix, an item
    with an open or merged pull request, a P0 feature, or anything else."""
    if is_critical_fix(item):
        return Event.FIX_JOINED
    if has_pr:
        return Event.PR_JOINED
    return Event.P0_FEATURE_JOINED if is_p0_feature(item) else Event.ITEM_JOINED


def placed_by_person(item: Item, history: Iterable[Change] = ()) -> bool:
    """Whether a person placed the item where it is: its Release differs from the last one a
    job set, or it is back there and its `Left` mark says a person moved it since. An item no
    job placed counts as a person's in a Release, and in the backlog once a person took it out
    of one: its `Left` mark names that Release, or its issue's events (`history`, its
    `release_changes`) show it left one. One never in a Release is unplaced.
    """
    record = item.job_record
    if ItemField.RELEASE in record:
        return record[ItemField.RELEASE] != item.release or bool(record.get(JobMark.LEFT))
    if item.release is not None or record.get(JobMark.LEFT):
        return True
    return any(change.kind is ChangeKind.LEFT_RELEASE for change in history)


def _milestone(mark: str | None) -> int | None:
    """The milestone number a mark names, or None when it names none."""
    return int(mark) if mark and mark.isdigit() else None


def admitted_to(item: Item) -> int | None:
    """The milestone number of the Release whose admitted set holds the item, if any."""
    return _milestone(item.job_record.get(JobMark.ADMITTED))


def joined_release(item: Item) -> int | None:
    """The milestone number of the Release the item entered as a person's join after the start
    or while cut, if any."""
    return _milestone(item.job_record.get(JobMark.JOINED))


def current_release(releases: Iterable[Release]) -> Release | None:
    """The current release: the open Release with the lowest version, or None when none is open."""
    opened = (release for release in releases if release.state is GitHubState.OPEN)
    return min(opened, key=lambda release: release.version, default=None)


def last_started(run_record: JobRecord) -> int | None:
    """The milestone number of the Release the run record names: the one the job last started,
    or recorded at its first run. None before the first run."""
    return _milestone(run_record.get(JobMark.STARTED))


def size_at_start(run_record: JobRecord) -> int | None:
    """The size the run record gives the Release it names, when it started or was first
    recorded; None when it gives none it can read."""
    size = run_record.get(JobMark.SIZE)
    return int(size) if size and size.isdigit() else None


def release_state(store: RoadmapStore, release: Release, default_branch: str) -> ReleaseState:
    """The release's state, from its release pull requests and its GitHub Release.

    It is shipped once one has merged and GitHub Release vX.Y.Z is published, merged while one
    has merged without the release being published yet, and cut while one is open.
    """
    pull_requests = [
        pull_request
        for pull_request in store.release_pull_requests(release.title)
        if is_release_pull_request(pull_request, release.version, default_branch)
    ]
    states = {pull_request.state for pull_request in pull_requests}
    if PullRequestState.MERGED in states:
        published = store.release_published(release.title)
        return ReleaseState.SHIPPED if published else ReleaseState.MERGED
    return ReleaseState.CUT if PullRequestState.OPEN in states else ReleaseState.STARTED


# ── The plan ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Decision:
    """One decision about one item: the event, its transition, and the comment it leaves.

    `release` is the release the decision is about, the current or the starting one; `target`
    the Release a move goes to, None for the backlog. A resumed decision is one an earlier run
    began, and `begun` its `Pending` mark as that run wrote it, with the fields written since;
    `item` is the item as it is now, and a `done` one has its comment posted already, so only
    its marks are left. `unproven` are the fields it began that hold its values with nothing to
    show the job set them, and `by_person` those a person has set since: it leaves both as they
    are, and drops the record of those it began, but for those `unlanded`, a person's whose
    field call the issue's events show never landed, which keep the record they had before it
    began. A decision that `admits` readies or nudges a critical fix that joined the release,
    and admits it in its own last write.
    """

    item: Item
    event: Event
    transition: Transition
    release: str
    target: str | None = None
    note: str = ""
    begun: _Pending | None = None
    done: bool = False
    unproven: frozenset[ItemField] = frozenset()
    by_person: frozenset[ItemField] = frozenset()
    unlanded: frozenset[ItemField] = frozenset()
    admits: bool = False
    joined: bool = False

    @property
    def resumed(self) -> bool:
        """Whether an earlier run began the decision."""
        return self.begun is not None

    @property
    def action(self) -> Action:
        """What the job does."""
        return self.transition.action

    @property
    def leaves(self) -> bool:
        """Whether the item leaves `release`."""
        return self.action in _LEAVING

    @property
    def writes(self) -> bool:
        """Whether the decision changes or admits the item, and so comments on it."""
        return self.action not in _SILENT

    @property
    def text(self) -> str:
        """What the job did and why, as one line."""
        template = MESSAGES.roadmap.actions[self.action]
        return template.format(release=self.release, target=self.target, reason=self.note)

    @property
    def comment(self) -> str:
        """The item's one-line reason comment."""
        if self.begun is not None:
            return self.begun.comment
        return MESSAGES.roadmap.reprioritize_comment.format(text=self.text)

    @property
    def untouched(self) -> frozenset[ItemField]:
        """The fields it leaves as they are: those someone else may have set since it began."""
        return self.unproven | self.by_person

    def same_as(self, other: Decision) -> bool:
        """Whether `other` decides the same about the same release."""
        return (self.event, self.action, self.release, self.target) == (
            other.event,
            other.action,
            other.release,
            other.target,
        )


class _Pending(BaseModel):
    """A decision as an item's `Pending` mark keeps it until it is finished.

    Releases are named by milestone number, and `target_title` is the title the target had when
    the decision began, which the issue's events keep. `was_in` and `was` are the item's Release
    and Status when the decision began, `status_at` when its Status had last changed then, and
    `moves` how many times its issue had joined or left a Release then, when the decision sets
    the Release. `recorded` holds what the job record held then for each field the decision
    writes, leaving out a field it held nothing for. A field joins `begun` in the job-record
    write that records its value, which the store makes before it sets the field, and joins
    `written` in a job-record write made once the field is set, with what the field's events
    count (`written_moves`) or its Status clock (`written_status_at`) is then. Only a written
    field is known to hold the job's value, until it changes since; a begun one may not have
    been set, and a person may have set it since. `admits` is the decision's admission of a
    critical fix it readies or nudges. `stays` records that the run that posts the comment of a
    move out of the release found the item back there, its Release a person's: the move was
    undone before its comment, so the item keeps its admission.
    """

    model_config = ConfigDict(frozen=True)

    event: Event
    action: Action
    reason: Reason
    release: int
    target: int | None = None
    target_title: str | None = None
    note: str = ""
    admits: bool = False
    comment: str
    posted: int = 0
    was_in: int | None = None
    was: str | None = None
    status_at: datetime | None = None
    moves: int | None = None
    recorded: dict[ItemField, str | None] = Field(default_factory=dict)
    begun: tuple[ItemField, ...] = ()
    written: tuple[ItemField, ...] = ()
    written_moves: int | None = None
    written_status_at: datetime | None = None
    stays: bool = False
    joined: bool = False

    def begin(self, item_field: ItemField) -> _Pending:
        """The mark with `item_field` among its begun fields."""
        if item_field in self.begun:
            return self
        return self.model_copy(update={"begun": (*self.begun, item_field)})

    def confirm(self, item_field: ItemField, store: RoadmapStore, number: int) -> _Pending:
        """The mark with `item_field` among its written fields, as the job left it: the Release
        with the events its write made, a leave and a join, counted without a read the events
        may lag behind; the Status with its clock, read once the write has returned."""
        update: dict[str, object] = {"written": (*self.written, item_field)}
        if item_field is ItemField.RELEASE and self.moves is not None:
            made = (self.was_in is not None) + (self.target is not None)
            update["written_moves"] = self.moves + made
        elif item_field is ItemField.STATUS:
            update["written_status_at"] = store.status_changed_at(number)
        return self.model_copy(update=update)

    def restore(
        self, fields: Iterable[ItemField]
    ) -> tuple[dict[ItemField, str | None], frozenset[ItemField]]:
        """The record each of `fields` had when the decision began: the values to record, and
        the fields to forget because the record held nothing for them."""
        listed = list(fields)
        recorded = {f: self.recorded[f] for f in listed if f in self.recorded}
        return recorded, frozenset(f for f in listed if f not in self.recorded)


def _put_back(
    record: JobRecord, recorded: Mapping[ItemField, str | None], forgotten: Iterable[ItemField]
) -> None:
    """Give `record` the values `recorded` holds, and drop the fields `forgotten`."""
    for item_field, value in recorded.items():
        record[item_field] = value
    for item_field in forgotten:
        record.pop(item_field, None)


@dataclass(frozen=True)
class _Resumed:
    """A change an earlier run began on an item and did not finish, as its `Pending` mark
    keeps it, and how the item stands since.

    `decision` is the change, about `item` as it is now; None when the mark can't be read, or
    names a Release that is gone. `undo` holds the fields its mark records as written that still
    hold its values, with what they were before. `unproven` holds the fields it began but did
    not record as written that changed since and hold its values: the job may have set them, or
    a person, so the change has happened, at least in part. `person` is the fields a person has
    set since: one the change wrote, or began and that changed since, that holds anything else
    now, even what it held before; one it wrote that has changed since, even back to its value;
    one it did not begin that holds anything but what it held before, even the change's value;
    and a Status it did not begin that has changed since, even back to what it held. A field it
    began that has not changed since was never set, and is neither.
    A `done` change has its comment posted, so only its marks are left. `release` is the
    milestone number of the release it is about, and `status_at` when the item's Status had last
    changed when it began, given only when it began its Status write: one that never began it
    made no change to the Status clock, so every change to it since is a person's, even one that
    left the Status as the change found it.
    """

    item: Item
    decision: Decision | None = None
    undo: tuple[tuple[ItemField, str | None], ...] = ()
    unproven: frozenset[ItemField] = frozenset()
    person: frozenset[ItemField] = frozenset()
    done: bool = False
    release: int | None = None
    status_at: datetime | None = None

    def revert(self) -> Revert:
        """Drop the change: put back the written fields that hold its values, and give the
        fields it began and did not record as written the record `_taken_back` leaves them."""
        if self.decision is None or self.decision.begun is None:
            return Revert(self.item)
        recorded, forgotten = _taken_back(self.decision, dropped=True)
        return Revert(self.item, self.undo, self.decision.text, recorded, forgotten)


@dataclass(frozen=True)
class Revert:
    """A change an earlier run began that this run does not finish: the fields it wrote that
    still hold its values go back to what they were, the fields it began and did not record as
    written get the record `_taken_back` leaves them (`recorded`, `forgotten`), and its
    `Pending` mark is cleared. `text` is what the change was to do; empty when its mark can't
    be read."""

    item: Item
    undo: tuple[tuple[ItemField, str | None], ...] = ()
    text: str = ""
    recorded: Mapping[ItemField, str | None] = field(default_factory=dict)
    forgotten: frozenset[ItemField] = frozenset()


@dataclass(frozen=True)
class ReleaseWrite:
    """A write to a Release or a branch, as the report names it. A `last` one comes after every
    other write of the run, the run record's included; a Release it creates or closes is
    returned."""

    text: str
    apply: Callable[[RoadmapStore], Release | None] = field(compare=False, repr=False)
    last: bool = False


@dataclass(frozen=True)
class ReprioritizationPlan:
    """Every write one run makes: to Releases and branches, to items, to the admitted set, and
    to the run record.

    `current` and `state` are the current release when the run read it, or the release under way
    when that one has shipped and the run record names a newer one already. `starting` is the
    release the run starts, and `shipped` the release whose ship starts it, or whose close is
    left, while its milestone is still open: the last of those the run closes. `unshipped` is
    the release the run record names when its milestone was closed without it shipping, so
    nothing starts, and `behind` the one it names when the current release is older than it.
    `reverts` are the changes earlier runs began that this run drops. `admitted` gains
    `admitted_release`'s `Admitted` mark and `released` loses it; each of `left` gets its
    Release as its `Left` mark, and so does each of `kept_out`, a backlog item no job placed
    whose issue's events show a person took it out of that Release. `record` is the Release the
    run record names once the run is done, when the run changes it, and `size` its size then; a
    first run that `opens_record` names it there before its marks. `numbers` holds each
    Release's milestone number by title, which the marks hold.
    """

    repo: str
    now: datetime
    current: str | None
    state: ReleaseState | None
    first_run: bool = False
    shipped: str | None = None
    starting: str | None = None
    unshipped: str | None = None
    behind: str | None = None
    release_writes: tuple[ReleaseWrite, ...] = ()
    reverts: tuple[Revert, ...] = ()
    decisions: tuple[Decision, ...] = ()
    admitted_release: str | None = None
    admitted: tuple[Item, ...] = ()
    released: tuple[Item, ...] = ()
    left: tuple[tuple[Item, str], ...] = ()
    kept_out: tuple[tuple[Item, str], ...] = ()
    record: str | None = None
    opens_record: bool = False
    size: int = 0
    numbers: Mapping[str, int] = field(default_factory=dict)
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()

    @property
    def changes(self) -> list[Decision]:
        """The decisions that change or admit an item."""
        return [decision for decision in self.decisions if decision.writes]

    def marks(
        self, numbers: Mapping[str, int]
    ) -> dict[int, tuple[Item, dict[JobMark, str | None]]]:
        """The marks the run sets or clears in items' job records apart from its changes: one
        write for each item. `numbers` gives each Release's milestone number by title."""
        release = self.admitted_release
        admitted = str(numbers[release]) if release is not None and self.admitted else None
        entries: list[tuple[Item, JobMark, str | None]] = [
            *((item, JobMark.ADMITTED, admitted) for item in self.admitted),
            *((item, JobMark.ADMITTED, None) for item in self.released),
            *(
                (item, JobMark.LEFT, _left_mark(title, numbers))
                for item, title in (*self.left, *self.kept_out)
            ),
        ]
        found: dict[int, tuple[Item, dict[JobMark, str | None]]] = {}
        for item, mark, value in entries:
            found.setdefault(item.number, (item, {}))[1][mark] = value
        return found

    @property
    def records(self) -> int:
        """The job-record writes the run makes apart from its changes, the run record's and
        those of the changes it drops included."""
        marked = {
            item.number
            for item in (
                *self.admitted,
                *self.released,
                *(i for i, _ in (*self.left, *self.kept_out)),
            )
        }
        return len(marked) + len(self.reverts) + (self.record is not None) + self.opens_record

    @property
    def has_writes(self) -> bool:
        """Whether the run writes anything at all."""
        return bool(self.release_writes or self.changes or self.records)


def _left_mark(title: str, numbers: Mapping[str, int]) -> str:
    """The `Left` mark naming the backlog, or the Release titled `title` by its number."""
    return title if title == CONST_ROADMAP_LEFT_BACKLOG else str(numbers[title])


# ── Reading ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Ranks:
    """The board's Priority and Value option orders: P0 and High first, an unset value last."""

    priorities: tuple[str, ...]
    values: tuple[str, ...]

    def priority(self, item: Item) -> int:
        """The item's Priority rank, 0 the highest."""
        return _rank(self.priorities, item.priority)

    def value(self, item: Item) -> int:
        """The item's Value rank, 0 the highest."""
        return _rank(self.values, item.value)

    def first(self, item: Item) -> tuple[int, int, int, int]:
        """Top-up order: critical fixes, P0 features, then Priority, Value and lowest number."""
        kind = 0 if is_critical_fix(item) else 1 if is_p0_feature(item) else 2
        return kind, self.priority(item), self.value(item), item.number

    def last(self, item: Item) -> tuple[bool, int, int, int]:
        """Trim and descope order: lowest Priority, lowest Value, highest number; a critical fix
        or a P0 feature only once nothing else is left."""
        protected = is_critical_fix(item) or is_p0_feature(item)
        return protected, -self.priority(item), -self.value(item), -item.number


def _rank(options: Sequence[str], value: str | None) -> int:
    return options.index(value) if value in options else len(options)


@dataclass
class _Run:
    """What one run reads once, and the reads it makes only when a rule needs them.

    `items` are the Items as the rules judge them: each with an earlier change it finishes as
    that change leaves it (its decision is among `finishing`), each with one it drops or judges
    again as it was before that change began. `resumed` are those earlier changes as read,
    `rejudged` the ones judged again, by item, and `reverts` those dropped before judging.
    `record` is the run record; `status_times` replaces when the Status of an item an earlier
    change began a Status write on last changed with when it had last changed before that
    change, since a job writing the Status is no activity. A change that never began its Status
    write leaves the item's Status clock as it is: a person who set the Status since, even to
    what the change found, worked on the item.
    """

    store: RoadmapStore
    repo: str
    config: RoadmapConfig
    now: datetime
    releases: tuple[Release, ...]
    items: tuple[Item, ...]
    ranks: _Ranks
    default_branch: Branch
    record: JobRecord = field(default_factory=dict)
    resumed: tuple[_Resumed, ...] = ()
    finishing: tuple[Decision, ...] = ()
    rejudged: Mapping[int, _Resumed] = field(default_factory=dict)
    reverts: tuple[Revert, ...] = ()
    status_times: Mapping[int, datetime | None] = field(default_factory=dict)
    _linked: dict[int, list[PullRequest]] | None = None

    @property
    def open_releases(self) -> list[Release]:
        """The open Releases, by version."""
        return [release for release in self.releases if release.state is GitHubState.OPEN]

    @property
    def numbers(self) -> dict[str, int]:
        """Each Release's milestone number, by its title."""
        return {release.title: release.number for release in self.releases}

    @property
    def started(self) -> int | None:
        """The milestone number of the Release the run record names."""
        return last_started(self.record)

    @property
    def size_at_start(self) -> int | None:
        """The size the run record gives that Release."""
        return size_at_start(self.record)

    @property
    def window(self) -> timedelta:
        """The stall window."""
        return timedelta(days=self.config.stall_days)

    def number_of(self, title: str) -> int | None:
        """The milestone number of the Release titled `title`, None when there is none yet."""
        return self.numbers.get(title)

    def members(self, title: str, *, closed: bool = False) -> list[Item]:
        """The open Items of the Release titled `title`, and its closed ones with `closed`."""
        version = Version(title)
        return [
            item
            for item in self.items
            if in_release(item.release, version) and (closed or item.state is GitHubState.OPEN)
        ]

    def status_changed_at(self, number: int) -> datetime | None:
        """When the Item's Status last changed, as the rules count it."""
        if number in self.status_times:
            return self.status_times[number]
        return self.store.status_changed_at(number)

    def linked_pull_requests(self, number: int) -> list[PullRequest]:
        """The open or merged pull requests whose bodies close issue `number`, read once per run."""
        if self._linked is None:
            self._linked = {}
            for pull_request in self.store.open_pull_requests():
                for linked in extract_linked_issues(pull_request.body, self.repo):
                    self._linked.setdefault(linked.number, []).append(pull_request)
        return self._linked.get(number, [])

    def note(self, transition: Transition, release: str, target: str | None, detail: str) -> str:
        """The reason's text for one decision."""
        return MESSAGES.roadmap.reasons[transition.reason].format(
            release=release,
            next=target or "",
            cap=self.config.release_cap,
            days=self.config.stall_days,
            detail=detail,
        )

    def decision(
        self,
        state: ReleaseState,
        event: Event,
        item: Item,
        release: str,
        target: str | None,
        detail: str = "",
    ) -> Decision:
        """The table's decision about `item`, going to `target` if it moves."""
        transition = decide(state, event)
        goes_to = target if transition.action in _TO_TARGET else None
        note = self.note(transition, release, goes_to, detail)
        return Decision(item, event, transition, release, goes_to, note)

    def admission_decision(
        self,
        state: ReleaseState,
        event: Event,
        item: Item,
        release: str,
        target: str | None,
        *,
        person: bool,
    ) -> Decision:
        """The admission decision about `item` joining after start or into a cut release.
        If placed by a person, the item is admitted, naming the rule it bypassed.
        """
        transition = decide(state, event)
        if person and transition.action is not Action.ADMIT and state != "merged":
            transition = Transition(Action.ADMIT, transition.reason)
            note = self.note(transition, release, target, "")
            return Decision(item, event, transition, release, None, note, joined=True)
        goes_to = target if transition.action in _TO_TARGET else None
        note = self.note(transition, release, goes_to, "")
        return Decision(item, event, transition, release, goes_to, note, joined=False)


def _require_migrated(options: Mapping[str, Sequence[str]], items: Iterable[Item]) -> None:
    """Refuse a board #739's migrate has not finished. Without the New and Blocked Status
    options the rules can't tell an item that is not ready or is Blocked; while an option
    migrate merges into New is left, or a release epic is still open, migrate has writes left,
    and an epic would count as an Item of its own release."""
    messages = MESSAGES.roadmap
    statuses = options.get(ItemField.STATUS.value, ())
    missing = [
        status
        for status in (CONST_ROADMAP_STATUS_NEW, CONST_ROADMAP_STATUS_BLOCKED)
        if status not in statuses
    ]
    merged = sorted(CONST_ROADMAP_PREMIGRATE_STATUSES.intersection(statuses))
    epics = [
        f"#{item.number}"
        for item in items
        if item.state is GitHubState.OPEN and CONST_ROADMAP_EPIC_LABEL in item.labels
    ]
    problems = [
        template.format(found=", ".join(found))
        for template, found in (
            (messages.reprioritize_unmigrated_missing, missing),
            (messages.reprioritize_unmigrated_merged, merged),
            (messages.reprioritize_unmigrated_epics, epics),
        )
        if found
    ]
    if problems:
        raise ConfigurationError(
            messages.reprioritize_unmigrated.format(problems="; ".join(problems)),
            key=ItemField.STATUS.value,
            details={"missing": missing, "merged": merged, "epics": epics},
        )


def _require_run_record(run: _Run) -> None:
    """Refuse a run with no run record when items carry the job's marks: the job has run
    before, and the run record card is gone, so a first run would admit everything added to the
    release since it started."""
    marked = [
        f"#{item.number}"
        for item in run.items
        if any(item.job_record.get(mark) for mark in JobMark)
    ]
    if marked:
        raise ConfigurationError(
            MESSAGES.roadmap.reprioritize_no_run_record.format(
                card=CONST_ROADMAP_RUN_RECORD_TITLE,
                items=", ".join(marked[:5]),
                count=len(marked),
            ),
            key=CONST_ROADMAP_RUN_RECORD_TITLE,
            details={"items": marked},
        )


def _recorded(run: _Run, current: Release) -> Release | None:
    """The Release the run record names, None before the first run; raising when the run record
    card holds a record whose `Started` mark names no milestone number, as an older version of
    the job or a hand edit leaves it, or names a milestone the repository no longer has."""
    started = run.started
    if started is None and run.record:
        held = JobMark.STARTED in run.record
        mark = json.dumps(run.record[JobMark.STARTED]) if held else "missing"
        raise ConfigurationError(
            MESSAGES.roadmap.reprioritize_record_unreadable.format(
                card=CONST_ROADMAP_RUN_RECORD_TITLE,
                started=mark,
                number=current.number,
                release=current.title,
            ),
            key=CONST_ROADMAP_RUN_RECORD_TITLE,
            details={"started": mark[:64]},
        )
    if started is None:
        return None
    found = next((release for release in run.releases if release.number == started), None)
    if found is None:
        raise ConfigurationError(
            MESSAGES.roadmap.reprioritize_record_gone.format(
                number=started, card=CONST_ROADMAP_RUN_RECORD_TITLE
            ),
            key=CONST_ROADMAP_RUN_RECORD_TITLE,
            details={"milestone": started},
        )
    return found


def _same_place(left: str | None, right: str | None) -> bool:
    """Whether two values of a field are the same, a Release compared as a version."""
    if left is None or right is None or not (is_release_title(left) and is_release_title(right)):
        return left == right
    return Version(left) == Version(right)


def _changed_since(
    store: RoadmapStore,
    number: int,
    item_field: ItemField,
    pending: _Pending,
    *,
    written: bool = False,
) -> bool:
    """Whether the field changed since the change began, or, `written`, since the job wrote
    it: the issue joined or left a Release since, for the Release, as its events count them;
    its Status changed since, for the Status."""
    if item_field is ItemField.RELEASE:
        moves = pending.written_moves if written else pending.moves
        return len(store.release_changes(number)) != moves
    status_at = pending.written_status_at if written else pending.status_at
    return store.status_changed_at(number) != status_at


def _never_joined(store: RoadmapStore, number: int, pending: _Pending, target: str | None) -> bool:
    """Whether the issue's Release events since the change began show it never joined `target`,
    the Release the change moves it to, by the title it has now or had then, as an event keeps
    it: then the change's milestone call never landed. Never for the backlog, which no join
    shows."""
    if target is None or pending.moves is None:
        return False
    named = {target, pending.target_title or target}
    since = store.release_changes(number)[pending.moves :]
    return not any(
        change.kind is ChangeKind.JOINED_RELEASE
        and any(_same_place(change.release, title) for title in named)
        for change in since
    )


class _Owner(StrEnum):
    """Whose a field a resumed change writes is now, as `_owner` reads it."""

    JOB = "job"
    NO_ONE = "no_one"
    UNPROVEN = "unproven"
    PERSON = "person"
    UNLANDED = "unlanded"


def _owner(
    store: RoadmapStore,
    item: Item,
    pending: _Pending,
    write: tuple[ItemField, str | None],
    was: str | None,
) -> _Owner:
    """Whose the field is that a resumed change writes (`write`, the field and the change's
    value), the field having held `was` when the change began; `_resumed` gives the rules."""
    item_field, value = write
    holds = _same_place(item.field_value(item_field), value)
    if item_field in pending.written:
        if not holds or _changed_since(store, item.number, item_field, pending, written=True):
            return _Owner.PERSON
        return _Owner.JOB
    if item_field in pending.begun:
        if not _changed_since(store, item.number, item_field, pending):
            return _Owner.NO_ONE
        if holds:
            return _Owner.UNPROVEN
        never = item_field is ItemField.RELEASE and _never_joined(
            store, item.number, pending, value
        )
        return _Owner.UNLANDED if never else _Owner.PERSON
    if not _same_place(item.field_value(item_field), was):
        return _Owner.PERSON
    if item_field is ItemField.STATUS and _changed_since(store, item.number, item_field, pending):
        return _Owner.PERSON
    return _Owner.NO_ONE


def _resumed(store: RoadmapStore, item: Item, titles: Mapping[int, str]) -> _Resumed | None:
    """The change an earlier run began on the item, from its `Pending` mark; None when it has
    none.

    A field the mark records as written is the job's while it holds the change's value and has
    not changed since the job wrote it, and a person's once it holds anything else or has
    changed since, even back to that value. A field it began, whose write may not have reached
    GitHub, is read again: one that has not changed since was never set, and is no one's yet;
    one that has changed and holds the change's value may be the job's write or a person's, so
    it is unproven, and the change has happened; one that holds anything else is a person's,
    and a Release the issue's events show never joined the change's target is `unlanded` too.
    A field it did not begin is a person's once it holds anything but what it held before, and
    the Status once it has changed since, even back to what it held: the job writes the Status
    only once it has recorded it as begun, so every change to it since is a person's. A Release
    it did not begin that a person moved out and back is where it was, as when no run saw it
    leave.
    """
    text = item.job_record.get(JobMark.PENDING)
    if not text:
        return None
    try:
        pending = _Pending.model_validate_json(text)
    except MalformedPendingError:
        return _Resumed(item)
    named = (pending.release, pending.target, pending.was_in)
    if any(number is not None and number not in titles for number in named):
        return _Resumed(item)
    if pending.moves is not None and ItemField.RELEASE not in pending.begun:
        # A person may have moved the item out and back since the change began: the Release
        # write it has yet to begin counts its events from here.
        pending = pending.model_copy(update={"moves": len(store.release_changes(item.number))})
    decision = Decision(
        item,
        pending.event,
        Transition(pending.action, pending.reason),
        titles[pending.release],
        titles[pending.target] if pending.target is not None else None,
        pending.note,
        begun=pending,
        admits=pending.admits,
        joined=pending.joined,
    )
    was = {
        ItemField.RELEASE: titles[pending.was_in] if pending.was_in is not None else None,
        ItemField.STATUS: pending.was,
    }
    writes = _field_writes(decision)
    owners = {write[0]: _owner(store, item, pending, write, was[write[0]]) for write in writes}

    def owned(*kinds: _Owner) -> frozenset[ItemField]:
        return frozenset(f for f, owner in owners.items() if owner in kinds)

    unproven, person = owned(_Owner.UNPROVEN), owned(_Owner.PERSON, _Owner.UNLANDED)
    undo = tuple(
        (f, was[f])
        for f, value in writes
        if owners[f] is _Owner.JOB and not _same_place(value, was[f])
    )
    return _Resumed(
        item,
        replace(decision, unproven=unproven, by_person=person, unlanded=owned(_Owner.UNLANDED)),
        undo,
        unproven,
        person,
        done=store.comments_on(item.number).count(pending.comment) > pending.posted,
        release=pending.release,
        status_at=pending.status_at if ItemField.STATUS in pending.begun else None,
    )


def _read_run(store: RoadmapStore, repo: str, config: RoadmapConfig, now: datetime) -> _Run:
    options = field_options(store.board_fields())
    items = tuple(store.items())
    _require_migrated(options, items)
    releases = tuple(store.releases())
    titles = {release.number: release.title for release in releases}
    resumed = tuple(found for item in items if (found := _resumed(store, item, titles)))
    return _Run(
        store=store,
        repo=repo,
        config=config,
        now=now,
        releases=releases,
        items=items,
        ranks=_Ranks(
            options.get(ItemField.PRIORITY.value, ()), options.get(ItemField.VALUE.value, ())
        ),
        default_branch=store.default_branch(),
        record=store.run_record(),
        resumed=resumed,
    )


def _as_begun(resumed: _Resumed) -> Item:
    """The item as it was before the change began, but for what a person set since: the
    fields it wrote that still hold its values back as they were, in the item and its job
    record, as putting them back records them; the fields it began and did not record as
    written with the record `_taken_back` leaves a dropped change's; and no `Pending` mark."""
    record = with_marks(resumed.item.job_record, {JobMark.PENDING: None})
    if resumed.decision is not None:
        _put_back(record, *_taken_back(resumed.decision, dropped=True))
    for item_field, value in resumed.undo:
        record[item_field] = value
    values = {item_field.name.lower(): value for item_field, value in resumed.undo}
    return resumed.item.model_copy(update={**values, "job_record": record})


def _pulled_into_shipped(run: _Run, resumed: _Resumed, decision: Decision | None) -> bool:
    """Whether the change is a start's pull-in whose milestone call never landed, about a
    release that has shipped since: no comment posted, no Release written or unproven. Finished,
    it would move the item into a release it was never in when it shipped."""
    if decision is None or decision.action is not Action.PULL_IN or decision.begun is None:
        return False
    if resumed.done or resumed.unproven or ItemField.RELEASE in decision.begun.written:
        return False
    release = next((r for r in run.releases if r.number == resumed.release), None)
    if release is None:
        return False
    return release_state(run.store, release, run.default_branch.name) is ReleaseState.SHIPPED


def _prepare(run: _Run, judged: int | None) -> _Run:
    """The run, with each earlier change sorted: finished, dropped, or judged again.

    A change whose comment is posted is finished: only its marks are left. So is one with an
    unproven field, which has happened at least in part, leaving the fields someone else may
    have set as they are. One whose fields a person has set since, or whose mark can't be read,
    is dropped. One about `judged`, the release this run judges, is judged again with the item
    as it was before the change began. A pull-in into a release that has shipped since, whose
    milestone call never landed, is dropped (`_pulled_into_shipped`): the item was never in that
    release when it shipped, and the start that runs now judges it afresh. Any other is
    finished, and the item then judged as it leaves it.
    """
    items = {item.number: item for item in run.items}
    finishing: list[Decision] = []
    reverts: list[Revert] = []
    rejudged: dict[int, _Resumed] = {}
    times: dict[int, datetime | None] = {}
    numbers = run.numbers
    for resumed in run.resumed:
        number, decision = resumed.item.number, resumed.decision
        dropped = resumed.person and not resumed.done and not resumed.unproven
        if decision is None or dropped or _pulled_into_shipped(run, resumed, decision):
            reverts.append(resumed.revert())
            items[number] = _as_begun(resumed)
        elif resumed.done:
            announced = replace(decision, done=True)
            finishing.append(announced)
            items[number] = _settled(announced, run.now, numbers, fields=False)
        elif resumed.release == judged and not resumed.unproven:
            rejudged[number] = resumed
            items[number] = _as_begun(resumed)
        else:
            finishing.append(decision)
            items[number] = _settled(decision, run.now, numbers)
        if ItemField.STATUS not in resumed.person and resumed.status_at is not None:
            times[number] = resumed.status_at
    return replace(
        run,
        items=tuple(items[item.number] for item in run.items),
        finishing=tuple(finishing),
        rejudged=rejudged,
        reverts=tuple(reverts),
        status_times=times,
    )


def _patch_bump(releases: Iterable[Release], above: Version) -> str:
    """The lowest patch release above `above` that no Release has yet."""
    taken = {release.version for release in releases}
    candidate = Version(f"{above.major}.{above.minor}.{above.micro + 1}")
    while candidate in taken:
        candidate = Version(f"{candidate.major}.{candidate.minor}.{candidate.micro + 1}")
    return f"v{candidate}"


def _create_release(title: str) -> ReleaseWrite:
    return ReleaseWrite(
        MESSAGES.roadmap.reprioritize_create_release.format(release=title),
        lambda store: store.create_release(title),
    )


def _close_release(title: str) -> ReleaseWrite:
    """Close a shipped release's milestone, after every other write of the run."""
    return ReleaseWrite(
        MESSAGES.roadmap.reprioritize_close_release.format(release=title),
        lambda store: store.close_release(title),
        last=True,
    )


# ── The current release's rules ───────────────────────────────────────────────


def _next_release(run: _Run, after: Release) -> tuple[str, tuple[ReleaseWrite, ...]]:
    """The next planned release after `after`, and the write that creates it when there is none."""
    later = [release for release in run.open_releases if release.version > after.version]
    if later:
        return later[0].title, ()
    title = _patch_bump(run.releases, after.version)
    return title, (_create_release(title),)


def _blocked(_: _Run, item: Item, __: list[Item]) -> str | None:
    return "" if item.status == CONST_ROADMAP_STATUS_BLOCKED else None


def _depends_outside(run: _Run, item: Item, members: list[Item]) -> str | None:
    """The open dependencies outside the current release, named; None when there are none."""
    inside = {member.number for member in members}
    ours = run.repo.lower()
    outside = [
        f"#{dependency.number}" if dependency.repository.lower() == ours else dependency.url
        for dependency in run.store.dependencies(item.number)
        if dependency.state is GitHubState.OPEN
        and not (dependency.repository.lower() == ours and dependency.number in inside)
    ]
    return ", ".join(outside) if outside else None


def _needs_split(_: _Run, item: Item, __: list[Item]) -> str | None:
    if CONST_ROADMAP_NEEDS_SPLIT_LABEL in item.labels:
        return ""
    if item.job_record.get(RefineRecordKey.NEEDS_SPLIT) in {"true", "1", "True"}:
        return ""
    return None


def _others_done(_: _Run, item: Item, members: list[Item]) -> str | None:
    """Whether every other item in the release, and there is one, is Done or closed."""
    others = [member for member in members if member.number != item.number]
    done = all(
        member.state is GitHubState.CLOSED or member.status == CONST_ROADMAP_STATUS_DONE
        for member in others
    )
    return "" if others and done else None


# An unstarted item's descoping reasons, in the order they are checked: the event for any item,
# and for a critical fix. `members` is every item in the release, open and closed.
_DESCOPE_CHECKS: tuple[tuple[Callable[[_Run, Item, list[Item]], str | None], Event, Event], ...] = (
    (_blocked, Event.BLOCKED, Event.FIX_BLOCKED),
    (_depends_outside, Event.DEPENDS_OUTSIDE, Event.FIX_DEPENDS_OUTSIDE),
    (_needs_split, Event.NEEDS_SPLIT, Event.FIX_NEEDS_SPLIT),
    (_others_done, Event.OTHERS_DONE, Event.FIX_OTHERS_DONE),
)


def _last_activity(run: _Run, item: Item) -> datetime | None:
    """The latest of the item's last status change and its open pull requests' last update and
    last commit; None when none is known."""
    moments = [run.status_changed_at(item.number)]
    for pull_request in run.linked_pull_requests(item.number):
        moments.extend((pull_request.updated_at, pull_request.last_commit_at))
    known = [moment for moment in moments if moment is not None]
    return max(known, default=None)


def _nudge_due(run: _Run, item: Item) -> bool:
    """Whether the item has had no nudge within the stall window."""
    nudged = item.job_record.get(JobMark.NUDGED)
    try:
        return nudged is None or run.now - datetime.fromisoformat(nudged) >= run.window
    except ValueError:
        return True


def _stall_event(run: _Run, item: Item) -> Event | None:
    """The stall window's event for a started item, if it has been idle for it."""
    if item.status not in (CONST_ROADMAP_STATUS_IN_PROGRESS, CONST_ROADMAP_STATUS_IN_REVIEW):
        return None
    activity = _last_activity(run, item)
    if activity is None or run.now - activity < run.window:
        return None
    if item.status == CONST_ROADMAP_STATUS_IN_REVIEW:
        return Event.REVIEW_IDLE if _nudge_due(run, item) else None
    return Event.FIX_STALLED if is_critical_fix(item) else Event.STALLED


def _rule_event(run: _Run, item: Item, members: list[Item]) -> tuple[Event, str] | None:
    """The first rule that applies to an item already in the current release, with its detail."""
    if is_started(item) or bool(run.linked_pull_requests(item.number)):
        stalled = _stall_event(run, item)
        return (stalled, "") if stalled else None
    fix = is_critical_fix(item)
    for check, event, fix_event in _DESCOPE_CHECKS:
        detail = check(run, item, members)
        if detail is not None:
            return (fix_event if fix else event), detail
    return None


def _cap_decisions(
    run: _Run,
    state: ReleaseState,
    current: Release,
    target: str,
    remaining: list[Item],
    admitted_now: list[Item],
    joined_now: Container[int] = frozenset(),
) -> list[Decision]:
    """The items descoped to hold the release to its size, lowest-ranked first.

    Each critical fix the run admits that takes the release over its cap descopes at most one
    item: the lowest-ranked unstarted item that is not a critical fix. With none left, the fix
    joins anyway. Beyond those, while the release holds more than the larger of the cap and its
    size at start, as the run record gives it, such items leave too: one a person moved back to
    Ready after a fix had joined makes room then.
    """
    cap, title = run.config.release_cap, current.title
    planned_remaining = [
        item
        for item in remaining
        if item.number not in joined_now and joined_release(item) != current.number
    ]
    for_fixes = max(0, min(len(planned_remaining) - cap, len(admitted_now)))
    known = run.size_at_start is not None and run.started == current.number
    over = len(planned_remaining) - max(cap, run.size_at_start or 0) if known else 0
    candidates = sorted(
        (
            item
            for item in planned_remaining
            if not is_started(item)
            and not is_critical_fix(item)
            and not run.linked_pull_requests(item.number)
        ),
        key=run.ranks.last,
    )
    victims = candidates[: max(for_fixes, over)]
    return [
        run.decision(state, Event.OVER_CAP, victim, title, target, f"#{admitted_now[n].number}")
        if n < for_fixes
        else run.decision(state, Event.OVER_SIZE, victim, title, target, str(len(remaining)))
        for n, victim in enumerate(victims)
    ]


def _descope_decisions(
    run: _Run, state: ReleaseState, current: str, target: str, decided: Container[int]
) -> dict[int, Decision]:
    """The descoping and stall decisions about every item still in the release."""
    members = run.members(current, closed=True)
    found: dict[int, Decision] = {}
    for item in run.members(current):
        rule = None if item.number in decided else _rule_event(run, item, members)
        if rule is None:
            continue
        decision = run.decision(state, rule[0], item, current, target, rule[1])
        if decision.action is not Action.KEEP:
            found[item.number] = decision
    return found


def _released(run: _Run, title: str) -> tuple[Item, ...]:
    """The items, open or closed, admitted to the Release titled `title` that have since left
    it: a person took them out, or a first run or a start that stopped part-way marked them
    before. A closed one loses its mark too, so reopening it where it was admitted is a join."""
    number, version = run.number_of(title), Version(title)
    return tuple(
        item
        for item in run.items
        if number is not None
        and admitted_to(item) == number
        and not in_release(item.release, version)
    )


def _taken_from(item: Item, current: Release | None, opened: Container[str]) -> str | None:
    """Where a person took the item out of: the current release it was admitted to, or an open
    release a job last placed it in, or the backlog (`CONST_ROADMAP_LEFT_BACKLOG`) when a job
    last placed it there. None when it is still there."""
    if current is not None and admitted_to(item) == current.number:
        return None if in_release(item.release, current.version) else current.title
    record = item.job_record
    if ItemField.RELEASE not in record or record[ItemField.RELEASE] == item.release:
        return None
    placed = record[ItemField.RELEASE]
    if placed is None:
        return CONST_ROADMAP_LEFT_BACKLOG
    return placed if placed in opened else None


def _left(
    run: _Run, current: Release | None, moved: Container[int]
) -> tuple[tuple[Item, str], ...]:
    """The items, open or closed, a person took out of where a job placed or admitted them,
    with that place, whose `Left` mark doesn't name it yet: their return is then judged again,
    and where a person puts them stands. An item the run itself `moved` gets no mark: a job's
    move clears it."""
    opened = {release.title for release in run.open_releases}
    found = (
        (item, _taken_from(item, current, opened)) for item in run.items if item.number not in moved
    )
    numbers = run.numbers
    return tuple(
        (item, title)
        for item, title in found
        if title is not None and item.job_record.get(JobMark.LEFT) != _left_mark(title, numbers)
    )


def _sets_release(decision: Decision, untouched: Container[ItemField]) -> bool:
    """Whether the decision sets the item's Release, but for the fields it leaves `untouched`."""
    return any(f is ItemField.RELEASE and f not in untouched for f, _ in _field_writes(decision))


def _moved(decisions: Iterable[Decision]) -> frozenset[int]:
    """The items whose Release the decisions set in this run, or finish setting: not a `done`
    one's, whose fields an earlier run wrote, nor one's whose Release a person set since."""
    return frozenset(
        d.item.number for d in decisions if not d.done and _sets_release(d, d.by_person)
    )


def _plan_rules(run: _Run, current: Release, state: ReleaseState) -> ReprioritizationPlan:
    """Admission, descoping, the stall window and the cap, in that order, for one run.

    An admitted critical fix meets the descoping and stall rules in the same run, and joins the
    admitted set unless one of them moves it out. Each item gets one decision, the last that
    applies to it, after any earlier change the run finishes on it. A fix that joins and that
    the stall rule readies or nudges gets that rule's decision, which `admits` it: the admission
    is part of that change, so a run that stops part-way through it leaves both to the next.
    """
    target, creates = _next_release(run, current)
    joined = {
        item.number: run.admission_decision(
            state,
            admission_event(item, has_pr=bool(run.linked_pull_requests(item.number))),
            item,
            current.title,
            target,
            person=placed_by_person(item, _history(run, item)),
        )
        for item in run.members(current.title)
        if admitted_to(item) != current.number
    }
    moving = {number: d for number, d in joined.items() if d.action is not Action.ADMIT}
    decisions = joined | _descope_decisions(run, state, current.title, target, moving.keys())
    leaving = {number for number, decision in decisions.items() if decision.leaves}
    # A fix the run admits takes the release over the cap at most once.
    admitted_now = [
        d.item
        for n, d in joined.items()
        if d.action is Action.ADMIT and is_critical_fix(d.item) and n not in leaving
    ]
    remaining = [item for item in run.members(current.title) if item.number not in leaving]
    joined_now = {n for n, d in joined.items() if d.joined}
    for victim in _cap_decisions(run, state, current, target, remaining, admitted_now, joined_now):
        decisions[victim.item.number] = victim
    # A fix the run admits that a rule also readies or nudges keeps that rule's decision, which
    # carries the admission.
    for number, joining in joined.items():
        last = decisions[number]
        if joining.action is Action.ADMIT and last.action is not Action.ADMIT and not last.leaves:
            decisions[number] = replace(last, admits=True, joined=joining.joined)
    ordered = tuple(decisions[number] for number in sorted(decisions))
    return ReprioritizationPlan(
        repo=run.repo,
        now=run.now,
        current=current.title,
        state=state,
        release_writes=creates if any(d.target == target for d in ordered) else (),
        decisions=(*run.finishing, *ordered),
        admitted_release=current.title,
        released=_released(run, current.title),
        left=_left(run, current, _moved((*run.finishing, *ordered))),
    )


# ── Release start ─────────────────────────────────────────────────────────────


def _start_event(item: Item, *, has_pr: bool = False) -> Event | None:
    """What a starting release does with an item placed in it that is New or Blocked."""
    if has_pr:
        return None
    fix = is_critical_fix(item)
    if item.status == CONST_ROADMAP_STATUS_NEW:
        return Event.FIX_NEW_AT_START if fix else Event.NEW_AT_START
    if item.status == CONST_ROADMAP_STATUS_BLOCKED:
        return Event.FIX_BLOCKED_AT_START if fix else Event.BLOCKED_AT_START
    return None


def _history(run: _Run, item: Item) -> list[Change]:
    """The item's joins and leaves of Releases, read only for a backlog item no job placed and
    with no `Left` mark, whose history alone tells whether a person took it out of a Release."""
    record = item.job_record
    if item.release is not None or ItemField.RELEASE in record or record.get(JobMark.LEFT):
        return []
    return run.store.release_changes(item.number)


def _candidates(run: _Run, later: str) -> tuple[list[Item], list[tuple[Item, str]]]:
    """Ready items in the backlog or the later planned release that no person placed there.

    Also the backlog items no job placed whose issue's events show a person took them out of a
    Release, with the last such Release, to record as their `Left` mark: a person's placement.
    One whose Release no longer goes by the title its events give stays out unmarked, and its
    events are read again at the next start.
    """
    version = Version(later)
    ready = [
        item
        for item in run.items
        if item.state is GitHubState.OPEN
        and item.status == CONST_ROADMAP_STATUS_READY
        and (item.release is None or in_release(item.release, version))
    ]
    found: list[Item] = []
    kept_out: list[tuple[Item, str]] = []
    for item in ready:
        history = _history(run, item)
        if not placed_by_person(item, history):
            found.append(item)
        elif left := [c.release for c in history if c.kind is ChangeKind.LEFT_RELEASE]:
            named = find_release(run.releases, left[-1]) if left[-1] else None
            kept_out.extend((item, release.title) for release in (named,) if release)
    return found, kept_out


def _planned_titles(
    run: _Run, titles: Sequence[str], floor: Version
) -> tuple[list[str], list[ReleaseWrite]]:
    """The starting release and the planned ones after it: the open `titles`, then patch bumps
    of the highest (of `floor` when there is none) until `planning_horizon`, and at least one,
    planned releases follow the starting one."""
    planned = list(titles)
    writes: list[ReleaseWrite] = []
    known = list(run.releases)
    while len(planned) < 1 + max(1, run.config.planning_horizon):
        title = _patch_bump(known, Version(planned[-1]) if planned else floor)
        known.append(Release(number=0, title=title))
        planned.append(title)
        writes.append(_create_release(title))
    return planned, writes


def _branch_writes(run: _Run, starting: str) -> list[ReleaseWrite]:
    """Create `release/vX.Y.Z` at the default branch's head, unless it exists."""
    name = f"{CONST_RELEASE_BRANCH_PREFIX}{starting}"
    if run.store.branch(name) is not None:
        return []
    sha = run.default_branch.sha
    text = MESSAGES.roadmap.reprioritize_create_branch.format(branch=name, sha=sha[:7])
    return [ReleaseWrite(text, lambda store: store.create_branch(name, sha))]


def _is_cut(run: _Run, title: str) -> bool:
    """Whether the Release titled `title` is cut or merged: its release pull request is open, or
    merged with the release not yet published. False for one the run creates."""
    release = find_release(run.releases, title)
    if release is None:
        return False
    state = release_state(run.store, release, run.default_branch.name)
    return state in (ReleaseState.CUT, ReleaseState.MERGED)


def _fill_or_trim(
    run: _Run, starting: str, later: str, kept: list[Item]
) -> tuple[list[Decision], list[tuple[Item, str]]]:
    """Top the starting release up to the cap, or trim it down to it; with the backlog items a
    person took out of a Release, which stay out (`_candidates`). A release a person cut before
    any run started it, its release pull request open or merged, is topped up with nothing."""
    cap = run.config.release_cap
    if len(kept) < cap and _is_cut(run, starting):
        return [], []
    if len(kept) < cap:
        candidates, kept_out = _candidates(run, later)
        pulled = sorted(candidates, key=run.ranks.first)[: cap - len(kept)]
        size = str(len(kept) + len(pulled))
        return [
            run.decision(ReleaseState.PLANNED, Event.CANDIDATE, item, starting, starting, size)
            for item in pulled
        ], kept_out
    unstarted = sorted(
        (
            item
            for item in kept
            if not is_started(item) and not run.linked_pull_requests(item.number)
        ),
        key=run.ranks.last,
    )
    return [
        run.decision(ReleaseState.PLANNED, Event.OVER_CAP_AT_START, item, starting, later)
        for item in unstarted[: len(kept) - cap]
    ], []


def _shipped_after(run: _Run, state: ReleaseState) -> list[Release]:
    """The open releases right after a shipped current release that have shipped too, in
    order: a person cut and shipped them while no run started the release after the current
    one. None when the current release has not shipped."""
    if state is not ReleaseState.SHIPPED:
        return []
    shipped: list[Release] = []
    for release in run.open_releases[1:]:
        if release_state(run.store, release, run.default_branch.name) is not ReleaseState.SHIPPED:
            break
        shipped.append(release)
    return shipped


def _startable(run: _Run, shipped: Sequence[Release]) -> list[str]:
    """The open releases from the one a start starts: the current release, or, when it has
    shipped with its milestone still open, the first after it and the releases that shipped
    since (`shipped`, the current one first) that has not shipped."""
    return [r.title for r in run.open_releases[len(shipped) :]]


def _plan_start(
    run: _Run, current: Release, state: ReleaseState, shipped: Sequence[Release]
) -> ReprioritizationPlan:
    """Start a release: branch it, clear its New and Blocked items, fill or trim it, admit it,
    and name it in the run record.

    A shipped `current` whose milestone is still open starts the first release after it that
    has not shipped, and every release in `shipped`, the current one and those after it that
    shipped too, is closed last; otherwise `current` itself starts, the release before it being
    closed already. The admitted set takes the release's closed items too, so one reopened
    there never joined it; the size counts the open ones.
    """
    floor = (shipped[-1] if shipped else current).version
    titles, creates = _planned_titles(run, _startable(run, shipped), floor)
    starting, later = titles[0], titles[1]
    number = run.number_of(starting)
    cleared = [
        run.decision(ReleaseState.PLANNED, event, item, starting, later)
        for item in run.members(starting)
        if (event := _start_event(item, has_pr=bool(run.linked_pull_requests(item.number))))
        is not None
    ]
    leaving = {decision.item.number for decision in cleared if decision.leaves}
    kept = [item for item in run.members(starting) if item.number not in leaving]
    closed = [i for i in run.members(starting, closed=True) if i.state is GitHubState.CLOSED]
    sized, kept_out = _fill_or_trim(run, starting, later, kept)
    trimmed = {decision.item.number for decision in sized if decision.leaves}
    pulled = len(sized) - len(trimmed)
    # A pulled-in item gets its mark with its change; a kept one that has it already, from an
    # earlier run that stopped part-way, needs none.
    admitted = [
        item
        for item in (*kept, *closed)
        if item.number not in trimmed and (number is None or admitted_to(item) != number)
    ]
    decisions = [*run.finishing, *(d for d in [*cleared, *sized] if d.action is not Action.KEEP)]
    return ReprioritizationPlan(
        repo=run.repo,
        now=run.now,
        current=current.title,
        state=state,
        shipped=shipped[-1].title if shipped else None,
        starting=starting,
        release_writes=(
            *creates,
            *_branch_writes(run, starting),
            *(_close_release(release.title) for release in shipped),
        ),
        decisions=tuple(sorted(decisions, key=lambda d: d.item.number)),
        admitted_release=starting,
        admitted=tuple(sorted(admitted, key=lambda item: item.number)),
        released=_released(run, starting),
        left=_left(run, None, _moved(decisions)),
        kept_out=tuple(kept_out),
        record=starting,
        size=len(kept) - len(trimmed) + pulled,
    )


# ── The run ───────────────────────────────────────────────────────────────────


def _plan_first_run(
    run: _Run, current: Release, state: ReleaseState, shipped: Sequence[Release]
) -> ReprioritizationPlan:
    """Record the admitted set of the release under way, then name it in the run record; move
    nothing.

    The release under way is the current one, or, once that has shipped with its milestone
    still open, the first release after it that has not shipped, which started then: every
    release in `shipped`, the current one and those after it that shipped too, is closed last,
    and a first run records the same release whether `release.yml` closed them or not. Its
    closed items join the admitted set too, and the size counts the open ones. The run names
    the release in the run record before its marks, unless a first run that stopped part-way
    has, and gives its size last.
    """
    recorded, creates = _next_release(run, shipped[-1]) if shipped else (current.title, ())
    number = run.number_of(recorded)
    members = run.members(recorded, closed=True) if not creates else []
    return ReprioritizationPlan(
        repo=run.repo,
        now=run.now,
        current=current.title,
        state=state,
        first_run=True,
        shipped=shipped[-1].title if shipped else None,
        release_writes=(*creates, *(_close_release(release.title) for release in shipped)),
        decisions=run.finishing,
        admitted_release=recorded,
        admitted=tuple(item for item in members if admitted_to(item) != number),
        released=_released(run, recorded),
        record=recorded,
        opens_record=number is None or run.started != number,
        size=sum(item.state is GitHubState.OPEN for item in members),
    )


def _plan_unshipped(
    run: _Run, current: Release, state: ReleaseState, unshipped: str
) -> ReprioritizationPlan:
    """Start nothing: the release before the current one was closed without shipping. A
    change an earlier run began is still finished, or dropped."""
    return ReprioritizationPlan(
        repo=run.repo,
        now=run.now,
        current=current.title,
        state=state,
        unshipped=unshipped,
        decisions=run.finishing,
    )


def _plan_behind(
    run: _Run, current: Release, state: ReleaseState, recorded: Release
) -> ReprioritizationPlan:
    """Hold the current release to no rule: it is older than the Release the run record names,
    as a hotfix milestone opened later is, so it never started and has no admitted set, and
    the release after it has started already. A change an earlier run began is still finished,
    or dropped."""
    return ReprioritizationPlan(
        repo=run.repo,
        now=run.now,
        current=current.title,
        state=state,
        behind=recorded.title,
        decisions=run.finishing,
    )


def _unshipped_before(run: _Run, current: Release) -> str | None:
    """The release before the current one, when its milestone was closed without it shipping:
    its release pull request has not merged, or its GitHub Release is not published. None once
    it has shipped, and when there is none, as when its milestone was deleted."""
    earlier = [release for release in run.releases if release.version < current.version]
    before = max(earlier, key=lambda release: release.version, default=None)
    if before is None:
        return None
    state = release_state(run.store, before, run.default_branch.name)
    return None if state is ReleaseState.SHIPPED else before.title


def _shipped_since(run: _Run, recorded: Release) -> bool:
    """Whether the Release the run record names has shipped since, and `release.yml` has
    closed its milestone, as it does after it publishes the release: then the release after it
    starts. One that shipped with its milestone still open is among the shipped releases a start
    skips already."""
    if recorded.state is not GitHubState.CLOSED:
        return False
    return release_state(run.store, recorded, run.default_branch.name) is ReleaseState.SHIPPED


def _under_way(run: _Run, recorded: Release) -> tuple[Release, ReleaseState] | None:
    """The Release the run record names, with its state, while it is open and has not shipped:
    the release under way once the shipped one before it is closed. None otherwise."""
    if recorded.state is not GitHubState.OPEN:
        return None
    state = release_state(run.store, recorded, run.default_branch.name)
    return None if state is ReleaseState.SHIPPED else (recorded, state)


def _plan_close(
    run: _Run,
    current: Release,
    state: ReleaseState,
    under_way: tuple[Release, ReleaseState] | None,
    shipped: Sequence[Release],
) -> ReprioritizationPlan:
    """Close the shipped releases whose successor the run record already names: a run that
    started it, or recorded it at a first run, stopped before its last writes, the closes of
    `shipped`, the current release and those after it that shipped too.

    That successor, while it is `under_way`, is held to the rules first, as the current release
    in its own state, so an item a person added to it since that run is judged now, and the
    closes are the last writes. Once its milestone is closed without it shipping, the closes are
    all there is; one that has shipped since starts the release after it instead
    (`_shipped_since`).
    """
    closes = tuple(_close_release(release.title) for release in shipped)
    if under_way is None:
        return ReprioritizationPlan(
            repo=run.repo,
            now=run.now,
            current=current.title,
            state=state,
            shipped=shipped[-1].title,
            release_writes=closes,
            decisions=run.finishing,
        )
    plan = _plan_rules(run, *under_way)
    return replace(plan, shipped=shipped[-1].title, release_writes=(*plan.release_writes, *closes))


def _reconcile(run: _Run, plan: ReprioritizationPlan) -> ReprioritizationPlan:
    """Settle each change an earlier run began that this run judged again: finish it when the
    plan decides the same about the item, and otherwise drop it before the plan's own decision.
    Add the changes dropped before judging, and the Releases' milestone numbers."""
    reverts = list(run.reverts)
    decisions = list(plan.decisions)
    for index, decision in enumerate(plan.decisions):
        resumed = run.rejudged.get(decision.item.number)
        if resumed is not None and resumed.decision and not decision.resumed:
            if decision.same_as(resumed.decision):
                decisions[index] = resumed.decision
    kept = {d.item.number for d in decisions if d.resumed}
    reverts += [
        resumed.revert() for number, resumed in sorted(run.rejudged.items()) if number not in kept
    ]
    return replace(
        plan,
        decisions=tuple(decisions),
        reverts=tuple(sorted(reverts, key=lambda revert: revert.item.number)),
        numbers=run.numbers,
    )


def _judged(
    run: _Run, plan_for: Callable[[_Run], ReprioritizationPlan], release: str | None
) -> ReprioritizationPlan:
    """The plan `plan_for` makes, with the changes earlier runs began settled: those about
    `release`, the release the plan judges, are judged again."""
    prepared = _prepare(run, run.number_of(release) if release else None)
    return _reconcile(prepared, plan_for(prepared))


def plan_reprioritization(
    store: RoadmapStore, *, repo: str, config: RoadmapConfig, now: datetime
) -> ReprioritizationPlan:
    """Read the roadmap and plan one run at `now`, writing nothing."""
    run = _read_run(store, repo, config, now)
    current = current_release(run.releases)
    if current is None:
        return ReprioritizationPlan(repo=repo, now=now, current=None, state=None)
    state = release_state(store, current, run.default_branch.name)
    recorded = _recorded(run, current)
    # The shipped releases whose milestones are still open: the current one, if it has shipped,
    # and each open release right after it that has shipped too.
    shipped = [current, *_shipped_after(run, state)] if state is ReleaseState.SHIPPED else []
    if recorded is None:
        _require_run_record(run)
    if recorded is None or run.size_at_start is None:
        return _judged(run, lambda r: _plan_first_run(r, current, state, shipped), None)
    if shipped and recorded.version > shipped[-1].version and not _shipped_since(run, recorded):
        under_way = _under_way(run, recorded)
        judged = under_way[0].title if under_way else None
        return _judged(run, lambda r: _plan_close(r, current, state, under_way, shipped), judged)
    if recorded.version > current.version and not shipped:
        return _judged(run, lambda r: _plan_behind(r, current, state, recorded), None)
    is_new = current.number != recorded.number
    unshipped = _unshipped_before(run, current) if is_new and not shipped else None
    if unshipped is not None:
        return _judged(run, lambda r: _plan_unshipped(r, current, state, unshipped), None)
    if (shipped or is_new) and decide(_X, Event.SHIPPED).action is Action.START_NEXT:
        starting = next(iter(_startable(run, shipped)), None)
        return _judged(run, lambda r: _plan_start(r, current, state, shipped), starting)
    return _judged(run, lambda r: _plan_rules(r, current, state), current.title)


def dry_run_reprioritization(repo: str, *, ref: str | None, now: datetime) -> ReprioritizationPlan:
    """The plan a dry run returns, having made no request: no release read, so nothing to
    judge, and the requests a run on `repo` makes, in order (#412, #1125). `requests` are the
    reads, ending with the closing GraphQL budget read; `write_requests` the writes `--confirm`
    makes before that read."""
    from devops_cli.roadmap.request_plan import reprioritize_requests

    reads, writes = reprioritize_requests(repo, ref)
    return ReprioritizationPlan(
        repo=repo,
        now=now,
        current=None,
        state=None,
        dry_run=True,
        requests=reads,
        write_requests=writes,
    )


def _field_writes(decision: Decision) -> list[tuple[ItemField, str | None]]:
    """The fields a decision sets: the Release for a move, then Status for a stalled item."""
    status: list[tuple[ItemField, str | None]] = [(ItemField.STATUS, CONST_ROADMAP_STATUS_READY)]
    release: list[tuple[ItemField, str | None]] = [(ItemField.RELEASE, decision.target)]
    writes = {
        Action.TO_BACKLOG: release,
        Action.TO_NEXT: release,
        Action.PULL_IN: release,
        Action.READY: status,
        Action.READY_TO_NEXT: release + status,
    }
    return writes.get(decision.action, [])


def _admits(decision: Decision) -> bool:
    """Whether the decision's last write admits the item to its release: an admission, a pull
    in at a start, or a change that `admits` the fix it readies or nudges, once its comment is
    posted or while the item is still a critical fix."""
    joins = decision.admits and (decision.done or is_critical_fix(decision.item) or decision.joined)
    return joins or decision.action in (Action.ADMIT, Action.PULL_IN)


def _final_marks(
    decision: Decision, now: datetime, numbers: Mapping[str, int]
) -> dict[JobMark, str | None]:
    """The marks the last write of a decision sets: its `Admitted` or `Nudged` mark, its
    `Left` mark cleared when it places the item, as `_moved` counts it, an unproven Release
    included, and its `Pending` mark cleared.

    A decision that `admits` a fix it readies or nudges admits it once its comment is posted,
    or while the item is still a critical fix: one a person made anything else before its
    comment is then judged as a join, as an unannounced admission is. A move out of the
    release clears the item's `Admitted` mark, but not an unannounced one whose Release a
    person set back to that release since: the item stays as the release admitted it, as when
    no run saw it leave. Nor one the run that posted its comment found back there, as its
    `Pending` mark's `stays` keeps, while the item is still there."""
    marks: dict[JobMark, str | None] = {JobMark.PENDING: None}
    release = numbers.get(decision.release)
    announced = decision.done and not (decision.begun is not None and decision.begun.stays)
    if _admits(decision):
        marks[JobMark.ADMITTED] = str(release)
        if decision.joined:
            marks[JobMark.JOINED] = str(release)
    elif (
        decision.leaves
        and release is not None
        and admitted_to(decision.item) == release
        and (
            announced
            or _sets_release(decision, decision.by_person)
            or not in_release(decision.item.release, Version(decision.release))
        )
    ):
        marks[JobMark.ADMITTED] = None
        marks[JobMark.JOINED] = None
    if _sets_release(decision, decision.by_person) and decision.item.job_record.get(JobMark.LEFT):
        marks[JobMark.LEFT] = None
    if decision.action is Action.NUDGE:
        marks[JobMark.NUDGED] = now.isoformat()
    return marks


def _undone_before_comment(decision: Decision, numbers: Mapping[str, int]) -> bool:
    """Whether the decision moves the item out of the release it is admitted to, and finds it
    back there, its Release a person's, before posting its comment: the move was undone before
    anyone was told of it, so the item keeps its admission even if the run stops before its
    last write."""
    release = numbers.get(decision.release)
    back = in_release(decision.item.release, Version(decision.release))
    return (
        decision.leaves
        and release is not None
        and admitted_to(decision.item) == release
        and not _sets_release(decision, decision.by_person)
        and back
    )


def _settled(
    decision: Decision, now: datetime, numbers: Mapping[str, int], *, fields: bool = True
) -> Item:
    """The item as it will be once `decision` is finished, for the rest of the run to plan by;
    with `fields` False, only its marks are left to write. A field it leaves untouched keeps its
    value, and its record is what `_taken_back` gives it."""
    writes = (
        [w for w in _field_writes(decision) if w[0] not in decision.untouched] if fields else []
    )
    record: JobRecord = with_marks(decision.item.job_record, _final_marks(decision, now, numbers))
    for item_field, value in writes:
        record[item_field] = value
    _put_back(record, *_taken_back(decision))
    values = {item_field.name.lower(): value for item_field, value in writes}
    return decision.item.model_copy(update={**values, "job_record": record})


def _pending(store: RoadmapStore, decision: Decision, numbers: Mapping[str, int]) -> _Pending:
    """The decision as its `Pending` mark keeps it until it is finished: with how many comments
    with its text the item has, what the job record holds for the fields it writes, and, as
    each field it writes needs to be read again, when the item's Status last changed and how
    many times its issue has joined or left a Release."""
    item = decision.item
    writes = [item_field for item_field, _ in _field_writes(decision)]
    sets_status, sets_release = ItemField.STATUS in writes, ItemField.RELEASE in writes
    return _Pending(
        event=decision.event,
        action=decision.action,
        reason=decision.transition.reason,
        release=numbers[decision.release],
        target=numbers[decision.target] if decision.target is not None else None,
        target_title=decision.target,
        note=decision.note,
        admits=decision.admits,
        joined=decision.joined,
        comment=decision.comment,
        posted=store.comments_on(item.number).count(decision.comment),
        was_in=numbers.get(item.release) if item.release is not None else None,
        was=item.status,
        status_at=store.status_changed_at(item.number) if sets_status else None,
        moves=len(store.release_changes(item.number)) if sets_release else None,
        recorded={f: item.job_record[f] for f in writes if f in item.job_record},
    )


def _apply_decision(
    store: RoadmapStore, decision: Decision, now: datetime, numbers: Mapping[str, int]
) -> None:
    """Record the decision as pending; set its fields; comment; then set its marks and clear
    the pending mark.

    Each field joins the pending mark's begun fields in the job-record write that records its
    value, which the store makes before it sets the field, and its written fields in a
    job-record write once the field is set. A resumed decision skips the fields its pending
    mark records as written, which still hold its values, and leaves its untouched fields as
    they are, with the record `_taken_back` gives those it began; a `done` one, whose comment
    that run posted, only sets its marks, so the comment is posted once.
    """
    item = decision.item
    pending = decision.begun
    if pending is None:
        pending = _pending(store, decision, numbers)
        store.set_marks(item, {JobMark.PENDING: pending.model_dump_json()})
    if not decision.done:
        for item_field, value in _field_writes(decision):
            if item_field in pending.written or item_field in decision.untouched:
                continue
            pending = pending.begin(item_field)
            store.set_field(
                item, item_field, value, marks={JobMark.PENDING: pending.model_dump_json()}
            )
            pending = pending.confirm(item_field, store, item.number)
            store.set_marks(item, {JobMark.PENDING: pending.model_dump_json()})
        if _undone_before_comment(decision, numbers) and not pending.stays:
            pending = pending.model_copy(update={"stays": True})
            store.set_marks(item, {JobMark.PENDING: pending.model_dump_json()})
        store.comment(item.number, decision.comment)
    recorded, forgotten = _taken_back(decision)
    store.set_marks(
        item, _final_marks(decision, now, numbers), recorded=recorded, forgotten=forgotten
    )


def _taken_back(
    decision: Decision, *, dropped: bool = False
) -> tuple[dict[ItemField, str | None], frozenset[ItemField]]:
    """The record a resumed decision, finished or `dropped`, leaves for the fields it began
    and did not record as written: the values to record, and the fields to forget.

    One that changed since, which it leaves untouched, loses its record when nothing shows the
    field call never landed: the job may have set it, or a person, so its value counts as a
    person's from then on, as an item's place does when no job placed it. The record it had
    before the decision began would name the place a job had put the item in: the decision's
    own move out of there would read as a person taking it out, and a person putting it back
    there as the job's placement, which a start then pulls in again. One `unlanded`, whose
    issue's events show it never joined the decision's target, was set by a person only, and
    gets back the record it had when the decision began, on both paths: that record names the
    last place a job set, so an item a person moved out and back is still where a job placed
    it. One that has not changed since was never set: a finished decision sets it, which
    records it, and a dropped one gives it back the record it had when the decision began, or
    none when it had none, so no `Left` mark names a Release the item never reached.
    """
    pending = decision.begun
    if pending is None:
        return {}, frozenset()
    begun = [f for f in pending.begun if f not in pending.written]
    unknown = decision.untouched - decision.unlanded
    unset = (
        f for f in begun if (dropped and f not in decision.untouched) or f in decision.unlanded
    )
    recorded, forgotten = pending.restore(unset)
    return recorded, forgotten | {f for f in begun if f in unknown}


def _apply_revert(store: RoadmapStore, revert: Revert, replaced: bool) -> None:
    """Put back the fields a dropped change wrote, then, in one write, the record of the fields
    it began and can't show it set, and clear its `Pending` mark, unless a decision of this run
    about the item `replaced` it with its own."""
    for item_field, value in revert.undo:
        store.set_field(revert.item, item_field, value)
    marks: dict[JobMark, str | None] = {} if replaced else {JobMark.PENDING: None}
    if marks or revert.recorded or revert.forgotten:
        store.set_marks(revert.item, marks, recorded=revert.recorded, forgotten=revert.forgotten)


def _in_order(changes: Iterable[Decision]) -> list[Decision]:
    """The changes in the order they are made: each item's in plan order, an earlier run's
    first, and those of items a fix is admitted to last, by an admission or by a change that
    readies or nudges it and `admits` it."""
    listed = list(changes)
    late = {d.item.number for d in listed if (d.action is Action.ADMIT or d.admits) and not d.done}
    return sorted(listed, key=lambda d: d.item.number in late)


def apply_reprioritization(store: RoadmapStore, plan: ReprioritizationPlan) -> None:
    """Make the plan's writes: Releases and branches, then the changes it drops, then items one
    change at a time, then the admitted set, then the run record, and last the closes of the
    shipped releases. A first run names its release in the run record before its marks.

    Admissions come after every other change. The cap counts only the fixes a run admits, so
    the item a fix makes room for leaves before the fix is admitted: a run that stops between
    the two leaves the fix to the next run, which admits it with its room already made.
    """
    numbers = dict(plan.numbers)
    for write in plan.release_writes:
        if not write.last and (made := write.apply(store)) is not None:
            numbers[made.title] = made.number
    changed = {decision.item.number for decision in plan.changes}
    for revert in plan.reverts:
        _apply_revert(store, revert, revert.item.number in changed)
    if plan.opens_record and plan.record is not None:
        store.set_run_record({JobMark.STARTED: str(numbers[plan.record])})
    for decision in _in_order(plan.changes):
        _apply_decision(store, decision, plan.now, numbers)
    for item, marks in plan.marks(numbers).values():
        store.set_marks(item, marks)
    if plan.record is not None:
        size: dict[JobMark, str | None] = {JobMark.SIZE: str(plan.size)}
        started = {} if plan.first_run else {JobMark.STARTED: str(numbers[plan.record])}
        store.set_run_record({**started, **size})
    for write in plan.release_writes:
        if write.last:
            write.apply(store)


# ── The report ────────────────────────────────────────────────────────────────


def _numbers(items: Iterable[Item]) -> str:
    return ", ".join(f"#{item.number}" for item in items)


def _section(heading: str, lines: Sequence[str]) -> list[str]:
    return [heading, "", *lines, ""] if lines else []


def _record_lines(plan: ReprioritizationPlan) -> list[str]:
    messages = MESSAGES.roadmap
    lines = []
    # A fix a change readies or nudges is admitted by that change's last write.
    admitted = [
        *plan.admitted,
        *(
            d.item
            for d in plan.changes
            if d.admits and d.release == plan.admitted_release and _admits(d)
        ),
    ]
    if admitted:
        lines.append(
            messages.reprioritize_admits.format(
                release=plan.admitted_release,
                items=_numbers(sorted(admitted, key=lambda item: item.number)),
            )
        )
    if plan.released:
        lines.append(
            messages.reprioritize_cleared.format(
                items=_numbers(plan.released), release=plan.admitted_release
            )
        )
    released = {item.number for item in plan.released}
    lines += [
        (
            messages.reprioritize_left_backlog
            if title == CONST_ROADMAP_LEFT_BACKLOG
            else messages.reprioritize_left
        ).format(number=item.number, release=title)
        for item, title in plan.left
        if item.number not in released
    ]
    lines += [
        messages.reprioritize_kept_out.format(number=item.number, release=title)
        for item, title in plan.kept_out
    ]
    if plan.record is not None:
        lines.append(messages.reprioritize_run_record.format(release=plan.record, size=plan.size))
    return lines


def _headline(plan: ReprioritizationPlan) -> list[str]:
    """What kind of run this is: a release start, a first run, a hold, or none of them."""
    text = _headline_text(plan)
    return [text, ""] if text else []


def _headline_text(plan: ReprioritizationPlan) -> str | None:
    messages = MESSAGES.roadmap
    if plan.starting and plan.shipped:
        return messages.reprioritize_start.format(shipped=plan.shipped, starting=plan.starting)
    if plan.starting:
        return messages.reprioritize_start_after_close.format(starting=plan.starting)
    if plan.first_run and plan.shipped:
        return messages.reprioritize_first_run_at_ship.format(
            shipped=plan.shipped, release=plan.admitted_release
        )
    if plan.first_run:
        return messages.reprioritize_first_run.format(release=plan.admitted_release)
    if plan.unshipped:
        return messages.reprioritize_unshipped.format(release=plan.unshipped, current=plan.current)
    if plan.behind:
        return messages.reprioritize_behind.format(current=plan.current, started=plan.behind)
    return None


def render_plan(plan: ReprioritizationPlan) -> str:
    """The plan as Markdown: the current release, each change with its reason, and the records."""
    messages = MESSAGES.roadmap
    lines = [messages.reprioritize_title.format(repo=plan.repo), ""]
    if plan.current is None or plan.state is None:
        return "\n".join([*lines, messages.reprioritize_no_release]) + "\n"
    lines += [messages.reprioritize_current.format(release=plan.current, state=plan.state), ""]
    lines += _headline(plan)
    dropped = [
        (
            messages.reprioritize_dropped_line if r.text else messages.reprioritize_unreadable_line
        ).format(number=r.item.number, title=r.item.title, text=r.text)
        for r in plan.reverts
    ]
    changes = dropped + [
        (
            messages.reprioritize_resumed_line if d.resumed else messages.reprioritize_change_line
        ).format(number=d.item.number, title=d.item.title, text=d.text)
        for d in plan.changes
    ]
    lines += _section(
        messages.reprioritize_release_writes, [f"- {write.text}" for write in plan.release_writes]
    )
    lines += _section(messages.reprioritize_changes, changes)
    lines += _section(messages.reprioritize_records, _record_lines(plan))
    if not plan.has_writes and not plan.unshipped and not plan.behind:
        lines += [messages.reprioritize_nothing]
    return "\n".join(lines).rstrip() + "\n"


# ── When the job is due ───────────────────────────────────────────────────────

_ITEM_CHANGES = frozenset(
    {
        ChangeKind.JOINED_RELEASE,
        ChangeKind.LEFT_RELEASE,
        ChangeKind.LABELED,
        ChangeKind.UNLABELED,
        ChangeKind.CLOSED,
        ChangeKind.REOPENED,
        ChangeKind.BLOCKED_BY_ADDED,
        ChangeKind.BLOCKED_BY_REMOVED,
    }
)
_FIELD_CHANGES = frozenset({ItemField.STATUS, ItemField.PRIORITY})


def is_own_change(change: Change) -> bool:
    """Whether a job made the change: the value it left is the one the Item's job record holds
    (ADR 0002).

    An Item with a `Left` mark joining a Release is never a job's own change, even when a job
    last placed it there: a person moved it since, so its return is judged again. Nor is an
    Item that carries an `Admitted` mark leaving a Release, even for where a job last placed
    it: a job that moves an Item clears its `Left` mark and, out of the Release whose admitted
    set it is in, its `Admitted` mark with the move. The mark names that Release by milestone
    number, which a change does not carry, so an Item that leaves another Release with a mark
    left over counts too, and the run it starts finds nothing to do.
    """
    record = change.job_record
    if change.field is None or change.field not in record or record[change.field] != change.value:
        return False
    if change.kind is ChangeKind.JOINED_RELEASE:
        return not record.get(JobMark.LEFT)
    if change.kind is ChangeKind.LEFT_RELEASE:
        return not record.get(JobMark.ADMITTED)
    return True


def _triggers(change: Change) -> bool:
    if change.kind in RELEASE_CHANGE_KINDS:
        return True
    if change.release is None or is_own_change(change):
        return False
    if change.kind is ChangeKind.FIELD_CHANGED:
        return change.field in _FIELD_CHANGES
    return change.kind in _ITEM_CHANGES


def is_due(changes: Iterable[Change], now: datetime, last_stall_check: datetime | None) -> bool:
    """Whether reprioritization is due, from the changes since the last poll (#741, #752).

    It is due when a release starts, is cut, is un-cut or ships; when an item in a Release joins
    or leaves it, closes or reopens, or its Status, Priority, labels or blocked-by links change;
    and once a day for the stall check, counted from `last_stall_check`. A comment, an edit and
    a job's own change (one whose value matches the Item's job record) are not triggers. With
    no state to read, it can't tell the current release from a planned one, so a change to an
    item in any Release counts; a run that finds nothing to do writes nothing.
    """
    stall_check = timedelta(hours=DEFAULT_ROADMAP_STALL_CHECK_HOURS)
    if last_stall_check is None or now - last_stall_check >= stall_check:
        return True
    return any(_triggers(change) for change in changes)


__all__ = [
    "INHERITS",
    "TRANSITIONS",
    "Action",
    "Decision",
    "Event",
    "Reason",
    "ReleaseState",
    "ReleaseWrite",
    "ReprioritizationPlan",
    "Revert",
    "Transition",
    "admission_event",
    "admitted_to",
    "apply_reprioritization",
    "current_release",
    "decide",
    "dry_run_reprioritization",
    "is_critical_fix",
    "is_due",
    "is_own_change",
    "is_p0_feature",
    "is_started",
    "last_started",
    "placed_by_person",
    "plan_reprioritization",
    "release_state",
    "render_plan",
]

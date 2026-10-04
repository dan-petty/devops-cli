"""The release lifecycle as a Hypothesis state machine over the in-memory roadmap store (#740).

Each rule is one thing that happens to the roadmap: a person places, files, starts, blocks,
labels, links, closes, reopens or moves an item back to Ready, renames the open releases, the
release is cut, un-cut or ships (or merges with `release.yml` failing to publish it, and is
published later), a day passes, or the job's next run stops part-way, at any of its gh calls: a
field write is GitHub's two, the job record and then the field. The job first runs either
with the first release under way, or once it has shipped. After it, the machine polls the
store's changes as the service will (#752), and runs reprioritization when `is_due` says so. A
run that stops part-way is run again, as the command says to: at once, or at the next poll, so
a person can act in between. One that stops at its last write, the close of a shipped milestone,
has made every other, so the run after it is a run of its own, checked as one. Every invariant
is checked after every step, and each one's message starts with the CONTEXT.md term it
enforces; while a stopped run waits for the next poll, the roadmap is half-changed, and only
the checks of a finished run apply.

The machine keeps its own record of what happened: when the job first ran, when a release
shipped and so when the next one started, who last placed each item, the release's size when
it started, which items it held then, open or closed, and which joined it after the start,
with what they were then. It never asks the job, its plan or its marks whether a release
started or who placed an item.

`DEVOPS_PROPERTY_PROFILE=deep` runs a deeper sweep on demand; Hypothesis's own profiles can't
deepen a test whose settings are set here, and loading one would change every other property
test.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from hypothesis import Phase, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    initialize,
    invariant,
    multiple,
    precondition,
    rule,
    run_state_machine_as_test,
)
from packaging.version import Version

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap import reprioritize
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.reprioritize import Event, ReleaseState, is_due
from devops_cli.roadmap.store import CloseReason, GitHubState, Item, ItemField, JobMark
from tests.roadmap_faults import FIELD, RECORD, Fault, StoppingStore

CONTEXT = Path(__file__).resolve().parent.parent / "CONTEXT.md"

OPTIONS = {
    ItemField.STATUS: ("New", "Ready", "In Progress", "In Review", "Done", "Blocked"),
    ItemField.PRIORITY: ("P0-Critical", "P1-High", "P2-Medium", "P3-Low"),
    ItemField.VALUE: ("High", "Medium", "Low"),
    ItemField.EFFORT: ("Low", "Medium", "High"),
}
CAP = 3
STALL_DAYS = 14
CONFIG = RoadmapConfig(board=1, release_cap=CAP, planning_horizon=2, stall_days=STALL_DAYS)
REPO = "example/roadmap"
START = datetime(2026, 10, 2, tzinfo=UTC)
STARTED = frozenset({"In Progress", "In Review", "Done"})
# What a person files: its type label and Priority.
KINDS = {
    "bug": ("type/bug", "P0-Critical"),
    "security": ("type/security", "P0-Critical"),
    "p0_feature": ("type/feature", "P0-Critical"),
    "feature": ("type/feature", "P2-Medium"),
}
PLACES = ("current", "next", "later", "backlog")
MOVES_ON = ("In Progress", "In Review", "Blocked", "needs-split", "closes")
REOPENS = ("Ready", "In Progress")
PERSON, JOB = "person", "job"
# A run's last write, when a release has shipped with its milestone open.
CLOSE = "close_release"
ALICE = "alice"
JUDGED = (ItemField.STATUS, ItemField.RELEASE)

INVARIANTS = MappingProxyType(
    {
        "admitted": (
            "Current release: after the release starts, every item in it is in the admitted "
            "set, and every item admitted after the start is a critical fix."
        ),
        "first_run": (
            "Current release: on the first run, the release admits whatever is already in it."
        ),
        "size": (
            "Current release: after the release starts, while its size is above the larger of "
            "the cap and its size at start, every unstarted item in it is an admitted critical "
            "fix."
        ),
        "cut": "Cut: after the cut, nothing joins until the release is un-cut.",
        "ship": "Ship: once the current release ships, the release after it starts.",
        "descope": "Descope: descoping touches only items that have not started.",
        "stalled": (
            "Stalled: the job sets an item back to Ready only once it has had no status change "
            "for the stall window."
        ),
        "blocked": "Blocked: no Blocked item is in a release at the moment it starts.",
        "held": (
            "Current release: once it has started, the job sends no item of its admitted set "
            "to the backlog, and moves none in review or done out of it."
        ),
        "placement": (
            "Reprioritization: the job never moves an item that a person placed in the backlog "
            "or in a later planned release into the current release."
        ),
        "stands": (
            "Reprioritization: the job never moves an item a person placed in the backlog or "
            "in a planned release, until that release starts."
        ),
        "reason": (
            "Reprioritization: the job moves an item a person placed in the current release "
            "only through admission, the cut lock, trimming at start or descoping, always with "
            "a reason comment."
        ),
        "fields": "Reprioritization: the job never changes priority, Value or Effort.",
        "pulled": (
            "Reprioritization: a start that leaves its release below the cap has pulled in every "
            "Ready item in the backlog or the later planned release that no person placed there."
        ),
        "finished": (
            "Reprioritization: a change the job begins is finished, with its reason comment, by "
            "the run that begins it or by the next one."
        ),
    }
)

_DEEP = os.environ.get("DEVOPS_PROPERTY_PROFILE") == "deep"
_GATE_EXAMPLES, _GATE_STEPS = 12, 8
# derandomize implies database=None; the shrink phase is kept.
SETTINGS = settings(
    derandomize=True,
    deadline=None,
    max_examples=300 if _DEEP else _GATE_EXAMPLES,
    stateful_step_count=30 if _DEEP else _GATE_STEPS,
    phases=(Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink),
)
# The deep sweep's search for the failure the cut lock's absence causes, which it shrinks to its
# minimal sequence. Short sequences keep the shrink within Hypothesis's limit on shrinks.
CUT_LOCK_SETTINGS = settings(SETTINGS, stateful_step_count=_GATE_STEPS, report_multiple_bugs=False)


def critical(item: Item) -> bool:
    """A critical fix as CONTEXT.md defines it: P0 and a defect or a security advisory."""
    return item.priority == "P0-Critical" and bool({"type/bug", "type/security"} & set(item.labels))


def descoped_by(seen: RunSeen) -> list[tuple[Item, Item]]:
    """The items a run moved out of the release it held into a later planned release, as they
    were before and after it: the admitted items of the current release, or any item of the
    release that started."""
    source = seen.current_after if seen.started else seen.current_before
    return [
        (seen.before[number], item)
        for number, item in seen.after.items()
        if seen.before[number].release == source
        and item.release in seen.later_before
        and item.release != seen.current_after
        and (seen.started or number in seen.admitted_before)
    ]


@dataclass(frozen=True)
class Window:
    """From a run that stopped until the run that finishes it: the roadmap before the stopped
    run, its comments, where its job writes begin, and when it began."""

    before: dict[int, Item]
    comments: dict[int, int]
    writes: int
    since: datetime


@dataclass(frozen=True)
class RunSeen:
    """What one job run changed, as the machine saw it. A run that finishes what a stopped one
    began also carries that one's `window`: the roadmap before it, the Status and Release
    writes the job made since (`job_fields`), and those a person made (`person_fields`).
    `readied` are the items this run, and not a run that stopped before it, set to Ready.
    `shipped_all` are the releases that shipped since the last run that finished, `shipped`
    the last of them."""

    now: datetime
    before: dict[int, Item]
    after: dict[int, Item]
    comments_before: dict[int, int]
    comments_after: dict[int, int]
    current_before: str
    current_after: str
    later_before: tuple[str, ...]
    placed_before: dict[int, str]
    admitted_before: frozenset[int]
    first_run: bool
    started: bool
    shipped: str | None
    under_way: str
    cut: bool
    window: Window
    job_fields: frozenset[tuple[int, ItemField]]
    person_fields: frozenset[tuple[int, ItemField]]
    readied: frozenset[int]
    shipped_all: tuple[str, ...] = ()

    def was(self, number: int) -> Item:
        """The item before the window, or, filed since, before this run."""
        return self.window.before.get(number, self.before[number])

    def from_shipped(self, number: int) -> bool:
        """Whether the item was in a release whose ship this run follows: a descope or a cut
        lock move out of it that a run stopped before the ship began, which this run finishes,
        into the next release, which may have shipped too while that run waited."""
        shipped = (self.shipped, *self.shipped_all)
        return self.shipped is not None and self.before[number].release in shipped

    def commented(self, number: int) -> bool:
        """Whether the item has a comment it had not before the window."""
        had = self.window.comments.get(number, self.comments_before.get(number, 0))
        return self.comments_after[number] > had


class RoadmapLifecycle(RuleBasedStateMachine):
    """The roadmap of one repository, with a person, the calendar and the reprioritization job."""

    items = Bundle("items")

    def __init__(self) -> None:
        super().__init__()
        self.now = START
        self.store = InMemoryRoadmapStore(board_options=OPTIONS, clock=lambda: self.now)
        self.person = self.store.as_actor("alice")
        for title in ("v1.0.0", "v1.0.1", "v1.0.2"):
            self.store.create_release(title)
        self.polled = START
        self.last_stall_check: datetime | None = None
        # The release pull request while it is open, and once merged until it is published.
        self.release_pr: int | None = None
        self.merged_pr: int | None = None
        self.cut_release: str | None = None
        # The machine's own record: whether the job has run, the release that shipped since
        # its last run, the release that started, and that release's admitted set.
        self.ran = False
        self.shipped: str | None = None
        self.shipped_all: list[str] = []
        self.started: str | None = None
        self.size_at_start = 0
        self.admitted: set[int] = set()
        self.fixes: set[int] = set()
        self.admitted_after_start: dict[int, bool] = {}
        # Items a person took out of the started release that no poll has seen out yet, with
        # whether each was a fix and joined after the start: putting one back before then is
        # no join, since the job can't tell it ever left.
        self.unseen_exits: dict[int, tuple[bool, bool | None]] = {}
        # Likewise, items a person moved that no run has recorded since, with who had placed
        # each and where it was then: moving one back there before then is no placement the job
        # can see, since it reads state, not the change feed (ADR 0003).
        self.unseen_moves: dict[int, tuple[str | None, str | None]] = {}
        # Of those, the items whose job record a run that stopped since wrote: it may have
        # recorded the exit, so a move back may read as the person's.
        self.touched: set[int] = set()
        self.placed_by: dict[int, str] = {}
        # Items whose place the job no longer claims as one a job set, until a job sets it
        # again: the windows the job's module accepts (`unclaimed`). And the Release writes a run
        # that waits to be run again began, and whose milestone call never landed, by item, with
        # the place each was to set.
        self.unclaimed: set[int] = set()
        self.begun_release: dict[int, str | None] = {}
        self.activity: dict[int, datetime] = {}
        self.stops_at = 0
        self.rerun_now = True
        # The write each run that stopped stopped at, by name, as GitHub's calls are named.
        self.stops: list[str] = []
        # A run that stopped and waits for the next poll to run it again.
        self.outstanding: Window | None = None
        # A run that stopped at its last write, the close of the shipped milestone, made every
        # other: the start, or the first run, is done, and the run after it holds the release
        # under way to the rules and closes the shipped one.
        self.closing = False
        self.last_run: RunSeen | None = None
        self.view: dict[int, Item] = {}
        self.open_titles: list[str] = []
        self.titles: dict[str, str] = {}
        self.refresh()

    # ── The roadmap as it stands ──

    def refresh(self) -> None:
        """Read the roadmap once per step: its items and its open releases."""
        self.view = self.snapshot()
        releases = self.store.releases()
        self.open_titles = [r.title for r in releases if r.state is GitHubState.OPEN]
        self.titles = {str(r.number): r.title for r in releases}

    def current(self) -> str:
        return self.open_titles[0]

    def under_way(self) -> str:
        """The release under way: the current one, or, while a shipped release's milestone is
        still open, the release after it, which the run that waits to be run again starts, or
        has started but for that close."""
        return self.after(self.shipped) if self.shipped else self.current()

    def snapshot(self) -> dict[int, Item]:
        return {item.number: item for item in self.store.items()}

    def comment_counts(self, items: dict[int, Item]) -> dict[int, int]:
        return {number: len(self.store.comments_on(number)) for number in items}

    def members(
        self, release: str, items: dict[int, Item] | None = None, *, closed: bool = False
    ) -> list[Item]:
        """The open items of `release`, and its closed ones with `closed`, in `items` or in
        this step's view."""
        return [
            item
            for item in (self.view if items is None else items).values()
            if (closed or item.state is GitHubState.OPEN) and item.release == release
        ]

    def titled(self, mark: str | None) -> str | None:
        """The title of the Release a mark names by its milestone number; any other mark as
        it is."""
        return self.titles.get(mark or "", mark)

    def mark_names(self, item: Item, mark: JobMark, title: str) -> bool:
        """Whether the item's `mark` names the Release titled `title`."""
        return self.titled(item.job_record.get(mark)) == title

    # ── What a person does ──

    def file(self, title: str, kind: str, status: str, release: str | None) -> int:
        label, priority = KINDS[kind]
        number = self.store.seed_issue(title, labels=(label,), on_board=True)
        for board_field, value in ((ItemField.STATUS, status), (ItemField.PRIORITY, priority)):
            self.person.set_field(self.store.item(number), board_field, value)  # type: ignore[arg-type]
        if release is not None:
            self.person.set_field(self.store.item(number), ItemField.RELEASE, release)  # type: ignore[arg-type]
            self.placed_by[number] = PERSON
        self.activity[number] = self.now
        return number

    def open_item(self, number: int) -> Item | None:
        item = self.store.item(number)
        return item if item is not None and item.state is GitHubState.OPEN else None

    # ── The poll and the job ──

    def poll(self) -> None:
        """Read the changes since the last poll, and run the job when it is due, or when a run
        stopped part-way and waits to be run again, its close of the shipped milestone included."""
        self.now += timedelta(seconds=10)
        changes = self.store.changes_since(self.polled)
        self.polled = self.now
        self.last_run = None
        waiting = self.outstanding is not None or self.closing
        if waiting or is_due(changes, self.now, self.last_stall_check):
            self.run_job()
        else:
            self.refresh()
        if self.outstanding is None:
            self.unseen_exits.clear()
            self.unseen_moves.clear()
            self.touched.clear()
            self.begun_release.clear()
        # What a person does next comes after the job's writes, as on GitHub, so its Status
        # clock tells the two apart.
        self.now += timedelta(seconds=1)

    def after(self, shipped: str) -> str:
        """The open release after `shipped`, the one that started when it shipped."""
        version = Version(shipped)
        return next(title for title in self.open_titles if Version(title) > version)

    def apply_job(self, position: int, rerun_now: bool) -> bool:
        """One run, stopping at its write `position`, if it has one, a field write being
        GitHub's two calls; then run again at once, as the command says, unless the rerun waits
        for the next poll, or the run stopped at its last write, the close of the shipped
        milestone, which leaves a run of its own. False when it stopped and was not run again."""
        plan = reprioritize.plan_reprioritization(
            self.store, repo=REPO, config=CONFIG, now=self.now
        )
        stopping = StoppingStore(self.store, Fault(position))
        made = len(self.store.job_writes())
        try:
            reprioritize.apply_reprioritization(stopping.as_store(), plan)
        except GitHubOperationError:
            self.stops.append(stopping.writes[-1])
            self.claimed(made, stopping.writes)
            if not rerun_now or self.stops[-1] == CLOSE:
                return False
            made = len(self.store.job_writes())
            plan = reprioritize.plan_reprioritization(
                self.store, repo=REPO, config=CONFIG, now=self.now
            )
            reprioritize.apply_reprioritization(self.store, plan)
        self.claimed(made, [])
        return True

    def claimed(self, made: int, calls: Sequence[str]) -> None:
        """Keep whose places the job's writes since its write `made` claim, from the gh calls
        a run made (`calls`, ending at the one that failed, if any).

        A Release field call that lands claims the item's place, as one a job set; a run that
        stopped at the written mark right after it leaves nothing to show the job made it, so
        the rerun finishes the move as it stands and drops the record: the item's place is no
        longer the job's (`unclaimed`), as for an item no job placed. A run that stopped at the
        field call has begun that write, and it waits with the place it was to set."""
        writes = self.store.job_writes()[made:]
        release = ItemField.RELEASE.value
        placing = [
            w
            for w in writes
            if w.key == release
            and w.number is not None
            and w.operation in ("record_field", "set_field")
        ]
        for write in placing:
            if write.operation == "set_field" and write.number is not None:
                self.unclaimed.discard(write.number)
                self.begun_release.pop(write.number, None)
        last = placing[-1] if placing else None
        if last is None or last.number is None:
            return
        if list(calls[-1:]) == [FIELD] and last.operation == "record_field":
            self.begun_release[last.number] = last.value
        elif list(calls[-2:]) == [FIELD, "set_marks"] and last.operation == "set_field":
            self.unclaimed.add(last.number)

    def run_job(self) -> None:
        """Run the job on the roadmap as the person left it, and keep what it did.

        A first run records the release under way, even right after a ship; any later run
        after a ship starts the release after the shipped one. A run that stops and waits for
        the next poll changes none of that, only who last placed the items it moved. A run that
        stops at its last write, the close of the shipped milestone, has made every other, so
        it is done but for the close: the run after it, at once or at the next poll, holds the
        release under way to the rules, and closes the shipped one, unless the release it
        started has shipped since too: then it starts the release after that one.
        """
        self.refresh()
        before, closing, under_way = self.view, self.closing, self.under_way()
        anew = closing and self.started != under_way
        current_before = under_way if closing and not anew else self.current()
        later = tuple(self.open_titles[self.open_titles.index(current_before) + 1 :])
        comments_before = self.comment_counts(before)
        window = self.outstanding or Window(
            before, comments_before, len(self.store.job_writes()), self.now
        )
        seen_before = (dict(self.placed_by), frozenset(self.admitted))
        first_run, shipped, shipped_all = not self.ran, self.shipped, tuple(self.shipped_all)
        cut = self.release_pr is not None or self.merged_pr is not None
        position, self.stops_at = self.stops_at, 0
        rerun_now, self.rerun_now = self.rerun_now, True
        own = len(self.store.job_writes())
        finished = self.apply_job(position, rerun_now)
        self.refresh()
        left_to_close = not finished and self.stops[-1] == CLOSE
        if not finished and not left_to_close:
            # The items filed since the window began, as this run found them.
            self.outstanding = replace(
                window,
                before={**before, **window.before},
                comments={**comments_before, **window.comments},
            )
            self.touched |= {
                w.number
                for w in self.store.job_writes()[own:]
                if w.number in self.unseen_moves
                and w.operation in ("set_mark", "record_field", "forget_field")
            }
            self.remember_stopped(before, comments_before)
            return
        self.outstanding = None
        self.ran, self.closing = True, left_to_close
        if not left_to_close:
            self.shipped = None
            self.shipped_all.clear()
        self.last_stall_check = self.now
        writes = self.store.job_writes()[window.writes :]
        changes = self.store.changes_since(window.since)
        seen = RunSeen(
            self.now,
            before,
            self.view,
            comments_before,
            self.comment_counts(self.view),
            current_before,
            self.under_way(),
            later,
            *seen_before,
            first_run,
            shipped is not None and not first_run and (not closing or anew),
            shipped,
            under_way,
            cut,
            window,
            frozenset(
                (w.number, ItemField(w.key))
                for w in writes
                if w.operation == "set_field" and w.number is not None and w.key
            ),
            frozenset(
                (c.number, c.field) for c in changes if c.actor == ALICE and c.field is not None
            ),
            frozenset(
                w.number
                for w in self.store.job_writes()[own:]
                if w.operation == "set_field"
                and w.number is not None
                and (w.key, w.value) == (ItemField.STATUS.value, "Ready")
            ),
            shipped_all,
        )
        self.last_run = seen
        self.remember(seen)
        if left_to_close and rerun_now:
            # The run is one of its own, so its checks come before the rerun's.
            for check in self.invariants:
                check.function(self)
            self.run_job()

    def remember_stopped(self, before: dict[int, Item], comments_before: dict[int, int]) -> None:
        """Keep what a run that stopped did: who last placed the items it moved, the items it
        announced it admitted, and those it announced it moved out. An item that joined the
        started release and got the job's comment while it stayed there was admitted then, as it
        was before the run, even though the run stopped before its mark; one a run since the
        window began moved out of the release, with its comment posted by this one, left the
        admitted set then. While the shipped release's milestone waits to be closed, the started
        release is the one under way."""
        for number, item in self.view.items():
            if item.release != before[number].release:
                self.placed_by[number] = JOB
                self.unseen_moves.pop(number, None)
        if not self.ran or self.started != self.under_way():
            return
        comments = self.comment_counts(self.view)
        began = self.outstanding.before if self.outstanding is not None else before
        # An admitted item a stopped run moved out, its comment posted by this one, has left
        # the set: the rerun only finishes its marks, wherever a person puts it in between.
        for number, item in self.view.items():
            was = began.get(number)
            commented = comments[number] > comments_before.get(number, 0)
            if was is not None and commented and was.release == self.started != item.release:
                self.admitted.discard(number)
                self.fixes.discard(number)
                self.admitted_after_start.pop(number, None)
                self.unseen_exits.pop(number, None)
        for item in self.members(self.under_way()):
            number = item.number
            if number not in self.admitted and comments[number] > comments_before.get(number, 0):
                fix = critical(before.get(number, item))
                self.admitted.add(number)
                self.admitted_after_start[number] = fix
                if fix:
                    self.fixes.add(number)

    def remember(self, seen: RunSeen) -> None:
        """Keep what the run did: its placements, the release's start, and what it admitted.

        The admitted set is the items the release held when it started, open or closed, and
        the items that joined it since; it loses only those that leave the release.
        """
        for number, item in seen.after.items():
            if item.release != seen.before[number].release:
                self.placed_by[number] = JOB
        if seen.first_run or seen.started:
            self.started = seen.under_way
            held = self.members(self.started, seen.after, closed=True)
            self.size_at_start = sum(item.state is GitHubState.OPEN for item in held)
            self.admitted = {item.number for item in held}
            self.fixes = {item.number for item in held if critical(item)}
            self.admitted_after_start = {}
            return
        members = {
            item.number for item in self.members(seen.current_after, seen.after, closed=True)
        }
        for number in self.admitted - members:
            self.admitted.discard(number)
            self.fixes.discard(number)
            self.admitted_after_start.pop(number, None)
        opened = {item.number for item in self.members(seen.current_after, seen.after)}
        for number in sorted(opened - self.admitted):
            fix = critical(seen.before[number])
            self.admitted.add(number)
            self.admitted_after_start[number] = fix
            if fix:
                self.fixes.add(number)

    # ── Rules ──

    @initialize(
        target=items,
        held=st.lists(
            st.sampled_from(("Ready", "In Progress", "New", "Blocked")), max_size=CAP + 1
        ),
        waiting=st.lists(st.sampled_from(("feature", "p0_feature")), max_size=2),
        stops_at=st.integers(0, CAP + 2),
        shipped=st.sampled_from((None, None, False, True)),
    )
    def start(
        self, held: list[str], waiting: list[str], stops_at: int = 0, shipped: bool | None = None
    ) -> object:
        """The release under way holds `held` features when the job first runs, and the backlog
        holds a Ready item of each kind in `waiting`, which a person may add to a release. The
        first run stops at its write `stops_at`, unless that is 0.

        With `shipped` set, v1.0.0 shipped before the job ever ran, with `release.yml` closing
        its milestone (True) or failing to (False), and v1.0.1 is under way.
        """
        under_way = "v1.0.0" if shipped is None else "v1.0.1"
        numbers = [self.file(f"held {n}", "feature", s, under_way) for n, s in enumerate(held)]
        numbers += [self.file(f"waiting {n}", k, "Ready", None) for n, k in enumerate(waiting)]
        if shipped is not None:
            self.cut_release = "v1.0.0"
            self.ship_pull_request(self.open_release_pull_request(draft=False))
            self.published(shipped, poll=False)
        self.stops_at = stops_at
        self.poll()
        return multiple(*numbers)

    @rule(at=st.integers(1, 16), later=st.booleans())
    def next_run_stops(self, at: int, later: bool = False) -> None:
        """A gh write fails part-way through the job's next run: its write `at`, if it has one.
        With `later`, the run is run again at the next poll, after whatever a person does in
        between, not at once."""
        self.stops_at, self.rerun_now = at, not later

    @rule(
        target=items,
        kind=st.sampled_from(("bug", "security")),
        status=st.sampled_from(("New", "Ready")),
    )
    def critical_fix_filed(self, kind: str, status: str) -> int:
        """A person files a critical fix straight into the release under way."""
        number = self.file(f"filed {kind}", kind, status, self.under_way())
        self.poll()
        return number

    @rule(item=items, place=st.sampled_from(PLACES))
    def person_places(self, item: int, place: str) -> None:
        """A person moves an item, open or closed, to the current release, a planned one, or
        the backlog.

        Putting an item where it already is changes nothing, on GitHub or here. An item taken
        out of the started release leaves its admitted set then: a return is a new join. Only
        a poll sees the exit, though: one put back while a stopped run waits to be run again
        is back in the set, since no run has seen it out. Likewise an item a person puts back
        where it was before such a run read it out is placed as it was then, by whoever had
        placed it: the job never recorded the exit, and its place is the one a job set.
        """
        found, releases = self.store.item(item), self.open_titles
        index = PLACES.index(place)
        if found is not None and (place == "backlog" or index < len(releases)):
            target = None if place == "backlog" else releases[index]
            self.person.set_field(found, ItemField.RELEASE, target)
            if target != found.release:
                self.placed(item, found.release, target)
                aim = self.begun_release.get(item, "")
                if self.outstanding is not None and aim in (None, target):
                    self.unclaimed.add(item)
            if found.release == self.started != target and item in self.admitted:
                self.unseen_exits[item] = (item in self.fixes, self.admitted_after_start.get(item))
                self.admitted.discard(item)
                self.fixes.discard(item)
                self.admitted_after_start.pop(item, None)
            elif target == self.started != found.release and item in self.unseen_exits:
                fix, after_start = self.unseen_exits.pop(item)
                self.admitted.add(item)
                if fix:
                    self.fixes.add(item)
                if after_start is not None:
                    self.admitted_after_start[item] = after_start
        self.poll()

    def placed(self, item: int, was: str | None, target: str | None) -> None:
        """A person moved the item from `was` to `target`: theirs, unless no run has recorded
        it out of where it was before, and `target` is that place.

        An item no one placed, moved out of the backlog and back, is the person's all the same:
        a start reads its issue's events, which show it left a Release. One a run that stopped
        since may have recorded out, having written its job record, may read either way, so
        the job no longer claims its place."""
        placer, where = self.unseen_moves.setdefault(item, (self.placed_by.get(item), was))
        if target != where:
            self.placed_by[item] = PERSON
            return
        del self.unseen_moves[item]
        self.placed_by[item] = placer or PERSON
        if item in self.touched:
            self.touched.discard(item)
            self.unclaimed.add(item)

    @rule(item=items, priority=st.sampled_from(OPTIONS[ItemField.PRIORITY]))
    def person_reprioritizes(self, item: int, priority: str) -> None:
        found = self.open_item(item)
        if found is not None:
            self.person.set_field(found, ItemField.PRIORITY, priority)
        self.poll()

    @rule(item=items, change=st.sampled_from(MOVES_ON))
    def item_moves_on(self, item: int, change: str) -> None:
        """An item starts, goes into review, becomes Blocked, is labeled needs-split or closes."""
        found = self.open_item(item)
        if found is not None and change == "closes":
            self.person.set_field(found, ItemField.STATUS, "Done")
            self.person.close_issue(item, CloseReason.COMPLETED, "Delivered.")
        elif found is not None and change == "needs-split":
            self.person.add_label(item, "needs-split")
        elif found is not None:
            self.person.set_field(found, ItemField.STATUS, change)
            self.activity[item] = self.now
        self.poll()

    @rule(item=items, status=st.sampled_from(REOPENS))
    def item_reopens(self, item: int, status: str) -> None:
        """A person reopens a closed item where it is, and sets it Ready or In Progress."""
        found = self.store.item(item)
        if found is not None and found.state is GitHubState.CLOSED:
            self.person.reopen_issue(item)
            self.person.set_field(found, ItemField.STATUS, status)
            self.activity[item] = self.now
        self.poll()

    @precondition(lambda self: self.shipped is None)
    @rule()
    def releases_renamed(self) -> None:
        """A person renames every open release to the next minor line, the highest first.

        GitHub keeps a milestone, with its issues and pull requests, by its number, so the
        release that started is the same one under its new title. A person renames no release
        that has shipped and is not yet closed: its GitHub Release keeps the old tag.
        """
        renamed: dict[str | None, str] = {}
        for title in reversed(self.open_titles):
            version = Version(title)
            new = f"v{version.major}.{version.minor + 1}.{version.micro}"
            self.person.edit_release(title, title=new)
            renamed[title] = new
        self.started = renamed.get(self.started, self.started)
        self.cut_release = renamed.get(self.cut_release, self.cut_release)
        self.unseen_moves = {
            number: (placer, renamed.get(where, where))
            for number, (placer, where) in self.unseen_moves.items()
        }
        self.begun_release = {
            number: renamed.get(aim, aim) for number, aim in self.begun_release.items()
        }
        # The job records the Release it set by its title, which the rename changes: an item it
        # placed in a renamed release reads as a person's from then on.
        self.unclaimed |= {
            number
            for number, item in self.view.items()
            if item.release in renamed and self.placed_by.get(number) == JOB
        }
        if self.outstanding is not None:
            before = {
                number: item.model_copy(update={"release": renamed.get(item.release, item.release)})
                for number, item in self.outstanding.before.items()
            }
            self.outstanding = replace(self.outstanding, before=before)
        self.poll()

    @rule(item=items)
    def item_goes_back_to_ready(self, item: int) -> None:
        """A person moves an item back to Ready, as from In Progress once a fix has joined."""
        found = self.open_item(item)
        if found is not None:
            self.person.set_field(found, ItemField.STATUS, "Ready")
        self.poll()

    @rule(item=items, on=items)
    def dependency_added(self, item: int, on: int) -> None:
        """A person adds a blocked-by link: `item` waits on `on`."""
        if item != on:
            self.person.link_dependency(item, on)
        self.poll()

    @rule(days=st.integers(1, STALL_DAYS + 1))
    def days_pass(self, days: int) -> None:
        """The clock moves on, which is how an item stalls."""
        self.now += timedelta(days=days)
        self.poll()

    @precondition(
        lambda self: (
            self.release_pr is None
            and self.merged_pr is None
            and self.under_way() != self.open_titles[-1]
        )
    )
    @rule(draft=st.booleans())
    def cut(self, draft: bool) -> None:
        """A person opens the release pull request, which cuts the release under way.

        A person cuts a release only while another is planned, so one is current once it ships,
        and never a release that has shipped, though its milestone is open while the run that
        starts the next one waits to be run again.
        """
        self.cut_release = self.under_way()
        self.release_pr = self.open_release_pull_request(draft=draft)
        self.poll()

    def open_release_pull_request(self, *, draft: bool) -> int:
        assert self.cut_release is not None
        return self.person.open_pull_request(
            f"feat(release): {self.cut_release}",
            base="main",
            head=f"chore/cut-{self.cut_release}",
            labels=("release",),
            release=self.cut_release,
            draft=draft,
        )

    def ship_pull_request(self, number: int) -> None:
        self.person.close_pull_request(number, merged=True)

    @precondition(lambda self: self.release_pr is not None)
    @rule()
    def uncut(self) -> None:
        """A person closes the release pull request without merging it."""
        assert self.release_pr is not None
        self.person.close_pull_request(self.release_pr)
        self.release_pr = None
        self.poll()

    def published(self, milestone_closed: bool, *, poll: bool = True) -> None:
        """GitHub Release vX.Y.Z is published, so the release ships; `release.yml` then closes
        the milestone, and carries on when that fails."""
        assert self.cut_release is not None
        self.person.publish_release(self.cut_release)
        if milestone_closed:
            self.person.close_release(self.cut_release)
        self.shipped, self.merged_pr = self.cut_release, None
        self.shipped_all.append(self.cut_release)
        if poll:
            self.poll()

    @precondition(lambda self: self.release_pr is not None or self.merged_pr is not None)
    @rule(milestone_closed=st.booleans(), published=st.booleans())
    def ship(self, milestone_closed: bool, published: bool = True) -> None:
        """The release pull request merges, and GitHub Release vX.Y.Z is published. Unless
        `published`, `release.yml` fails to publish it, and the release stays cut until a person
        publishes it by hand: a later `ship` once the pull request has merged."""
        if self.release_pr is not None:
            self.ship_pull_request(self.release_pr)
            self.merged_pr, self.release_pr = self.release_pr, None
        if published:
            self.published(milestone_closed)
        else:
            self.poll()

    # ── Invariants ──

    @invariant()
    def admitted_set_holds_the_release(self) -> None:
        current = self.current()
        if self.started != current or self.outstanding is not None:
            return
        members = self.members(current)
        assert all(self.mark_names(item, JobMark.ADMITTED, current) for item in members) and all(
            self.admitted_after_start.values()
        ), INVARIANTS["admitted"]

    @invariant()
    def first_run_admits_what_is_there(self) -> None:
        """A first run right after a ship admits what the release under way holds, whether
        `release.yml` closed the shipped milestone or not."""
        seen = self.last_run
        if seen is None or not seen.first_run:
            return
        held = {item.number for item in self.members(seen.under_way, seen.before, closed=True)}
        admitted = {
            item.number
            for item in seen.after.values()
            if self.mark_names(item, JobMark.ADMITTED, seen.under_way)
        }
        moved = [n for n, item in seen.after.items() if item.release != seen.before[n].release]
        assert (admitted, moved) == (held, []), INVARIANTS["first_run"]

    @invariant()
    def size_beyond_the_cap_is_only_critical_fixes(self) -> None:
        """Checked after each run. A person setting an item's Status back to the value the job
        last set reads as the job's own change, which is no trigger (ADR 0002), so the job sees
        that item back in Ready at its next run, at the latest the next day's stall check."""
        current = self.current()
        members = self.members(current)
        if self.last_run is None or self.started != current:
            return
        if len(members) <= max(CAP, self.size_at_start):
            return
        assert all(
            item.status in STARTED
            or (item.number in self.admitted and (item.number in self.fixes or critical(item)))
            for item in members
        ), INVARIANTS["size"]

    @invariant()
    def nothing_joins_a_cut_release(self) -> None:
        """A first run admits whatever is already in the release, cut or not, and so does a
        start, but the start of a release a person cut before it pulls nothing in: it moves no
        item into it but those it finishes moving out of a shipped release."""
        seen = self.last_run
        if seen is None or not seen.cut or seen.first_run:
            return
        if seen.started:
            starting = seen.under_way
            pulled = [
                number
                for number, item in seen.after.items()
                if self.cut_release == starting
                and item.release == starting
                and seen.before[number].release != starting
                and not seen.from_shipped(number)
            ]
            assert pulled == [], INVARIANTS["cut"]
            return
        joined = [
            item.number
            for item in self.members(seen.current_before, seen.after)
            if item.number not in seen.admitted_before
        ]
        assert joined == [], INVARIANTS["cut"]

    @invariant()
    def a_shipped_release_gives_way_to_the_next(self) -> None:
        """Checked once the run that closes the shipped milestones has finished: each release
        that shipped since the last finished run is closed. And no run moves an item into a
        shipped release from anywhere but another one."""
        seen = self.last_run
        if seen is None or seen.shipped is None:
            return
        shipped = {seen.shipped, *seen.shipped_all}
        moved_in = [
            number
            for number, item in seen.after.items()
            if item.release in shipped and seen.before[number].release not in shipped
        ]
        assert moved_in == [], INVARIANTS["ship"]
        if not self.closing:
            assert not shipped & set(self.open_titles), INVARIANTS["ship"]

    @invariant()
    def descoping_touches_only_unstarted_items(self) -> None:
        seen = self.last_run
        if seen is None:
            return
        window = timedelta(days=STALL_DAYS)
        assert all(
            before.status not in ("In Review", "Done")
            and after.status not in STARTED
            and (before.status != "In Progress" or seen.now - self.activity[after.number] >= window)
            for before, after in descoped_by(seen)
        ), INVARIANTS["descope"]

    @invariant()
    def only_a_stalled_item_goes_back_to_ready(self) -> None:
        """Checked on the Ready writes of the run that finishes, not those of a run that stopped
        before it, which a person may have worked on since: the machine's activity counts a
        person's status changes but setting Ready, and the job's Status clock counts that too,
        so an item the job finds stalled has stalled here too."""
        seen = self.last_run
        if seen is None:
            return
        window = timedelta(days=STALL_DAYS)
        assert all(seen.now - self.activity[number] >= window for number in seen.readied), (
            INVARIANTS["stalled"]
        )

    @invariant()
    def no_blocked_item_at_the_start(self) -> None:
        seen = self.last_run
        if seen is None or not seen.started or self.started is None:
            return
        assert all(item.status != "Blocked" for item in self.members(self.started, seen.after)), (
            INVARIANTS["blocked"]
        )

    @invariant()
    def the_admitted_set_stays(self) -> None:
        """In a run that neither records nor starts a release, no item the release held at its
        start, or admitted since, goes to the backlog, nor one in review or done anywhere."""
        seen = self.last_run
        if seen is None or seen.first_run or seen.started:
            return
        current = seen.current_before
        held = [n for n in seen.admitted_before if seen.before[n].release == current]
        sent = [
            n
            for n in held
            if seen.after[n].release is None
            or (seen.before[n].status in ("In Review", "Done") and seen.after[n].release != current)
        ]
        assert sent == [], INVARIANTS["held"]

    @invariant()
    def a_persons_placement_elsewhere_stands(self) -> None:
        """The job moves an item out of the backlog or a planned release only when that release
        starts, and then only one no person placed there."""
        seen = self.last_run
        if seen is None:
            return
        judged = {seen.current_before} | ({seen.under_way} if seen.started else set())
        moved = [
            number
            for number, item in seen.after.items()
            if item.release != seen.before[number].release
            and seen.placed_before.get(number) == PERSON
            and seen.before[number].release not in judged
            and not seen.from_shipped(number)
        ]
        assert moved == [], INVARIANTS["stands"]

    @invariant()
    def a_persons_placement_stands(self) -> None:
        seen = self.last_run
        if seen is None:
            return
        pulled = [
            number
            for number, item in seen.after.items()
            if item.release == seen.current_after
            and seen.before[number].release != seen.current_after
            and not seen.from_shipped(number)
        ]
        assert not any(seen.placed_before.get(number) == PERSON for number in pulled), INVARIANTS[
            "placement"
        ]

    @invariant()
    def every_move_has_a_reason(self) -> None:
        """Every item the job moved since the run it finishes began has a reason comment; one a
        person moved since is the person's, unless this run moved it again anywhere but back to
        where it was before."""
        seen = self.last_run
        if seen is None:
            return
        moved = [
            n
            for n, item in seen.after.items()
            if (item.release != seen.was(n).release)
            and (
                (n, ItemField.RELEASE) not in seen.person_fields
                or item.release != seen.before[n].release
            )
        ]
        assert all(seen.commented(n) for n in moved), INVARIANTS["reason"]

    @invariant()
    def a_start_fills_its_release_from_items_no_person_placed(self) -> None:
        """Checked after a run that starts a release. The job's module accepts the windows
        `unclaimed` keeps, where a place a job set reads as a person's: a Release write that
        landed with nothing to show the job made it, or that a person overtook by moving the
        item into its target, or anywhere when it was a move to the backlog, while the run
        waited; a move back that a run that stopped may have recorded as an exit; and a rename
        of the release a job placed the item in, since the job records it by title. A release
        a person cut before its start pulls nothing in."""
        seen = self.last_run
        if seen is None or not seen.started:
            return
        starting = seen.under_way
        cut = seen.cut and self.cut_release == starting
        if cut or len(self.members(starting, seen.after)) >= CAP:
            return
        later = self.after(starting)
        left = [
            number
            for number, item in seen.after.items()
            if item.state is GitHubState.OPEN
            and item.status == "Ready"
            and item.release in (None, later)
            and self.placed_by.get(number) != PERSON
            and number not in self.unclaimed
        ]
        assert left == [], INVARIANTS["pulled"]

    @invariant()
    def no_ranking_field_changes(self) -> None:
        seen = self.last_run
        if seen is None:
            return
        assert all(
            (item.priority, item.value, item.effort)
            == (seen.before[n].priority, seen.before[n].value, seen.before[n].effort)
            for n, item in seen.after.items()
        ), INVARIANTS["fields"]

    @invariant()
    def every_change_is_finished(self) -> None:
        """No change is left pending once a run finishes, and each Status or Release the job
        wrote, from the run it finishes on, either has a reason comment or is as it was: the
        `Pending` mark alone can't show a change that was begun without one."""
        if self.outstanding is not None:
            return
        assert not any(item.job_record.get(JobMark.PENDING) for item in self.view.values()), (
            INVARIANTS["finished"]
        )
        seen = self.last_run
        if seen is None:
            return
        unexplained = [
            (number, name)
            for number, name in seen.job_fields
            if name in JUDGED
            and (number, name) not in seen.person_fields
            and seen.after[number].field_value(name) != seen.was(number).field_value(name)
            and not seen.commented(number)
        ]
        assert unexplained == [], INVARIANTS["finished"]


TestRoadmapLifecycle = RoadmapLifecycle.TestCase
TestRoadmapLifecycle.settings = SETTINGS


# ── The machine itself ────────────────────────────────────────────────────────


def context_terms() -> set[str]:
    """Every term CONTEXT.md defines, read from its `**Term**:` lines."""
    text = CONTEXT.read_text(encoding="utf-8")
    return set(re.findall(r"^\*\*(?P<term>[^*]+)\*\*:$", text, flags=re.MULTILINE))


def test_each_invariant_message_starts_with_a_term_context_md_defines() -> None:
    terms = context_terms()
    leading = {message.split(":", 1)[0] for message in INVARIANTS.values()}
    assert (leading - terms, len(INVARIANTS)) == (set(), 15)


def test_the_gate_settings_keep_shrinking_and_need_no_database() -> None:
    assert (
        SETTINGS.derandomize,
        SETTINGS.database,
        SETTINGS.deadline,
        Phase.shrink in SETTINGS.phases,
    ) == (True, None, None, True)


def rule_steps(failure: BaseException) -> list[str]:
    """The rules of the failing sequence Hypothesis printed, without its invariant checks."""
    checks = {check.function.__name__ for check in RoadmapLifecycle().invariants}
    notes = "\n".join(getattr(failure, "__notes__", []))
    named = re.findall(r"state\.(?P<rule>\w+)\(", notes)
    return [name for name in named if name not in checks and name != "teardown"]


def test_the_machine_fails_without_the_cut_lock_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the cut lock gone, a critical fix filed into a cut release joins it.

    The gate replays the minimal failing sequence, the start, the cut and a critical fix filed
    into the release, and checks every invariant after each step; with the row in place, the
    same steps pass. A search for that sequence can't be relied on within the gate's second:
    what Hypothesis draws, derandomized or not, depends on the constants of the modules loaded,
    and the number of examples a search needs to find it varies with them, often past what a
    second allows. `DEVOPS_PROPERTY_PROFILE=deep` runs that search instead, and shrinks the
    failure to the same three steps.
    """

    def minimal(state: RoadmapLifecycle) -> RoadmapLifecycle:
        return replay(
            state,
            lambda: state.start(held=[], waiting=[]),
            lambda: state.cut(draft=False),
            lambda: state.critical_fix_filed(kind="bug", status="New"),
        )

    kept = minimal(RoadmapLifecycle())
    cut_lock = (ReleaseState.CUT, Event.FIX_JOINED)
    rows = {key: row for key, row in reprioritize.TRANSITIONS.items() if key != cut_lock}
    monkeypatch.setattr(reprioritize, "TRANSITIONS", MappingProxyType(rows))
    if _DEEP:
        with pytest.raises(AssertionError, match=r"^Cut: ") as failure:
            run_state_machine_as_test(RoadmapLifecycle, settings=CUT_LOCK_SETTINGS)
        print("\n".join(getattr(failure.value, "__notes__", [])))
        steps = rule_steps(failure.value)
    else:
        with pytest.raises(AssertionError, match=r"^Cut: "):
            minimal(RoadmapLifecycle())
        steps = ["start", "cut", "critical_fix_filed"]
    assert (kept.current(), steps) == ("v1.0.0", ["start", "cut", "critical_fix_filed"])


def _every_member_joins(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reviewers' HELDOUT: the rules take every item in the release for one that joined."""
    monkeypatch.setattr(reprioritize, "admitted_to", lambda _: None)


def _every_member_but_a_p0_joins(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reviewers' HELDOUT2: only the release's P0 items count as admitted."""
    real = reprioritize.admitted_to
    monkeypatch.setattr(
        reprioritize,
        "admitted_to",
        lambda item: real(item) if item.priority == "P0-Critical" else None,
    )


def _the_reviewed_write_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """The write order the reviewers replayed atomicity (A) on: Status before the Release, and
    no `Pending` mark, so a run that stops after the Status leaves a change no mark records."""
    fields = reprioritize._field_writes

    def status_first(decision: reprioritize.Decision) -> list[tuple[ItemField, str | None]]:
        return sorted(fields(decision), key=lambda write: write[0] is not ItemField.STATUS)

    def unrecorded(
        store: Any, decision: reprioritize.Decision, now: datetime, numbers: Any
    ) -> None:
        for item_field, value in status_first(decision):
            store.set_field(decision.item, item_field, value)
        store.comment(decision.item.number, decision.comment)
        store.set_marks(decision.item, reprioritize._final_marks(decision, now, numbers))

    monkeypatch.setattr(reprioritize, "_apply_decision", unrecorded)


def _no_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A start that finds no candidate to top its release up with."""
    monkeypatch.setattr(reprioritize, "_candidates", lambda *_: ([], []))


def _the_ninth_rounds_dropped_record(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tenth round's second fix undone: the record of a begun Release a person set since is
    dropped even when the issue's events show the change's milestone call never landed."""
    monkeypatch.setattr(reprioritize, "_never_joined", lambda *_: False)


def _a_start_with_a_waiting_feature(state: RoadmapLifecycle) -> None:
    """v1.0.0 starts empty, a Ready feature waits in the backlog, and v1.0.0 ships."""
    state.start(held=[], waiting=["feature"])
    replay(state, lambda: state.cut(draft=False), lambda: state.ship(milestone_closed=True))


def _three_held_then_a_day(state: RoadmapLifecycle) -> None:
    replay(
        state,
        lambda: state.start(held=["Ready", "Ready", "In Progress"], waiting=[]),
        lambda: state.days_pass(days=1),
    )


def _a_stall_whose_release_write_fails(state: RoadmapLifecycle) -> None:
    """The stall's Release write fails at its milestone call, once its job record has landed;
    a mutant that writes the Status first has set it by then, with no record and no comment."""
    replay(
        state,
        lambda: state.start(held=["In Progress", "Ready"], waiting=[]),
        lambda: state.next_run_stops(at=3),
        lambda: state.days_pass(days=STALL_DAYS + 1),
    )


@pytest.mark.parametrize(
    ("mutate", "steps", "message"),
    [
        (_every_member_joins, _three_held_then_a_day, INVARIANTS["held"]),
        (_every_member_but_a_p0_joins, _three_held_then_a_day, INVARIANTS["held"]),
        (_the_reviewed_write_order, _a_stall_whose_release_write_fails, INVARIANTS["finished"]),
        (_no_candidates, _a_start_with_a_waiting_feature, INVARIANTS["pulled"]),
        (
            _the_ninth_rounds_dropped_record,
            lambda state: _a_top_up_moved_out_and_back(state, at=5),
            INVARIANTS["pulled"],
        ),
    ],
    ids=["heldout", "heldout2", "atomicity-a", "no-candidates", "unlanded-record-dropped"],
)
def test_the_machine_fails_on_each_mutant_the_reviewers_replayed(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[pytest.MonkeyPatch], None],
    steps: Callable[[RoadmapLifecycle], None],
    message: str,
) -> None:
    """Each replay passes on the job as it is, and fails the machine once the job is mutated
    as the reviewers did: a run that sends the release's admitted items to the backlog, and a
    stall whose Status was written without a record or a comment. The reviewers' machine
    passed all three, so the job's unit tests were their only cover. The last two show the
    pull-in invariant is not vacuous: a start with no candidates fails it, and so does the
    tenth round's replay of a top-up whose milestone call never landed once the record of the
    item's place is dropped, as the ninth round did."""
    steps(RoadmapLifecycle())
    mutate(monkeypatch)
    with pytest.raises(AssertionError) as failure:
        steps(RoadmapLifecycle())
    assert str(failure.value).splitlines()[0] == message


# ── Failing sequences found while building it (#740) ─────────────────────────
# Each replays the steps Hypothesis printed, and checks every invariant after each step.


def replay(state: RoadmapLifecycle, *steps: Callable[[], object]) -> RoadmapLifecycle:
    """Run `steps` on the machine, checking every invariant after each, as Hypothesis does."""
    for step in steps:
        step()
        for check in state.invariants:
            check.function(state)
    return state


def test_empty_releases_that_ship_with_their_milestones_open_leave_a_current_release() -> None:
    """The first run found v1.0.0 empty and, with no run record, recorded nothing, so the run
    after each ship was a first run again, which recorded the next release without starting it:
    no planned release was created, and the third ship left no open release. The run record now
    names each release the job records or starts, so each ship starts the next one.

    Hypothesis printed: `start(held=[], waiting=[])`, then `cut(draft=False)` and `ship()`
    three times.
    """
    state = RoadmapLifecycle()
    replay(
        state,
        lambda: state.start(held=[], waiting=[]),
        *(
            step
            for _ in range(3)
            for step in (
                lambda: state.cut(draft=False),
                lambda: state.ship(milestone_closed=False),
            )
        ),
    )
    assert (state.current(), len(state.open_titles)) == ("v1.0.3", 3)


def test_a_p0_feature_put_back_where_the_job_sent_it_is_judged_once_that_release_starts() -> None:
    """The job sent a P0 feature to v1.0.1, a person moved it to v1.0.2 and, once v1.0.1 had
    started, back to v1.0.1. That set the Release the job last set, so `is_due` took it for the
    job's own change and the item sat in the release outside its admitted set. Its `Left` mark
    now makes the return a trigger, and the admission rule sends it on to v1.0.2: v1.0.1 started
    empty, and the run record says so.

    Hypothesis printed (seed 0, 400 examples of 40 steps, while building): the steps below.
    """
    state = RoadmapLifecycle()
    started = state.start(held=["Ready"], waiting=["p0_feature"])
    feature = started.values[1]  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.person_places(item=feature, place="current"),
        lambda: state.cut(draft=False),
        lambda: state.uncut(),
        lambda: state.cut(draft=False),
        lambda: state.person_places(item=feature, place="later"),
        lambda: state.ship(milestone_closed=False),
        lambda: state.person_places(item=feature, place="current"),
    )
    item = state.view[feature]
    assert (state.current(), item.release, state.titled(item.job_record.get(JobMark.ADMITTED))) == (
        "v1.0.1",
        "v1.0.2",
        None,
    )


def test_a_blocked_item_placed_in_the_next_release_leaves_it_when_that_release_starts() -> None:
    """The first run found v1.0.0 empty and recorded nothing, so the run after the ship was a
    first run that recorded v1.0.1 as it stood, with the Blocked item a person had placed there.
    The run record names v1.0.0, so the ship starts v1.0.1, and the start sends the Blocked item
    to the backlog.

    Hypothesis printed (seed 28, 300 examples of 50 steps, while building): the steps below.
    """
    state = RoadmapLifecycle()
    (feature,) = state.start(held=[], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.item_moves_on(change="Blocked", item=feature),
        lambda: state.person_places(item=feature, place="next"),
        lambda: state.ship(milestone_closed=False),
    )
    assert (state.current(), state.view[feature].release) == ("v1.0.1", None)


def test_a_release_whose_only_admitted_item_was_descoped_is_not_started_again() -> None:
    """The reviewer's replay: the job sent a P2 feature to the backlog, then descoped the
    release's one admitted item, which cleared the last `Admitted` mark naming v1.0.0, so the
    next run took v1.0.0 for a release not yet started and pulled the feature back in. The run
    record still names v1.0.0, and the machine tracks the start itself.

    Hypothesis printed: the steps below.
    """
    state = RoadmapLifecycle()
    held, feature = state.start(held=["Ready"], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.person_places(item=feature, place="current"),
        lambda: state.item_moves_on(item=held, change="Blocked"),
        lambda: state.days_pass(days=1),
    )
    found = state.view[feature]
    assert (state.current(), found.release, found.priority) == ("v1.0.0", None, "P2-Medium")


def test_an_item_moved_back_to_ready_once_a_fix_filled_the_release_leaves_it() -> None:
    """The reviewer's replay of the size: three started items, a fix joins with nothing to
    descope, then a person moves one back to Ready. The release holds four, above both its cap
    and its size at start, so the unstarted feature leaves for v1.0.1."""
    state = RoadmapLifecycle()
    held = state.start(held=["In Progress"] * CAP, waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.critical_fix_filed(kind="bug", status="Ready"),
        lambda: state.item_goes_back_to_ready(item=held[0]),
    )
    assert (len(state.members(state.current())), state.view[held[0]].release) == (CAP, "v1.0.1")


def test_a_merged_release_pull_request_keeps_the_release_cut_until_it_is_published() -> None:
    """The reviewer's replay of the cut window: the release pull request merges and
    `release.yml` fails to publish the release. Its code is in `main` already, so the release
    stays cut, and a critical fix filed into it goes first into the next release."""
    state = RoadmapLifecycle()
    state.start(held=["Ready"], waiting=[])
    fix = replay(
        state,
        lambda: state.cut(draft=True),
        lambda: state.ship(milestone_closed=False, published=False),
        lambda: state.critical_fix_filed(kind="security", status="Ready"),
    ).view
    filed = max(fix)
    assert (state.current(), fix[filed].release) == ("v1.0.0", "v1.0.1")


def test_an_admitted_item_a_person_takes_out_and_puts_back_is_judged_again() -> None:
    """The job sent a feature to the backlog; a person placed it in v1.0.1, which started
    holding it, then took it back to the backlog, which is where the job last placed it. That
    move read as the job's own, so no run cleared its `Admitted` mark, and putting it back in
    v1.0.1 escaped the admission rule. Leaving an admitted release is now never the job's own
    change unless the job cleared the mark."""
    state = RoadmapLifecycle()
    (feature,) = state.start(held=[], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.person_places(item=feature, place="current"),
        lambda: state.person_places(item=feature, place="next"),
        lambda: state.cut(draft=False),
        lambda: state.ship(milestone_closed=True),
        lambda: state.person_places(item=feature, place="backlog"),
        lambda: state.person_places(item=feature, place="current"),
    )
    assert (state.current(), state.view[feature].release) == ("v1.0.1", None)


def test_a_feature_a_person_moved_back_to_the_backlog_where_the_job_sent_it_stays_there() -> None:
    """The job sent a feature to the backlog; a person placed it in v1.0.1, then moved it back
    to the backlog. Its place matched the job's last placement, so v1.0.1's start pulled it in.
    The run after the person placed it records that a person took it out of the backlog.

    Hypothesis printed (seed 7, 300 examples of 40 steps, `PYTHONHASHSEED=22`): the steps below.
    """
    state = RoadmapLifecycle()
    (feature,) = state.start(held=[], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.days_pass(days=1),
        lambda: state.person_places(item=feature, place="current"),
        lambda: state.person_places(item=feature, place="next"),
        lambda: state.person_places(item=feature, place="backlog"),
        lambda: state.cut(draft=False),
        lambda: state.ship(milestone_closed=False, published=True),
    )
    assert (state.current(), state.view[feature].release) == ("v1.0.1", None)


def test_a_stalled_fix_put_back_in_the_release_is_readied_and_admitted() -> None:
    """A fix In Progress for 15 days in a planned release joins the current one: the stall
    rule's Ready replaced its admission, so it sat in the release outside its admitted set.

    Shortened from what Hypothesis printed (seed 1, 300 examples of 40 steps,
    `PYTHONHASHSEED=11`), which reached the same join after 30 more steps.
    """
    state = RoadmapLifecycle()
    state.start(held=[], waiting=[])
    fix = replay(state, lambda: state.critical_fix_filed(kind="bug", status="New")).view
    (number,) = fix
    replay(
        state,
        lambda: state.item_moves_on(item=number, change="In Progress"),
        lambda: state.person_places(item=number, place="later"),
        lambda: state.days_pass(days=STALL_DAYS + 1),
        lambda: state.person_places(item=number, place="current"),
    )
    found = state.view[number]
    assert (found.release, found.status, state.titled(found.job_record.get(JobMark.ADMITTED))) == (
        "v1.0.0",
        "Ready",
        "v1.0.0",
    )


def test_a_status_set_back_to_the_jobs_own_value_is_judged_at_the_next_run() -> None:
    """The job set a stalled item back to Ready; once it started again, a person set it back to
    Ready when the release held more than its size. That reads as the job's own change, so no
    run follows, and the size invariant failed before the next one. The machine checks the size
    after each run; the next day's stall check descopes the item.

    Hypothesis printed (seed 3, 300 examples of 40 steps, `PYTHONHASHSEED=33`): the steps below.
    """
    state = RoadmapLifecycle()
    started = state.start(
        held=["Ready", "In Progress"], waiting=["feature", "feature"], shipped=False
    )
    stalls = started.values[1]  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.cut(draft=False),
        *(lambda days=days: state.days_pass(days=days) for days in (1, 1, 1, 2, 9)),
        lambda: state.ship(milestone_closed=False, published=True),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
        lambda: state.critical_fix_filed(kind="bug", status="Ready"),
        lambda: state.cut(draft=False),
        lambda: state.uncut(),
        lambda: state.item_moves_on(change="In Progress", item=stalls),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
        lambda: state.item_goes_back_to_ready(item=stalls),
    )
    unjudged = state.view[stalls].release
    replay(state, lambda: state.days_pass(days=1))
    assert (unjudged, state.view[stalls].release) == ("v1.0.2", "v1.0.3")


def _a_top_up_overruled(state: RoadmapLifecycle, at: int = 4) -> int:
    """(a): the start's Release write that pulls a backlog feature in stops at its job record
    (4) or its milestone call (5); a person then places the feature in v1.0.3."""
    (feature,) = state.start(held=[], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=at, later=True),
        lambda: state.ship(milestone_closed=True),
        lambda: state.person_places(item=feature, place="later"),
    )
    return feature


def _an_admission_overruled(state: RoadmapLifecycle, at: int = 2) -> int:
    """(b): the admission that sends a late feature to the backlog stops at its job record (2)
    or its milestone call (3); a person then places it in v1.0.1."""
    _, feature = state.start(held=["Ready"], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=at, later=True),
        lambda: state.person_places(item=feature, place="current"),
        lambda: state.person_places(item=feature, place="next"),
    )
    return int(feature)


def _a_stall_overruled(state: RoadmapLifecycle) -> int:
    (held,) = state.start(held=["In Progress"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.days_pass(days=STALL_DAYS + 1),
        lambda: state.item_moves_on(item=held, change="In Review"),
    )
    return int(held)


def _a_fix_admission_then_a_cut(state: RoadmapLifecycle) -> int:
    state.start(held=[], waiting=[])
    replay(
        state,
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
        lambda: state.cut(draft=False),
    )
    return max(state.view)


def _a_descope_then_a_ship(state: RoadmapLifecycle) -> int:
    """The descope of a Blocked item stops at its comment, and the release ships."""
    _, blocked = state.start(held=["Ready", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=5, later=True),
        lambda: state.item_moves_on(item=blocked, change="Blocked"),
        lambda: state.ship(milestone_closed=True),
    )
    return int(blocked)


def _a_descope_made_by_hand(state: RoadmapLifecycle, at: int = 2) -> int:
    """S7: the descope of a Blocked item stops at its Release write, at the job record (2) or,
    once that has landed, at the milestone call (3); a person moves the item to v1.0.1, and the
    rerun stops too, at its first write, then the person sets it Ready. After the milestone
    call, the item holds the move's Release with nothing to show who set it, so the reruns
    finish the move as one that happened: the first write is its comment."""
    _, blocked = state.start(held=["Ready", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=at, later=True),
        lambda: state.item_moves_on(item=blocked, change="Blocked"),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.person_places(item=blocked, place="next"),
        lambda: state.item_goes_back_to_ready(item=blocked),
    )
    return int(blocked)


def _a_p0_feature_placed_by_hand(state: RoadmapLifecycle, at: int = 2) -> int:
    """S5: the move of a late P0 feature to v1.0.1 stops at its Release write, at the job
    record (2) or the milestone call (3); a person places it there, and the rerun stops too,
    then the person makes it P2. After the milestone call, the reruns finish the move."""
    _, feature = state.start(held=["Ready"], waiting=["p0_feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=at, later=True),
        lambda: state.person_places(item=feature, place="current"),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.person_places(item=feature, place="next"),
        lambda: state.person_reprioritizes(item=feature, priority="P2-Medium"),
    )
    return int(feature)


@pytest.mark.parametrize(
    ("steps", "where", "stops"),
    [
        (_a_top_up_overruled, "v1.0.3", ["record"]),
        (lambda state: _a_top_up_overruled(state, at=5), "v1.0.3", ["field"]),
        (_an_admission_overruled, "v1.0.1", ["record"]),
        (lambda state: _an_admission_overruled(state, at=3), "v1.0.1", ["field"]),
        (_a_stall_overruled, "v1.0.0", ["record"]),
        (_a_fix_admission_then_a_cut, "v1.0.1", ["comment"]),
        (_a_descope_then_a_ship, None, ["comment"]),
        (_a_descope_made_by_hand, "v1.0.1", ["record", "set_marks"]),
        (lambda state: _a_descope_made_by_hand(state, at=3), "v1.0.1", ["field", "comment"]),
        (_a_p0_feature_placed_by_hand, "v1.0.1", ["record", "set_marks"]),
        (lambda state: _a_p0_feature_placed_by_hand(state, at=3), "v1.0.1", ["field", "comment"]),
    ],
    ids=[
        "a-top-up",
        "a-top-up-at-its-milestone-call",
        "b-admission",
        "b-admission-at-its-milestone-call",
        "c-stall-in-review",
        "d-fix-then-cut",
        "descope-then-ship",
        "s7-two-edits",
        "s7-two-edits-at-its-milestone-call",
        "s5-two-edits",
        "s5-two-edits-at-its-milestone-call",
    ],
)
def test_a_stopped_run_left_for_the_next_poll_is_judged_again(
    steps: Callable[[RoadmapLifecycle], int], where: str | None, stops: list[str]
) -> None:
    """The reviewers' replays (a) to (d), S5 and S7, and the start after an interrupted
    descope, through the machine: a run stops and is run again at the next poll, after a person
    moved the item, moved it into review, cut the release or shipped it. The rerun finishes what
    the rules still decide, and a person's change made since stands, whether the run stopped at
    a Release write's job record or, once that had landed, at its milestone call; a move a
    person then made by hand is finished as one that happened. Each case checks where its runs
    stopped.

    Hypothesis printed (d) for the reviewers' variant of the machine (seed 7, 200 examples of
    30 steps), shrunk to the steps of `_a_fix_admission_then_a_cut` and five days passing.
    """
    state = RoadmapLifecycle()
    number = steps(state)
    assert (state.outstanding, state.view[number].release, state.stops) == (None, where, stops)


def test_an_item_closed_when_its_release_started_and_reopened_stays_in_it() -> None:
    """The reviewers' replay: v1.0.1 starts holding a closed feature, which a person reopens.
    It never joined v1.0.1: the start admits closed items too."""
    state = RoadmapLifecycle()
    (feature,) = state.start(held=[], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.person_places(item=feature, place="next"),
        lambda: state.item_moves_on(item=feature, change="closes"),
        lambda: state.cut(draft=False),
        lambda: state.ship(milestone_closed=True),
        lambda: state.item_reopens(item=feature, status="In Progress"),
    )
    assert (state.current(), state.view[feature].release) == ("v1.0.1", "v1.0.1")


def test_a_closed_admitted_item_taken_out_and_put_back_is_judged_once_reopened() -> None:
    """The reviewers' replay: v1.0.0 started holding a feature that then closes. A person
    takes it, still closed, to the backlog and back, then reopens it. The run that saw it out
    cleared its mark, so the reopened feature joined after the start and goes to the backlog."""
    state = RoadmapLifecycle()
    _, done = state.start(held=["Ready", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.item_moves_on(item=done, change="closes"),
        lambda: state.person_places(item=done, place="backlog"),
        lambda: state.person_places(item=done, place="current"),
        lambda: state.item_reopens(item=done, status="In Progress"),
    )
    assert (state.current(), state.view[done].release) == ("v1.0.0", None)


def test_a_renamed_release_keeps_its_admitted_set_and_its_admission_rule() -> None:
    """The reviewers' replay: a person renames the open releases after v1.0.0 started, then
    adds a feature to it. v1.1.0 is v1.0.0 renamed: its held item stays, and the feature goes
    to the backlog."""
    state = RoadmapLifecycle()
    held, feature = state.start(held=["Ready"], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.releases_renamed(),
        lambda: state.person_places(item=feature, place="current"),
    )
    assert (state.current(), state.view[held].release, state.view[feature].release) == (
        "v1.1.0",
        "v1.1.0",
        None,
    )


@pytest.mark.parametrize(
    "then",
    [
        lambda state, fix: state.person_reprioritizes(item=fix, priority="P1-High"),
        lambda state, _: state.cut(draft=False),
    ],
    ids=["reprioritized", "cut"],
)
def test_a_fix_whose_admission_was_announced_before_its_run_stopped_stays_admitted(
    then: Callable[[RoadmapLifecycle, int], None],
) -> None:
    """The run that admits a fix stops after its comment, before its mark, and a person then
    reprioritizes the fix or cuts the release before the rerun. The fix was admitted, comment
    and all, while it was a critical fix and before the cut: the rerun only records it.

    A sweep (300 examples of 60 steps, not derandomized) found both, as errors of the machine,
    which took the fix for one joining at the rerun.
    """
    state = RoadmapLifecycle()
    state.start(held=[], waiting=[])
    replay(
        state,
        lambda: state.next_run_stops(at=3, later=True),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
    )
    fix = max(state.view)
    replay(state, lambda: then(state, fix))
    found = state.view[fix]
    assert (found.release, state.titled(found.job_record.get(JobMark.ADMITTED))) == (
        "v1.0.0",
        "v1.0.0",
    )


def _a_cut_lock_move_the_start_finishes(state: RoadmapLifecycle, closed: bool) -> int:
    """Seed 101: the run that sends a fix filed into cut v1.0.0 on to v1.0.1 stops at its
    Release write, and v1.0.0 ships before the rerun, which starts v1.0.1 and finishes the
    move into it."""
    state.start(held=[], waiting=[])
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
        lambda: state.ship(milestone_closed=closed, published=True),
    )
    return max(state.view)


def _a_cut_while_a_start_waits(state: RoadmapLifecycle) -> int:
    """Seeds 106 and 111: the start of v1.0.1 stops at its first write and waits, with v1.0.0's
    milestone still open; a person cuts the release under way and files a fix into it."""
    state.start(held=[], waiting=[])
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.ship(milestone_closed=False, published=True),
        lambda: state.cut(draft=False),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
    )
    return max(state.view)


def _a_descope_announced_then_undone_by_hand(state: RoadmapLifecycle) -> int:
    """The reviewers' case: the descope of a Blocked feature posts its comment and stops at its
    last write; a person puts the feature back in v1.0.0 before the rerun."""
    _, blocked = state.start(held=["Ready", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=6, later=True),
        lambda: state.item_moves_on(item=blocked, change="Blocked"),
        lambda: state.person_places(item=blocked, place="current"),
    )
    return int(blocked)


@pytest.mark.parametrize(
    ("steps", "where"),
    [
        (lambda state: _a_cut_lock_move_the_start_finishes(state, closed=False), "v1.0.1"),
        (lambda state: _a_cut_lock_move_the_start_finishes(state, closed=True), "v1.0.1"),
        (_a_cut_while_a_start_waits, "v1.0.2"),
        (_a_descope_announced_then_undone_by_hand, None),
    ],
    ids=[
        "cut-lock-then-ship-milestone-open",
        "cut-lock-then-ship-milestone-closed",
        "cut-while-a-start-waits",
        "descope-announced-then-undone",
    ],
)
def test_the_machines_own_errors_the_fourth_rounds_sweeps_found(
    steps: Callable[[RoadmapLifecycle], int], where: str | None
) -> None:
    """Sweeps of 300 examples of 40 steps, not derandomized (seeds 101, 106 and 111), failed on
    the job as the third fix round left it, each an error of the machine's own record:
    `placement` and `stands` took the fix the start moved out of the shipped release for one a
    person placed elsewhere, `cut` cut the shipped release whose milestone a waiting start had
    not closed yet, and a stopped run's announced descope stayed in the machine's admitted set,
    so `held` fired when the feature a person put back went to the backlog. The job is right in
    each: the fix goes first into the next release, a fix filed into a cut release goes on, and
    a feature put back after its descope joins after the start."""
    state = RoadmapLifecycle()
    number = steps(state)
    assert (state.outstanding, state.view[number].release) == (None, where)


def _a_start_stopped_at_its_close(state: RoadmapLifecycle) -> int:
    """Seed 705: the first run at v1.0.0's ship records v1.0.1, which is cut and ships with its
    milestone open; the run that starts v1.0.2 stops at its last write, the close of v1.0.1,
    and waits for the next poll; a person files a critical fix into v1.0.2."""
    state.start(held=["Ready"], waiting=[], stops_at=0, shipped=False)
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=5, later=True),
        lambda: state.ship(milestone_closed=False, published=True),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
    )
    return max(state.view)


def _a_first_run_stopped_at_its_close(state: RoadmapLifecycle) -> int:
    """The first run at v1.0.0's ship, which records v1.0.1, stops at its last write, the close
    of v1.0.0, and waits for the next poll, as when a person runs it again by hand later: the
    machine's first run is run again at once. A person places a P2 feature in v1.0.1."""
    state.rerun_now = False
    _, feature = state.start(held=["Ready"], waiting=["feature"], stops_at=4, shipped=False).values  # type: ignore[attr-defined]
    replay(state, lambda: state.person_places(item=feature, place="next"))
    return int(feature)


@pytest.mark.parametrize(
    ("steps", "current", "where"),
    [
        (_a_start_stopped_at_its_close, "v1.0.2", "v1.0.2"),
        (_a_first_run_stopped_at_its_close, "v1.0.1", None),
    ],
    ids=["seed-705-start-then-fix", "first-run-at-a-ship-then-p2-feature"],
)
def test_an_item_added_after_a_run_stopped_at_its_close_is_judged_by_the_rerun(
    steps: Callable[[RoadmapLifecycle], int], current: str, where: str | None
) -> None:
    """Sweeps of random seeds (96 of 300 examples of 40 steps, 30 of 200 of 70) failed
    `admitted` at seed 705 only, shrunk to the steps of `_a_start_stopped_at_its_close`: the
    run record named v1.0.2 already, so the rerun only closed v1.0.1, and the fix sat in v1.0.2
    outside its admitted set until a later run was due. The first run at a ship stopped at its
    close fails the same way. The rerun now holds the release the run record names to the
    rules, then closes the shipped one: the fix is admitted, the feature goes to the backlog,
    each with its comment."""
    state = RoadmapLifecycle()
    number = steps(state)
    found = state.view[number]
    assert (
        state.outstanding,
        state.closing,
        state.stops,
        state.current(),
        found.release,
        state.titled(found.job_record.get(JobMark.ADMITTED)),
        len(state.store.comments_on(number)),
    ) == (None, False, ["close_release"], current, where, where, 1)


def _a_stalled_fix_joins_and_its_run_stops(
    state: RoadmapLifecycle, at: int, reprioritized: bool
) -> int:
    """Seed 820: a critical fix In Progress since it was filed into v1.0.0 is moved to v1.0.1,
    goes idle, and comes back after 14 days: one run admits it and readies it. That run stops
    at its write `at` and waits for the next poll: 4, the Status's written mark, after the
    Status landed; 6, the change's last write, after its comment. With `reprioritized`, a
    person makes the fix P1 before the rerun; otherwise the next poll finds nothing new."""
    state.start(held=[], waiting=[])
    fix = state.critical_fix_filed(kind="bug", status="New")
    replay(
        state,
        lambda: state.item_moves_on(change="In Progress", item=fix),
        lambda: state.person_places(item=fix, place="next"),
        lambda: state.days_pass(days=1),
        lambda: state.days_pass(days=STALL_DAYS - 1),
        lambda: state.next_run_stops(at=at, later=True),
        lambda: state.person_places(item=fix, place="current"),
        (
            (lambda: state.person_reprioritizes(item=fix, priority="P1-High"))
            if reprioritized
            else (lambda: state.item_goes_back_to_ready(item=fix))
        ),
    )
    return fix


@pytest.mark.parametrize(
    ("at", "reprioritized"),
    [(6, True), (6, False), (4, False)],
    ids=["seed-820-comment-posted-then-p1", "comment-posted", "status-landed-unconfirmed"],
)
def test_a_fix_readied_as_it_joins_is_admitted_by_that_change_when_its_run_stops(
    at: int, reprioritized: bool
) -> None:
    """Sweeps of 200 examples of 70 steps (seed 820, not derandomized) failed `held`: the fix's
    admission was a mark the run wrote after every change, not part of the change that readied
    it, so a run that stopped after that change began left the fix without its mark. The rerun
    finished the Ready and judged the fix as a join: once a person had made it P1, after the
    comment saying that as a critical fix it stays, it went to the backlog; left as it was, it
    was admitted again with a second comment. The readying change now carries the admission in
    its `Pending` mark and its last write: one stall comment, and the fix stays admitted."""
    state = RoadmapLifecycle()
    fix = _a_stalled_fix_joins_and_its_run_stops(state, at, reprioritized)
    found = state.view[fix]
    assert (
        state.outstanding,
        state.stops,
        found.release,
        found.status,
        state.titled(found.job_record.get(JobMark.ADMITTED)),
        len(state.store.comments_on(fix)),
    ) == (None, ["set_marks"], "v1.0.0", "Ready", "v1.0.0", 2)


def test_a_stall_descope_a_person_undid_before_its_comment_keeps_the_item_admitted() -> None:
    """Sweeps of 300 examples of 40 steps (seed 1021, not derandomized) failed `held`: a stall
    descope of an item v1.0.0 started holding stopped at its Status's written mark, after its
    Release was written and its Status landed unconfirmed, and a person put the item back in
    v1.0.0 before the rerun. The rerun finished the change as it stands, with its comment, and
    cleared the item's `Admitted` mark as for any move out, so the admission rule sent the item
    to the backlog. The change was never announced and the item never left as far as any run
    saw, so it keeps its mark, as an item whose exit no run saw does."""
    state = RoadmapLifecycle()
    stalled, *_ = state.start(held=["In Progress", "Ready", "Ready", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.days_pass(days=1),
        lambda: state.days_pass(days=1),
        lambda: state.days_pass(days=STALL_DAYS - 3),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
        lambda: state.next_run_stops(at=7, later=True),
        lambda: state.days_pass(days=1),
        lambda: state.person_places(item=stalled, place="current"),
    )
    found = state.view[stalled]
    assert (
        state.outstanding,
        state.stops,
        found.release,
        found.status,
        state.titled(found.job_record.get(JobMark.ADMITTED)),
        len(state.store.comments_on(stalled)),
    ) == (None, ["set_marks"], "v1.0.0", "Ready", "v1.0.0", 1)


def test_an_item_moved_out_and_back_before_a_run_recorded_it_is_where_a_job_put_it() -> None:
    """Seed 746 of 300 examples of 40 steps, not derandomized, failed `stands`, the machine's
    own error: the cut lock sent a feature to the backlog; a person placed it in v1.0.0, the run
    that read it there stopped at its first write and waited, and the person put it back in the
    backlog before the rerun. No run recorded it out of the backlog, so the job, which reads
    state, not the change feed (ADR 0003), holds it where a job placed it, and v1.0.1's start
    pulls it in; the machine had counted the backlog as the person's placement. Now an item a
    person moves back where it was before any run recorded it out is placed by whoever placed it
    then, as the machine's admitted set already treats an exit no run saw."""
    state = RoadmapLifecycle()
    (feature,) = state.start(held=[], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.item_goes_back_to_ready(item=feature),
        lambda: state.next_run_stops(at=1),
        lambda: state.cut(draft=False),
        lambda: state.person_places(item=feature, place="current"),
        *(lambda: state.item_goes_back_to_ready(item=feature) for _ in range(3)),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.item_goes_back_to_ready(item=feature),
        lambda: state.person_places(item=feature, place="current"),
        lambda: state.next_run_stops(at=1),
        lambda: state.person_places(item=feature, place="backlog"),
        lambda: state.ship(milestone_closed=False),
    )
    assert (state.stops, state.current(), state.view[feature].release) == (
        ["set_marks"],
        "v1.0.1",
        "v1.0.1",
    )


def _a_top_up_undone_by_hand(at: int) -> tuple[object, ...]:
    """Seed 6031, shrunk: the cut lock sends a critical fix filed into v1.0.1 on to v1.0.2; made
    P1 and put back in v1.0.1, it goes to the backlog, the job's placement. v1.0.2's start pulls
    it in, and stops at its write `at`: 7, the Release's written mark, after its milestone call
    landed; 8, its comment. A person moves it back to the backlog before the rerun."""
    state, filed = RoadmapLifecycle(), []
    replay(
        state,
        lambda: state.start(held=[], waiting=[], shipped=False),
        lambda: state.cut(draft=False),
        lambda: filed.append(state.critical_fix_filed(kind="bug", status="Ready")),
        lambda: state.person_reprioritizes(item=filed[0], priority="P1-High"),
        lambda: state.person_places(item=filed[0], place="current"),
        lambda: state.next_run_stops(at=at, later=True),
        lambda: state.ship(milestone_closed=False),
        lambda: state.person_places(item=filed[0], place="backlog"),
    )
    found = state.view[filed[0]]
    return (
        state.outstanding,
        found.release,
        state.titled(found.job_record.get(JobMark.LEFT)),
        len(state.store.comments_on(filed[0])),
        state.stops,
    )


def test_a_top_up_a_person_undid_after_its_milestone_landed_leaves_the_item_where_they_put_it() -> (
    None
):
    """Seed 6031 of 300 examples of 40 steps, not derandomized, failed `stands`: the rerun
    dropped the top-up, its Release now a person's, but put back the job record the Release
    had before the change began, which named the backlog where a job had sent the fix. The
    person's placement read as the job's, and the same run's top-up pulled the fix into
    v1.0.2 again, with a second comment. A run that stops one write later left it where the
    person put it. The record of a field a person set since is now dropped, so both end alike:
    the fix stays in the backlog, marked as taken out of v1.0.2."""
    assert (_a_top_up_undone_by_hand(7), _a_top_up_undone_by_hand(8)) == (
        (None, None, "v1.0.2", 2, ["set_marks"]),
        (None, None, "v1.0.2", 2, ["comment"]),
    )


def test_a_stall_whose_item_a_person_set_in_progress_again_before_the_rerun_is_dropped() -> None:
    """Seed 10129 of 300 examples of 40 steps, not derandomized, failed `descope`: the stall
    descope of an In Progress item stopped at its Release's job record, before it began its
    Status write, and a person set the item In Progress again before the rerun. Its Status held
    what the change found, so the rerun judged it again by its Status clock as the change found
    it, still stalled, and finished the descope. Only the change's own Status write is no
    activity: the person's is, so the item stays in v1.0.0, In Progress, with no comment.

    Hypothesis printed: the steps below."""
    state = RoadmapLifecycle()
    (item,) = state.start(held=["Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.item_moves_on(change="In Progress", item=item),
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.days_pass(days=STALL_DAYS),
        lambda: state.item_moves_on(change="In Progress", item=item),
    )
    found = state.view[item]
    assert (
        state.outstanding,
        state.stops,
        found.release,
        found.status,
        found.job_record.get(JobMark.PENDING),
        len(state.store.comments_on(item)),
    ) == (None, ["record"], "v1.0.0", "In Progress", None, 0)


@pytest.mark.parametrize(
    ("worked", "stops"),
    [(("In Progress",), ["set_marks"]), (("In Review", "In Progress"), ["set_marks", "comment"])],
    ids=["set-again", "review-and-back"],
)
def test_a_stall_whose_move_landed_unconfirmed_keeps_the_status_a_person_set_since(
    worked: tuple[str, ...], stops: list[str]
) -> None:
    """The eleventh round's reviewers' case through the machine: the stall descope of an In
    Progress item stops at its Release's written mark, after its milestone call landed, so
    nothing shows who set the Release, and a person sets the item In Progress again, or, while
    the rerun stops at its first write and waits again, into review and back. The rerun
    finishes the move as it stands, with its comment, and leaves the Status as the person set
    it: its clock changed since the change began. The rerun used to write Ready over it, which
    fails `Stalled`, since the person's status change is new."""
    state = RoadmapLifecycle()
    (item,) = state.start(held=["Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.item_moves_on(change="In Progress", item=item),
        lambda: state.next_run_stops(at=4, later=True),
        lambda: state.days_pass(days=STALL_DAYS),
    )
    for n, status in enumerate(worked):
        if n < len(worked) - 1:
            state.next_run_stops(at=1, later=True)
        replay(state, lambda status=status: state.item_moves_on(change=status, item=item))
    found = state.view[item]
    assert (
        state.outstanding,
        state.stops,
        found.release,
        found.status,
        found.job_record.get(JobMark.PENDING),
        len(state.store.comments_on(item)),
    ) == (None, stops, "v1.0.1", "In Progress", None, 1)


def _a_top_up_moved_out_and_back(state: RoadmapLifecycle, at: int) -> int:
    """The admission rule sends a feature placed in started v1.0.0 to the backlog, the job's
    placement; v1.0.1's start pulls it in and stops at its write `at`: 4, the Release's job
    record; 5, its milestone call, once that record has landed. The rerun waits for the next
    poll and stops at its first write, then a person moves the feature to v1.0.2 and back to
    the backlog before the run after it."""
    _, feature = state.start(held=["Ready"], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.person_places(item=feature, place="current"),
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=at, later=True),
        lambda: state.ship(milestone_closed=True),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.person_places(item=feature, place="next"),
        lambda: state.person_places(item=feature, place="backlog"),
    )
    return int(feature)


def _a_top_up_moved_out_and_back_by_hand(at: int) -> tuple[object, ...]:
    state = RoadmapLifecycle()
    feature = _a_top_up_moved_out_and_back(state, at)
    found = state.view[feature]
    return (
        state.outstanding,
        state.stops,
        found.release,
        state.titled(found.job_record.get(JobMark.LEFT)),
        len(state.store.comments_on(feature)),
    )


def test_a_top_up_whose_milestone_call_never_landed_still_pulls_in_an_item_moved_out_and_back() -> (
    None
):
    """The tenth round's reviewers' replay: the ninth round dropped the job record of a begun
    Release a person set since, so when the top-up stopped at its milestone call, and a person
    moved the feature out of the backlog and back while the rerun waited, the feature read as
    the person's placement and stayed out, with a `Left` mark naming v1.0.2. The issue's events
    show the feature never joined v1.0.1, so the job's call never landed and the record from
    before it, the backlog where the job sent the feature, still names the job's placement: the
    start pulls it in, as when the run stops one write earlier, at the job record."""
    assert (_a_top_up_moved_out_and_back_by_hand(4), _a_top_up_moved_out_and_back_by_hand(5)) == (
        (None, ["record", "set_marks"], "v1.0.1", None, 2),
        (None, ["field", "set_marks"], "v1.0.1", None, 2),
    )


def _a_release_ships_while_the_start_before_it_waits(state: RoadmapLifecycle) -> int | None:
    """Seed 15007: v1.0.0 ships with its milestone open, and the run that starts v1.0.1 stops
    at its first write and waits; a person cuts v1.0.1, the rerun stops at its first write
    again, and v1.0.1 ships with its milestone open too."""
    (feature,) = state.start(held=[], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.ship(milestone_closed=False, published=True),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.cut(draft=False),
        lambda: state.ship(milestone_closed=False, published=True),
    )
    return int(feature)


def _a_release_ships_while_its_start_waits_to_close_the_one_before(
    state: RoadmapLifecycle, *, closed: bool = False
) -> int | None:
    """The start of v1.0.1 stops at its last write, the close of v1.0.0, and waits; a person
    cuts v1.0.1, the run that holds it to the rules stops at that close again, and v1.0.1 ships
    too, its milestone left open or, `closed`, closed by `release.yml`. The run record names
    v1.0.1, which has shipped since."""
    state.start(held=[], waiting=[])
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=4, later=True),
        lambda: state.ship(milestone_closed=False, published=True),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.cut(draft=False),
        lambda: state.ship(milestone_closed=closed, published=True),
    )
    return None


@pytest.mark.parametrize(
    ("steps", "stops"),
    [
        (_a_release_ships_while_the_start_before_it_waits, ["create_release"] * 2),
        (_a_release_ships_while_its_start_waits_to_close_the_one_before, ["close_release"] * 2),
        (
            lambda state: _a_release_ships_while_its_start_waits_to_close_the_one_before(
                state, closed=True
            ),
            ["close_release"] * 2,
        ),
    ],
    ids=["seed-15007-start-waits", "start-waits-to-close", "start-waits-to-close-milestone-closed"],
)
def test_a_release_that_ships_while_the_start_before_it_waits_is_closed_and_the_next_starts(
    steps: Callable[[RoadmapLifecycle], int | None], stops: list[str]
) -> None:
    """Seed 15007 of 200 examples of 70 steps, not derandomized, failed `Ship`: the run after
    v1.0.1's ship started v1.0.1, which had shipped. It pulled the backlog feature into it,
    admitted it there and closed only v1.0.0, and the next day's run closed v1.0.1 with the
    feature still in it. A start now skips every open release after the current one that has
    shipped too, and closes each of them last. When the run record already names the release
    that shipped since, as after a start that stopped at its close, the run starts the release
    after it too, rather than closing only the releases before the one the run record names and
    leaving that start to a later run. Each ends with v1.0.2 started, and the feature, if any,
    pulled into it.

    The twelfth round's reviewers added the third case: with v1.0.1's milestone closed, as
    `release.yml` closes it, v1.0.1 was not among the open shipped releases, so the run only
    closed v1.0.0, and the run record stayed on v1.0.1 until a later run was due. The machine
    kept v1.0.1 as the started release after the job had started v1.0.2, so every check of the
    current release was skipped: it now records that start too.

    Hypothesis printed the steps of the first, the waiting feature added."""
    state = RoadmapLifecycle()
    feature = steps(state)
    found = state.view[feature] if feature is not None else None
    assert (
        state.outstanding,
        state.closing,
        state.stops,
        state.open_titles[0],
        state.titled(state.store.run_record().get(JobMark.STARTED)),
        state.started,
        found and (found.release, state.titled(found.job_record.get(JobMark.ADMITTED))),
    ) == (None, False, stops, "v1.0.2", "v1.0.2", "v1.0.2", found and ("v1.0.2", "v1.0.2"))


def test_a_feature_placed_in_a_release_started_while_a_close_waited_goes_to_the_backlog() -> None:
    """The twelfth round's reviewers' replay of the third case above: a person then places a P2
    feature in v1.0.2. With v1.0.2 unstarted, a later start admitted it, with no comment; it
    joined after v1.0.2 started, so it goes to the backlog."""
    state = RoadmapLifecycle()
    _a_release_ships_while_its_start_waits_to_close_the_one_before(state, closed=True)
    late = state.file("late feature", "feature", "Ready", None)
    replay(state, lambda: state.person_places(item=late, place="current"))
    found = state.view[late]
    assert (
        state.current(),
        state.started,
        found.release,
        state.titled(found.job_record.get(JobMark.ADMITTED)),
        len(state.store.comments_on(late)),
    ) == ("v1.0.2", "v1.0.2", None, None, 1)


def _a_start_waits_and_its_release_is_cut(state: RoadmapLifecycle, closed: bool) -> int:
    """The start of v1.0.1 stops at its first write and waits; a person cuts v1.0.1, which the
    rerun starts, and ships it, its milestone `closed` by `release.yml` or left open. A Ready
    feature waits in the backlog throughout."""
    (feature,) = state.start(held=[], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.ship(milestone_closed=False, published=True),
        lambda: state.cut(draft=False),
        lambda: state.ship(milestone_closed=closed, published=True),
    )
    return int(feature)


def _a_pull_in_waits_and_its_release_ships(state: RoadmapLifecycle, at: int, closed: bool) -> int:
    """v1.0.1's start pulls a backlog feature in and stops at its write `at`: 4, the Release's
    job record; 5, its milestone call; 6, its written mark, after the milestone call landed. The
    rerun stops at its first write and waits; a person cuts v1.0.1 and ships it, its milestone
    `closed` or left open."""
    (feature,) = state.start(held=[], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=at, later=True),
        lambda: state.ship(milestone_closed=False),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.cut(draft=False),
        lambda: state.ship(milestone_closed=closed),
    )
    return int(feature)


def _a_descope_undone_and_its_comment_then_stopped(state: RoadmapLifecycle) -> int:
    """The stall descope of an In Progress item v1.0.0 started holding stops at its Status's
    written mark; a person puts the item back in v1.0.0, and the rerun posts the comment and
    stops at its last write, before a day passes."""
    held, _ = state.start(held=["In Progress", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=7, later=True),
        lambda: state.days_pass(days=STALL_DAYS + 1),
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.person_places(item=held, place="current"),
        lambda: state.days_pass(days=1),
    )
    return int(held)


def _a_descope_put_back_then_placed_by_hand(state: RoadmapLifecycle) -> int:
    """The descope of a Blocked item stops at its comment, its Release written; a person sets
    the item In Progress, so the rerun drops the change, and stops once it has put the Release
    back, before it clears the `Pending` mark; the person then places the item in v1.0.1, the
    change's own target."""
    _, blocked = state.start(held=["Ready", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=5, later=True),
        lambda: state.item_moves_on(item=blocked, change="Blocked"),
        lambda: state.next_run_stops(at=3, later=True),
        lambda: state.item_moves_on(item=blocked, change="In Progress"),
        lambda: state.person_places(item=blocked, place="next"),
    )
    return int(blocked)


def _a_stall_put_back_then_readied_by_hand(state: RoadmapLifecycle) -> int:
    """The stall descope of an In Progress item stops at its comment, its Release and Status
    written; a person sets the item In Progress, so the rerun drops the change, and stops once
    it has put the Release back; the person then sets the item Ready, the change's own value."""
    held, _ = state.start(held=["In Progress", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=8, later=True),
        lambda: state.days_pass(days=STALL_DAYS + 1),
        lambda: state.next_run_stops(at=3, later=True),
        lambda: state.item_moves_on(item=held, change="In Progress"),
        lambda: state.item_goes_back_to_ready(item=held),
    )
    return int(held)


def _a_descope_whose_item_went_out_and_back_first(state: RoadmapLifecycle) -> int:
    """The descope of a Blocked item stops at its Release's job record; a person moves the item
    to v1.0.1, so the rerun drops the change, and stops before it clears the `Pending` mark;
    the person moves it back, and that rerun finishes the descope but stops at its comment."""
    _, blocked = state.start(held=["Ready", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.item_moves_on(item=blocked, change="Blocked"),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.person_places(item=blocked, place="next"),
        lambda: state.next_run_stops(at=4, later=True),
        lambda: state.person_places(item=blocked, place="current"),
        lambda: state.days_pass(days=1),
    )
    return int(blocked)


@pytest.mark.parametrize(
    ("steps", "stops", "expected"),
    [
        (
            lambda state: _a_start_waits_and_its_release_is_cut(state, closed=True),
            ["create_release"],
            ("v1.0.2", "Ready", "v1.0.2", 1),
        ),
        (
            lambda state: _a_start_waits_and_its_release_is_cut(state, closed=False),
            ["create_release"],
            ("v1.0.2", "Ready", "v1.0.2", 1),
        ),
        (
            lambda state: _a_pull_in_waits_and_its_release_ships(state, at=4, closed=True),
            ["record", "set_marks"],
            ("v1.0.2", "Ready", "v1.0.2", 1),
        ),
        (
            lambda state: _a_pull_in_waits_and_its_release_ships(state, at=5, closed=True),
            ["field", "set_marks"],
            ("v1.0.2", "Ready", "v1.0.2", 1),
        ),
        (
            lambda state: _a_pull_in_waits_and_its_release_ships(state, at=4, closed=False),
            ["record", "set_marks"],
            ("v1.0.2", "Ready", "v1.0.2", 1),
        ),
        (
            lambda state: _a_pull_in_waits_and_its_release_ships(state, at=6, closed=True),
            ["set_marks", "comment"],
            ("v1.0.1", "Ready", "v1.0.1", 1),
        ),
        (
            _a_descope_undone_and_its_comment_then_stopped,
            ["set_marks", "comment"],
            ("v1.0.0", "Ready", "v1.0.0", 1),
        ),
        (
            _a_descope_put_back_then_placed_by_hand,
            ["comment", "set_marks"],
            ("v1.0.1", "In Progress", None, 0),
        ),
        (
            _a_stall_put_back_then_readied_by_hand,
            ["comment", "set_marks"],
            ("v1.0.0", "Ready", "v1.0.0", 0),
        ),
        (
            _a_descope_whose_item_went_out_and_back_first,
            ["record", "set_marks", "comment"],
            ("v1.0.1", "Blocked", None, 1),
        ),
    ],
    ids=[
        "cut-before-its-start-milestone-closed",
        "cut-before-its-start-milestone-open",
        "pull-in-at-its-record-then-shipped",
        "pull-in-at-its-milestone-call-then-shipped",
        "pull-in-at-its-record-then-shipped-milestone-open",
        "pull-in-landed-then-shipped",
        "descope-undone-before-its-comment",
        "written-release-put-back-then-placed",
        "written-status-put-back-then-readied",
        "out-and-back-before-its-release-write",
    ],
)
def test_the_twelfth_rounds_job_replays_end_where_the_rules_put_each_item(
    steps: Callable[[RoadmapLifecycle], int],
    stops: list[str],
    expected: tuple[object, ...],
) -> None:
    """The twelfth round's reviewers' replays of the job, through the machine:

    - A start of a release a person cut while the start waited topped it up from the backlog,
      past the cut lock; once it shipped, the feature sat Ready in its closed milestone. The
      start pulls nothing into a cut release now, and the feature joins v1.0.2 at its start.
    - A pull-in whose milestone call never landed was finished after its release shipped,
      moving the feature into the shipped release. It is dropped now, and v1.0.2's start pulls
      the feature in. One whose milestone call landed before the ship stays with that release.
    - A descope a person undid before its comment kept the item's admission only while the run
      that posted the comment finished; stopped before its last write, the next run cleared the
      mark and sent the item to the backlog as a join. Its `Pending` mark keeps that now.
    - A dropped change's revert put the field back and stopped before clearing its mark; a
      person then set the change's own value, which the next run took for the job's write:
      it moved the item out of v1.0.1 where the person placed it, or took the Status clock
      from before the change and readied and descoped an item the person had just worked on.
      A written field is the job's only until it changes since.
    - Counted from the change's start, a Release write after a person moved the item out and
      back read as changed since the job wrote it, and the next run dropped the job's own move,
      uncommented. The count starts when the Release write begins now.

    The machine missed the first two: its cut and ship checks skipped a start."""
    state = RoadmapLifecycle()
    number = steps(state)
    found = state.view[number]
    assert (
        state.outstanding,
        state.stops,
        (
            found.release,
            found.status,
            state.titled(found.job_record.get(JobMark.ADMITTED)),
            len(state.store.comments_on(number)),
        ),
    ) == (None, stops, expected)


def _two_ships_while_a_close_waits_then_a_fix_moved(state: RoadmapLifecycle) -> int:
    """C: v1.0.0 and then v1.0.1 ship while the start of v1.0.1 waits to close v1.0.0; the run
    after the second ship starts v1.0.2, and a person cuts it and moves a fix into it."""
    state.start(held=[], waiting=[])
    fix = state.critical_fix_filed(kind="bug", status="New")
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=4, later=True),
        lambda: state.ship(milestone_closed=False),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.ship(milestone_closed=False),
        lambda: state.next_run_stops(at=1, later=True),
        lambda: state.cut(draft=False),
        lambda: state.person_places(item=fix, place="later"),
    )
    return fix


def _a_move_and_its_comment_in_two_stopped_runs(state: RoadmapLifecycle) -> int:
    """F: the dependency descope of a held feature stops at its comment, the rerun posts it and
    stops at its last write; a person puts the feature back."""
    held, waiting = state.start(held=["Ready"], waiting=["feature"]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=5, later=True),
        lambda: state.dependency_added(item=held, on=waiting),
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.dependency_added(item=held, on=held),
        lambda: state.person_places(item=held, place="current"),
    )
    return int(held)


def _a_cut_lock_move_into_a_release_that_ships_too(state: RoadmapLifecycle) -> int:
    """A: the cut lock's move of a fix out of v1.0.0 waits while v1.0.0 and then v1.0.1 ship,
    and the start of v1.0.2 finishes it into closed v1.0.1."""
    state.start(held=[], waiting=[])
    filed: list[int] = []
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=2, later=True),
        lambda: filed.append(state.critical_fix_filed(kind="bug", status="New")),
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.ship(milestone_closed=True),
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.cut(draft=False),
        lambda: state.ship(milestone_closed=False),
    )
    return filed[0]


def _a_fix_admitted_while_a_close_waits_then_made_p1(state: RoadmapLifecycle) -> int:
    """B: while the start of v1.0.1 waits to close v1.0.0, the run that admits a fix filed into
    v1.0.1 posts its comment and stops at its last write; a person makes the fix P1."""
    state.start(held=[], waiting=[])
    filed: list[int] = []
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=4, later=True),
        lambda: state.ship(milestone_closed=False),
        lambda: state.next_run_stops(at=3, later=True),
        lambda: filed.append(state.critical_fix_filed(kind="bug", status="New")),
        lambda: state.person_reprioritizes(item=filed[0], priority="P1-High"),
    )
    return filed[0]


def _a_fix_moved_by_a_stopped_rerun_then_closed(state: RoadmapLifecycle) -> int:
    """E: the cut lock's move of a fix stops at its comment and waits; a second fix is filed,
    the rerun moves it on and stops at its comment too, and a person closes the second fix."""
    state.start(held=[], waiting=[])
    filed: list[int] = []
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=5, later=True),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
        lambda: state.next_run_stops(at=7, later=True),
        lambda: filed.append(state.critical_fix_filed(kind="bug", status="New")),
        lambda: state.item_moves_on(item=filed[0], change="closes"),
    )
    return filed[0]


def _a_cap_descope_announced_by_a_stopped_rerun(state: RoadmapLifecycle) -> int:
    """(b): a fix filed into the full release descopes a held feature, whose written mark
    fails; the rerun posts the comment and stops at its last write; a person puts the feature
    back the next day."""
    *_, victim = state.start(held=["Ready"] * CAP, waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=4, later=True),
        lambda: state.critical_fix_filed(kind="bug", status="Ready"),
        lambda: state.next_run_stops(at=2, later=True),
        lambda: state.days_pass(days=1),
        lambda: state.person_places(item=victim, place="current"),
    )
    return int(victim)


def _a_stalled_fix_reprioritized_then_worked_on(state: RoadmapLifecycle) -> int:
    """(c): an idle In Progress fix is readied, and that run stops at its comment; a person
    makes it P1, the rerun puts the Status back and descopes it, and stops at the Release's
    written mark; the person sets it In Progress, right after that run."""
    fix = state.file("fix", "bug", "In Progress", "v1.0.0")
    state.file("feature", "feature", "In Progress", "v1.0.0")
    state.poll()
    state.now += timedelta(days=STALL_DAYS + 1)
    replay(
        state,
        lambda: state.next_run_stops(at=5, later=True),
        lambda: state.person_places(item=fix, place="current"),
        lambda: state.next_run_stops(at=6, later=True),
        lambda: state.person_reprioritizes(item=fix, priority="P1-High"),
        lambda: state.item_moves_on(item=fix, change="In Progress"),
    )
    return fix


@pytest.mark.parametrize(
    ("steps", "stops", "expected"),
    [
        (
            _two_ships_while_a_close_waits_then_a_fix_moved,
            ["close_release", "close_release", "create_release", "create_release"],
            ("v1.0.2", "New", "v1.0.2", 1),
        ),
        (
            _a_move_and_its_comment_in_two_stopped_runs,
            ["comment", "set_marks"],
            (None, "Ready", None, 2),
        ),
        (
            _a_cut_lock_move_into_a_release_that_ships_too,
            ["record", "create_branch", "record"],
            ("v1.0.1", "New", None, 1),
        ),
        (
            _a_fix_admitted_while_a_close_waits_then_made_p1,
            ["close_release", "set_marks"],
            ("v1.0.1", "New", "v1.0.1", 1),
        ),
        (
            _a_fix_moved_by_a_stopped_rerun_then_closed,
            ["comment", "comment"],
            ("v1.0.0", "Done", None, 1),
        ),
        (
            _a_cap_descope_announced_by_a_stopped_rerun,
            ["set_marks", "set_marks"],
            (None, "Ready", None, 2),
        ),
        (
            _a_stalled_fix_reprioritized_then_worked_on,
            ["comment", "set_marks"],
            ("v1.0.1", "In Progress", None, 1),
        ),
    ],
    ids=[
        "c-a-start-after-a-waiting-close",
        "f-a-move-and-its-comment-apart",
        "a-every-release-that-shipped",
        "b-the-release-under-way",
        "e-an-item-filed-in-the-window",
        "b-the-window-and-unseen-exits",
        "c-a-clock-tick",
    ],
)
def test_the_machines_own_errors_the_twelfth_rounds_reviewers_found(
    steps: Callable[[RoadmapLifecycle], int], stops: list[str], expected: tuple[object, ...]
) -> None:
    """Each failed the eleventh round's machine, on the job as it was and as it is; the job is
    right in each:

    - C: a run that starts a release after a close waited, another release having shipped
      meanwhile, was not recorded as a start: the machine kept the older release as started,
      and read the cut and the fix after it as a join to a cut release (`Cut`).
    - F: an admitted item one stopped run moved out and a later one announced stayed in the
      machine's admitted set, so the person's return, a new join, failed `held`.
    - A: only the last release that shipped while a run waited counted as shipped, so the
      finished cut-lock move into the release that shipped first failed `stands`.
    - B: while a close waited, a stopped run's announced admission to the release under way
      went unrecorded, and the fix made P1 failed `admitted`.
    - E: an item filed after the window began was judged from the finishing run's view, so
      the job's undo of a move a stopped rerun made failed `reason`.
    - (b): an announced move was checked against the roadmap before the rerun, not before the
      window, and its exit stayed among the unseen ones, so `held` failed.
    - (c): the clock moved only at polls, so a person's Status edit right after a run carried
      the job's own timestamp and the job could not see it (`Stalled`): a second passes now
      after each poll."""
    state = RoadmapLifecycle()
    number = steps(state)
    found = state.view[number]
    assert (
        state.outstanding,
        state.stops,
        (
            found.release,
            found.status,
            state.titled(found.job_record.get(JobMark.ADMITTED)),
            len(state.store.comments_on(number)),
        ),
    ) == (None, stops, expected)


# ── GitHub's calls failing twice (#740) ───────────────────────────────────────
# Each gh write of a run can fail before it applies, or after, and so can a write of the run
# that follows. The sweep fails one write of a run, either way, then one write of the rerun or
# none, runs the job until a run finishes, and compares what the roadmap holds with the same
# run left alone. A field write is GitHub's two calls throughout.


def _ship_unpolled(state: RoadmapLifecycle, *, milestone_closed: bool) -> RoadmapLifecycle:
    """The release under way ships, and no poll has run the job since."""
    if state.release_pr is None:
        state.cut_release = state.under_way()
        state.release_pr = state.open_release_pull_request(draft=False)
    state.ship_pull_request(state.release_pr)
    state.release_pr = None
    state.published(milestone_closed, poll=False)
    return state


def _before_the_first_run() -> RoadmapLifecycle:
    state = RoadmapLifecycle()
    for n, status in enumerate(("Ready", "In Progress", "New", "Blocked")):
        state.file(f"held {n}", "feature", status, "v1.0.0")
    state.file("waiting", "feature", "Ready", None)
    return state


def _before_a_top_up() -> RoadmapLifecycle:
    """The reviewers' top-up: a Ready critical fix and a feature wait in the backlog."""
    state = RoadmapLifecycle()
    state.start(held=["Ready"], waiting=[])
    state.file("next", "feature", "Ready", "v1.0.1")
    state.file("backlog fix", "bug", "Ready", None)
    state.file("backlog feature", "feature", "Ready", None)
    return _ship_unpolled(state, milestone_closed=True)


def _before_a_trim() -> RoadmapLifecycle:
    state = RoadmapLifecycle()
    state.start(held=["Ready"], waiting=[])
    for n, kind in enumerate(("feature", "p0_feature", "feature", "feature", "feature")):
        state.file(f"next {n}", kind, "Ready", "v1.0.1")
    state.file("new", "feature", "New", "v1.0.1")
    state.file("blocked fix", "bug", "Blocked", "v1.0.1")
    return _ship_unpolled(state, milestone_closed=False)


def _before_a_first_run_at_a_ship() -> RoadmapLifecycle:
    state = RoadmapLifecycle()
    state.file("next", "feature", "Ready", "v1.0.1")
    state.file("blocked", "feature", "Blocked", "v1.0.1")
    state.file("backlog feature", "feature", "Ready", None)
    return _ship_unpolled(state, milestone_closed=False)


def _before_the_rules() -> RoadmapLifecycle:
    """Admission of a feature, a P0 feature and a fix, the cap, Blocked, a stall and a nudge."""
    state = RoadmapLifecycle()
    held = state.start(held=["Ready"] * CAP + ["In Progress", "In Review"], waiting=[]).values  # type: ignore[attr-defined]
    state.now += timedelta(days=STALL_DAYS + 1)
    state.person.set_field(state.store.item(held[0]), ItemField.STATUS, "Blocked")  # type: ignore[arg-type]
    for title, kind in (("late feature", "feature"), ("p0 feature", "p0_feature"), ("fix", "bug")):
        state.file(title, kind, "Ready", "v1.0.0")
    return state


def _before_the_stalls() -> RoadmapLifecycle:
    """An idle In Progress fix and feature: the fix goes back to Ready, the feature leaves too."""
    state = RoadmapLifecycle()
    state.file("fix", "bug", "In Progress", "v1.0.0")
    state.file("feature", "feature", "In Progress", "v1.0.0")
    state.poll()
    state.now += timedelta(days=STALL_DAYS + 1)
    return state


def _pulled_in(state: RoadmapLifecycle, *, next_items: int = 1) -> int:
    """v1.0.0 started holding a Ready feature, and v1.0.1, holding `next_items` features a person
    placed, starts once v1.0.0 ships: its top-up pulls a Ready backlog feature in, the job's
    placement."""
    state.start(held=["Ready"], waiting=[])
    for n in range(next_items):
        state.file(f"next {n}", "feature", "Ready", "v1.0.1")
    pulled = state.file("backlog feature", "feature", "Ready", None)
    _ship_unpolled(state, milestone_closed=True)
    state.poll()
    assert state.view[pulled].release == "v1.0.1"
    return pulled


def _before_a_pulled_in_item_is_blocked() -> RoadmapLifecycle:
    """The job pulled a feature into v1.0.1, and a person sets it Blocked: it is descoped."""
    state = RoadmapLifecycle()
    pulled = _pulled_in(state)
    state.person.set_field(state.store.item(pulled), ItemField.STATUS, "Blocked")  # type: ignore[arg-type]
    return state


def _before_a_pulled_in_item_stalls() -> RoadmapLifecycle:
    """The job pulled a feature into v1.0.1, a person starts it, and it goes idle: it goes
    back to Ready and is descoped."""
    state = RoadmapLifecycle()
    pulled = _pulled_in(state)
    state.person.set_field(state.store.item(pulled), ItemField.STATUS, "In Progress")  # type: ignore[arg-type]
    state.now += timedelta(days=STALL_DAYS + 1)
    return state


def _before_a_pulled_in_item_makes_room() -> RoadmapLifecycle:
    """The job pulled a feature into v1.0.1, which a person filled to its cap, and a critical
    fix is filed into it: the feature, the newest of the lowest-ranked, makes room."""
    state = RoadmapLifecycle()
    _pulled_in(state, next_items=CAP - 1)
    state.file("fix", "bug", "Ready", "v1.0.1")
    return state


def _before_a_descoped_item_is_new_at_the_start() -> RoadmapLifecycle:
    """The job descoped a Blocked feature from v1.0.0 to v1.0.1, a person sets it New, and
    v1.0.0 ships: v1.0.1's start sends it to the backlog."""
    state = RoadmapLifecycle()
    _, blocked = state.start(held=["Ready", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    state.item_moves_on(item=blocked, change="Blocked")
    assert state.view[blocked].release == "v1.0.1"
    state.person.set_field(state.store.item(blocked), ItemField.STATUS, "New")  # type: ignore[arg-type]
    return _ship_unpolled(state, milestone_closed=True)


def _before_a_backlog_left_item_starts(status: str) -> RoadmapLifecycle:
    """The job sent a feature filed into v1.0.0 after its start to the backlog; a person places
    it in v1.0.1, which the next run marks as taken out of the backlog where the job placed it,
    and sets it `status`; v1.0.0 ships: v1.0.1's start sends it back to the backlog, which
    clears the mark."""
    state = RoadmapLifecycle()
    state.start(held=["Ready"], waiting=[])
    late = state.file("late feature", "feature", "Ready", "v1.0.0")
    state.poll()
    state.person_places(item=late, place="next")
    assert state.view[late].job_record.get(JobMark.LEFT) == "backlog"
    state.person.set_field(state.store.item(late), ItemField.STATUS, status)  # type: ignore[arg-type]
    return _ship_unpolled(state, milestone_closed=True)


def _before_an_admitted_item_comes_back() -> RoadmapLifecycle:
    """A person takes a feature v1.0.0 started holding to the backlog, which the next run marks
    as taken out of v1.0.0, and puts it back: it joined after the start, and goes to the
    backlog, which clears the mark."""
    state = RoadmapLifecycle()
    held, _ = state.start(held=["Ready", "Ready"], waiting=[]).values  # type: ignore[attr-defined]
    state.person_places(item=held, place="backlog")
    assert state.titled(state.view[held].job_record.get(JobMark.LEFT)) == "v1.0.0"
    state.person.set_field(state.store.item(held), ItemField.RELEASE, "v1.0.0")  # type: ignore[arg-type]
    return state


def _before_a_pulled_in_item_comes_back() -> RoadmapLifecycle:
    """The job pulled a feature into v1.0.1; a person takes it to the backlog, which the next
    run marks as taken out of v1.0.1, and puts it back: it goes to the backlog."""
    state = RoadmapLifecycle()
    pulled = _pulled_in(state)
    state.person_places(item=pulled, place="backlog")
    assert state.titled(state.view[pulled].job_record.get(JobMark.LEFT)) == "v1.0.1"
    state.person.set_field(state.store.item(pulled), ItemField.RELEASE, "v1.0.1")  # type: ignore[arg-type]
    return state


def _before_a_fix_joins_idle(status: str) -> RoadmapLifecycle:
    """A critical fix has waited in v1.0.2 with `status` for longer than the stall window, and a
    person moves it into v1.0.0, which started empty: one change admits it and readies it, In
    Progress, or nudges it, In Review."""
    state = RoadmapLifecycle()
    state.start(held=[], waiting=[])
    fix = state.file("fix", "bug", status, "v1.0.2")
    state.poll()
    state.now += timedelta(days=STALL_DAYS + 1)
    state.person.set_field(state.store.item(fix), ItemField.RELEASE, "v1.0.0")  # type: ignore[arg-type]
    return state


SWEPT = MappingProxyType(
    {
        "first-run": _before_the_first_run,
        "top-up": _before_a_top_up,
        "trim": _before_a_trim,
        "first-run-at-a-ship": _before_a_first_run_at_a_ship,
        "rules": _before_the_rules,
        "stalls": _before_the_stalls,
        "pulled-in-then-blocked": _before_a_pulled_in_item_is_blocked,
        "pulled-in-then-stalled": _before_a_pulled_in_item_stalls,
        "pulled-in-then-room-made": _before_a_pulled_in_item_makes_room,
        "descoped-then-new-at-start": _before_a_descoped_item_is_new_at_the_start,
        "backlog-left-then-blocked-at-start": lambda: _before_a_backlog_left_item_starts("Blocked"),
        "backlog-left-then-new-at-start": lambda: _before_a_backlog_left_item_starts("New"),
        "admitted-out-and-back": _before_an_admitted_item_comes_back,
        "pulled-in-out-and-back": _before_a_pulled_in_item_comes_back,
        "fix-joins-stalled": lambda: _before_a_fix_joins_idle("In Progress"),
        "fix-joins-idle-in-review": lambda: _before_a_fix_joins_idle("In Review"),
    }
)
# A write fails before it applies, or applies and then reports the failure.
APPLIED = (False, True)


def _job_ran(state: RoadmapLifecycle, fault: Fault) -> bool:
    """One run with `fault`; whether it finished."""
    plan = reprioritize.plan_reprioritization(state.store, repo=REPO, config=CONFIG, now=state.now)
    try:
        reprioritize.apply_reprioritization(StoppingStore(state.store, fault).as_store(), plan)
    except GitHubOperationError:
        return False
    return True


def _writes_of_the_next_run(state: RoadmapLifecycle) -> int:
    """How many writes the next run makes, as it makes them."""
    plan = reprioritize.plan_reprioritization(state.store, repo=REPO, config=CONFIG, now=state.now)
    counted = StoppingStore(state.store)
    reprioritize.apply_reprioritization(counted.as_store(), plan)
    return len(counted.writes)


def _settled(state: RoadmapLifecycle) -> tuple[object, ...]:
    """Everything the roadmap holds once runs have made every write the job has left, three at
    most: Releases, branches, the run record, each item's place, Status and marks, and the
    comments on it. A first run leaves an item already Blocked to the run after it, and a run
    whose last write applied and reported a failure has finished, so its rerun is that next
    run."""
    store = state.store
    for _ in range(3):
        plan = reprioritize.plan_reprioritization(store, repo=REPO, config=CONFIG, now=state.now)
        if not plan.has_writes:
            break
        reprioritize.apply_reprioritization(store, plan)
    items, releases = store.items(), store.releases()
    return (
        plan.has_writes,
        [(release.title, release.state) for release in releases],
        [store.branch(f"release/{release.title}") for release in releases],
        store.run_record(),
        [
            (item.number, item.release, item.status, *(item.job_record.get(m) for m in JobMark))
            for item in items
        ],
        [store.comments_on(item.number) for item in items],
    )


def _recorded(store: InMemoryRoadmapStore) -> list[tuple[object, ...]]:
    """Each item's job record of its Release and Status."""
    fields = (ItemField.RELEASE, ItemField.STATUS)
    return [
        (item.number, *(item.job_record.get(f, "none") for f in fields)) for item in store.items()
    ]


@dataclass
class SweepCounts:
    """What a sweep ran and found: its cases, those whose rerun failed too, those that settled
    other than the run left alone did, and those that left a job record without a value the job
    had set."""

    cases: int = 0
    double: int = 0
    diverged: list[str] = dataclass_field(default_factory=list)
    unclaimed: list[str] = dataclass_field(default_factory=list)


def _fault_name(fault: Fault) -> str:
    return f"{fault.at}{' applied' if fault.applied else ''}" if fault.at else "none"


def _sweep(
    name: str,
    build: Callable[[], RoadmapLifecycle],
    counts: SweepCounts,
    *,
    twice: bool,
    firsts: Sequence[Fault] = (),
) -> None:
    """Fail each write of the run `build` leaves due, before and after it applies, or only the
    `firsts`; with `twice`, fail each write of the rerun too, either way; then run the job until
    a run finishes; once settled, compare the roadmap with the one the run left alone settles
    to."""
    whole = build()
    writes = _writes_of_the_next_run(whole)
    expected, records = _settled(whole), _recorded(whole.store)
    every = (Fault(at, applied) for at in range(1, writes + 1) for applied in APPLIED)
    for first in firsts or every:
        reruns = [Fault()]
        if twice:
            probe = build()
            _job_ran(probe, first)
            rerun = _writes_of_the_next_run(probe)
            reruns += [Fault(at, applied) for at in range(1, rerun + 1) for applied in APPLIED]
        for second in reruns:
            state = build()
            for fault in (first, second, Fault()):
                if _job_ran(state, fault):
                    break
            case = f"{name}: {_fault_name(first)}, then {_fault_name(second)}"
            counts.cases += 1
            counts.double += second.at > 0
            if _settled(state) != expected:
                counts.diverged.append(case)
            elif _recorded(state.store) != records:
                counts.unclaimed.append(case)


def test_a_run_whose_gh_calls_fail_before_or_after_applying_ends_as_the_run_left_alone() -> None:
    """The reviewers' double-fault sweep, at the gate's size: v1.0.1's start, which tops it up
    with a Ready critical fix from the backlog, fails at each of its writes, before the write
    applies and after, and the next run finishes it; and once the fix's job record has landed
    without its milestone (the record call failing after it applied, or the milestone call
    failing), each write of the rerun fails too, either way, before a third run. Each settles
    where the start left alone does. `DEVOPS_PROPERTY_PROFILE=deep` runs the whole sweep:
    sixteen scenarios, each write of each failing either way, then each write of the rerun
    either way or none, and prints its counts."""
    counts = SweepCounts()
    if _DEEP:
        for name, build in SWEPT.items():
            _sweep(name, build, counts, twice=True)
    else:
        build = SWEPT["top-up"]
        fix = next(item.number for item in build().store.items() if item.title == "backlog fix")
        _sweep("top-up", build, counts, twice=False)
        landed = [Fault(1, True, RECORD, fix), Fault(1, False, FIELD, fix)]
        _sweep("top-up", build, counts, twice=True, firsts=landed)
    if _DEEP:
        print(
            f"cases {counts.cases}, rerun failing too {counts.double}, diverged "
            f"{len(counts.diverged)}, unclaimed {len(counts.unclaimed)}"
        )
    expected = (counts.cases, counts.double) if _DEEP else (86, 52)
    assert (counts.cases, counts.double, counts.diverged) == (*expected, [])


@pytest.mark.parametrize(
    ("name", "moved", "expected"),
    [
        ("pulled-in-then-blocked", "backlog feature", (22, 8)),
        ("pulled-in-then-stalled", "backlog feature", (40, 20)),
        ("pulled-in-then-room-made", "backlog feature", (40, 20)),
        ("descoped-then-new-at-start", "held 1", (32, 12)),
        ("backlog-left-then-blocked-at-start", "late feature", (32, 12)),
        ("backlog-left-then-new-at-start", "late feature", (32, 12)),
        ("admitted-out-and-back", "held 0", (22, 8)),
        ("pulled-in-out-and-back", "backlog feature", (22, 8)),
    ],
    ids=[
        "blocked",
        "stalled",
        "room-made",
        "new-at-start",
        "backlog-left-then-blocked-at-start",
        "backlog-left-then-new-at-start",
        "admitted-out-and-back",
        "pulled-in-out-and-back",
    ],
)
def test_a_move_of_an_item_the_job_placed_whose_gh_calls_fail_ends_as_the_run_left_alone(
    name: str, moved: str, expected: tuple[int, int]
) -> None:
    """The reviewers' sweep of moves of an item a job placed, at the gate's size: a feature
    v1.0.1's top-up pulled in is set Blocked, stalls, or makes room for a critical fix, or a
    feature the job descoped to v1.0.1 is New when v1.0.1 starts, and the run that moves it
    again fails at each of its writes, before the write applies and after; and once its
    milestone call has landed with nothing to show the job made it (the call reporting a
    failure after it applied, or the written mark after it failing), each write of the rerun
    fails too, either way. Each settles where the run left alone does, with no `Left` mark: the
    job's own move is never read as a person taking the item out of the place the job had put
    it.

    The last four move an item that carries a `Left` mark: one a person took out of the backlog
    where the job sent it, New or Blocked when its release starts, and an admitted or pulled-in
    feature a person took out and put back. A move whose milestone call landed unconfirmed kept
    the stale mark, such as `Left=backlog` on an item in the backlog, until it cleared the mark
    as a confirmed one does; one fault was enough."""
    build = SWEPT[name]
    number = next(item.number for item in build().store.items() if item.title == moved)
    counts = SweepCounts()
    _sweep(name, build, counts, twice=False)
    landed = [Fault(1, True, FIELD, number), Fault(2, False, "set_marks", number)]
    _sweep(name, build, counts, twice=True, firsts=landed)
    assert (counts.cases, counts.double, counts.diverged) == (*expected, [])


@pytest.mark.parametrize(
    ("name", "expected"),
    [("fix-joins-stalled", (26, 12)), ("fix-joins-idle-in-review", (14, 6))],
    ids=["stalled", "idle-in-review"],
)
def test_a_fix_readied_or_nudged_as_it_joins_whose_gh_calls_fail_ends_as_the_run_left_alone(
    name: str, expected: tuple[int, int]
) -> None:
    """The reviewers' sweep of a critical fix that joins idle, at the gate's size: one change
    admits it and readies it, or nudges it, and each write of that run fails, before it applies
    and after; and once the change's `Pending` mark has landed, or its comment, each reporting a
    failure, each write of the rerun fails too, either way. Each settles where the run left
    alone does. The admission was a mark written after every change, so a rerun found the fix
    unadmitted, and admitted it again with a second comment; one fault was enough."""
    build = SWEPT[name]
    number = next(item.number for item in build().store.items() if item.title == "fix")
    counts = SweepCounts()
    _sweep(name, build, counts, twice=False)
    landed = [Fault(1, True, "set_marks", number), Fault(1, True, "comment", number)]
    _sweep(name, build, counts, twice=True, firsts=landed)
    assert (counts.cases, counts.double, counts.diverged) == (*expected, [])


def _a_cap_descope_then_a_cut(state: RoadmapLifecycle) -> int:
    """Seed 502: a fix filed into the full release descopes a held feature, whose milestone call
    lands and whose written mark fails; the release is cut before the rerun."""
    *_, victim = state.start(held=["Ready"] * CAP, waiting=[]).values  # type: ignore[attr-defined]
    replay(
        state,
        lambda: state.next_run_stops(at=4, later=True),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
        lambda: state.cut(draft=False),
    )
    return int(victim)


def _a_cut_lock_move_then_an_uncut(state: RoadmapLifecycle) -> int:
    """Seed 510: a fix filed into the cut release goes on to the next, its milestone call lands
    and its written mark fails; the release pull request is closed before the rerun."""
    state.start(held=[], waiting=[])
    replay(
        state,
        lambda: state.cut(draft=False),
        lambda: state.next_run_stops(at=4, later=True),
        lambda: state.critical_fix_filed(kind="bug", status="New"),
        lambda: state.uncut(),
    )
    return max(state.view)


def _a_size_descope_then_a_reprioritization(state: RoadmapLifecycle) -> int:
    """Seed 512: four fixes fill a release that started empty; a person makes the last one P1,
    so the size descopes it, its milestone call lands and its written mark fails; the person
    makes it P0 again before the rerun."""
    state.start(held=[], waiting=[])
    fixes = [state.critical_fix_filed(kind="bug", status="New") for _ in range(CAP + 1)]
    replay(
        state,
        lambda: state.next_run_stops(at=4, later=True),
        lambda: state.person_reprioritizes(item=fixes[-1], priority="P1-High"),
        lambda: state.person_reprioritizes(item=fixes[-1], priority="P0-Critical"),
    )
    return fixes[-1]


@pytest.mark.parametrize(
    ("steps", "comments"),
    [
        (_a_cap_descope_then_a_cut, 1),
        (_a_cut_lock_move_then_an_uncut, 1),
        (_a_size_descope_then_a_reprioritization, 2),
    ],
    ids=["seed-502-cap-then-cut", "seed-510-cut-lock-then-uncut", "seed-512-size-then-p0"],
)
def test_a_move_whose_milestone_call_landed_unrecorded_is_finished_whatever_changed_since(
    steps: Callable[[RoadmapLifecycle], int], comments: int
) -> None:
    """Sweeps of 300 examples of 40 steps (seeds 502, 510 and 512, not derandomized) failed on
    this fix round's first rule, which judged such a move again and, the rules no longer
    deciding it after a cut, an un-cut or a reprioritization, took its Release for a person's
    and dropped it: the job's own move stood with no comment. Its milestone call landed, but
    its written mark failed, so nothing shows the job set the Release, and nothing can tell it
    from a person's: the rerun finishes the move as one that happened, with its comment."""
    state = RoadmapLifecycle()
    number = steps(state)
    assert (
        state.outstanding,
        state.stops,
        state.view[number].release,
        len(state.store.comments_on(number)),
    ) == (None, ["set_marks"], "v1.0.1", comments)

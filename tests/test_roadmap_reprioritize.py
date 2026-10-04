"""`devops roadmap reprioritize` over the in-memory roadmap store (#740).

Each case builds a roadmap as a person leaves it, runs the job at an injected `now`, and reads
back what the store holds and what the job wrote. No case runs `gh` or opens a socket.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp import server as mcp_server
from devops_cli.commands.roadmap import app
from devops_cli.config.constants import (
    CONST_ROADMAP_NEEDS_SPLIT_LABEL,
    CONST_ROADMAP_PREMIGRATE_STATUSES,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_MEMORY_HEAD_SHA
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.labels import load_label_specs
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore, JobWrite
from devops_cli.roadmap.reprioritize import (
    ReleaseState,
    ReprioritizationPlan,
    apply_reprioritization,
    is_due,
    plan_reprioritization,
    render_plan,
)
from devops_cli.roadmap.store import (
    CardKind,
    Change,
    ChangeKind,
    CloseReason,
    FieldOption,
    FieldSpec,
    GitHubState,
    Item,
    ItemField,
    JobMark,
)
from tests.roadmap_faults import FIELD, RECORD, Fault, StoppingStore

REPO = "example/roadmap"
NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
CURRENT, NEXT, LATER = "v0.2.25", "v0.2.26", "v0.2.27"
CONFIG = RoadmapConfig(board=1)
OPTIONS = {
    ItemField.STATUS: ("New", "Ready", "In Progress", "In Review", "Done", "Blocked"),
    ItemField.PRIORITY: ("P0-Critical", "P1-High", "P2-Medium", "P3-Low"),
    ItemField.VALUE: ("High", "Medium", "Low"),
    ItemField.EFFORT: ("Low", "Medium", "High"),
}
LABELS = {
    "feature": "type/feature",
    "bug": "type/bug",
    "security": "type/security",
    "epic": "type/epic",
}
SIGNATURE = " (devops roadmap reprioritize)"

runner = CliRunner()


class Roadmap:
    """One repository's roadmap, a person who edits it, and the calendar the job runs at."""

    def __init__(self, store: InMemoryRoadmapStore | None = None) -> None:
        self.now = NOW
        self.config = CONFIG
        self.store = store or InMemoryRoadmapStore(board_options=OPTIONS, clock=self.clock)
        self.person = self.store.as_actor("alice")
        for title in (CURRENT, NEXT, LATER):
            self.store.create_release(title)

    def clock(self) -> datetime:
        return self.now

    def file(
        self,
        title: str = "item",
        *,
        kind: str = "feature",
        priority: str = "P2-Medium",
        status: str = "Ready",
        value: str | None = None,
        release: str | None = CURRENT,
    ) -> int:
        """A person files an item with its fields, and places it."""
        number = self.store.seed_issue(title, labels=(LABELS[kind],), on_board=True)
        fields = {ItemField.STATUS: status, ItemField.PRIORITY: priority, ItemField.VALUE: value}
        for board_field, chosen in fields.items():
            if chosen is not None:
                self.person.set_field(self.item(number), board_field, chosen)
        self.place(number, release)
        return number

    def fix(
        self, title: str = "fix", *, status: str = "Ready", release: str | None = CURRENT
    ) -> int:
        """A person files a critical fix: P0 and `type/bug`."""
        return self.file(title, kind="bug", priority="P0-Critical", status=status, release=release)

    def place(self, number: int, release: str | None) -> None:
        """A person moves an item into `release`, or to the backlog."""
        self.person.set_field(self.item(number), ItemField.RELEASE, release)

    def set(self, number: int, board_field: ItemField, value: str) -> None:
        self.person.set_field(self.item(number), board_field, value)

    def item(self, number: int) -> Item:
        found = self.store.item(number)
        assert found is not None
        return found

    def release_of(self, *numbers: int) -> list[str | None]:
        return [self.item(number).release for number in numbers]

    def number(self, title: str) -> str:
        """The milestone number of the Release titled `title`, as a mark names it."""
        found = self.store.release(title)
        assert found is not None
        return str(found.number)

    def titled(self, mark: str | None) -> str | None:
        """The title of the Release a mark names by its milestone number; any other mark as
        it is, such as `backlog`."""
        found = [r.title for r in self.store.releases() if str(r.number) == mark]
        return found[0] if found else mark

    def admitted(self, number: int) -> str | None:
        """The title of the Release whose admitted set holds the item."""
        return self.titled(self.item(number).job_record.get(JobMark.ADMITTED))

    def run_record(self) -> dict[JobMark, str | None]:
        """The run record, with the Release its `Started` mark names by title."""
        record = {
            mark: value
            for mark, value in self.store.run_record().items()
            if isinstance(mark, JobMark)
        }
        if JobMark.STARTED in record:
            record[JobMark.STARTED] = self.titled(record[JobMark.STARTED])
        return record

    def stopped(
        self, operation: str, nth: int = 1, when: Callable[..., bool] = lambda *_: True
    ) -> None:
        """Run the job with the store's `nth` `operation` write for which `when` holds failing,
        as a gh call that fails part-way through a run; the command then says to run it again."""
        stop_once(self.store, operation, nth, when)
        with pytest.raises(GitHubOperationError, match="HTTP 502"):
            self.run()

    def stopped_at(self, fault: Fault) -> StoppingStore:
        """Run the job with each field write made as GitHub's two calls, the job record and
        then the field, and with `fault` failing one write; the command then says to run it
        again."""
        stopping = StoppingStore(self.store, fault)
        with pytest.raises(GitHubOperationError, match="HTTP 502"):
            apply_reprioritization(stopping.as_store(), self.plan())
        return stopping

    def size(self, release: str = CURRENT) -> int:
        return sum(item.state is GitHubState.OPEN for item in self.store.items(release=release))

    def comments(self, number: int) -> list[str]:
        """The job's comments on the item, without their signature."""
        return [comment.removesuffix(SIGNATURE) for comment in self.store.comments_on(number)]

    def plan(self) -> ReprioritizationPlan:
        return plan_reprioritization(self.store, repo=REPO, config=self.config, now=self.now)

    def run(self) -> list[JobWrite]:
        """Run the job at `now`, returning what it wrote."""
        before = len(self.store.job_writes())
        apply_reprioritization(self.store, self.plan())
        return self.store.job_writes()[before:]

    def release_pull_request(self, release: str = CURRENT, *, draft: bool = False) -> int:
        """A person opens the release pull request of `release`, the current release unless
        named, which cuts it."""
        return self.person.open_pull_request(
            f"feat(release): {release}",
            base="main",
            head=f"release/{release}",
            labels=("release",),
            release=release,
            draft=draft,
        )

    def ship(self, release: str = CURRENT, *, close_milestone: bool = False) -> None:
        """The release pull request of `release` merges and its GitHub Release is published."""
        self.person.close_pull_request(self.release_pull_request(release), merged=True)
        self.person.publish_release(release)
        if close_milestone:
            self.person.close_release(release)


def started_with(roadmap: Roadmap, *numbers: int) -> Roadmap:
    """Run the first run, which records the release's admitted set and moves nothing."""
    assert numbers
    roadmap.run()
    return roadmap


@pytest.fixture
def roadmap() -> Roadmap:
    return Roadmap()


@pytest.fixture
def started(roadmap: Roadmap) -> Roadmap:
    """The current release has started holding one Ready feature."""
    return started_with(roadmap, roadmap.file("held"))


# ── Admission ─────────────────────────────────────────────────────────────────


def test_after_the_start_a_p2_feature_added_moves_to_the_backlog_with_a_reason(
    started: Roadmap,
) -> None:
    added = started.file("late feature")
    started.run()
    assert (started.release_of(added), started.comments(added)) == (
        [None],
        [
            "Moved to the backlog: after v0.2.25 started, only a critical fix can join it. A "
            "person can place it in a planned release, and that placement stands."
        ],
    )


def test_a_p0_feature_added_after_the_start_moves_to_the_next_release_and_goes_first_there(
    started: Roadmap,
) -> None:
    """At the next release's start, trimming to the cap spares the P0 feature."""
    feature = started.file("p0 feature", priority="P0-Critical")
    started.run()
    moved = (started.release_of(feature), started.comments(feature))
    others = [started.file(f"next {n}", priority="P1-High", release=NEXT) for n in range(12)]
    started.ship()
    started.run()
    assert (moved, started.release_of(feature, others[-1]), started.size(NEXT)) == (
        (
            [NEXT],
            [
                "Moved to v0.2.26: a P0 feature waits for the next release once v0.2.25 has "
                "started, and goes first when v0.2.26 starts."
            ],
        ),
        [NEXT, LATER],
        12,
    )


@pytest.mark.parametrize("kind", ["bug", "security"])
def test_a_critical_fix_added_after_the_start_stays_and_joins_the_admitted_set(
    started: Roadmap, kind: str
) -> None:
    fix = started.file("fix", kind=kind, priority="P0-Critical")
    started.run()
    item = started.item(fix)
    assert (item.release, started.admitted(fix), started.comments(fix)) == (
        CURRENT,
        CURRENT,
        ["Admitted to v0.2.25: a critical fix can join v0.2.25 after it starts."],
    )


def test_an_item_added_between_runs_with_no_change_recorded_is_found_through_the_admitted_set(
    started: Roadmap,
) -> None:
    started.now += timedelta(minutes=1)
    since = started.now
    slipped = started.store.seed_issue("slipped in", release=CURRENT, on_board=True)
    changes = started.store.changes_since(since)
    started.run()
    assert (changes, started.release_of(slipped)) == ([], [None])


# ── The cap ───────────────────────────────────────────────────────────────────


def test_with_twelve_unstarted_items_a_critical_fix_descopes_the_lowest_ranked_one(
    roadmap: Roadmap,
) -> None:
    """Lowest Priority first, then the lowest Value, then the highest issue number."""
    high = [roadmap.file(f"p1 {n}", priority="P1-High", value="High") for n in range(9)]
    low_a = roadmap.file("p3 low a", priority="P3-Low", value="Low")
    low_b = roadmap.file("p3 low b", priority="P3-Low", value="Low")
    p3_high = roadmap.file("p3 high", priority="P3-Low", value="High")
    started_with(roadmap, *high, low_a, low_b, p3_high)
    fix = roadmap.fix()
    roadmap.run()
    assert (
        roadmap.release_of(low_b, low_a, p3_high, fix),
        roadmap.comments(low_b),
        roadmap.size(),
    ) == (
        [NEXT, CURRENT, CURRENT, CURRENT],
        [
            f"Moved to v0.2.26: critical fix #{fix} took v0.2.25 over its size of 12 items, "
            "and this was its lowest-ranked unstarted item."
        ],
        12,
    )


def test_with_twelve_started_items_a_critical_fix_joins_and_the_release_holds_thirteen(
    roadmap: Roadmap,
) -> None:
    held = [roadmap.file(f"started {n}", status="In Progress") for n in range(12)]
    started_with(roadmap, *held)
    fix = roadmap.fix()
    roadmap.run()
    assert (roadmap.release_of(fix, *held), roadmap.size()) == ([CURRENT] * 13, 13)


def test_with_eleven_started_items_and_an_admitted_fix_a_second_fix_joins_without_descoping(
    roadmap: Roadmap,
) -> None:
    held = [roadmap.file(f"started {n}", status="In Progress") for n in range(11)]
    started_with(roadmap, *held)
    first = roadmap.fix("first fix")
    roadmap.run()
    second = roadmap.fix("second fix")
    roadmap.run()
    assert (roadmap.release_of(first, second, *held), roadmap.size()) == ([CURRENT] * 13, 13)


def test_with_ten_items_a_critical_fix_descopes_nothing(roadmap: Roadmap) -> None:
    held = [roadmap.file(f"ready {n}", priority="P3-Low") for n in range(10)]
    started_with(roadmap, *held)
    fix = roadmap.fix()
    roadmap.run()
    assert (roadmap.release_of(fix, *held), roadmap.size()) == ([CURRENT] * 11, 11)


def test_an_item_moved_back_to_ready_once_a_fix_filled_the_release_makes_room(
    roadmap: Roadmap,
) -> None:
    """The reviewer's replay: 12 started items, a fix joins with nothing to descope, then a
    person moves one back to Ready. While the release holds more than the larger of its cap and
    its size at start, every unstarted item in it is an admitted critical fix."""
    held = [roadmap.file(f"started {n}", status="In Progress") for n in range(12)]
    started_with(roadmap, *held)
    fix = roadmap.fix()
    roadmap.run()
    joined = roadmap.size()
    roadmap.set(held[0], ItemField.STATUS, "Ready")
    roadmap.run()
    assert (
        joined,
        roadmap.release_of(held[0], fix),
        roadmap.size(),
        roadmap.comments(held[0]),
    ) == (
        13,
        [NEXT, CURRENT],
        12,
        [
            "Moved to v0.2.26: v0.2.25 holds 13 items, more than its size of 12 and more than "
            "it held when it started, and this was its lowest-ranked unstarted item."
        ],
    )


# ── The cut ───────────────────────────────────────────────────────────────────


def test_a_draft_release_pull_request_sends_a_fix_on_until_it_is_closed_unmerged(
    started: Roadmap,
) -> None:
    release_pr = started.release_pull_request(draft=True)
    fix = started.fix()
    started.run()
    while_cut = (started.release_of(fix), started.comments(fix))
    started.person.close_pull_request(release_pr)
    started.place(fix, CURRENT)
    started.run()
    assert (while_cut, started.release_of(fix), started.admitted(fix)) == (
        (
            [NEXT],
            [
                "Moved to v0.2.26: v0.2.25 is cut, so nothing joins it until its release pull "
                "request is closed; a critical fix goes first into the next release."
            ],
        ),
        [CURRENT],
        CURRENT,
    )


def test_a_merged_release_pull_request_keeps_the_release_cut_until_it_is_published(
    started: Roadmap,
) -> None:
    """Its code is in `main` already; if `release.yml` fails to publish, the release stays cut."""
    started.person.close_pull_request(started.release_pull_request(), merged=True)
    fix = started.fix()
    plan = started.plan()
    started.run()
    started.person.publish_release(CURRENT)
    assert (
        plan.state,
        started.release_of(fix),
        started.comments(fix),
        started.plan().state,
    ) == (
        ReleaseState.CUT,
        [NEXT],
        [
            "Moved to v0.2.26: v0.2.25 is cut, so nothing joins it until its release pull "
            "request is closed; a critical fix goes first into the next release."
        ],
        ReleaseState.SHIPPED,
    )


# ── The first run ─────────────────────────────────────────────────────────────


def test_the_first_run_records_the_admitted_set_and_a_second_run_writes_nothing(
    roadmap: Roadmap,
) -> None:
    """Even a release over the cap, holding a P2 feature, a New item and a P0 feature. The run
    names the release in the run record first and gives its size last, and every mark names
    the release by its milestone number."""
    held = [roadmap.file(f"held {n}", priority="P1-High") for n in range(12)]
    held += [
        roadmap.file("p2", priority="P2-Medium"),
        roadmap.file("new", status="New"),
        roadmap.file("p0 feature", priority="P0-Critical"),
        roadmap.file("in progress", status="In Progress"),
    ]
    plan = roadmap.plan()
    first = roadmap.run()
    second = roadmap.run()
    assert (
        plan.first_run,
        first,
        [roadmap.store.comments_on(number) for number in held],
        roadmap.size(),
        second,
    ) == (
        True,
        [
            JobWrite("set_run_record", None, "Started", roadmap.number(CURRENT)),
            *(JobWrite("set_mark", number, "Admitted", roadmap.number(CURRENT)) for number in held),
            JobWrite("set_run_record", None, "Size", "16"),
        ],
        [[]] * 16,
        16,
        [],
    )


def test_a_first_run_on_an_empty_release_records_it_so_the_next_run_holds_it_to_its_rules(
    roadmap: Roadmap,
) -> None:
    """With no item to carry a mark, the run record alone says the release was recorded."""
    first = roadmap.run()
    added = roadmap.file("p2 feature")
    plan = roadmap.plan()
    roadmap.run()
    assert (
        first,
        plan.first_run,
        roadmap.run_record(),
        roadmap.release_of(added),
    ) == (
        [
            JobWrite("set_run_record", None, "Started", roadmap.number(CURRENT)),
            JobWrite("set_run_record", None, "Size", "0"),
        ],
        False,
        {JobMark.STARTED: CURRENT, JobMark.SIZE: "0"},
        [None],
    )


def _held_is_blocked(roadmap: Roadmap, held: int) -> None:
    roadmap.set(held, ItemField.STATUS, "Blocked")


def _held_is_moved_on(roadmap: Roadmap, held: int) -> None:
    roadmap.place(held, LATER)


@pytest.mark.parametrize(
    "takes_out", [_held_is_blocked, _held_is_moved_on], ids=["descoped", "moved-by-a-person"]
)
def test_a_started_release_whose_admitted_items_all_left_is_never_started_again(
    started: Roadmap, takes_out: Callable[[Roadmap, int], None]
) -> None:
    """Every `Admitted` mark of v0.2.25 is cleared, and the run record still names it, so a P2
    feature the admission rule sent to the backlog is not pulled back by a second start."""
    feature = started.file("p2 feature")
    started.run()
    takes_out(started, 1)
    started.run()
    plan = started.plan()
    started.run()
    assert (plan.starting, started.release_of(feature), len(started.comments(feature))) == (
        None,
        [None],
        1,
    )


def test_a_release_that_started_empty_holds_its_admission_rule(started: Roadmap) -> None:
    """v0.2.26 starts holding only a New item, which goes to the backlog, so its start sets no
    `Admitted` mark; the run record names it all the same."""
    started.file("new", status="New", release=NEXT)
    started.ship(close_milestone=True)
    started.run()
    feature = started.file("p2 feature", release=NEXT)
    plan = started.plan()
    started.run()
    assert (
        plan.starting,
        started.run_record(),
        started.release_of(feature),
    ) == (None, {JobMark.STARTED: NEXT, JobMark.SIZE: "0"}, [None])


# ── Release start ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("existing", [None, "f" * 40], ids=["missing", "exists"])
def test_a_ship_creates_the_next_release_branch_at_the_default_head_only_when_missing(
    started: Roadmap, existing: str | None
) -> None:
    if existing:
        started.store.seed_branch(f"release/{NEXT}", existing)
    started.ship()
    writes = started.run()
    created = [write for write in writes if write.operation == "create_branch"]
    assert (started.store.branch(f"release/{NEXT}"), len(created)) == (
        existing or DEFAULT_ROADMAP_MEMORY_HEAD_SHA,
        0 if existing else 1,
    )


def test_a_ship_closes_the_shipped_milestone_and_creates_the_next_planned_one(
    started: Roadmap,
) -> None:
    started.ship()
    plan = started.plan()
    started.run()
    assert (
        (plan.shipped, plan.starting),
        [(release.title, release.state) for release in started.store.releases()],
    ) == (
        (CURRENT, NEXT),
        [
            (CURRENT, GitHubState.CLOSED),
            (NEXT, GitHubState.OPEN),
            (LATER, GitHubState.OPEN),
            ("v0.2.28", GitHubState.OPEN),
        ],
    )


def _candidates(roadmap: Roadmap) -> tuple[list[int], list[int], list[int]]:
    """Ready candidates, best first, then items the start must leave where they are.

    Returns the candidates in top-up order, the items left in the backlog and those left in
    the later release.
    """
    fix = roadmap.fix("backlog fix", release=None)
    p0_feature = roadmap.file("backlog p0 feature", priority="P0-Critical", release=None)
    job_later = roadmap.file("p1 high, placed by a job", priority="P1-High", value="High")
    roadmap.store.set_field(roadmap.item(job_later), ItemField.RELEASE, LATER)
    job_backlog = roadmap.file("sent to the backlog by a job", priority="P1-High", value="High")
    roadmap.store.set_field(roadmap.item(job_backlog), ItemField.RELEASE, None)
    p1_low = roadmap.file("p1 low", priority="P1-High", value="Low", release=None)
    blocked = roadmap.file("blocked", priority="P0-Critical", status="Blocked", release=None)
    new = roadmap.file("new", priority="P1-High", status="New", release=None)
    person_later = roadmap.file("placed in the later release", priority="P1-High", release=LATER)
    person_backlog = roadmap.file("moved to the backlog", priority="P1-High")
    roadmap.store.set_field(roadmap.item(person_backlog), ItemField.RELEASE, LATER)
    roadmap.place(person_backlog, None)
    # No job ever placed this one: its issue's own events show a person took it out of LATER.
    never_job_placed = roadmap.file("moved by a person only", priority="P0-Critical", release=LATER)
    roadmap.place(never_job_placed, None)
    return (
        [fix, p0_feature, job_later, job_backlog, p1_low],
        [blocked, new, person_backlog, never_job_placed],
        [person_later],
    )


def test_a_starting_release_is_topped_up_to_the_cap_in_order_from_items_no_person_placed(
    started: Roadmap,
) -> None:
    """Critical fixes, then P0 features, then Priority, Value and the lowest number."""
    kept = [started.file(f"next {n}", release=NEXT) for n in range(8)]
    ranked, in_backlog, in_later = _candidates(started)
    started.ship()
    started.run()
    pulled = ranked[:4]
    assert (
        started.release_of(*kept, *pulled),
        started.release_of(ranked[4], *in_backlog),
        started.release_of(*in_later),
        started.comments(pulled[0]),
        [started.admitted(number) for number in kept + pulled],
    ) == (
        [NEXT] * 12,
        [None] * 5,
        [LATER],
        [
            "Moved to v0.2.26: v0.2.26 started with fewer than its 12 items and was topped up "
            "to 12 from Ready items, critical fixes and P0 features first."
        ],
        [NEXT] * 12,
    )


def test_a_starting_release_over_the_cap_is_trimmed_into_the_later_release(
    started: Roadmap,
) -> None:
    """Never a started item, nor a critical fix or a P0 feature while another item remains."""
    keep = [
        started.file("in progress", priority="P3-Low", status="In Progress", release=NEXT),
        started.fix("next fix", release=NEXT),
        started.file("p0 feature", priority="P0-Critical", release=NEXT),
        *(started.file(f"p1 {n}", priority="P1-High", release=NEXT) for n in range(9)),
    ]
    trim_last = started.file("p1 last", priority="P1-High", release=NEXT)
    low_x = started.file("p3 low x", priority="P3-Low", value="Low", release=NEXT)
    low_y = started.file("p3 low y", priority="P3-Low", value="Low", release=NEXT)
    high_z = started.file("p3 high z", priority="P3-Low", value="High", release=NEXT)
    started.ship()
    started.run()
    assert (
        started.release_of(*keep),
        started.release_of(low_y, low_x, high_z, trim_last),
        started.comments(low_y),
        started.size(NEXT),
    ) == (
        [NEXT] * 12,
        [LATER] * 4,
        [
            "Moved to v0.2.27: v0.2.26 started with more than 12 items, and this was its "
            "lowest-ranked unstarted item."
        ],
        12,
    )


def test_at_the_start_new_and_blocked_items_leave_but_a_new_critical_fix_stays(
    started: Roadmap,
) -> None:
    new_feature = started.file("new feature", status="New", release=NEXT)
    new_fix = started.fix("new fix", status="New", release=NEXT)
    blocked_fix = started.fix("blocked fix", status="Blocked", release=NEXT)
    blocked_feature = started.file("blocked feature", status="Blocked", release=NEXT)
    started.ship()
    started.run()
    assert (
        started.release_of(new_feature, new_fix, blocked_fix, blocked_feature),
        [started.comments(n) for n in (new_feature, blocked_fix, blocked_feature)],
    ) == (
        [None, NEXT, LATER, None],
        [
            ["Moved to the backlog: it was New, not Ready, when v0.2.26 started."],
            ["Moved to v0.2.27: a Blocked item can't join a starting release (v0.2.26)."],
            ["Moved to the backlog: a Blocked item can't join a starting release (v0.2.26)."],
        ],
    )


def test_the_next_release_starts_when_release_yml_has_closed_the_shipped_milestone(
    started: Roadmap,
) -> None:
    """`release.yml` closes the milestone when the release PR merges, before the job runs.

    The next release starts then, and keeps its items: it is not yet the current release whose
    admitted set they would be missing from.
    """
    ready = [started.file(f"next {n}", release=NEXT) for n in range(3)]
    new = started.file("new", status="New", release=NEXT)
    started.ship(close_milestone=True)
    plan = started.plan()
    started.run()
    assert (
        (plan.current, plan.starting, plan.shipped),
        started.release_of(*ready, new),
        [started.admitted(number) for number in ready],
        started.store.branch(f"release/{NEXT}"),
    ) == (
        (NEXT, NEXT, None),
        [NEXT, NEXT, NEXT, None],
        [NEXT] * 3,
        DEFAULT_ROADMAP_MEMORY_HEAD_SHA,
    )


def test_a_milestone_closed_by_hand_starts_nothing_until_its_release_ships(
    started: Roadmap,
) -> None:
    """The reviewer's replay: closing v0.2.25's milestone is no ship. v0.2.26 starts, and is
    trimmed to the cap, only once v0.2.25's release pull request has merged and GitHub Release
    v0.2.25 is published."""
    waiting = [started.file(f"next {n}", release=NEXT) for n in range(13)]
    started.person.close_release(CURRENT)
    held = started.plan()
    writes = started.run()
    started.ship()
    shipped = started.plan()
    started.run()
    assert (
        (held.current, held.unshipped, held.starting, held.has_writes),
        writes,
        "v0.2.25 is closed but has not shipped" in render_plan(held),
        (shipped.starting, started.size(NEXT), started.release_of(waiting[-1])),
    ) == ((NEXT, CURRENT, None, False), [], True, (NEXT, 12, [LATER]))


def test_an_item_a_person_moved_to_the_backlog_stays_there_though_no_job_ever_placed_it(
    started: Roadmap,
) -> None:
    """The reviewer's replay: a person files a Ready P1 item into v0.2.27, then moves it to the
    backlog. No job placed it, yet its issue's events show a person took it out of v0.2.27, so
    v0.2.26's start leaves it there and records that Release as its `Left` mark."""
    item = started.file("p1", priority="P1-High", release=LATER)
    started.run()
    started.place(item, None)
    started.run()
    started.ship(close_milestone=True)
    plan = started.plan()
    started.run()
    assert (
        (plan.starting, [(kept.number, title) for kept, title in plan.kept_out]),
        started.release_of(item),
        started.comments(item),
        started.titled(started.item(item).job_record.get(JobMark.LEFT)),
        started.item(item).job_record.keys(),
    ) == ((NEXT, [(item, LATER)]), [None], [], LATER, {JobMark.LEFT})


def test_an_item_a_person_moved_back_to_the_backlog_where_a_job_had_sent_it_stays_there(
    started: Roadmap,
) -> None:
    """Found by the machine: the admission rule sent a feature to the backlog, a person placed
    it in v0.2.26 and then moved it back to the backlog. The backlog is where the job last
    placed it, yet the last move was a person's: the run after the person placed it recorded
    that a person took it out of the backlog, so v0.2.26's start leaves it there."""
    feature = started.file("late feature")
    started.run()
    started.place(feature, NEXT)
    started.run()
    started.place(feature, None)
    started.ship(close_milestone=True)
    plan = started.plan()
    started.run()
    assert (plan.starting, started.release_of(feature), len(started.comments(feature))) == (
        NEXT,
        [None],
        1,
    )


@pytest.mark.parametrize("closed", [False, True], ids=["milestone-open", "milestone-closed"])
def test_a_first_run_at_a_ship_records_the_release_under_way_whatever_the_milestone(
    roadmap: Roadmap, closed: bool
) -> None:
    """With no run record, v0.2.25 shipped before the job ever ran: whether `release.yml`
    closed its milestone or not, the run records v0.2.26 as it stands, closes v0.2.25 and moves
    nothing. Its Blocked item is then judged by the next run's descoping rules."""
    new = roadmap.file("new", status="New", release=NEXT)
    blocked = roadmap.file("blocked", status="Blocked", release=NEXT)
    candidate = roadmap.file("backlog candidate", release=None)
    roadmap.ship(close_milestone=closed)
    plan = roadmap.plan()
    roadmap.run()
    recorded = (
        (plan.first_run, plan.shipped, plan.starting, plan.admitted_release),
        roadmap.release_of(new, blocked, candidate),
        [roadmap.admitted(number) for number in (new, blocked)],
        roadmap.run_record(),
        [(release.title, release.state) for release in roadmap.store.releases()],
        [roadmap.comments(number) for number in (new, blocked, candidate)],
    )
    roadmap.run()
    assert (recorded, roadmap.release_of(new, blocked)) == (
        (
            (True, None if closed else CURRENT, None, NEXT),
            [NEXT, NEXT, None],
            [NEXT, NEXT],
            {JobMark.STARTED: NEXT, JobMark.SIZE: "2"},
            [(CURRENT, GitHubState.CLOSED), (NEXT, GitHubState.OPEN), (LATER, GitHubState.OPEN)],
            [[], [], []],
        ),
        [NEXT, LATER],
    )


@pytest.mark.parametrize(
    ("first_run", "kind", "expected"),
    [
        (False, "bug", ("admit", NEXT, NEXT)),
        (False, "feature", ("to_backlog", None, None)),
        (True, "feature", ("to_backlog", None, None)),
    ],
    ids=["start-then-fix", "start-then-p2-feature", "first-run-then-p2-feature"],
)
def test_a_run_that_stopped_at_its_close_is_followed_by_the_rules_then_the_close(
    roadmap: Roadmap, first_run: bool, kind: str, expected: tuple[str, str | None, str | None]
) -> None:
    """v0.2.25 ships with its milestone open, and the run that starts v0.2.26, or records it at
    a first run, stops at its last write, the close of v0.2.25: the run record names v0.2.26
    already. A person then files an item into v0.2.26. The next run holds v0.2.26 to the rules
    as the current release: it admits a critical fix and sends a P2 feature to the backlog, and
    closes v0.2.25 last. It used to only close v0.2.25, and the item went unjudged until a later
    run was due."""
    if not first_run:
        started_with(roadmap, roadmap.file("held"))
    roadmap.file("next", release=NEXT)
    roadmap.ship()
    roadmap.stopped("close_release")
    record = roadmap.run_record()
    priority = "P0-Critical" if kind == "bug" else "P2-Medium"
    filed = roadmap.file("filed", kind=kind, priority=priority, release=NEXT)
    plan = roadmap.plan()
    last = roadmap.run()[-1]
    assert (
        record,
        (plan.current, plan.state, plan.shipped, plan.starting, plan.first_run),
        [(d.item.number, d.action.value) for d in plan.changes],
        [write.text for write in plan.release_writes],
        (last.operation, last.key, last.value),
        (expected[0], *roadmap.release_of(filed), roadmap.admitted(filed)),
        len(roadmap.comments(filed)),
        [r.title for r in roadmap.store.releases() if r.state is GitHubState.CLOSED],
    ) == (
        {JobMark.STARTED: NEXT, JobMark.SIZE: "1"},
        (NEXT, ReleaseState.STARTED, CURRENT, None, False),
        [(filed, expected[0])],
        [f"close Release {CURRENT}"],
        ("edit_release", CURRENT, "closed"),
        expected,
        1,
        [CURRENT],
    )


@pytest.mark.parametrize(
    ("first_run", "waits", "stops", "pulled"),
    [
        (False, False, 0, LATER),
        (False, False, 1, LATER),
        (False, False, 2, LATER),
        (True, False, 0, None),
        (False, True, 0, NEXT),
        (True, True, 0, LATER),
    ],
    ids=[
        "start",
        "start-stopped-at-its-first-close",
        "start-stopped-at-its-second-close",
        "first-run",
        "after-a-start-stopped-at-its-close",
        "after-a-first-run-stopped-at-its-close",
    ],
)
def test_a_release_that_shipped_before_any_run_started_it_is_closed_and_the_next_one_starts(
    roadmap: Roadmap, first_run: bool, waits: bool, stops: int, pulled: str | None
) -> None:
    """Seed 15007: v0.2.25 ships with its milestone open, and so does v0.2.26 before any run
    starts it, as when the run that would have stopped and waited. v0.2.26 has shipped, so the
    run starts v0.2.27, or a first run records it, and closes both milestones last, the current
    one first; a start that stops at either close leaves the rest to the next run. The start
    used to begin v0.2.26: it pulled the backlog feature into the shipped release, admitted it
    there and closed only v0.2.25.

    With `waits`, the run at v0.2.25's ship started v0.2.26, or recorded it at a first run, and
    stopped at its close of v0.2.25, and v0.2.26 ships before the next run: the run record names
    a release that has shipped, so that run starts v0.2.27 too, where it used to close v0.2.25
    alone and leave v0.2.26 open until a later run."""
    if not first_run:
        started_with(roadmap, roadmap.file("held"))
    candidate = roadmap.file("backlog feature", release=None)
    roadmap.ship()
    if waits:
        roadmap.stopped("close_release")
    roadmap.ship(NEXT)
    plan = roadmap.plan()
    if stops:
        roadmap.stopped("close_release", stops)
    roadmap.run()
    recorded = first_run and not waits
    assert (
        (plan.first_run, plan.shipped, plan.starting, plan.admitted_release),
        [write.text for write in plan.release_writes if write.last],
        [(r.title, r.state) for r in roadmap.store.releases()][:3],
        roadmap.run_record()[JobMark.STARTED],
        (*roadmap.release_of(candidate), roadmap.admitted(candidate)),
        roadmap.plan().has_writes,
    ) == (
        (recorded, NEXT, None if recorded else LATER, LATER),
        [f"close Release {CURRENT}", f"close Release {NEXT}"],
        [(CURRENT, GitHubState.CLOSED), (NEXT, GitHubState.CLOSED), (LATER, GitHubState.OPEN)],
        LATER,
        (pulled, pulled),
        False,
    )


def _start_stopped_at_its_close(roadmap: Roadmap) -> None:
    started_with(roadmap, roadmap.file("held"))
    roadmap.ship()
    roadmap.stopped("close_release")


def _first_run_stopped_at_its_close(roadmap: Roadmap) -> None:
    roadmap.ship()
    roadmap.stopped("close_release")


def _start_then_the_shipped_milestone_reopened(roadmap: Roadmap) -> None:
    """v0.2.26 starts once v0.2.25 ships; a person reopens v0.2.25's milestone once v0.2.26
    has shipped, as below, and before the next run."""
    started_with(roadmap, roadmap.file("held"))
    roadmap.ship(close_milestone=True)
    roadmap.run()


@pytest.mark.parametrize(
    "before",
    [
        _start_stopped_at_its_close,
        _first_run_stopped_at_its_close,
        _start_then_the_shipped_milestone_reopened,
    ],
    ids=[
        "start-stopped-at-its-close",
        "first-run-stopped-at-its-close",
        "shipped-milestone-reopened",
    ],
)
def test_a_run_record_naming_a_release_shipped_and_closed_since_starts_the_one_after_it(
    roadmap: Roadmap, before: Callable[[Roadmap], None]
) -> None:
    """The twelfth round's reviewers' replays: the run record names v0.2.26, which ships with
    its milestone closed by `release.yml` before the next run, while v0.2.25's milestone is
    still open: the run that started v0.2.26, or recorded it at a first run, stopped at its close
    of v0.2.25, or a person reopened v0.2.25's milestone. The next run starts v0.2.27 and closes
    v0.2.25. It used to close v0.2.25 only, leaving v0.2.27 unstarted until a later run, whose
    start then admitted a P2 feature a person had placed in v0.2.27 meanwhile, with no
    comment."""
    before(roadmap)
    roadmap.ship(NEXT, close_milestone=True)
    if before is _start_then_the_shipped_milestone_reopened:
        roadmap.person.edit_release(CURRENT, state=GitHubState.OPEN)
    plan = roadmap.plan()
    roadmap.run()
    late = roadmap.file("late feature", release=LATER)
    roadmap.run()
    assert (
        (plan.shipped, plan.starting),
        [write.text for write in plan.release_writes if write.last],
        roadmap.run_record()[JobMark.STARTED],
        [(r.title, r.state) for r in roadmap.store.releases()][:3],
        roadmap.release_of(late),
        roadmap.comments(late),
    ) == (
        (CURRENT, LATER),
        [f"close Release {CURRENT}"],
        LATER,
        [(CURRENT, GitHubState.CLOSED), (NEXT, GitHubState.CLOSED), (LATER, GitHubState.OPEN)],
        [None],
        [
            "Moved to the backlog: after v0.2.27 started, only a critical fix can join it. A "
            "person can place it in a planned release, and that placement stands."
        ],
    )


@pytest.mark.parametrize("merged", [False, True], ids=["pull-request-open", "merged-unpublished"])
def test_a_release_cut_before_its_start_is_topped_up_with_nothing(
    started: Roadmap, merged: bool
) -> None:
    """The twelfth round's reviewers' replay: v0.2.25 ships, and before any run starts v0.2.26
    a person opens its release pull request, which may merge before its release is published.
    v0.2.26's start keeps and admits its own item and pulls nothing in: nothing joins a cut
    release. It used to top it up from the backlog, and once v0.2.26 shipped, the feature sat
    Ready in its closed milestone, where no later start looks. v0.2.27's start pulls it in."""
    kept = started.file("next", release=NEXT)
    feature = started.file("backlog feature", release=None)
    started.ship(close_milestone=True)
    pull_request = started.release_pull_request(NEXT)
    if merged:
        started.person.close_pull_request(pull_request, merged=True)
    plan = started.plan()
    started.run()
    at_start = (started.release_of(kept, feature), started.admitted(kept), started.run_record())
    started.ship(NEXT, close_milestone=True)
    started.run()
    assert (
        (plan.starting, [(d.item.number, d.action.value) for d in plan.changes]),
        at_start,
        (*started.release_of(feature), started.admitted(feature)),
    ) == (
        (NEXT, []),
        ([NEXT, None], NEXT, {JobMark.STARTED: NEXT, JobMark.SIZE: "1"}),
        (LATER, LATER),
    )


# ── Descoping ─────────────────────────────────────────────────────────────────


def _blocked(roadmap: Roadmap, number: int, _: int) -> str:
    roadmap.set(number, ItemField.STATUS, "Blocked")
    return "it is Blocked and had not started."


def _dependency(roadmap: Roadmap, number: int, _: int) -> str:
    waits_on = roadmap.file("elsewhere", release=LATER)
    roadmap.person.link_dependency(number, waits_on)
    return f"it waits on #{waits_on}, open outside v0.2.25."


def _needs_split(roadmap: Roadmap, number: int, _: int) -> str:
    roadmap.person.add_label(number, "needs-split")
    return "it is labeled needs-split, so it must be split before it fits one pull request."


def _others_done(roadmap: Roadmap, _: int, other: int) -> str:
    roadmap.set(other, ItemField.STATUS, "Done")
    return "every other item in v0.2.25 is done, and it had not started."


@pytest.mark.parametrize(
    "reason",
    [_blocked, _dependency, _needs_split, _others_done],
    ids=["blocked", "dependency", "needs-split", "others-done"],
)
def test_each_descoping_reason_moves_an_unstarted_item_with_a_comment_naming_it(
    roadmap: Roadmap, reason: Callable[[Roadmap, int, int], str]
) -> None:
    item = roadmap.file("unstarted")
    other = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item, other)
    named = reason(roadmap, item, other)
    roadmap.run()
    assert (roadmap.release_of(item, other), roadmap.comments(item)) == (
        [NEXT, CURRENT],
        [f"Moved to v0.2.26: {named}"],
    )


def test_a_started_item_is_descoped_by_no_reason_but_the_stall(roadmap: Roadmap) -> None:
    in_progress = roadmap.file("in progress", status="In Progress")
    in_review = roadmap.file("in review", status="In Review")
    other = roadmap.file("done", status="Done")
    started_with(roadmap, in_progress, in_review, other)
    for number in (in_progress, in_review):
        _dependency(roadmap, number, other)
        _needs_split(roadmap, number, other)
    writes = roadmap.run()
    assert (roadmap.release_of(in_progress, in_review), writes) == ([CURRENT, CURRENT], [])


def test_an_admitted_critical_fix_is_descoped_only_when_it_is_blocked(roadmap: Roadmap) -> None:
    fix = roadmap.fix()
    other = roadmap.file("done", status="Done")
    started_with(roadmap, fix, other)
    _dependency(roadmap, fix, other)
    _needs_split(roadmap, fix, other)
    kept = (roadmap.run(), roadmap.release_of(fix))
    _blocked(roadmap, fix, other)
    roadmap.run()
    assert (kept, roadmap.release_of(fix), roadmap.comments(fix)) == (
        ([], [CURRENT]),
        [NEXT],
        ["Moved to v0.2.26: it is Blocked and had not started."],
    )


# ── The stall window ──────────────────────────────────────────────────────────


def _working_on(roadmap: Roadmap, number: int) -> int:
    """A person opens the item's pull request into the release branch."""
    return roadmap.person.open_pull_request(
        "feat: work", base=f"release/{CURRENT}", head="feat/work", body=f"Closes #{number}"
    )


def test_an_in_progress_item_idle_for_fourteen_days_goes_back_to_ready_and_is_descoped(
    roadmap: Roadmap,
) -> None:
    item = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item)
    pull_request = _working_on(roadmap, item)
    opened = roadmap.store.open_pull_requests()
    roadmap.now += timedelta(days=14)
    writes = roadmap.run()
    found = roadmap.item(item)
    assert (
        (found.status, found.release),
        roadmap.comments(item),
        roadmap.store.open_pull_requests() == opened,
        [w for w in writes if w.number == pull_request or w.operation == "create_branch"],
    ) == (
        ("Ready", NEXT),
        [
            "Status set to Ready and moved to v0.2.26: it had no status change, pull request "
            "update or commit for 14 days, so it counts as not started again."
        ],
        True,
        [],
    )


def test_a_commit_on_a_linked_pull_request_keeps_an_item_from_stalling(roadmap: Roadmap) -> None:
    item = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item)
    pull_request = _working_on(roadmap, item)
    roadmap.now += timedelta(days=10)
    roadmap.person.push_to_pull_request(pull_request)
    roadmap.now += timedelta(days=10)
    assert (roadmap.run(), roadmap.item(item).status) == ([], "In Progress")


def test_an_idle_in_progress_critical_fix_goes_back_to_ready_and_stays(roadmap: Roadmap) -> None:
    fix = roadmap.fix(status="In Progress")
    started_with(roadmap, fix)
    roadmap.now += timedelta(days=14)
    roadmap.run()
    assert ((roadmap.item(fix).status, roadmap.item(fix).release), roadmap.comments(fix)) == (
        ("Ready", CURRENT),
        [
            "Status set to Ready: it had no status change, pull request update or commit for "
            "14 days; as a critical fix it stays in v0.2.25."
        ],
    )


def test_an_idle_in_review_item_gets_one_nudge_per_stall_window_and_stays(
    roadmap: Roadmap,
) -> None:
    item = roadmap.file("in review", status="In Review")
    started_with(roadmap, item)
    roadmap.now += timedelta(days=14)
    roadmap.run()
    same_day = roadmap.run()
    roadmap.now += timedelta(days=14)
    roadmap.run()
    assert (roadmap.release_of(item), same_day, roadmap.comments(item)) == (
        [CURRENT],
        [],
        [
            "Nudge: this item has been in review for 14 days without a status change, pull "
            "request update or commit, and it holds the cut of v0.2.25."
        ]
        * 2,
    )


def test_a_critical_fix_that_joins_stalled_goes_back_to_ready_and_is_admitted(
    started: Roadmap,
) -> None:
    """Found by the machine: a fix In Progress for 15 days in a planned release joins the
    current one. The stall rule sets it back to Ready, and the fix still joins the admitted
    set: the stall decision used to replace the admission, so the fix sat in the release
    without its `Admitted` mark. The plan lists the admission with the release's other
    admitted-set records."""
    fix = started.fix(status="In Progress", release=LATER)
    started.run()
    started.now += timedelta(days=15)
    started.place(fix, CURRENT)
    report = render_plan(started.plan())
    started.run()
    item = started.item(fix)
    assert (
        item.release,
        item.status,
        started.admitted(fix),
        f"- {CURRENT} admits #{fix}." in report,
    ) == (
        CURRENT,
        "Ready",
        CURRENT,
        True,
    )


STALLED_FIX = (
    "Status set to Ready: it had no status change, pull request update or commit for 14 days; "
    f"as a critical fix it stays in {CURRENT}."
)


@pytest.mark.parametrize(
    ("fault", "reprioritized"),
    [
        (Fault(1, True, "set_marks"), False),
        (Fault(1, True, FIELD), False),
        (Fault(3, False, "set_marks"), False),
        (Fault(3, False, "set_marks"), True),
    ],
    ids=[
        "pending-landed-then-failed",
        "status-landed-then-failed",
        "last-write-failed",
        "last-write-failed-then-p1",
    ],
)
def test_a_fix_that_joins_stalled_is_admitted_by_the_change_that_readies_it(
    started: Roadmap, fault: Fault, reprioritized: bool
) -> None:
    """Seed 820: the run that readies a stalled fix as it joins stops part-way through that
    change. The admission was a mark the run wrote after every change, so the rerun finished
    the Ready, found the fix unadmitted, and admitted it with a second comment, or, once a
    person had made it P1 after the stall comment saying it stays, sent it to the backlog. The
    change carries the admission now: one comment, and the fix stays admitted."""
    fix = started.fix(status="In Progress", release=LATER)
    started.run()
    started.now += timedelta(days=15)
    started.place(fix, CURRENT)
    started.stopped_at(Fault(fault.at, fault.applied, fault.write, fix))
    if reprioritized:
        started.set(fix, ItemField.PRIORITY, "P1-High")
    started.run()
    item = started.item(fix)
    assert (
        item.release,
        item.status,
        started.admitted(fix),
        started.comments(fix),
        started.plan().has_writes,
    ) == (CURRENT, "Ready", CURRENT, [STALLED_FIX], False)


def test_a_stall_descope_a_person_undid_before_its_comment_keeps_the_item_admitted(
    roadmap: Roadmap,
) -> None:
    """Seed 1021: the stall descope of an item the release started holding stops at its
    Status's written mark, after its Release was written and its Status landed unconfirmed, and
    a person puts the item back in v0.2.25. The rerun finishes the change as it stands, with
    its comment, and used to clear the item's `Admitted` mark as for any move out, so the
    admission rule then sent it to the backlog. Unannounced and undone, the move keeps the mark."""
    held = roadmap.file("held", status="In Progress")
    started_with(roadmap, held)
    roadmap.now += timedelta(days=15)
    roadmap.stopped_at(Fault(3, False, "set_marks", held))
    roadmap.place(held, CURRENT)
    roadmap.run()
    item = roadmap.item(held)
    assert (
        item.release,
        item.status,
        roadmap.admitted(held),
        len(roadmap.comments(held)),
        roadmap.plan().has_writes,
    ) == (CURRENT, "Ready", CURRENT, 1, False)


def test_a_descope_undone_before_its_comment_keeps_the_admission_when_its_rerun_stops(
    roadmap: Roadmap,
) -> None:
    """The twelfth round's reviewers' replay: as seed 1021, but the rerun's comment lands and
    reports a failure, so its last write never runs. The next run found the comment posted and
    cleared the item's `Admitted` mark as for an announced move, and the admission rule sent
    the item to the backlog: the outcome turned on whether one write failed. The rerun records
    in the change's `Pending` mark, before the comment, that the move was undone, and the item
    keeps its mark."""
    held = roadmap.file("held", status="In Progress")
    started_with(roadmap, held)
    roadmap.now += timedelta(days=15)
    roadmap.stopped_at(Fault(3, False, "set_marks", held))
    roadmap.place(held, CURRENT)
    roadmap.stopped_at(Fault(1, True, "comment", held))
    roadmap.run()
    item = roadmap.item(held)
    assert (
        item.release,
        item.status,
        roadmap.admitted(held),
        len(roadmap.comments(held)),
        roadmap.plan().has_writes,
    ) == (CURRENT, "Ready", CURRENT, 1, False)


# ── What the job writes ───────────────────────────────────────────────────────


def test_a_board_migrate_has_not_prepared_is_refused_before_any_write() -> None:
    """Board 2's Status options before #739's migrate: no New and no Blocked."""
    unmigrated = ("Todo", "Backlog", "Ready", "In Progress", "In Review", "Done")
    store = InMemoryRoadmapStore(board_options={**OPTIONS, ItemField.STATUS: unmigrated})
    roadmap = Roadmap(store)
    roadmap.file("epic", status="Backlog")
    writes = store.job_writes()
    with pytest.raises(ConfigurationError, match="no New, Blocked option") as refused:
        roadmap.plan()
    assert ("`devops roadmap migrate`" in str(refused.value), store.job_writes()) == (True, writes)


# Board 2 after a person made migrate's option edits and before `migrate --confirm`: Backlog
# renamed to New and Blocked added, while Todo goes only once migrate has moved its cards.
POST_EDIT = ("Todo", "New", "Ready", "In Progress", "In Review", "Done", "Blocked")


@pytest.mark.parametrize(
    ("statuses", "epic", "named"),
    [
        (POST_EDIT, True, ["Todo", "#5"]),
        (POST_EDIT, False, ["Todo"]),
        (OPTIONS[ItemField.STATUS], True, ["#5"]),
    ],
    ids=["edited-with-an-epic", "edited", "an-open-epic"],
)
def test_a_board_migrate_has_not_finished_is_refused_before_any_write(
    statuses: tuple[str, ...], epic: bool, named: list[str]
) -> None:
    """The reviewers' replay: with New and Blocked added by hand but `migrate --confirm` not
    run, the Status field still has Todo and release epic #5 is still an Item of v0.2.25, so
    the run would count the epic in the release's size at start."""
    store = InMemoryRoadmapStore(board_options={**OPTIONS, ItemField.STATUS: statuses})
    roadmap = Roadmap(store)
    for n in range(3):
        roadmap.file(f"held {n}")
    roadmap.file("closed epic", kind="epic")
    roadmap.person.close_issue(4, CloseReason.NOT_PLANNED, "Retired.")
    if epic:
        roadmap.file("v0.2.25 epic", kind="epic")
    writes = store.job_writes()
    with pytest.raises(ConfigurationError, match="`devops roadmap migrate`") as refused:
        roadmap.plan()
    assert ([name in str(refused.value) for name in named], store.job_writes()) == (
        [True] * len(named),
        writes,
    )


def test_the_status_options_the_guard_refuses_are_those_migrate_merges_into_new() -> None:
    template = json.loads(Path(".github/project-template.json").read_text(encoding="utf-8"))
    status = next(f for f in template["fields"] if f["name"] == ItemField.STATUS.value)
    replaced = {name for option in status["options"] for name in option.get("replaces", ())}
    assert replaced == CONST_ROADMAP_PREMIGRATE_STATUSES


def test_every_item_write_comes_with_a_reason_comment_and_none_sets_a_ranking_field(
    roadmap: Roadmap,
) -> None:
    """Admission, the cap, descoping, the stall window and a nudge, in one run.

    The admitted-set records of a first run, of a start's kept items and of items a person took
    out are reported under the plan's "Admitted set" heading, not commented.
    """
    held = [roadmap.file(f"p1 {n}", priority="P1-High") for n in range(11)]
    stalls = roadmap.file("in progress", status="In Progress")
    nudged = roadmap.file("in review", status="In Review")
    blocked = roadmap.file("to be blocked")
    started_with(roadmap, *held, stalls, nudged, blocked)
    roadmap.now += timedelta(days=14)
    roadmap.set(blocked, ItemField.STATUS, "Blocked")
    late = roadmap.file("late feature")
    fix = roadmap.fix()
    writes = roadmap.run()
    commented = {w.number for w in writes if w.operation == "comment"}
    changed = {w.number for w in writes if w.operation != "comment" and w.number is not None}
    assert (
        changed,
        changed <= commented,
        {w.key for w in writes if w.operation == "set_field"},
    ) == (
        {held[-1], stalls, nudged, blocked, late, fix},
        True,
        {"Status", "Release"},
    )


# ── A run that stops part-way ─────────────────────────────────────────────────
# Any gh write can fail (a 502, a timeout, a secondary rate limit). The command then says to
# run it again, so each case fails one write of a run at every position in turn, runs the job
# again, and compares the result with the same run left alone.

SMALL_CAP = 3
WRITES = (
    "create_release",
    "close_release",
    "create_branch",
    "set_field",
    "set_marks",
    "comment",
    "set_run_record",
)


def stop_at(store: InMemoryRoadmapStore, position: int) -> list[str]:
    """Make the store's `position`-th write raise once (0: none); the names of the writes made
    or tried, in order, are returned as they happen."""
    called: list[str] = []
    for name in WRITES:
        real = getattr(store, name)

        def write(*args: object, _name: str = name, _real: Any = real, **kwargs: Any) -> object:
            called.append(_name)
            if len(called) == position:
                raise GitHubOperationError("HTTP 502", operation="roadmap.write")
            return _real(*args, **kwargs)

        setattr(store, name, write)
    return called


def stop_once(
    store: InMemoryRoadmapStore, operation: str, nth: int, when: Callable[..., bool]
) -> None:
    """Make the store's `nth` `operation` write for which `when` holds raise, once."""
    real = getattr(store, operation)
    calls = 0

    def write(*args: object, **kwargs: Any) -> object:
        nonlocal calls
        calls += when(*args)
        if when(*args) and calls == nth:
            raise GitHubOperationError("HTTP 502", operation="roadmap.write")
        return real(*args, **kwargs)

    setattr(store, operation, write)


def outcome(roadmap: Roadmap) -> tuple[object, ...]:
    """Everything a run leaves: Releases, the branch, the run record, each item's place,
    Status and marks, and the comments on it."""
    items = roadmap.store.items()
    return (
        [(release.title, release.state) for release in roadmap.store.releases()],
        roadmap.store.branch(f"release/{NEXT}"),
        roadmap.store.run_record(),
        [
            (
                item.number,
                item.release,
                item.status,
                *(item.job_record.get(mark) for mark in JobMark),
            )
            for item in items
        ],
        [roadmap.comments(item.number) for item in items],
    )


def _first_run(roadmap: Roadmap) -> None:
    for n in range(4):
        roadmap.file(f"held {n}")


def _start_with_a_trim(roadmap: Roadmap) -> None:
    started_with(roadmap, roadmap.file("held"))
    for n in range(SMALL_CAP + 2):
        roadmap.file(f"next {n}", priority="P3-Low" if n % 2 else "P1-High", release=NEXT)
    roadmap.file("new", status="New", release=NEXT)
    roadmap.fix("blocked fix", status="Blocked", release=NEXT)
    roadmap.ship()


def _start_with_a_top_up(roadmap: Roadmap) -> None:
    started_with(roadmap, roadmap.file("held"))
    roadmap.file("next", release=NEXT)
    roadmap.file("blocked", status="Blocked", release=NEXT)
    roadmap.fix("backlog fix", release=None)
    roadmap.file("backlog feature", release=None)
    roadmap.ship()


def _first_run_at_a_ship(roadmap: Roadmap) -> None:
    """v0.2.25 shipped before the job ever ran, and its milestone is still open."""
    roadmap.file("next", release=NEXT)
    roadmap.file("blocked", status="Blocked", release=NEXT)
    roadmap.file("backlog feature", release=None)
    roadmap.ship()


def _rules(roadmap: Roadmap) -> None:
    """Admission of a P2 feature, a P0 feature and a fix, the cap, Blocked, a stall and a nudge."""
    held = [roadmap.file(f"p1 {n}", priority="P1-High", value="Medium") for n in range(SMALL_CAP)]
    held += [roadmap.file("stalls", status="In Progress"), roadmap.file("idle", status="In Review")]
    started_with(roadmap, *held)
    roadmap.now += timedelta(days=14)
    roadmap.set(held[0], ItemField.STATUS, "Blocked")
    roadmap.file("late feature")
    roadmap.file("p0 feature", priority="P0-Critical")
    roadmap.fix()


@pytest.mark.parametrize(
    "scenario",
    [_first_run, _start_with_a_trim, _start_with_a_top_up, _first_run_at_a_ship, _rules],
    ids=["first-run", "start-with-a-trim", "start-with-a-top-up", "first-run-at-a-ship", "rules"],
)
def test_a_run_that_stops_at_any_write_is_finished_by_the_next_run(
    scenario: Callable[[Roadmap], None],
) -> None:
    """The next run finishes it exactly as the run would have: nothing moves that the run left
    alone, nothing it began is lost, and every change keeps its one comment, even when the run
    stopped right after posting it, before clearing `Pending`. A run that stops at its last
    write, the close of the shipped milestone, has made every other, so the next run is one of
    its own, and ends as the run left alone and the run after it do: after a first run at a
    ship, it descopes the item that was Blocked already."""
    whole = Roadmap()
    whole.config = RoadmapConfig(board=1, release_cap=SMALL_CAP)
    scenario(whole)
    writes = stop_at(whole.store, 0)
    whole.run()
    count, last = len(writes), writes[-1]
    expected = [outcome(whole)] * count
    if last == "close_release":
        whole.run()
        expected[-1] = outcome(whole)
    finished = []
    for position in range(1, count + 1):
        stopped = Roadmap()
        stopped.config = whole.config
        scenario(stopped)
        stop_at(stopped.store, position)
        with pytest.raises(GitHubOperationError, match="HTTP 502"):
            stopped.run()
        stopped.run()
        finished.append(outcome(stopped) == expected[position - 1])
    assert (count > 3, finished) == (True, [True] * count)


def test_a_run_that_stops_after_a_comment_finishes_the_change_without_a_second_one(
    started: Roadmap,
) -> None:
    """The move, the mark that records it as written, and its comment are made, then the write
    that clears `Pending` fails: the next run finds the comment already posted, and only clears
    the mark."""
    feature = started.file("late feature")
    called = stop_at(started.store, 5)
    with pytest.raises(GitHubOperationError, match="HTTP 502"):
        started.run()
    stopped = (list(called), started.item(feature).job_record.get(JobMark.PENDING) is not None)
    finished = started.run()
    assert (
        stopped,
        finished,
        started.release_of(feature),
        len(started.comments(feature)),
        started.item(feature).job_record.get(JobMark.PENDING),
    ) == (
        (["set_marks", "set_field", "set_marks", "comment", "set_marks"], True),
        [JobWrite("set_mark", feature, "Pending", None)],
        [None],
        1,
        None,
    )


@pytest.mark.parametrize(
    ("write", "applied"),
    [(RECORD, True), (FIELD, False)],
    ids=["record-landed-then-failed", "milestone-call-failed"],
)
def test_a_job_move_whose_job_record_landed_without_its_milestone_is_finished(
    started: Roadmap, write: str, applied: bool
) -> None:
    """GitHub takes a field write as two calls, the job record first: here the record lands,
    naming the backlog and the Release as begun, and the milestone write never does, because
    the record call reported a failure after it applied or the milestone call failed. The item
    is still in v0.2.25, and its issue shows no Release change since the move began, so the
    next run knows the job never moved it and no person did: it finishes the move, with its
    one comment, and the item reads as the job's placement."""
    feature = started.file("late feature")
    started.stopped_at(Fault(1, applied=applied, write=write, item=feature))
    stopped = (
        started.release_of(feature),
        started.item(feature).job_record.get(ItemField.RELEASE, "none"),
    )
    report = render_plan(started.plan())
    started.run()
    item = started.item(feature)
    assert (
        stopped,
        "(finishing what an earlier run began)" in report,
        item.release,
        item.job_record.get(ItemField.RELEASE, "none"),
        item.job_record.get(JobMark.PENDING),
        started.comments(feature),
        started.plan().has_writes,
    ) == (
        ([CURRENT], None),
        True,
        None,
        None,
        None,
        [
            "Moved to the backlog: after v0.2.25 started, only a critical fix can join it. A "
            "person can place it in a planned release, and that placement stands."
        ],
        False,
    )


def _top_up_of_a_backlog_fix(roadmap: Roadmap) -> tuple[int, int]:
    """v0.2.25 started holding one item and shipped; the backlog holds a Ready P0 `type/bug`
    item and a P2 feature, which v0.2.26's start pulls in, the fix first."""
    started_with(roadmap, roadmap.file("held"))
    fix = roadmap.fix("backlog fix", release=None)
    feature = roadmap.file("backlog feature", release=None)
    roadmap.ship(close_milestone=True)
    return fix, feature


@pytest.mark.parametrize(
    ("write", "applied"),
    [(RECORD, True), (FIELD, False), (FIELD, True)],
    ids=["record-landed-then-failed", "milestone-call-failed", "milestone-landed-then-failed"],
)
def test_a_top_up_whose_milestone_write_never_landed_is_finished_as_the_whole_start(
    write: str, applied: bool
) -> None:
    """The reviewers' replay: v0.2.26's start pulls in a Ready critical fix, and its Release
    write stops between GitHub's two calls: the job record, naming v0.2.26, lands and reports a
    failure, or the milestone call fails, or it lands and reports a failure. The rerun ends as
    the start would have: the fix is in v0.2.26 and its admitted set, with one comment and no
    `Left` mark, and the run record gives the size with it. When the milestone call itself
    landed, the job can't show it set the Release, so the record keeps no Release for it."""
    whole = Roadmap()
    fix, feature = _top_up_of_a_backlog_fix(whole)
    whole.run()
    stopped = Roadmap()
    assert _top_up_of_a_backlog_fix(stopped) == (fix, feature)
    stopped.stopped_at(Fault(1, applied=applied, write=write, item=fix))
    report = render_plan(stopped.plan())
    stopped.run()
    found = stopped.item(fix)
    assert (
        outcome(stopped) == outcome(whole),
        (found.release, stopped.admitted(fix), found.job_record.get(JobMark.LEFT)),
        stopped.run_record(),
        stopped.comments(fix),
        found.job_record.get(ItemField.RELEASE, "none"),
        "left v0.2.26" in report or "not finishing" in report,
        stopped.plan().has_writes,
    ) == (
        True,
        (NEXT, NEXT, None),
        {JobMark.STARTED: NEXT, JobMark.SIZE: "2"},
        whole.comments(fix),
        "none" if (write, applied) == (FIELD, True) else NEXT,
        False,
        False,
    )


def _a_pulled_in_feature_set_blocked(roadmap: Roadmap) -> int:
    """v0.2.26's start pulls a Ready backlog feature in, a job's placement; a person then sets
    it Blocked, so the next run descopes it to v0.2.27."""
    _, feature = _top_up_of_a_backlog_fix(roadmap)
    roadmap.run()
    roadmap.set(feature, ItemField.STATUS, "Blocked")
    return feature


def _a_descoped_feature_new_at_the_start(roadmap: Roadmap) -> int:
    """The job descopes a Blocked feature from v0.2.25 to v0.2.26, a job's placement; a person
    then sets it New and v0.2.25 ships, so v0.2.26's start sends it to the backlog."""
    held = [roadmap.file("a"), roadmap.file("b")]
    started_with(roadmap, *held)
    roadmap.set(held[1], ItemField.STATUS, "Blocked")
    roadmap.run()
    roadmap.set(held[1], ItemField.STATUS, "New")
    roadmap.ship(close_milestone=True)
    return held[1]


@pytest.mark.parametrize(
    "scenario",
    [_a_pulled_in_feature_set_blocked, _a_descoped_feature_new_at_the_start],
    ids=["top-up-then-blocked", "descope-then-new-at-start"],
)
@pytest.mark.parametrize(
    ("at", "applied", "write"),
    [(1, True, FIELD), (2, False, "set_marks")],
    ids=["milestone-landed-then-failed", "written-mark-failed"],
)
def test_a_move_of_an_item_a_job_placed_that_landed_unconfirmed_leaves_no_left_mark(
    scenario: Callable[[Roadmap], int], at: int, applied: bool, write: str
) -> None:
    """The reviewers' replays: the job moves an item it had placed itself, out of the Release
    a top-up pulled it into or a descope sent it to, and the move's milestone call lands and
    reports a failure, or the written mark after it fails. Nothing shows the job set the
    Release, so the rerun finishes the move with its comment and keeps no Release recorded for
    the item, as for one no job placed: had it put back the Release recorded before the move,
    the next run would read the job's own move as a person taking the item out of the place
    the job had put it, and mark it `Left`. The next run has nothing to do, and the roadmap is
    where the run left alone leaves it."""
    whole, stopped = Roadmap(), Roadmap()
    number = scenario(whole)
    whole.run()
    assert scenario(stopped) == number
    stopping = stopped.stopped_at(Fault(at, applied, write, number))
    stopped.run()
    report = render_plan(stopped.plan())
    stopped.run()
    found = stopped.item(number)
    assert (
        stopping.writes[-1],
        found.release,
        found.job_record.get(JobMark.LEFT),
        found.job_record.get(ItemField.RELEASE, "none"),
        "where a job placed it" in report,
        outcome(stopped) == outcome(whole),
    ) == (write, whole.item(number).release, None, "none", False, True)


# ── A change a stopped run began, judged again ────────────────────────────────
# Between a run that stops and the next one, a person may move the item or the release may be
# cut. The next run finishes the change only when the rules still decide it; a person's
# change made since stands.


def test_a_top_up_a_person_overruled_before_the_rerun_is_not_finished(started: Roadmap) -> None:
    """The reviewers' replay (a): v0.2.26's start stops at the Release write that pulls the
    backlog item in, and a person then places it in v0.2.27. The rerun leaves it there."""
    started.file("p2", release=NEXT)
    pulled = started.file("p1", priority="P1-High", release=None)
    started.ship(close_milestone=True)
    started.stopped("set_field")
    started.place(pulled, LATER)
    started.run()
    item = started.item(pulled)
    assert (
        item.release,
        started.admitted(pulled),
        started.comments(pulled),
        item.job_record.get(JobMark.PENDING),
        started.run_record()[JobMark.STARTED],
    ) == (LATER, None, [], None, NEXT)


def test_an_admission_a_person_overruled_before_the_rerun_is_not_finished(
    started: Roadmap,
) -> None:
    """The reviewers' replay (b): the run that sends a late P2 feature to the backlog stops at
    its Release write, and a person then places it in v0.2.26. That placement stands."""
    feature = started.file("late feature")
    started.stopped("set_field")
    started.place(feature, NEXT)
    report = render_plan(started.plan())
    started.run()
    assert (
        started.release_of(feature),
        started.comments(feature),
        started.item(feature).job_record.get(JobMark.PENDING),
        f"#{feature} late feature: not finishing what an earlier run began" in report,
    ) == ([NEXT], [], None, True)


@pytest.mark.parametrize("nth", [1, 2], ids=["at-its-move", "after-its-move"])
def test_a_stall_whose_item_went_into_review_before_the_rerun_is_undone(
    roadmap: Roadmap, nth: int
) -> None:
    """The reviewers' replay (c): the run that descopes an idle In Progress item stops at its
    Release write, or right after it, and a person then moves the item to In Review. A started
    item is never descoped: the rerun leaves it, or puts it back, in v0.2.25."""
    item = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item)
    roadmap.now += timedelta(days=15)
    roadmap.stopped("set_field", nth)
    roadmap.set(item, ItemField.STATUS, "In Review")
    roadmap.run()
    found = roadmap.item(item)
    assert (
        (found.release, found.status),
        roadmap.comments(item),
        found.job_record.get(JobMark.PENDING),
    ) == ((CURRENT, "In Review"), [], None)


@pytest.mark.parametrize("nth", [1, 2], ids=["at-its-move", "after-its-move"])
@pytest.mark.parametrize(
    "worked",
    [("In Progress",), ("In Review", "In Progress")],
    ids=["set-again", "review-and-back"],
)
def test_a_stall_whose_item_a_person_worked_on_before_the_rerun_is_undone(
    roadmap: Roadmap, nth: int, worked: tuple[str, ...]
) -> None:
    """Seed 10129: the run that descopes an idle In Progress item stops at its Release write,
    or right after it, before it begins its Status write, and a person then sets the item In
    Progress again, or moves it into review and back. The item's Status holds what the change
    found, but its Status clock is the person's: the rerun judged the item by the clock as the
    change found it, still stalled, and finished the descope. The person's activity is new, so
    the rerun leaves the item, or puts it back, in v0.2.25."""
    item = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item)
    roadmap.now += timedelta(days=15)
    roadmap.stopped("set_field", nth)
    for status in worked:
        roadmap.set(item, ItemField.STATUS, status)
    roadmap.run()
    found = roadmap.item(item)
    assert (
        (found.release, found.status),
        roadmap.comments(item),
        found.job_record.get(JobMark.PENDING),
        roadmap.admitted(item),
    ) == ((CURRENT, "In Progress"), [], None, CURRENT)


@pytest.mark.parametrize(
    "worked",
    [("In Progress",), ("In Review", "In Progress")],
    ids=["set-again", "review-and-back"],
)
def test_a_stall_whose_move_landed_unconfirmed_leaves_the_status_a_person_set_since(
    roadmap: Roadmap, worked: tuple[str, ...]
) -> None:
    """The eleventh round's reviewers' case: the stall descope's milestone call lands and still
    reports a failure, so nothing shows who set the Release, and a person then sets the item In
    Progress again, or moves it into review and back. The rerun finishes the move as it stands,
    with its comment, but the Status is the person's: its clock has changed since the change
    began, though it holds what the change found. The rerun used to write Ready over it."""
    item = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item)
    roadmap.now += timedelta(days=15)
    roadmap.stopped_at(Fault(1, applied=True, write=FIELD, item=item))
    for status in worked:
        roadmap.set(item, ItemField.STATUS, status)
    roadmap.run()
    found = roadmap.item(item)
    assert (
        (found.release, found.status),
        len(roadmap.comments(item)),
        found.job_record.get(JobMark.PENDING),
    ) == ((NEXT, "In Progress"), 1, None)


@pytest.mark.parametrize(
    "worked",
    [("In Progress",), ("In Review", "In Progress")],
    ids=["set-again", "review-and-back"],
)
def test_a_stall_about_a_release_that_shipped_since_gives_way_to_the_status_a_person_set(
    roadmap: Roadmap, worked: tuple[str, ...]
) -> None:
    """The finding's other path: the stall descope stops at its Release write, before its
    milestone call, and v0.2.25 ships before the rerun; a person sets the item In Progress
    again, or moves it into review and back. The change is about a release that has shipped,
    so the rerun, v0.2.26's start, used to finish it: Ready over the person's Status, the item
    moved to v0.2.26 with the stall comment. The Status is the person's, so the change gives
    way: the item stays where the person worked on it, with no comment."""
    item = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item)
    roadmap.now += timedelta(days=15)
    roadmap.stopped("set_field")
    roadmap.ship()
    for status in worked:
        roadmap.set(item, ItemField.STATUS, status)
    plan = roadmap.plan()
    roadmap.run()
    found = roadmap.item(item)
    assert (
        plan.starting,
        (found.release, found.status),
        roadmap.comments(item),
        found.job_record.get(JobMark.PENDING),
    ) == (NEXT, (CURRENT, "In Progress"), [], None)


def test_a_fix_whose_release_was_cut_before_the_rerun_goes_to_the_next_release(
    started: Roadmap,
) -> None:
    """The reviewers' replay (d): the run that admits a New critical fix stops at its comment,
    and a person then opens a draft release pull request. The rerun sends the fix on, as a run
    after the cut would have."""
    fix = started.fix(status="New")
    started.stopped("comment")
    started.release_pull_request(draft=True)
    started.run()
    assert (started.release_of(fix), started.admitted(fix), started.comments(fix)) == (
        [NEXT],
        None,
        [
            "Moved to v0.2.26: v0.2.25 is cut, so nothing joins it until its release pull "
            "request is closed; a critical fix goes first into the next release."
        ],
    )


def test_an_admission_whose_comment_was_posted_before_the_cut_is_finished(
    started: Roadmap,
) -> None:
    """The fix was admitted, comment and all, before the run stopped at its last write and the
    release was cut: the rerun only records it, and the fix stays."""
    fix = started.fix(status="New")
    started.stopped("set_marks", 2)
    started.release_pull_request(draft=True)
    started.run()
    assert (started.release_of(fix), started.admitted(fix), len(started.comments(fix))) == (
        [CURRENT],
        CURRENT,
        1,
    )


def test_a_descope_a_ship_interrupted_is_finished_and_then_judged_by_the_start(
    roadmap: Roadmap,
) -> None:
    """The reviewers' replay: the run that descopes a Blocked item to v0.2.26 stops at its
    comment, and v0.2.25 ships before the rerun. The rerun finishes the descope, then starts
    v0.2.26 like any start: a Blocked item can't join it."""
    held = [roadmap.file("ready"), roadmap.file("to be blocked")]
    started_with(roadmap, *held)
    roadmap.set(held[1], ItemField.STATUS, "Blocked")
    roadmap.stopped("comment")
    roadmap.ship(close_milestone=True)
    roadmap.run()
    assert (roadmap.release_of(held[1]), roadmap.admitted(held[1]), roadmap.comments(held[1])) == (
        [None],
        None,
        [
            "Moved to v0.2.26: it is Blocked and had not started.",
            "Moved to the backlog: a Blocked item can't join a starting release (v0.2.26).",
        ],
    )


@pytest.mark.parametrize(
    "write", [RECORD, FIELD], ids=["at-its-job-record", "at-its-milestone-call"]
)
def test_a_pull_in_that_never_landed_before_its_release_shipped_is_dropped(write: str) -> None:
    """The twelfth round's reviewers' replay: v0.2.26's start pulls a backlog feature in and
    stops at that Release write, its job record or its milestone call failing, and v0.2.26
    ships before the next run. That run, v0.2.27's start, finished the pull-in as a change about
    another release, moving the feature into shipped v0.2.26, where no later start looks. The
    feature was never in v0.2.26 when it shipped: the run drops the pull-in, and v0.2.27's start
    pulls the feature in."""
    roadmap = Roadmap()
    started_with(roadmap, roadmap.file("held"))
    feature = roadmap.file("backlog feature", release=None)
    roadmap.ship(close_milestone=True)
    roadmap.stopped_at(Fault(1, write=write, item=feature))
    roadmap.ship(NEXT, close_milestone=True)
    plan = roadmap.plan()
    roadmap.run()
    found = roadmap.item(feature)
    assert (
        (plan.starting, [revert.item.number for revert in plan.reverts]),
        (found.release, roadmap.admitted(feature), found.job_record.get(JobMark.PENDING)),
        roadmap.comments(feature),
    ) == (
        (LATER, [feature]),
        (LATER, LATER, None),
        [
            "Moved to v0.2.27: v0.2.27 started with fewer than its 12 items and was topped up "
            "to 1 from Ready items, critical fixes and P0 features first."
        ],
    )


def _at_its_release_write(roadmap: Roadmap, number: int) -> None:
    """The run stops at the item's first field write, its Release: the in-memory store writes
    the record and the field in one step, so neither lands."""
    roadmap.stopped("set_field", when=lambda item, *_: item.number == number)


def _left_alone(roadmap: Roadmap, _: int) -> None:
    """The run is not stopped."""
    roadmap.run()


def _at_its_milestone_call(roadmap: Roadmap, number: int) -> None:
    """The run stops at the item's first field write, its Release, as GitHub takes it: the
    job record, naming the change's Release, lands, and the milestone call fails."""
    roadmap.stopped_at(Fault(1, write=FIELD, item=number))


Stop = Callable[[Roadmap, int], None]


def _late_feature_sent_back_by_hand(roadmap: Roadmap, stop: Stop) -> int:
    """S1: the run that sends a late P2 feature to the backlog stops at that write; a person
    moves it to the backlog and makes it P0."""
    started_with(roadmap, roadmap.file("held"))
    feature = roadmap.file("late feature")
    stop(roadmap, feature)
    roadmap.place(feature, None)
    roadmap.set(feature, ItemField.PRIORITY, "P0-Critical")
    return feature


def _p0_feature_placed_by_hand(roadmap: Roadmap, stop: Stop) -> int:
    """S5: the run that sends a late P0 feature to v0.2.26 stops at that write; a person
    places it in v0.2.26 and makes it P2."""
    started_with(roadmap, roadmap.file("held"))
    feature = roadmap.file("p0 feature", priority="P0-Critical")
    stop(roadmap, feature)
    roadmap.place(feature, NEXT)
    roadmap.set(feature, ItemField.PRIORITY, "P2-Medium")
    return feature


def _blocked_item_descoped_by_hand(roadmap: Roadmap, stop: Stop) -> int:
    """S7: the run that descopes a Blocked item stops at its Release write; a person moves it
    to v0.2.26 and sets it Ready."""
    held = [roadmap.file("a"), roadmap.file("b")]
    started_with(roadmap, *held)
    roadmap.set(held[1], ItemField.STATUS, "Blocked")
    stop(roadmap, held[1])
    roadmap.place(held[1], NEXT)
    roadmap.set(held[1], ItemField.STATUS, "Ready")
    return held[1]


def _stalled_item_moved_on_by_hand(roadmap: Roadmap, stop: Stop) -> int:
    """S8: the run that descopes an idle In Progress item stops at its Release write; a person
    moves it to v0.2.26 and sets it In Review."""
    item = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item)
    roadmap.now += timedelta(days=15)
    stop(roadmap, item)
    roadmap.place(item, NEXT)
    roadmap.set(item, ItemField.STATUS, "In Review")
    return item


def _new_item_sent_back_at_the_start_by_hand(roadmap: Roadmap, stop: Stop) -> int:
    """S10: v0.2.26's start stops at the write that sends a New item to the backlog; a person
    moves it to the backlog and sets it Ready."""
    started_with(roadmap, roadmap.file("held"))
    new = roadmap.file("new", status="New", release=NEXT)
    roadmap.file("next", release=NEXT)
    roadmap.ship(close_milestone=True)
    stop(roadmap, new)
    roadmap.place(new, None)
    roadmap.set(new, ItemField.STATUS, "Ready")
    return new


S_SCENARIOS = pytest.mark.parametrize(
    ("scenario", "place", "status"),
    [
        (_late_feature_sent_back_by_hand, None, "Ready"),
        (_p0_feature_placed_by_hand, NEXT, "Ready"),
        (_blocked_item_descoped_by_hand, NEXT, "Ready"),
        (_stalled_item_moved_on_by_hand, NEXT, "In Review"),
        (_new_item_sent_back_at_the_start_by_hand, None, "Ready"),
    ],
    ids=["s1-to-backlog", "s5-to-next", "s7-blocked", "s8-stall", "s10-new-at-start"],
)


@S_SCENARIOS
def test_a_value_a_person_set_where_a_stopped_change_never_wrote_it_is_never_put_back(
    scenario: Callable[[Roadmap, Stop], int], place: str | None, status: str
) -> None:
    """The reviewers' replays S1, S5, S7, S8 and S10: the stopped run never wrote the Release,
    and a person then set it to the very value the change was going to write, with another
    field. The `Pending` mark records no write of it, so the value is the person's: the rerun
    drops the change, writes no field of the item, and leaves it where the person put it."""
    roadmap = Roadmap()
    number = scenario(roadmap, _at_its_release_write)
    writes = roadmap.run()
    found = roadmap.item(number)
    assert (
        (found.release, found.status),
        roadmap.comments(number),
        roadmap.admitted(number),
        found.job_record.get(JobMark.PENDING),
        [write for write in writes if write.operation == "set_field" and write.number == number],
        roadmap.plan().has_writes,
    ) == ((place, status), [], None, None, [], False)


def _apart_from_left(roadmap: Roadmap, number: int) -> tuple[object, ...]:
    """`outcome`, with the `Left` mark of item `number` left out."""
    releases, branch, record, items, comments = outcome(roadmap)
    at = 3 + list(JobMark).index(JobMark.LEFT)
    rows = [row[:at] + row[at + 1 :] if row[0] == number else row for row in items]  # type: ignore[index]
    return releases, branch, record, rows, comments


@S_SCENARIOS
def test_a_value_a_person_set_after_a_release_write_whose_milestone_call_failed_stands(
    scenario: Callable[[Roadmap, Stop], int], place: str | None, status: str
) -> None:
    """The reviewers' replays S1, S5, S7, S8 and S10 in GitHub's order: the job record of the
    Release write lands, naming the change's Release as begun, and the milestone call fails;
    then a person sets the Release to that very value, with another field. The issue shows a
    Release change since the move began, so the value may be the job's write or the person's:
    the rerun never puts it back nor writes it, and finishes the move as one that happened. It
    ends where the run left alone ends once the person has made the same edits, with the same
    comment and marks and no `Left` mark, and the job record keeps no Release for the item, so
    its place counts as a person's. S10's rerun is still v0.2.26's start, which reads the
    backlog item's events and marks it as taken out of v0.2.26, the release it was in, so no
    later start pulls it back in."""
    left = NEXT if scenario is _new_item_sent_back_at_the_start_by_hand else None
    github, whole = Roadmap(), Roadmap()
    number = scenario(github, _at_its_milestone_call)
    begun = github.item(number).job_record.get(ItemField.RELEASE, "none")
    writes = github.run()
    assert scenario(whole, _left_alone) == number
    whole.run()
    found = github.item(number)
    assert (
        begun == place,
        (found.release, found.status),
        (github.comments(number), len(whole.comments(number))),
        github.titled(found.job_record.get(JobMark.LEFT)),
        found.job_record.get(ItemField.RELEASE, "none"),
        [write for write in writes if write.operation == "set_field" and write.number == number],
        github.plan().has_writes,
        _apart_from_left(github, number) == _apart_from_left(whole, number),
    ) == (True, (place, status), (whole.comments(number), 1), left, "none", [], False, True)


def test_a_status_a_person_set_back_after_a_stopped_run_wrote_it_stands(roadmap: Roadmap) -> None:
    """The reviewers' replay S9: the run that readies and descopes an idle item writes its
    Release and Status, then stops at its comment; an hour later a person sets the item In
    Progress again. That Status is the person's though the item held it before, so the rerun
    puts back only the Release the job wrote, posts nothing, and judges the item by the
    person's Status change, not the one before the stopped run."""
    item = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item)
    roadmap.now += timedelta(days=15)
    roadmap.stopped("comment")
    roadmap.now += timedelta(hours=1)
    roadmap.set(item, ItemField.STATUS, "In Progress")
    writes = roadmap.run()
    found = roadmap.item(item)
    assert (
        (found.release, found.status),
        roadmap.comments(item),
        [write for write in writes if write.operation == "set_field"],
        found.job_record.get(JobMark.PENDING),
    ) == ((CURRENT, "In Progress"), [], [JobWrite("set_field", item, "Release", CURRENT)], None)


def _a_written_release_put_back_then_set_by_hand(roadmap: Roadmap) -> int:
    """The descope of a Blocked item writes its Release and stops at its comment; a person sets
    the item In Progress, so the rerun drops the change, puts the Release back and stops before
    it clears the `Pending` mark; the person then places the item in v0.2.26, the change's own
    target."""
    held = [roadmap.file("a"), roadmap.file("b")]
    started_with(roadmap, *held)
    roadmap.set(held[1], ItemField.STATUS, "Blocked")
    roadmap.stopped("comment")
    roadmap.set(held[1], ItemField.STATUS, "In Progress")
    roadmap.stopped_at(Fault(1, False, "set_marks", held[1]))
    roadmap.place(held[1], NEXT)
    return held[1]


def _a_written_status_put_back_then_set_by_hand(roadmap: Roadmap) -> int:
    """The stall descope of an idle item writes its Release and Status and stops at its
    comment; an hour later a person sets the item In Progress, so the rerun drops the change,
    puts the Release back and stops before it clears the `Pending` mark; the person then sets
    the item Ready, the change's own value."""
    item = roadmap.file("in progress", status="In Progress")
    started_with(roadmap, item)
    roadmap.now += timedelta(days=15)
    roadmap.stopped("comment")
    roadmap.now += timedelta(hours=1)
    roadmap.set(item, ItemField.STATUS, "In Progress")
    roadmap.stopped_at(Fault(1, False, "set_marks", item))
    roadmap.set(item, ItemField.STATUS, "Ready")
    return item


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        (_a_written_release_put_back_then_set_by_hand, (NEXT, "In Progress")),
        (_a_written_status_put_back_then_set_by_hand, (CURRENT, "Ready")),
    ],
    ids=["release", "status"],
)
def test_a_written_field_a_person_set_to_the_changes_value_after_it_was_put_back_stands(
    scenario: Callable[[Roadmap], int], expected: tuple[str, str]
) -> None:
    """The twelfth round's reviewers' replays: a dropped change's revert puts a field it wrote
    back and stops before clearing its `Pending` mark, which still records the field as
    written, and a person then sets that field to the change's value. The next run took the
    value for the job's write: it moved the item out of v0.2.26, where the person placed it,
    or put back the Status clock from before the change and readied and descoped an item the
    person had just set Ready. The written mark keeps the field's event count or Status clock
    as the job's write left it, so a field that changed since is the person's."""
    roadmap = Roadmap()
    number = scenario(roadmap)
    roadmap.run()
    found = roadmap.item(number)
    assert (
        (found.release, found.status),
        roadmap.comments(number),
        found.job_record.get(JobMark.PENDING),
        roadmap.plan().has_writes,
    ) == (expected, [], None, False)


def test_a_release_write_after_a_person_moved_the_item_out_and_back_is_the_jobs() -> None:
    """A guard on the fix above: the descope of a Blocked item stops before its Release write
    begins; a person moves the item to v0.2.26, so the rerun drops the change and stops before
    it clears the `Pending` mark; the person moves it back, and that rerun finishes the descope
    and stops at its comment. Counted from when the change began, the job's own Release write
    read as changed since, and the next run dropped the job's move, uncommented. The count
    starts when the Release write begins."""
    roadmap = Roadmap()
    held = [roadmap.file("a"), roadmap.file("b")]
    started_with(roadmap, *held)
    roadmap.set(held[1], ItemField.STATUS, "Blocked")
    roadmap.stopped_at(Fault(1, False, RECORD, held[1]))
    roadmap.place(held[1], NEXT)
    roadmap.stopped_at(Fault(1, False, "set_marks", held[1]))
    roadmap.place(held[1], CURRENT)
    roadmap.stopped_at(Fault(1, False, "comment", held[1]))
    roadmap.run()
    assert (roadmap.release_of(held[1]), roadmap.comments(held[1])) == (
        [NEXT],
        ["Moved to v0.2.26: it is Blocked and had not started."],
    )


def test_a_finished_move_a_person_changed_before_the_rerun_records_where_they_put_it(
    started: Roadmap,
) -> None:
    """The reviewers' replay: the run that sends a late feature to the backlog posts its
    comment and stops at its last write; a person then places the feature in v0.2.27. The
    rerun only finishes the marks, and records that a person took the item out of the backlog
    where the job placed it, so the next run has nothing to do, and once the person puts it
    back in the backlog the next start leaves it there."""
    late = started.file("late feature")
    started.stopped("set_marks", nth=3, when=lambda item, *_: item.number == late)
    started.place(late, LATER)
    started.run()
    settled = (started.item(late).job_record.get(JobMark.LEFT), started.plan().has_writes)
    started.place(late, None)
    started.ship(close_milestone=True)
    started.run()
    assert (settled, started.release_of(late), started.item(late).job_record.get(JobMark.LEFT)) == (
        ("backlog", False),
        [None],
        "backlog",
    )


def _a_top_up_moved_back_by_hand(at: int, write: str) -> tuple[Roadmap, tuple[object, ...]]:
    """The job sends a late feature to the backlog; v0.2.26's start pulls it in, and that
    move's `at`-th `write` fails; a person then moves it back to the backlog, and the job runs
    again."""
    roadmap = Roadmap()
    started_with(roadmap, roadmap.file("held"))
    late = roadmap.file("late feature")
    roadmap.run()
    roadmap.ship(close_milestone=True)
    stopping = roadmap.stopped_at(Fault(at, write=write, item=late))
    roadmap.place(late, None)
    roadmap.run()
    found = roadmap.item(late)
    return roadmap, (
        stopping.writes[-1],
        found.release,
        roadmap.titled(found.job_record.get(JobMark.LEFT)),
        found.job_record.get(ItemField.RELEASE, "none"),
        len(roadmap.comments(late)),
        roadmap.admitted(late),
        roadmap.plan().has_writes,
    )


def test_a_top_up_a_person_undid_after_its_milestone_landed_leaves_the_item_where_they_put_it() -> (
    None
):
    """The top-up's milestone call lands and its written mark fails, or its comment fails one
    write later, and a person moves the item back to the backlog before the rerun. Either way
    the person's placement stands: the rerun drops the move, marks the item as taken out of
    v0.2.26, and pulls nothing back in. The written mark's failure leaves no proof the job set
    the Release, so the item's job record keeps none for it: had it put back the record from
    before the move, which named the backlog where the job had sent the item, the person's
    placement would read as the job's, and the same start would pull the item in again."""
    unconfirmed, unconfirmed_outcome = _a_top_up_moved_back_by_hand(2, "set_marks")
    commented, commented_outcome = _a_top_up_moved_back_by_hand(1, "comment")
    assert (unconfirmed_outcome, commented_outcome, outcome(unconfirmed) == outcome(commented)) == (
        ("set_marks", None, NEXT, "none", 1, None, False),
        ("comment", None, NEXT, NEXT, 1, None, False),
        True,
    )


def test_a_renamed_release_is_not_started_again_and_its_items_stay_admitted(
    roadmap: Roadmap,
) -> None:
    """The reviewers' replay: after the first run, a person files a P2 feature into v0.2.25
    and a Ready P1 item into the backlog, then renames v0.2.27, v0.2.26 and v0.2.25 to v0.3.2,
    v0.3.1 and v0.3.0. GitHub keeps a milestone by its number, so v0.3.0 is the release that
    started: the feature goes to the backlog, and the plan and comment name v0.3.0."""
    held = [roadmap.file(f"held {n}") for n in range(3)] + [roadmap.file("new", status="New")]
    roadmap.run()
    feature = roadmap.file("late feature")
    waiting = roadmap.file("waiting", priority="P1-High", release=None)
    for old, new in ((LATER, "v0.3.2"), (NEXT, "v0.3.1"), (CURRENT, "v0.3.0")):
        roadmap.person.edit_release(old, title=new)
    plan = roadmap.plan()
    roadmap.run()
    assert (
        (plan.current, plan.starting),
        roadmap.release_of(*held, feature, waiting),
        [roadmap.admitted(number) for number in held],
        roadmap.comments(feature),
        roadmap.run_record(),
        roadmap.store.branch("release/v0.3.0"),
    ) == (
        ("v0.3.0", None),
        ["v0.3.0"] * 4 + [None, None],
        ["v0.3.0"] * 4,
        [
            "Moved to the backlog: after v0.3.0 started, only a critical fix can join it. A "
            "person can place it in a planned release, and that placement stands."
        ],
        {JobMark.STARTED: "v0.3.0", JobMark.SIZE: "4"},
        None,
    )


def test_an_item_closed_at_the_first_run_and_reopened_stays_in_the_release(
    roadmap: Roadmap,
) -> None:
    """The reviewers' replay: the first run admits the release's closed items too, so one a
    person reopens never joined it. Its size counts only the open one."""
    roadmap.file("held")
    done = roadmap.file("done", priority="P1-High", status="Done")
    roadmap.person.close_issue(done, CloseReason.COMPLETED, "Delivered.")
    roadmap.run()
    roadmap.person.reopen_issue(done)
    roadmap.set(done, ItemField.STATUS, "In Progress")
    roadmap.run()
    assert (
        roadmap.release_of(done),
        roadmap.admitted(done),
        roadmap.comments(done),
        roadmap.run_record()[JobMark.SIZE],
    ) == ([CURRENT], CURRENT, ["Delivered."], "1")


def test_an_item_closed_when_its_release_started_and_reopened_stays_in_it(
    started: Roadmap,
) -> None:
    done = started.file("done", release=NEXT, status="Done")
    started.person.close_issue(done, CloseReason.COMPLETED, "Delivered.")
    started.file("next", release=NEXT)
    started.ship(close_milestone=True)
    started.run()
    started.person.reopen_issue(done)
    started.set(done, ItemField.STATUS, "In Progress")
    started.run()
    assert (started.release_of(done), started.admitted(done), started.run_record()) == (
        [NEXT],
        NEXT,
        {JobMark.STARTED: NEXT, JobMark.SIZE: "1"},
    )


def test_a_closed_admitted_item_taken_out_and_put_back_is_judged_again_once_reopened(
    roadmap: Roadmap,
) -> None:
    """The reviewers' replay: the first run admits a closed item with the rest of v0.2.25. A
    person moves it, still closed, to the backlog, a run follows, then back into v0.2.25, a run
    follows, and then reopens it In Progress. The run that saw it out cleared its mark as for
    an open item, so the reopened P2 item joined after the start and goes to the backlog."""
    roadmap.file("held")
    done = roadmap.file("done", status="Done")
    roadmap.person.close_issue(done, CloseReason.COMPLETED, "Delivered.")
    roadmap.run()
    roadmap.place(done, None)
    roadmap.run()
    cleared = (
        roadmap.admitted(done),
        roadmap.titled(roadmap.item(done).job_record.get(JobMark.LEFT)),
    )
    roadmap.place(done, CURRENT)
    roadmap.run()
    roadmap.person.reopen_issue(done)
    roadmap.set(done, ItemField.STATUS, "In Progress")
    roadmap.run()
    assert (cleared, roadmap.release_of(done), roadmap.admitted(done)) == (
        (None, CURRENT),
        [None],
        None,
    )


def _completes_the_run_record(marks: Mapping[JobMark, str | None]) -> bool:
    """Whether a run record write is the one that gives the size, which completes it."""
    return JobMark.SIZE in marks


def test_a_first_run_that_stopped_after_its_marks_clears_the_mark_of_an_item_moved_out(
    roadmap: Roadmap,
) -> None:
    """The reviewers' replay: the first run marks two P2 features and stops before its run
    record is complete; a person moves one to v0.2.26. The rerun records v0.2.25 without it
    and clears its mark, so putting it back is a join the admission rule judges."""
    roadmap.file("a")
    moved = roadmap.file("b")
    roadmap.stopped("set_run_record", when=_completes_the_run_record)
    roadmap.place(moved, NEXT)
    roadmap.run()
    cleared = roadmap.admitted(moved)
    roadmap.place(moved, CURRENT)
    roadmap.run()
    assert (cleared, roadmap.run_record()[JobMark.SIZE], roadmap.release_of(moved)) == (
        None,
        "1",
        [None],
    )


def test_a_start_that_stopped_after_its_marks_clears_the_mark_of_an_item_moved_out(
    started: Roadmap,
) -> None:
    started.file("a", release=NEXT)
    moved = started.file("b", release=NEXT)
    started.ship(close_milestone=True)
    started.stopped("set_run_record", when=_completes_the_run_record)
    started.place(moved, LATER)
    started.run()
    cleared = started.admitted(moved)
    started.place(moved, NEXT)
    started.run()
    assert (cleared, started.run_record()[JobMark.SIZE], started.release_of(moved)) == (
        None,
        "1",
        [None],
    )


def test_a_run_record_card_taken_off_the_board_is_refused_not_taken_for_a_first_run(
    started: Roadmap,
) -> None:
    """The reviewers' replay: a person removes the run record card after the release started.
    Items carry the job's marks, so the next run refuses, naming the card, instead of
    admitting the P2 feature filed since as a first run would."""
    started.file("late feature")
    card = next(c for c in started.store.cards() if c.kind is CardKind.DRAFT_ISSUE)
    started.person.remove_card(card)
    writes = started.store.job_writes()
    with pytest.raises(ConfigurationError, match="Roadmap run record") as refused:
        started.plan()
    assert ("#1" in str(refused.value), started.store.job_writes()) == (True, writes)


@pytest.mark.parametrize("started_mark", ["v0.2.25", None])
def test_a_run_record_whose_started_mark_names_no_milestone_number_is_refused_as_unreadable(
    started: Roadmap, started_mark: str | None
) -> None:
    """The reviewers' replay: a person types the release's title into the card's Started mark.
    The card is on the board, so the refusal says its record can't be read and asks for the
    milestone number; it does not send the person looking for a missing card."""
    started.file("late feature")
    started.store.set_run_record({JobMark.STARTED: started_mark})
    writes = started.store.job_writes()
    with pytest.raises(ConfigurationError) as refused:
        started.plan()
    message = str(refused.value)
    assert (
        "is on the board" in message,
        f'for the current release, {CURRENT}, that is "{started.number(CURRENT)}"' in message,
        "has no" in message,
        started.store.job_writes(),
    ) == (True, True, False, writes)


def test_a_run_record_naming_a_milestone_that_is_gone_is_refused(started: Roadmap) -> None:
    started.person.delete_release(CURRENT)
    with pytest.raises(ConfigurationError, match="names milestone #1"):
        started.plan()


def test_a_pending_mark_this_version_cannot_read_is_dropped(started: Roadmap) -> None:
    """A mark a newer version wrote, or one naming a Release that is gone, can't be finished:
    the run clears it and judges the item as it is."""
    feature = started.file("late feature")
    started.store.set_marks(started.item(feature), {JobMark.PENDING: '{"event": "later"}'})
    report = render_plan(started.plan())
    started.run()
    assert (
        f"#{feature} late feature: an earlier run left a change this run can't read" in report,
        started.item(feature).job_record.get(JobMark.PENDING),
        started.release_of(feature),
    ) == (True, None, [None])


def test_a_milestone_older_than_the_started_release_is_held_to_no_rule(started: Roadmap) -> None:
    """The reviewers' replay: once v0.2.25 started, a person opens v0.2.24.1 and files a
    security fix, a P0 feature and a Blocked item into it. v0.2.24.1 is the current release,
    yet it never started: the job moves nothing, and nothing into v0.2.25."""
    hotfix = "v0.2.24.1"
    started.person.create_release(hotfix)
    filed = [
        started.file("fix", kind="security", priority="P0-Critical", release=hotfix),
        started.file("p0 feature", priority="P0-Critical", release=hotfix),
        started.file("blocked", priority="P1-High", status="Blocked", release=hotfix),
    ]
    plan = started.plan()
    writes = started.run()
    assert (
        plan.current,
        writes,
        started.release_of(*filed),
        f"{hotfix} is older than {CURRENT}" in render_plan(plan),
    ) == (hotfix, [], [hotfix] * 3, True)


# ── When the job is due ───────────────────────────────────────────────────────

LAST_CHECK = NOW - timedelta(hours=1)


def _due(roadmap: Roadmap, act: Callable[[Roadmap], object]) -> bool:
    """Whether the job is due after `act`, polled a minute later and an hour after the last
    stall check."""
    roadmap.now += timedelta(minutes=1)
    since = roadmap.now
    act(roadmap)
    last_check = roadmap.now - timedelta(hours=1)
    return is_due(roadmap.store.changes_since(since), roadmap.now, last_check)


def _edited(roadmap: Roadmap) -> list[Change]:
    """GitHub reports a body edit as `edited`; no store write makes one."""
    return [Change(kind=ChangeKind.EDITED, number=1, actor="alice", at=NOW, release=CURRENT)]


@pytest.mark.parametrize(
    "act",
    [
        lambda r: r.store.comment(1, "Any update?"),
        lambda r: r.run(),
        lambda r: r.set(1, ItemField.VALUE, "High"),
    ],
    ids=["comment", "the-jobs-own-changes", "value"],
)
def test_is_due_is_false_for_comments_and_the_jobs_own_changes(
    roadmap: Roadmap, act: Callable[[Roadmap], object]
) -> None:
    """The job's own run descopes a Blocked item and admits a fix: no change it made counts."""
    started_with(roadmap, roadmap.file("held"))
    roadmap.set(roadmap.file("blocked"), ItemField.STATUS, "Blocked")
    roadmap.fix()
    assert (_due(roadmap, act), is_due(_edited(roadmap), NOW, LAST_CHECK)) == (False, False)


TRIGGERS: dict[str, Callable[[Roadmap], object]] = {
    "cut": lambda r: r.release_pull_request(draft=True),
    "un-cut": lambda r: r.person.close_pull_request(r.release_pull_request()),
    "ship": lambda r: r.ship(),
    "added": lambda r: r.file("added"),
    "removed": lambda r: r.place(1, None),
    "priority": lambda r: r.set(1, ItemField.PRIORITY, "P1-High"),
    "status": lambda r: r.set(1, ItemField.STATUS, "In Progress"),
    "release": lambda r: r.place(1, NEXT),
    "label": lambda r: r.person.add_label(1, "needs-split"),
    "blocked-by": lambda r: r.person.link_dependency(1, r.file("elsewhere", release=None)),
    "closed": lambda r: r.person.close_issue(1, CloseReason.COMPLETED, "Delivered."),
}


@pytest.mark.parametrize("act", TRIGGERS.values(), ids=TRIGGERS.keys())
def test_is_due_is_true_for_each_trigger(
    started: Roadmap, act: Callable[[Roadmap], object]
) -> None:
    assert _due(started, act) is True


def test_is_due_when_a_person_puts_back_an_item_where_a_job_had_placed_and_admitted_it(
    started: Roadmap,
) -> None:
    """Putting it back sets the Release the job last set, which alone reads as the job's own
    change; the `Left` mark the job recorded when the person took it out says otherwise."""
    started.store.set_field(started.item(1), ItemField.RELEASE, CURRENT)
    started.place(1, None)
    started.run()
    left = started.item(1).job_record
    assert (
        (left.get(JobMark.ADMITTED), started.titled(left.get(JobMark.LEFT))),
        _due(started, lambda r: r.place(1, CURRENT)),
    ) == ((None, CURRENT), True)


def test_is_due_when_a_person_takes_an_admitted_item_back_to_where_a_job_last_placed_it(
    started: Roadmap,
) -> None:
    """The job sent a P2 feature to the backlog, and a person placed it in v0.2.26, which then
    started holding it. Taking it back to the backlog sets the Release the job last set, yet
    is no job's change: its `Admitted` mark still names v0.2.26. Were the run that clears the
    mark skipped, putting the item back would escape the admission rule."""
    feature = started.file("late feature")
    started.run()
    started.place(feature, NEXT)
    started.ship()
    started.run()
    due = _due(started, lambda r: r.place(feature, None))
    if due:
        started.run()
    started.place(feature, NEXT)
    started.run()
    assert (due, started.release_of(feature)) == (True, [None])


def test_is_due_on_a_release_start_and_once_a_day_for_the_stall_check() -> None:
    start = Change(kind=ChangeKind.RELEASE_STARTED, number=0, actor=None, at=NOW, release=NEXT)
    day = timedelta(days=1)
    assert (
        is_due([start], NOW, LAST_CHECK),
        is_due([], NOW, None),
        is_due([], NOW, NOW - day + timedelta(seconds=1)),
        is_due([], NOW, NOW - day),
    ) == (True, True, False, True)


# ── The command and its MCP mirror ────────────────────────────────────────────


@pytest.fixture
def board(roadmap_store: InMemoryRoadmapStore) -> Roadmap:
    """The store every command opens, with the board's fields and `.github/roadmap.toml`."""
    for board_field, names in OPTIONS.items():
        roadmap_store.seed_field(
            FieldSpec(
                name=board_field.value,
                single_select=True,
                options=tuple(FieldOption(name=name) for name in names),
            )
        )
    roadmap_store.seed_file(".github/roadmap.toml", "board = 1\n")
    return Roadmap(roadmap_store)


def _reprioritize(*flags: str) -> str:
    result = runner.invoke(app, ["reprioritize", "--repo", REPO, *flags])
    assert result.exit_code == 0, result.output
    return " ".join(result.output.split())


def _snapshot(store: InMemoryRoadmapStore) -> tuple[Iterable[object], ...]:
    return (store.items(), store.releases(), store.job_writes())


def test_plan_lists_each_change_with_its_reason_and_writes_nothing(board: Roadmap) -> None:
    held = board.file("held")
    first = _reprioritize("--confirm")
    late = board.file("late feature")
    before = _snapshot(board.store)
    previews = [_reprioritize("--plan"), _reprioritize()]
    unchanged = _snapshot(board.store) == before
    applied = _reprioritize("--confirm")
    change = (
        f"#{late} late feature: Moved to the backlog: after v0.2.25 started, only a critical "
        "fix can join it."
    )
    assert (
        f"records the admitted set of {CURRENT}" in first,
        [change in preview and "Nothing was written" in preview for preview in previews],
        unchanged,
        "Made 1 change(s)" in applied,
        board.release_of(held, late),
    ) == (True, [True, True], True, True, [CURRENT, None])


def test_the_mcp_mirror_previews_unless_its_mode_is_confirm(board: Roadmap) -> None:
    board.file("held")
    tool = asyncio.run(mcp_server.mcp.get_tool("roadmap_reprioritize"))
    names = {listed.name for listed in asyncio.run(mcp_server.mcp._list_tools())}

    def in_process(cmd: list[str], **_: object) -> str:
        return runner.invoke(app, cmd[4:]).output

    with patch.object(mcp_server, "_run_mcp_cmd", side_effect=in_process):
        mcp_server.roadmap_reprioritize(repo=REPO)
        previewed = len(board.store.job_writes())
        mcp_server.roadmap_reprioritize(repo=REPO, mode="confirm")
    assert (
        "roadmap_reprioritize" in names,
        tool.parameters["properties"]["mode"]["default"] if tool else None,
        previewed,
        len(board.store.job_writes()) > previewed,
    ) == (True, "plan", 3, True)


def test_the_needs_split_label_the_rules_read_is_one_the_repository_declares() -> None:
    declared = {spec.name for spec in load_label_specs(Path(".github/labels.yml"))}
    assert CONST_ROADMAP_NEEDS_SPLIT_LABEL in declared

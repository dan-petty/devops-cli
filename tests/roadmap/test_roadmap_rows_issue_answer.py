"""A row leaves out an item that is no issue of the repository now, and goes on (#7331, #7337).

The snapshot of a lane keeps the record of an issue that left the repository until the next full
read. GitHub redirects the read of such an issue by its number, and the answer names the issue at
its new place. A listing below its number answers 404. The store refuses that answer, drops the
record and logs the number one time. The row sends no write request for the item, gives it no
failure, and works on its other items in the same round. The later rounds of the lane do not list
the item.

The rows run on the GitHub store over `GitHubFake`, the `gh` process edge.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from devops_cli.roadmap.alternatives import (
    AlternativesPlan,
    AlternativesWriter,
    plan_alternatives,
    raise_for_failed_checks,
)
from devops_cli.roadmap.implement.implement import reset_retry_reads
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.run import service_job
from devops_cli.roadmap.status_sync import (
    ClosedCleared,
    StatusSynced,
    clear_closed_issues,
    sync_statuses,
)
from devops_cli.roadmap.stop_clear import ClearLimits, StopsCleared, clear_stops
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import FileSnapshotStore, IncrementalListing
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    ItemField,
    encode_job_record,
    install_roadmap_store,
    with_record,
)
from devops_cli.server.service import TriggerBatch
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.github_repository import GitHubFake
from tests.support.scripted_model import Script

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "acme/widgets"
OTHER = "acme/other"
ITEM_LABELS = ("priority/p2-medium", "status/ready")
ITEM_BODY = with_record("Text of 7", encode_job_record({}, {ItemField.STATUS: "Ready"}))


def _round(github: GitHubFake, listing: IncrementalListing) -> GitHubRoadmapStore:
    """The store of one round of a lane, which reads every issue through `listing`."""
    return GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github), listing=listing)


def _numbers(store: GitHubRoadmapStore) -> list[int]:
    """The numbers of the items that the store lists, in order of number."""
    return sorted(item.number for item in store.items())


@pytest.fixture
def github() -> GitHubFake:
    """A repository with the item #7, whose type is a skip class of the alternatives check and
    whose Status the Service owns, and with the closed item #12."""
    fake = GitHubFake(REPO)
    fake.seed_issue(7, "docs(roadmap): explain the check", labels=ITEM_LABELS, body=ITEM_BODY)
    fake.seed_issue(12, "An older item", state="closed", labels=ITEM_LABELS, body="Text of 12")
    return fake


@pytest.fixture
def lane(github: GitHubFake, tmp_path: Path) -> IncrementalListing:
    """The listing of a lane whose snapshot holds #7 as an open item. After the lane kept the
    snapshot, the issue left the repository: it is issue #12 of another repository now."""
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    assert _numbers(_round(github, listing)) == [7, 12]
    github.move_issue(7, to=OTHER, as_number=12)
    return listing


def _alternatives(github: GitHubFake, lane: IncrementalListing, model: Script) -> AlternativesPlan:
    """One round of the alternatives check on the lane, as the row runs it: each check is written
    when it is done, and the round fails when it tried items and checked none."""
    store = _round(github, lane)
    plan = plan_alternatives(
        store,
        repo=REPO,
        investigator=model.model(),
        writer=AlternativesWriter(store, REPO),
        limit=20,
    )
    raise_for_failed_checks(plan)
    return plan


def _checked(plan: AlternativesPlan) -> tuple[list[int], list[int]]:
    """The numbers of the items that the round checked, and of the items whose check failed."""
    return (
        [check.item.number for check in plan.checks],
        [failure.item.number for failure in plan.failures],
    )


def _lines_about(caplog: pytest.LogCaptureFixture, number: int) -> list[str]:
    """Each logged line that names item `number`."""
    return [text for log in caplog.records if f"#{number} " in (text := log.getMessage())]


def test_an_alternatives_round_leaves_out_an_item_that_left_and_checks_the_other_due_item(
    github: GitHubFake,
    lane: IncrementalListing,
    config: Callable[..., Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The round reads the body of #7 again before it writes the check. The answer names another
    issue, so the round leaves #7 out with one log line that names its new place. It checks #8,
    the other due item, and ends with success. The next round selects neither."""
    config(roadmap={"alternatives": {"references": "off"}})
    github.seed_issue(8, "docs(roadmap): explain the round", labels=ITEM_LABELS, body="Text of 8")
    model = Script()

    with caplog.at_level(logging.INFO):
        first = _alternatives(github, lane, model)
    second = _alternatives(github, lane, model)

    written = [args for args in github.writes() if f"repos/{REPO}/issues/8" in args]
    assert (_checked(first), _checked(second), _numbers(_round(github, lane)), model.seen) == (
        ([8], []),
        ([], []),
        [8, 12],
        [],
    )
    assert (len(written), len(github.writes())) == (1, 1)
    assert _lines_about(caplog, 7) == [
        f"#7 is no issue of {REPO} now: GitHub answers with {OTHER}#12. The store leaves it out."
    ]


def test_an_alternatives_round_leaves_out_an_item_whose_comments_answer_404(
    github: GitHubFake, tmp_path: Path, config: Callable[..., Any]
) -> None:
    """#9 is no skip class, so the first read of the round for it is the listing of its
    comments, which answers 404 after the issue left. The record leaves the listing at that read:
    the round calls no model for #9, checks #7, and the next round does not select #9."""
    config(roadmap={"alternatives": {"references": "off"}})
    github.seed_issue(9, "feat(roadmap): add a check", labels=ITEM_LABELS, body="Text of 9")
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    assert _numbers(_round(github, listing)) == [7, 9, 12]
    github.move_issue(9, to=OTHER, as_number=13)
    model = Script()

    first = _alternatives(github, listing, model)
    listed = _numbers(_round(github, listing))
    second = _alternatives(github, listing, model)

    assert (_checked(first), listed, _checked(second), model.seen) == (
        ([7], []),
        [7, 12],
        ([], []),
        [],
    )
    assert [args for args in github.writes() if f"repos/{REPO}/issues/9" in args] == []


def test_an_alternatives_round_with_10_items_that_left_ends_with_success_in_one_run(
    tmp_path: Path, config: Callable[..., Any]
) -> None:
    """Ten open items left the repository at one time: five of a skip class and five of no skip
    class. One round leaves out each of them, fails for none and checks the one item that
    stayed."""
    config(roadmap={"alternatives": {"references": "off"}})
    fake = GitHubFake(REPO)
    titles = ("docs(roadmap): explain the check", "feat(roadmap): add a check")
    for number in range(1, 12):
        fake.seed_issue(number, titles[number % 2], labels=ITEM_LABELS, body=f"Text of {number}")
    fake.issues[11]["title"] = titles[0]
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    assert _numbers(_round(fake, listing)) == list(range(1, 12))
    for number in range(1, 11):
        fake.move_issue(number, to=OTHER, as_number=100 + number)
    model = Script()

    plan = _alternatives(fake, listing, model)

    assert (_checked(plan), _numbers(_round(fake, listing)), model.seen) == (([11], []), [11], [])


def test_a_status_sweep_sends_no_write_for_an_item_whose_read_answers_with_another_issue(
    github: GitHubFake, lane: IncrementalListing
) -> None:
    """The plan of the item is on the default branch, so the sweep sets its Status to Planned.
    It reads the issue again first. The answer names another issue, so the sweep leaves the item,
    and the next round does not list it."""
    planned = PlannedChanges("main", {7: "7-a-change"}, {})

    synced = sync_statuses(_round(github, lane), repo=REPO, planned=planned)
    later = _round(github, lane)
    synced_later = sync_statuses(later, repo=REPO, planned=planned)

    assert (synced, synced_later, _numbers(later), github.writes()) == (
        StatusSynced(),
        StatusSynced(),
        [12],
        [],
    )


def _stopped(number: int) -> dict[str, Any]:
    """The body and the labels of an item that a stop of the Service set Blocked."""
    record = encode_job_record({ImplementRecordKey.STOPPED: "job"}, {ItemField.STATUS: "Blocked"})
    return {
        "labels": ("priority/p2-medium", "status/blocked"),
        "body": with_record(f"Text of {number}", record),
    }


def test_the_status_passes_of_the_implement_row_leave_out_an_item_that_left_and_go_on(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The implement row sets the Status of its items in three passes: the Status sweep, the
    clear of the closed issues and the clear of the stops. #7 holds a stop of the Service, so the
    stop pass lists its comments to find a retry of a person. #7 left the repository: its issue
    route answers with the issue at its new place and its comments route answers 404. No pass
    fails for #7, the stop pass goes on with #6 and #8, and the sweep sets the Status of #9."""
    reset_retry_reads()
    fake = GitHubFake(REPO)
    for number in (6, 7, 8):
        fake.seed_issue(number, f"fix(roadmap): repair {number}", **_stopped(number))
    fake.seed_issue(9, "fix(roadmap): repair 9", labels=ITEM_LABELS, body=ITEM_BODY)
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    assert _numbers(_round(fake, listing)) == [6, 7, 8, 9]
    fake.move_issue(7, to=OTHER, as_number=12)
    planned = PlannedChanges("main", {9: "9-a-change"}, {})
    store = _round(fake, listing)

    with caplog.at_level(logging.INFO):
        swept = sync_statuses(store, repo=REPO, planned=planned)
        closed = clear_closed_issues(store, repo=REPO)
        stops = clear_stops(
            store, planned=planned, digest=lambda: None, limits=ClearLimits(1, 3, 2)
        )

    read = [args[0] for args in fake.calls if "/comments" in args[0]]
    assert (swept, closed, stops, _numbers(store), _numbers(_round(fake, listing))) == (
        StatusSynced(changed=(9,)),
        ClosedCleared(),
        StopsCleared(),
        [6, 8, 9],
        [6, 8, 9],
    )
    assert sorted(path.split("/issues/")[1][0] for path in read) == ["6", "7", "8"]
    assert _lines_about(caplog, 7) == [
        f"#7 is no issue of {REPO} now: GitHub answers with {OTHER}#12. The store leaves it out."
    ]


@pytest.mark.parametrize("action", ["transferred", "deleted"])
def test_a_round_drops_the_record_of_an_issue_that_a_delivery_says_left(
    github: GitHubFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    action: str,
) -> None:
    """The batch of a lane holds an `issues` delivery with the action `transferred` or `deleted`
    for #7. The round of the lane drops the record of #7 from its listing before any row runs,
    with no read of #7 from GitHub, and no later round lists it. A batch of another delivery
    drops nothing."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / "data"))
    listing = IncrementalListing(FileSnapshotStore(tmp_path / "listing"))
    install_roadmap_store(lambda repo, *, listing=None, **_: _round(github, listing))
    assert _numbers(_round(github, listing)) == [7, 12]
    at = datetime(2026, 11, 26, tzinfo=UTC)
    other = TriggerBatch(
        repo=REPO,
        counts={("webhook", "issues", "labeled"): 1},
        first_at=at,
        last_at=at,
        subjects=frozenset({7}),
    )
    left = other.model_copy(
        update={"counts": {("webhook", "issues", action): 1}, "left": frozenset({7})}
    )

    service_job(other, table=(), lane="status", listing=listing)
    listed_after_another_delivery = _numbers(_round(github, listing))
    github.move_issue(7, to=OTHER, as_number=12)
    with caplog.at_level(logging.INFO):
        service_job(left, table=(), lane="status", listing=listing)

    read = [args for args in github.calls if f"repos/{REPO}/issues/7" in " ".join(args)]
    assert (listed_after_another_delivery, _numbers(_round(github, listing)), read) == (
        [7, 12],
        [12],
        [],
    )
    assert _lines_about(caplog, 7) == [
        f"#7 is no issue of {REPO} now: a delivery says that it left. The lane status leaves "
        "it out."
    ]

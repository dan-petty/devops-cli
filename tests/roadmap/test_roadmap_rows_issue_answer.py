"""A row sends no write for an item whose issue read answers with another issue (#7331).

The snapshot of a lane keeps the record of an issue that left the repository until the next full
read. GitHub redirects the read of such an issue by its number, and the answer names the issue at
its new place. The store refuses that answer, so the row sends no write request, and the later
rounds of the lane do not list the item.

The rows run on the GitHub store over `GitHubFake`, the `gh` process edge.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.alternatives import AlternativesWriter, plan_alternatives
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.status_sync import StatusSynced, sync_statuses
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import FileSnapshotStore, IncrementalListing
from devops_cli.roadmap.stores.store import ItemField, encode_job_record, with_record
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


def test_an_alternatives_round_sends_no_write_for_an_item_whose_read_answers_with_another_issue(
    github: GitHubFake, lane: IncrementalListing, config: Callable[..., Any]
) -> None:
    """The round reads the body of the item again before it writes the check. The answer names
    another issue, so the store refuses the read as it refuses the read of a missing issue, and
    the next round does not select the item."""
    config(roadmap={"alternatives": {"references": "off"}})
    model = Script()
    first = _round(github, lane)

    with pytest.raises(GitHubOperationError) as refused:
        plan_alternatives(
            first, repo=REPO, investigator=model.model(), writer=AlternativesWriter(first, REPO)
        )
    second = _round(github, lane)
    plan = plan_alternatives(
        second, repo=REPO, investigator=model.model(), writer=AlternativesWriter(second, REPO)
    )

    assert (
        str(refused.value),
        (plan.checks, plan.failures),
        _numbers(second),
        github.writes(),
        model.seen,
    ) == (f"#7 is not an issue of {REPO}.", ([], []), [12], [], [])


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

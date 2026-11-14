"""The requests that a round sends to GitHub over `GitHubFake`: the issue events it reads and the
Projects requests it never sends (#1361, ADR 0016).
"""

from __future__ import annotations

from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from devops_cli.roadmap.run import (
    run_due_jobs,
    service_job,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import Change, ChangeKind
from tests.support.fakes.github import API, RunnerSession
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.process import ProcessFake
from tests.support.roadmap_run import (
    NOW,
    PLANNED,
    POLL,
    POLL_KEY,
    REPO,
    IntakeModel,
    intake_table,
    labeled_changes,
    poll_round,
    serve_over,
    service_github,
    stamp_successes,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def _github_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, events: list[dict[str, Any]]
) -> tuple[GitHubFake, GitHubRoadmapStore]:
    """A repository with 60 Items and an open milestone, its intake run five minutes ago, the
    Service logged in as `roadmap-bot`, and the store a round opens over it."""
    github = GitHubFake(
        REPO, milestones=[{"number": 26, "title": PLANNED, "state": "open"}], events=events
    )
    for number in range(1, 61):
        github.seed_issue(number, labels=("priority/p2-medium", "status/ready"))
    stamp_successes(tmp_path, intake=NOW - timedelta(minutes=5))
    store = GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))
    return github, store


@pytest.mark.usefixtures("roadmap_bot")
def test_a_round_judging_50_foreign_label_changes_reads_only_the_issue_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A label change makes no job due, and no rule reads an Item or an issue for it, so the
    round reads the issue events and nothing else (#1360)."""
    github, store = _github_round(tmp_path, monkeypatch, labeled_changes(50, "alice"))
    ran = poll_round(store, tmp_path)
    assert (ran, [args[-1].split("?")[0] for args in github.calls]) == (
        (),
        [f"{API}/repos/{REPO}/issues/events"],
    )


@pytest.mark.usefixtures("roadmap_bot")
def test_a_poll_whose_changes_are_all_the_services_own_sends_no_graphql_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Service's own events are dropped, so a poll with no interval due and nothing else
    since the cutoff reads only the issue events (#1360)."""
    github, store = _github_round(tmp_path, monkeypatch, labeled_changes(12, "roadmap-bot"))
    ran = poll_round(store, tmp_path)
    assert (ran, [args[-1].split("?")[0] for args in github.calls]) == (
        (),
        [f"{API}/repos/{REPO}/issues/events"],
    )


@pytest.mark.usefixtures("roadmap_bot")
def test_a_service_round_that_places_a_candidate_sends_no_projects_request(
    process_fake: ProcessFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reopened issue makes intake due in a model-lane round. The round places the candidate
    with labels alone: it sends no request to a project board and reads no
    `.github/roadmap.toml` (ADR 0016)."""
    reopened = {"event": "reopened", "actor": {"login": "alice"}, "issue": {"number": 4}}
    github = service_github([reopened])
    github.seed_issue(4, "A candidate", body="Export the report as CSV.")
    serve_over(tmp_path, monkeypatch, github)
    github.install(process_fake)
    model, ran = IntakeModel(), []
    lane = partial(service_job, table=intake_table(model, ran), lane="intake")
    lane(POLL)
    assert (ran, github.project_calls(), sorted(github.labels(4))) == (
        ["intake"],
        [],
        ["effort/low", "priority/p2-medium", "status/new", "type/feature", "value/medium"],
    )


@pytest.mark.usefixtures("roadmap_bot")
def test_three_lanes_of_one_poll_share_one_issue_events_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lanes of a repository run on separate workers, and one poll reads the issue events
    once for all of them (#3942)."""
    from devops_cli.roadmap.run import PollCache

    github, store = _github_round(tmp_path, monkeypatch, labeled_changes(3, "alice"))
    cache = PollCache()
    table = intake_table(IntakeModel([]), [])

    for _ in range(3):
        run_due_jobs(
            REPO,
            store,
            batch={POLL_KEY: 1},
            table=table,
            data_dir=tmp_path,
            now=NOW,
            polls=cache,
        )

    events = [args[-1].split("?")[0] for args in github.calls if "issues/events" in args[-1]]
    assert len(events) == 1


@pytest.mark.usefixtures("roadmap_bot")
def test_a_second_poll_reads_the_issue_events_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache lives for one poll, so the next poll sends its own request (#3942)."""
    from devops_cli.roadmap.run import PollCache

    github, store = _github_round(tmp_path, monkeypatch, labeled_changes(3, "alice"))
    cache = PollCache()
    table = intake_table(IntakeModel([]), [])
    first = NOW
    second = NOW + timedelta(minutes=10)

    for now in (first, second):
        run_due_jobs(
            REPO,
            store,
            batch={POLL_KEY: 1},
            table=table,
            data_dir=tmp_path,
            now=now,
            polls=cache,
        )

    events = [args[-1].split("?")[0] for args in github.calls if "issues/events" in args[-1]]
    assert len(events) == 2


def test_the_cached_listing_covers_a_later_lane_cutoff() -> None:
    """A lane with a later cutoff filters the one cached listing, and the read happens once
    (#3942)."""
    from devops_cli.roadmap.run import PollCache

    cache = PollCache()
    changes = [
        Change(
            kind=ChangeKind.LABELED,
            number=1,
            actor="alice",
            at=NOW - timedelta(minutes=10),
            label="scope/cli",
        ),
        Change(
            kind=ChangeKind.LABELED,
            number=2,
            actor="alice",
            at=NOW - timedelta(minutes=1),
            label="scope/cli",
        ),
    ]
    reads: list[Any] = []

    def read(cutoff: Any) -> list[Change]:
        reads.append(cutoff)
        return changes

    early = cache.changes_since(REPO, NOW, NOW - timedelta(minutes=20), read)
    late = cache.changes_since(REPO, NOW, NOW - timedelta(minutes=5), read)

    assert (len(reads), len(early), [change.number for change in late]) == (1, 2, [2])


def test_the_cache_keeps_one_listing_for_each_repository() -> None:
    """One poll of two repositories reads the issue events of each repository once (#3942)."""
    from devops_cli.roadmap.run import PollCache

    cache = PollCache()
    reads: list[str] = []

    def read(repo: str) -> Any:
        def changes(cutoff: Any) -> list[Change]:
            reads.append(repo)
            return []

        return changes

    cache.changes_since(REPO, NOW, NOW, read(REPO))
    cache.changes_since("example/other", NOW, NOW, read("example/other"))

    assert reads == [REPO, "example/other"]

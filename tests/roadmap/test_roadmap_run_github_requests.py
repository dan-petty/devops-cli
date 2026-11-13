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
    service_job,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from tests.support.fakes.github import API, RunnerSession
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.process import ProcessFake
from tests.support.roadmap_run import (
    NOW,
    PLANNED,
    POLL,
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

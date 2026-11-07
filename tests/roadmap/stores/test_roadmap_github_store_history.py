"""The history of an issue that the GitHub roadmap store reads from its timeline: closures,
renames, authors and close times (#1335).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from devops_cli.exceptions.git import (
    GitHubOperationError,
)
from devops_cli.roadmap.stores.store import (
    ChangeKind,
)
from tests.support.roadmap_github_store import MILESTONES, issue_payload, recorded_store


def _timeline(nodes: list[dict[str, Any]], total: int | None = None) -> dict[str, Any]:
    connection = {"nodes": nodes, "totalCount": len(nodes) if total is None else total}
    return {"data": {"repository": {"issue": {"timelineItems": connection}}}}


def test_closures_read_the_timelines_closes_and_reopens_oldest_first() -> None:
    nodes: list[dict[str, Any]] = [
        {
            "__typename": "ClosedEvent",
            "createdAt": "2026-10-01T10:00:00Z",
            "stateReason": "DUPLICATE",
            "duplicateOf": {"number": 742},
        },
        {"__typename": "ReopenedEvent", "createdAt": "2026-10-01T11:00:00Z"},
    ]
    store, runner = recorded_store({"timelineItems": _timeline(nodes)})
    closures = store.closures(950)
    assert (
        [(c.kind, c.at.hour, c.reason, c.duplicate_of) for c in closures],
        runner.calls[0][0][-2:],
    ) == (
        [(ChangeKind.CLOSED, 10, "duplicate", 742), (ChangeKind.REOPENED, 11, None, None)],
        ["-F", "number=950"],
    )


def test_closures_past_the_connection_limit_raise() -> None:
    store, _ = recorded_store({"timelineItems": _timeline([], total=101)})
    with pytest.raises(GitHubOperationError, match="Read 0 of 101"):
        store.closures(950)


def test_last_renamed_at_reads_the_newest_title_change_of_the_timeline() -> None:
    nodes: list[dict[str, Any]] = [
        {"__typename": "RenamedTitleEvent", "createdAt": "2026-10-01T10:00:00Z"},
        {"__typename": "RenamedTitleEvent", "createdAt": "2026-10-02T09:00:00Z"},
    ]
    store, runner = recorded_store({"timelineItems": _timeline(nodes)})

    renamed = store.last_renamed_at(950)

    assert renamed == datetime(2026, 10, 2, 9, tzinfo=UTC)
    assert "RENAMED_TITLE_EVENT" in " ".join(runner.calls[0][0])


def test_last_renamed_at_is_none_for_a_title_that_never_changed() -> None:
    store, _ = recorded_store({"timelineItems": _timeline([])})
    assert store.last_renamed_at(950) is None


def test_pull_title_reads_a_pull_request_through_the_issues_endpoint() -> None:
    pull = issue_payload(951, title="docs(openspec): plan #950 Add it", pull_request={"url": "u"})
    store, _ = recorded_store({"issues/951": pull, "issues/952": issue_payload(952)})

    assert (store.pull_title(951), store.pull_title(952)) == (
        "docs(openspec): plan #950 Add it",
        None,
    )


def test_issue_records_and_milestones_carry_author_and_close_times() -> None:
    closed = {**MILESTONES[0], "state": "closed", "closed_at": "2026-10-03T20:37:25Z"}
    store, _ = recorded_store(
        {
            "milestones?state=all": [closed],
            "issues?state=all": [
                issue_payload(
                    950,
                    author_association="COLLABORATOR",
                    created_at="2026-10-04T01:00:00Z",
                    updated_at="2026-10-04T02:30:00Z",
                    closed_at=None,
                )
            ],
        }
    )
    (issue,) = store.issues()
    (milestone,) = store.milestones()
    assert (
        issue.author_association,
        issue.created_at,
        issue.updated_at,
        milestone.closed_at,
    ) == (
        "COLLABORATOR",
        datetime(2026, 10, 4, 1, tzinfo=UTC),
        datetime(2026, 10, 4, 2, 30, tzinfo=UTC),
        datetime(2026, 10, 3, 20, 37, 25, tzinfo=UTC),
    )

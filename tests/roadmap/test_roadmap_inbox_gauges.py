"""The inbox gauge (#2968): one series for each counted kind of each repository, sent by
`read_inbox`'s counts. A fake repository holds the lines; no request leaves the process."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.inbox import Inbox, emit_inbox_counts, read_inbox
from devops_cli.roadmap.inbox_kind import COUNTED_KINDS, InboxKind
from devops_cli.roadmap.stores.store import (
    ItemField,
    RefineRecordKey,
    StageRecordKey,
    encode_job_record,
    with_record,
)
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS
from devops_cli.telemetry.instruments import ROADMAP_INBOX_ITEMS
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/roadmap"
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
LABELS = "- name: scope/cli\n  color: DCDCD6\n  description: The CLI\n"
LABELS_BEHIND = f"{LABELS}- name: scope/extra\n  color: DCDCD6\n  description: Extra\n"


def _ago(**span: float) -> datetime:
    return NOW - timedelta(**span)


def _repository(repo: str = REPO, *, labels: str = LABELS) -> InMemoryRoadmapStore:
    """A repository whose labels file `labels` holds, with the labels that it declares."""
    made = InMemoryRoadmapStore(repo=repo, clock=lambda: NOW)
    made.seed_file(CONST_ROADMAP_LABELS_PATH, labels)
    made.seed_label("scope/cli", "DCDCD6", "The CLI")
    for spec in WORKFLOW_LABELS:
        made.seed_label(spec.name, spec.color, spec.description)
    return made


def _item(
    store: InMemoryRoadmapStore,
    title: str = "work",
    *,
    marks: Mapping[Any, str | None] | None = None,
    fields: Mapping[ItemField, str] | None = None,
    updated_at: datetime | None = None,
) -> int:
    """An item of the roadmap whose job record holds `marks`."""
    block = encode_job_record({}, marks or {}) if marks else None
    return store.seed_issue(
        title,
        body=with_record("", block),
        fields={ItemField.PRIORITY: "P2-Medium", **(fields or {})},
        updated_at=updated_at,
    )


def _read(store: InMemoryRoadmapStore, repo: str = REPO) -> Inbox:
    return read_inbox(store, repo=repo, now=NOW, planned_limit=20, draft_days=7, wait_days=7)


def _points(collector: FakeCollector) -> dict[str, tuple[str, float]]:
    return {
        attrs["kind"]: (attrs["repo"], value)
        for attrs, value in collector.points(ROADMAP_INBOX_ITEMS.name)
    }


def test_the_counted_kinds_are_the_eight_active_kinds() -> None:
    """The gauge counts the eight active kinds of the inbox, and `queue` stays out: seven
    repositories then add at most 56 series, below the cap (#2968)."""
    assert COUNTED_KINDS == (
        InboxKind.BLOCKED,
        InboxKind.REFINE,
        InboxKind.SPLIT,
        InboxKind.ALTERNATIVES,
        InboxKind.FAILED,
        InboxKind.STAGE_RETRY,
        InboxKind.CLAIM,
        InboxKind.LABELS,
    )
    assert InboxKind.QUEUE not in COUNTED_KINDS


def test_the_gauge_shows_the_count_of_each_counted_kind(otlp: FakeCollector) -> None:
    """Two blocked lines and one refine line give 2 for `blocked`, 1 for `refine` and 0 for each
    other counted kind, and each series carries the repository name (#2968)."""
    store = _repository()
    _item(store, "blocked one", fields={ItemField.STATUS: "Blocked"})
    _item(store, "blocked two", fields={ItemField.STATUS: "Blocked"})
    _item(
        store,
        "waiting",
        fields={ItemField.STATUS: "New"},
        marks={RefineRecordKey.NEXT_STEP: "person"},
    )

    emit_inbox_counts(_read(store), repo=REPO)

    assert _points(otlp) == {
        "blocked": (REPO, 2.0),
        "refine": (REPO, 1.0),
        "split": (REPO, 0.0),
        "alternatives": (REPO, 0.0),
        "failed": (REPO, 0.0),
        "stage_retry": (REPO, 0.0),
        "claim": (REPO, 0.0),
        "labels": (REPO, 0.0),
    }


def test_the_gauge_holds_at_most_56_series(otlp: FakeCollector) -> None:
    """Seven repositories that hold a line of each counted kind add 56 series, each with its
    `repo` label and a counted `kind` (#2968)."""
    repos = [f"example/repo{index}" for index in range(7)]
    for repo in repos:
        store = _repository(repo, labels=LABELS_BEHIND)
        _item(store, "blocked", fields={ItemField.STATUS: "Blocked"})
        _item(
            store,
            "waiting",
            fields={ItemField.STATUS: "New"},
            marks={RefineRecordKey.NEXT_STEP: "person"},
        )
        _item(
            store,
            "split",
            fields={ItemField.STATUS: "New"},
            marks={RefineRecordKey.NEXT_STEP: "split"},
        )
        _item(
            store,
            "covering tool",
            fields={ItemField.STATUS: "New"},
            marks={RefineRecordKey.ALTERNATIVES_ASKED: "grafanalib"},
        )
        _item(
            store,
            "failed",
            fields={ItemField.STATUS: "New"},
            marks={RefineRecordKey.NEXT_STEP: "failed"},
        )
        _item(
            store,
            "ready",
            fields={ItemField.STATUS: "Ready"},
            marks={StageRecordKey.FAILED_CLASS: FailureClass.LIMIT_REACHED.value},
        )
        _item(store, "claimed", fields={ItemField.OWNER: "Agent"}, updated_at=_ago(days=9))

        emit_inbox_counts(_read(store, repo), repo=repo)

    points = [
        (attrs["repo"], attrs["kind"], value)
        for attrs, value in otlp.points(ROADMAP_INBOX_ITEMS.name)
    ]
    assert (
        len(points),
        sorted({repo for repo, _, _ in points}),
        {kind for _, kind, _ in points},
        {value for _, _, value in points},
    ) == (56, sorted(repos), {kind.value for kind in COUNTED_KINDS}, {1.0})


@pytest.mark.parametrize("kind", list(COUNTED_KINDS))
def test_each_counted_kind_carries_its_repository(kind: InboxKind, otlp: FakeCollector) -> None:
    """A gauge series of each counted kind carries the key of the repository that it counts."""
    store = _repository()

    emit_inbox_counts(_read(store), repo="Example/Roadmap")

    assert _points(otlp)[kind.value] == ("example/roadmap", 0.0)


def test_trackers_do_not_increment_inbox_gauges(otlp: FakeCollector) -> None:
    """Tracker items with stale refine waits add nothing to inbox item gauges (#6446)."""
    from devops_cli.config.constants import (
        CONST_ROADMAP_EPIC_LABEL,
        CONST_ROADMAP_P3_PRIORITY,
        CONST_ROADMAP_STATUS_NEW,
    )
    from devops_cli.roadmap.stores.store import ItemField, RefineRecordKey, encode_job_record

    repo = "example/repo"
    store = _repository(repo)
    fields = {
        ItemField.STATUS: CONST_ROADMAP_STATUS_NEW,
        ItemField.PRIORITY: CONST_ROADMAP_P3_PRIORITY,
    }
    store.seed_issue(
        "Epic refine wait",
        body=encode_job_record({}, {RefineRecordKey.NEXT_STEP: "person"}),
        fields=fields,
        labels=(CONST_ROADMAP_EPIC_LABEL,),
        updated_at=_ago(hours=2),
    )
    store.seed_issue(
        "Parent split wait",
        body=encode_job_record({}, {RefineRecordKey.NEXT_STEP: "split"}),
        fields=fields,
        sub_issues=2,
        updated_at=_ago(hours=2),
    )
    store.seed_issue(
        "Real alternatives wait",
        body=encode_job_record({}, {RefineRecordKey.ALTERNATIVES_ASKED: "ruff"}),
        fields=fields,
        updated_at=_ago(hours=2),
    )

    emit_inbox_counts(_read(store, repo), repo=repo)
    counts = {attrs["kind"]: value for attrs, value in otlp.points(ROADMAP_INBOX_ITEMS.name)}
    assert counts["refine"] == 0.0
    assert counts["split"] == 0.0
    assert counts["alternatives"] == 1.0

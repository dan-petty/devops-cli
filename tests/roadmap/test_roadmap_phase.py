"""Tests for roadmap pipeline phases, phase age, and stall detection (#5495)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from devops_cli.config.constants import CONST_ROADMAP_EPIC_LABEL
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.stores.store import (
    AlternativesRecordKey,
    FixChecksRecordKey,
    GitHubState,
    ImplementRecordKey,
    Item,
    OwnerQuestionRecordKey,
    RefineRecordKey,
    StageRecordKey,
)


def _item(
    number: int = 1,
    *,
    title: str = "Test item",
    labels: tuple[str, ...] = (),
    status: str | None = None,
    owner: str | None = None,
    state: GitHubState = GitHubState.OPEN,
    sub_issues: int = 0,
    job_record: dict[str, str] | None = None,
    updated_at: datetime | None = None,
) -> Item:
    item_labels = list(labels)
    if status is not None and not any(lbl.startswith("status/") for lbl in item_labels):
        item_labels.append(f"status/{status.lower().replace(' ', '-')}")
    if owner is not None and not any(lbl.startswith("owner/") for lbl in item_labels):
        item_labels.append(f"owner/{owner.lower()}")
    return Item(
        number=number,
        title=title,
        url=f"https://github.com/example/repo/issues/{number}",
        state=state,
        labels=tuple(item_labels),
        status=status,
        owner=owner,
        sub_issues=sub_issues,
        job_record=job_record or {},
        updated_at=updated_at or datetime(2026, 11, 15, 0, 0, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("item", "pulls", "expected_phase"),
    [
        # New item with no labels or status
        (_item(1, title="New candidate"), None, "new"),
        # New item with explicit status/new
        (_item(2, status="New"), None, "new"),
        # Bot item judged/approved in refine
        (
            _item(3, job_record={RefineRecordKey.JUDGE: "approved"}),
            None,
            "judged",
        ),
        # Item with alternatives check verdict
        (
            _item(4, job_record={AlternativesRecordKey.VERDICT: "none"}),
            None,
            "judged",
        ),
        # Ready item with status label
        (_item(5, status="Ready"), None, "ready"),
        # Ready item via refine next_step
        (
            _item(6, job_record={RefineRecordKey.NEXT_STEP: "ready"}),
            None,
            "ready",
        ),
        # Staged item with draft stage PR
        (
            _item(7, job_record={StageRecordKey.PR: "101"}),
            {101: PullStatus(state="open", draft=True)},
            "staged",
        ),
        # Planned item with status label
        (_item(8, status="Planned"), None, "planned"),
        # Planned item via stage.ready mark
        (
            _item(9, job_record={StageRecordKey.PR: "101", StageRecordKey.READY: "101"}),
            None,
            "planned",
        ),
        # Planned item via ready (non-draft) PR
        (
            _item(10, job_record={StageRecordKey.PR: "101"}),
            {101: PullStatus(state="open", draft=False)},
            "planned",
        ),
        # In-review item with status In Progress
        (_item(11, status="In Progress"), None, "in-review"),
        # In-review item with draft delivery PR
        (
            _item(12, job_record={ImplementRecordKey.PR: "102"}),
            {102: PullStatus(state="open", draft=True)},
            "in-review",
        ),
        # Ready-for-review item with status In Review
        (_item(13, status="In Review"), None, "ready-for-review"),
        # An implement Job that ended at the draft writes In Review, and with no pull data the
        # draft is in review, not ready for review (#6559)
        (
            _item(17, status="In Review", job_record={ImplementRecordKey.RESULT: "drafted"}),
            None,
            "in-review",
        ),
        # With no pull data a drafted delivery is in review: a record mark of the ready path can
        # be stale after the review step makes the pull request a draft again (#6559)
        (
            _item(
                18,
                status="In Review",
                job_record={
                    ImplementRecordKey.RESULT: "drafted",
                    FixChecksRecordKey.RESULT: "ready",
                },
            ),
            None,
            "in-review",
        ),
        # The pull data says the drafted delivery is a draft again, whatever the record says
        (
            _item(
                19,
                status="In Review",
                job_record={
                    ImplementRecordKey.PR: "102",
                    ImplementRecordKey.RESULT: "drafted",
                    FixChecksRecordKey.RESULT: "ready",
                },
            ),
            {102: PullStatus(state="open", draft=True)},
            "in-review",
        ),
        # A Staged item delivers on its plan pull request, which the plan path marked ready
        (
            _item(
                20,
                status="In Review",
                job_record={
                    ImplementRecordKey.PR: "102",
                    StageRecordKey.PR: "102",
                    StageRecordKey.READY: "102",
                    ImplementRecordKey.RESULT: "drafted",
                },
            ),
            {102: PullStatus(state="open", draft=False)},
            "ready-for-review",
        ),
        # Ready-for-review item with ready delivery PR
        (
            _item(14, job_record={ImplementRecordKey.PR: "102"}),
            {102: PullStatus(state="open", draft=False)},
            "ready-for-review",
        ),
        # Closed item is merged
        (_item(15, state=GitHubState.CLOSED), None, "merged"),
        # Merged delivery PR
        (
            _item(16, job_record={ImplementRecordKey.PR: "102"}),
            {102: PullStatus(state="closed", merged=True)},
            "merged",
        ),
    ],
)
def test_phase_table_for_fixture_states(
    item: Item, pulls: dict[int, PullStatus] | None, expected_phase: str
) -> None:
    """A table test gives the phase of each fixture state (#5495)."""
    from devops_cli.roadmap.phase import phase

    assert phase(item, pulls=pulls) == expected_phase


def test_phase_age_measures_elapsed_time() -> None:
    """Phase age measures the seconds since the newest event that set the phase (#5495)."""
    from devops_cli.roadmap.phase import phase_age

    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    two_hours_ago = now - timedelta(hours=2)

    # Item with record timestamp
    item = _item(
        1,
        job_record={
            StageRecordKey.JOB_AT: two_hours_ago.isoformat(),
            StageRecordKey.PR: "101",
        },
    )
    assert phase_age(item, now=now) == pytest.approx(7200.0, rel=1e-3)

    # Item with label timestamp from times mapping
    ready_item = _item(2, status="Ready")
    times = {2: {"status/ready": two_hours_ago}}
    assert phase_age(ready_item, times=times, now=now) == pytest.approx(7200.0, rel=1e-3)


def test_an_item_with_a_running_unit_person_cause_or_claim_is_not_stalled() -> None:
    """An item with a running unit, a person cause or a claim is not stalled (#5495)."""
    from devops_cli.roadmap.phase import has_person_cause, is_stalled

    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    twenty_five_hours_ago = now - timedelta(hours=25)

    # Base item: over 24h in phase Ready, no unit, no cause, no claim -> STALLED
    stalled_item = _item(
        1,
        status="Ready",
        updated_at=twenty_five_hours_ago,
    )
    times = {1: {"status/ready": twenty_five_hours_ago}}
    assert (
        is_stalled(stalled_item, running_units=set(), stall_hours=24, times=times, now=now) is True
    )

    # Item under stall limit (e.g. 10 hours) -> NOT stalled
    ten_hours_ago = now - timedelta(hours=10)
    fresh_item = _item(2, status="Ready", updated_at=ten_hours_ago)
    fresh_times = {2: {"status/ready": ten_hours_ago}}
    assert (
        is_stalled(fresh_item, running_units=set(), stall_hours=24, times=fresh_times, now=now)
        is False
    )

    # Item with a running unit -> NOT stalled
    assert (
        is_stalled(stalled_item, running_units={1}, stall_hours=24, times=times, now=now) is False
    )

    # Item with an agent claim -> NOT stalled
    agent_claimed = _item(
        3,
        status="Ready",
        owner="Agent",
        updated_at=twenty_five_hours_ago,
    )
    assert (
        is_stalled(
            agent_claimed,
            running_units=set(),
            stall_hours=24,
            times={3: {"status/ready": twenty_five_hours_ago}},
            now=now,
        )
        is False
    )

    # Item with a human claim -> NOT stalled
    human_claimed = _item(
        4,
        status="Ready",
        owner="Human",
        updated_at=twenty_five_hours_ago,
    )
    assert (
        is_stalled(
            human_claimed,
            running_units=set(),
            stall_hours=24,
            times={4: {"status/ready": twenty_five_hours_ago}},
            now=now,
        )
        is False
    )

    # Person causes:
    # 1. refine waiting on person
    refine_person = _item(
        5,
        status="New",
        job_record={RefineRecordKey.NEXT_STEP: "person"},
        updated_at=twenty_five_hours_ago,
    )
    assert has_person_cause(refine_person) is True
    assert is_stalled(refine_person, running_units=set(), stall_hours=24, now=now) is False

    # 2. owner question open
    owner_q = _item(
        6,
        status="Ready",
        job_record={OwnerQuestionRecordKey.HASH: "abc123hash"},
        updated_at=twenty_five_hours_ago,
    )
    assert has_person_cause(owner_q) is True
    assert is_stalled(owner_q, running_units=set(), stall_hours=24, now=now) is False

    # 3. implement stopped
    stopped_item = _item(
        7,
        status="Blocked",
        job_record={ImplementRecordKey.STOPPED: "compile_error"},
        updated_at=twenty_five_hours_ago,
    )
    assert has_person_cause(stopped_item) is True
    assert is_stalled(stopped_item, running_units=set(), stall_hours=24, now=now) is False

    # 4. stage needs split
    split_item = _item(
        8,
        status="Ready",
        job_record={StageRecordKey.NEEDS_SPLIT: "budget exceeded"},
        updated_at=twenty_five_hours_ago,
    )
    assert has_person_cause(split_item) is True
    assert is_stalled(split_item, running_units=set(), stall_hours=24, now=now) is False

    # 5. refine blocked by other items
    blocked_by_item = _item(
        9,
        status="New",
        job_record={RefineRecordKey.BLOCKED_BY: "123,456"},
        updated_at=twenty_five_hours_ago,
    )
    assert has_person_cause(blocked_by_item) is True
    assert is_stalled(blocked_by_item, running_units=set(), stall_hours=24, now=now) is False


def test_has_person_cause_additional_branches() -> None:
    """Additional branches of has_person_cause: returned hash, alternatives asked, needs fix."""
    from devops_cli.roadmap.phase import has_person_cause

    # Returned body hash matches body hash
    returned = _item(
        10,
        job_record={
            RefineRecordKey.BODY_HASH: "hash123",
            RefineRecordKey.RETURNED_BODY_HASH: "hash123",
        },
    )
    assert has_person_cause(returned) is True

    # Alternatives asked
    alts = _item(11, job_record={RefineRecordKey.ALTERNATIVES_ASKED: "yes"})
    assert has_person_cause(alts) is True

    # Stage needs fix
    fix = _item(12, job_record={StageRecordKey.NEEDS_FIX: "lint error"})
    assert has_person_cause(fix) is True

    # Returned body hash does not match
    mismatch = _item(
        14,
        job_record={
            RefineRecordKey.BODY_HASH: "hash123",
            RefineRecordKey.RETURNED_BODY_HASH: "different_hash",
        },
    )
    assert has_person_cause(mismatch) is False

    # Answered owner question is not a person cause
    answered = _item(
        13,
        job_record={
            OwnerQuestionRecordKey.HASH: "q1",
            OwnerQuestionRecordKey.ANSWER: "a1",
        },
    )
    assert has_person_cause(answered) is False


def test_phase_age_and_parse_timestamp_branches() -> None:
    """phase_age records and PR closed_at handling."""
    from devops_cli.roadmap.phase import _parse_timestamp, is_stalled, phase_age

    assert _parse_timestamp(None) is None
    assert _parse_timestamp("invalid-date-format") is None

    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    one_hour_ago = now - timedelta(hours=1)

    # Staged phase with JOB_AT
    staged = _item(
        20,
        job_record={
            StageRecordKey.BRANCH: "feat/stage",
            StageRecordKey.JOB_AT: one_hour_ago.isoformat(),
        },
    )
    assert phase_age(staged, now=now) == pytest.approx(3600.0, rel=1e-3)

    # In review phase with ImplementRecordKey.SHA timestamp
    in_review = _item(
        21,
        status="In Progress",
        job_record={
            ImplementRecordKey.SHA: one_hour_ago.isoformat(),
        },
    )
    assert phase_age(in_review, now=now) == pytest.approx(3600.0, rel=1e-3)

    # In review phase with delivery PR closed_at
    pull = PullStatus(
        number=100,
        state="closed",
        draft=False,
        merged=False,
        closed_at=one_hour_ago,
    )
    pr_item = _item(
        22,
        status="In Progress",
        job_record={ImplementRecordKey.PR: "100"},
    )
    assert phase_age(pr_item, pulls={100: pull}, now=now) == pytest.approx(3600.0, rel=1e-3)

    # Planned phase with JOB_AT
    planned = _item(
        25,
        status="Planned",
        job_record={
            StageRecordKey.READY: "true",
            StageRecordKey.JOB_AT: one_hour_ago.isoformat(),
        },
    )
    assert phase_age(planned, now=now) == pytest.approx(3600.0, rel=1e-3)

    # Open PR without closed_at
    open_pull = PullStatus(
        number=300,
        state="open",
        draft=False,
        merged=False,
    )
    open_pr_item = _item(
        26,
        status="In Progress",
        job_record={ImplementRecordKey.PR: "300"},
    )
    assert phase_age(open_pr_item, pulls={300: open_pull}, now=now) >= 0.0

    # Non-digit PR number in record
    bad_pr_item = _item(
        27,
        status="In Progress",
        job_record={ImplementRecordKey.PR: "not-a-number"},
    )
    assert phase_age(bad_pr_item, pulls={300: open_pull}, now=now) >= 0.0

    # Closed item is not stalled
    closed = _item(24, state=GitHubState.CLOSED)
    assert is_stalled(closed, running_units=set(), stall_hours=24, now=now) is False


def test_find_running_units() -> None:
    """find_running_units extracts running unit numbers and handles API errors."""
    from unittest.mock import MagicMock

    from devops_cli.exceptions.k8s import ClusterJobError
    from devops_cli.k8s.cluster_job import ITEM_LABEL
    from devops_cli.k8s.cluster_job_api import JobState
    from devops_cli.roadmap.phase import find_running_units

    class MockJob:
        def __init__(self, state: JobState, item: str | None) -> None:
            self.state = state
            self.labels = {ITEM_LABEL: item} if item else {}

    mock_api = MagicMock()
    mock_api.list_jobs.return_value = [
        MockJob(JobState.RUNNING, "42"),
        MockJob(JobState.RUNNING, "invalid"),
        MockJob(JobState.SUCCEEDED, "99"),
        MockJob(JobState.RUNNING, None),
    ]

    running = find_running_units("owner/repo", jobs=mock_api)
    assert running == {42}

    # Error handling
    error_api = MagicMock()
    error_api.list_jobs.side_effect = ClusterJobError("cluster unreachable")
    assert find_running_units("owner/repo", jobs=error_api) == set()


@pytest.mark.parametrize(
    "record",
    [
        {RefineRecordKey.NEXT_STEP: "person"},
        {RefineRecordKey.NEXT_STEP: "split"},
        {RefineRecordKey.NEXT_STEP: "failed"},
        {RefineRecordKey.BODY_HASH: "abc", RefineRecordKey.RETURNED_BODY_HASH: "abc"},
        {RefineRecordKey.ALTERNATIVES_ASKED: "ruff"},
        {RefineRecordKey.BLOCKED_BY: "#42"},
        {OwnerQuestionRecordKey.HASH: "q1"},
    ],
)
def test_trackers_ignore_refine_and_owner_person_causes(record: dict[str, str]) -> None:
    """has_person_cause ignores refine and owner keys on tracker items (#6446)."""
    from devops_cli.roadmap.phase import has_person_cause

    epic = _item(1, labels=(CONST_ROADMAP_EPIC_LABEL,), job_record=record)
    parent = _item(2, sub_issues=2, job_record=record)
    regular = _item(3, job_record=record)

    assert has_person_cause(epic) is False
    assert has_person_cause(parent) is False
    assert has_person_cause(regular) is True


def test_trackers_keep_execution_stop_person_causes() -> None:
    """Execution stop keys remain person causes even if an item has tracker markers (#6446)."""
    from devops_cli.roadmap.phase import has_person_cause

    stopped = _item(
        1, labels=(CONST_ROADMAP_EPIC_LABEL,), job_record={ImplementRecordKey.STOPPED: "job"}
    )
    assert has_person_cause(stopped) is True

"""An intake decision that lacks a value its writes or its report line need stops intake with
`RoadmapIntakeError`, and before any write (#1538). These checks were asserts, which Python drops
under `-O`; no public path builds such a decision, so the tests call the writer and the report
directly."""

from __future__ import annotations

import pytest

from devops_cli.exceptions.roadmap import RoadmapIntakeError
from devops_cli.roadmap import intake
from devops_cli.roadmap.intake import IntakeDecision, Outcome, Placement, Subject
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import item_of

_BACKLOG = Placement(milestone=None, text="the backlog")


def _issue_subject(store: InMemoryRoadmapStore) -> Subject:
    number = store.seed_issue("feat(cli): one candidate")
    issue = next(issue for issue in store.issues() if issue.number == number)
    return Subject(title=issue.title, body=issue.body, number=number, item=item_of(issue))


def _labels(store: InMemoryRoadmapStore, number: int | None) -> tuple[str, ...]:
    return next(tuple(issue.labels) for issue in store.issues() if issue.number == number)


def test_a_placement_with_no_priority_writes_nothing(roadmap_store: InMemoryRoadmapStore) -> None:
    subject = _issue_subject(roadmap_store)
    decision = IntakeDecision(
        subject, Outcome.PLACE, labels=("type/feature",), placement=_BACKLOG, priority=None
    )

    with pytest.raises(RoadmapIntakeError, match="Priority") as raised:
        intake._apply_placement(roadmap_store, decision)

    assert (f"#{subject.number}" in str(raised.value), _labels(roadmap_store, subject.number)) == (
        True,
        (),
    )


def test_an_issue_placement_with_no_item_writes_nothing(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    subject = _issue_subject(roadmap_store)
    no_item = Subject(title=subject.title, body=subject.body, number=subject.number, item=None)
    decision = IntakeDecision(
        no_item, Outcome.PLACE, labels=("type/feature",), placement=_BACKLOG, priority="P2-Medium"
    )

    with pytest.raises(RoadmapIntakeError, match="item") as raised:
        intake._apply_placement(roadmap_store, decision)

    assert (f"#{subject.number}" in str(raised.value), _labels(roadmap_store, subject.number)) == (
        True,
        (),
    )


def test_a_placement_line_with_no_placement_stops_the_report() -> None:
    subject = Subject(title="feat(cli): one candidate", body="", number=7)
    decision = IntakeDecision(subject, Outcome.PLACE, priority="P2-Medium")

    with pytest.raises(RoadmapIntakeError, match="placement") as raised:
        intake._decision_lines(decision)

    assert "#7" in str(raised.value)

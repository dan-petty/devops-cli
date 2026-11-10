"""The report of the Jev shadow records (#4395): the records of the job record joined with the
final labels of the issues, with no model request."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.roadmap.intake.intake_jev_shadow import ShadowIntakeModel
from devops_cli.roadmap.jev_shadow_report import (
    BANDS,
    observed_issues,
    render_report,
    report_of,
)
from devops_cli.roadmap.stores.store import CloseReason, GitHubState, IntakeRecordKey, ItemField
from tests.support.roadmap_intake import FakeModel, Roadmap

if TYPE_CHECKING:
    from tests.support.fakes.jev import JevFake

HIGH, LOW = 2, 0


def _shadow(roadmap: Roadmap, jev: JevFake) -> None:
    roadmap.run(ShadowIntakeModel(FakeModel(topics=("embeddings",)), jev.model))


def _person_sets(roadmap: Roadmap, number: int, field: ItemField, value: str) -> None:
    roadmap.person.set_field(roadmap.item(number), field, value)


def test_the_report_counts_agreement_and_accuracy_against_the_final_labels(
    roadmap: Roadmap, jev: JevFake
) -> None:
    """The triage model says P2-Medium. Jev says P1-High for #a and P3-Low for #b. A person
    sets P1-High on #a and leaves #b: Jev is right on #a only, and triage on #b only."""
    jev.picks = {"priority": "P1-High"}
    first = roadmap.issue("Cache embeddings")
    _shadow(roadmap, jev)
    jev.picks = {"priority": "P3-Low"}
    second = roadmap.issue("Keep vectors")
    _shadow(roadmap, jev)
    _person_sets(roadmap, first, ItemField.PRIORITY, "P1-High")

    stats = report_of(roadmap.store.issues()).fields["priority"]

    assert (stats.records, stats.agree, stats.judged) == (2, 0, 2)
    assert (stats.jev_right, stats.triage_right) == (1, 1)
    assert (stats.only_jev, stats.only_triage) == (1, 1)
    assert second > first


def test_the_report_sorts_the_answers_of_jev_into_the_bands_of_its_probability(
    roadmap: Roadmap, jev: JevFake
) -> None:
    jev.confidence = 0.9
    jev.picks = {"priority": "P2-Medium"}
    roadmap.issue("Cache embeddings")
    _shadow(roadmap, jev)

    bands = report_of(roadmap.store.issues()).fields["priority"].bands

    assert bands[len(BANDS) - 1] == [1, 1]
    assert sum(total for total, _ in bands) == 1


def test_an_issue_with_no_final_label_for_a_field_is_not_judged_for_it(
    roadmap: Roadmap, jev: JevFake
) -> None:
    number = roadmap.issue("Cache embeddings")
    _shadow(roadmap, jev)
    roadmap.person.set_field(roadmap.item(number), ItemField.VALUE, None)

    stats = report_of(roadmap.store.issues()).fields["value"]

    assert (stats.records, stats.judged) == (1, 0)


def test_the_duplicate_flags_are_counted_against_the_issues_closed_as_a_duplicate(
    roadmap: Roadmap, jev: JevFake
) -> None:
    first = roadmap.issue("Cache embeddings")
    second = roadmap.issue("Keep embeddings cached")
    jev.picks = {f"duplicate_of_{first}": 0.95}
    triage = FakeModel(topics=("embeddings",))
    roadmap.run(ShadowIntakeModel(triage, jev.model))
    roadmap.store.close(second, CloseReason.DUPLICATE, comment=None)

    duplicate = report_of(roadmap.store.issues()).duplicate

    assert (duplicate.records, duplicate.jev_flags, duplicate.triage_flags) == (1, 1, 0)
    assert (duplicate.closed, duplicate.jev_flags_closed, duplicate.triage_flags_closed) == (
        1,
        1,
        0,
    )


def test_a_mark_that_cannot_be_read_is_counted_and_skipped(roadmap: Roadmap, jev: JevFake) -> None:
    number = roadmap.issue("Cache embeddings")
    _shadow(roadmap, jev)
    roadmap.store.set_marks(roadmap.item(number), {IntakeRecordKey.JEV_SHADOW: "not json"})

    observed, unreadable = observed_issues(roadmap.store.issues())

    assert (observed, unreadable) == ([], 1)


def test_an_open_issue_without_a_record_is_not_listed(roadmap: Roadmap) -> None:
    roadmap.issue("Cache embeddings", state=GitHubState.OPEN)

    assert report_of(roadmap.store.issues()).issues == 0


def test_the_text_names_each_field_and_the_caveat(roadmap: Roadmap, jev: JevFake) -> None:
    roadmap.issue("Cache embeddings")
    _shadow(roadmap, jev)

    text = render_report(report_of(roadmap.store.issues()))

    for name in ("type", "priority", "value", "effort"):
        assert f"- {name}: 1 record(s)" in text
    assert "only Jev" in text
    assert "Duplicate flags: 0 record(s)" in text


def test_the_text_with_no_record_says_how_a_record_starts(roadmap: Roadmap) -> None:
    text = render_report(report_of(roadmap.store.issues()))

    assert "roadmap.intake.jev to shadow" in text

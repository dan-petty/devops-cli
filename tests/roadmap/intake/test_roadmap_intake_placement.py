"""How intake places a candidate as a New item in the backlog: the fields it writes, their order,
and what a person already set (#1335).
"""

from __future__ import annotations

from devops_cli.roadmap.stores.store import (
    Evidence,
    EvidenceKind,
    ItemField,
)
from tests.support.roadmap_intake import LATER, PLANNED, FakeModel, Roadmap, labels_of

# ── Placing a candidate ───────────────────────────────────────────────────────


def test_an_open_issue_with_no_priority_becomes_a_new_backlog_item(roadmap: Roadmap) -> None:
    number = roadmap.issue("feat(cli): export the board as CSV")
    roadmap.run(FakeModel())
    assert (roadmap.fields(number), labels_of(roadmap, number)) == (
        ("New", "P2-Medium", "Medium", "Low", None),
        ("type/feature", "scope/cli"),
    )


def test_the_writes_follow_the_order_that_leaves_priority_last(roadmap: Roadmap) -> None:
    number = roadmap.issue("feat: one")
    writes = roadmap.run(FakeModel(proposals={"feat: one": {"priority": "P1-High"}}))
    assert [(w.operation, w.key) for w in writes] == [
        ("label_issue", None),
        ("set_field", "Status"),
        ("set_field", "Value"),
        ("set_field", "Effort"),
        ("comment", None),
        ("set_field", "Priority"),
    ]
    assert {w.number for w in writes} == {number}


# ── Placement ─────────────────────────────────────────────────────────────────


def test_a_milestone_a_person_set_stands_at_intake(roadmap: Roadmap) -> None:
    """Intake sets no milestone: an issue a person put in one keeps it, a P0 feature included,
    and no reason comment names the milestone again (#4836)."""
    roadmap.store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="4242"))
    later = roadmap.issue("feat: later", milestone=LATER)
    planned = roadmap.issue("feat: squeezed in", milestone=PLANNED)
    p0_feature = roadmap.issue("feat: retry", "Run 4242 failed.", milestone=PLANNED)
    proposal = {"evidence": {"kind": "failed_run", "value": "4242"}}
    writes = roadmap.run(FakeModel(proposals={"feat: retry": proposal}))
    (p0_comment,) = roadmap.comments(p0_feature)
    assert (
        roadmap.fields(later)[4],
        roadmap.fields(planned)[4],
        roadmap.comments(planned),
        PLANNED in p0_comment,
        roadmap.fields(p0_feature)[1::3],
        [w for w in writes if w.key == "Milestone"],
    ) == (LATER, PLANNED, [], False, ("P0-Critical", PLANNED), [])


def test_a_candidate_with_a_value_a_person_set_gets_only_its_empty_fields(
    roadmap: Roadmap,
) -> None:
    """A person put a candidate in a milestone and labeled it `value/high`: intake writes only
    Status, Effort and Priority, the person's Value and milestone stay, and the labels show
    each fact, so intake posts no reason comment. The job record claims no Value (ADR 0002)."""
    number = roadmap.issue(
        "feat: half done",
        labels=("type/docs",),
        milestone=LATER,
        fields={ItemField.VALUE: "High"},
    )
    writes = roadmap.run(FakeModel())
    assert (
        roadmap.fields(number),
        labels_of(roadmap, number),
        [(w.operation, w.key) for w in writes],
        roadmap.comments(number),
        ItemField.VALUE in roadmap.item(number).job_record,
    ) == (
        ("New", "P2-Medium", "High", "Low", LATER),
        ("type/docs",),
        [
            ("set_field", "Status"),
            ("set_field", "Effort"),
            ("set_field", "Priority"),
        ],
        [],
        False,
    )


def test_a_second_run_over_the_same_state_writes_nothing(roadmap: Roadmap) -> None:
    roadmap.issue("feat: one")
    roadmap.issue("feat: two")
    roadmap.run(FakeModel())
    assert roadmap.run(FakeModel()) == []

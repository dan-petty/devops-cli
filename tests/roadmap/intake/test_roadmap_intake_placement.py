"""How intake places a candidate as a New item in the backlog: the fields it writes, their order,
and what a person already set (#1335).
"""

from __future__ import annotations

from devops_cli.config.constants import CONST_ROADMAP_INTAKE_REASON_MARKER
from devops_cli.roadmap.stores.store import (
    Evidence,
    EvidenceKind,
    ItemField,
)
from tests.support.roadmap_intake import LATER, PLANNED, FakeModel, Roadmap, labels_of

# ── Placing a candidate ───────────────────────────────────────────────────────


def test_an_open_issue_with_no_priority_becomes_a_new_backlog_item_with_one_reason_comment(
    roadmap: Roadmap,
) -> None:
    number = roadmap.issue("feat(cli): export the board as CSV")
    roadmap.run(FakeModel())
    (comment,) = roadmap.comments(number)
    assert (
        roadmap.fields(number),
        labels_of(roadmap, number),
        comment.startswith(CONST_ROADMAP_INTAKE_REASON_MARKER),
        "P2-Medium" in comment and "useful, not urgent." in comment,
    ) == (
        ("New", "P2-Medium", "Medium", "Low", None),
        ("type/feature", "scope/cli"),
        True,
        True,
    )


def test_the_writes_follow_the_order_that_leaves_priority_last(roadmap: Roadmap) -> None:
    number = roadmap.issue("feat: one")
    writes = roadmap.run(FakeModel())
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
    and its comment says a person placed it there."""
    roadmap.store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="4242"))
    later = roadmap.issue("feat: later", milestone=LATER)
    planned = roadmap.issue("feat: squeezed in", milestone=PLANNED)
    p0_feature = roadmap.issue("feat: retry", "Run 4242 failed.", milestone=PLANNED)
    proposal = {"evidence": {"kind": "failed_run", "value": "4242"}}
    writes = roadmap.run(FakeModel(proposals={"feat: retry": proposal}))
    (comment,) = roadmap.comments(planned)
    assert (
        roadmap.fields(later)[4],
        roadmap.fields(planned)[4],
        f"kept in milestone {PLANNED}: a person placed it in {PLANNED}" in comment,
        roadmap.fields(p0_feature)[1::3],
        [w for w in writes if w.key == "Milestone"],
    ) == (LATER, PLANNED, True, ("P0-Critical", PLANNED), [])


def test_a_candidate_with_a_value_a_person_set_gets_only_its_empty_fields(
    roadmap: Roadmap,
) -> None:
    """A person put a candidate in a milestone and labeled it `value/high`: intake writes only
    Status, Effort and Priority, the person's Value and milestone stay, and the reason comment
    says where the issue stays and gives no Value. The job record claims no Value (ADR 0002)."""
    number = roadmap.issue(
        "feat: half done",
        labels=("type/docs",),
        milestone=LATER,
        fields={ItemField.VALUE: "High"},
    )
    writes = roadmap.run(FakeModel())
    (comment,) = roadmap.comments(number)
    assert (
        roadmap.fields(number),
        labels_of(roadmap, number),
        [(w.operation, w.key) for w in writes],
        f"Intake placed this item kept in milestone {LATER}" in comment,
        ("- Value:" in comment, "- Effort: Low." in comment),
        ItemField.VALUE in roadmap.item(number).job_record,
    ) == (
        ("New", "P2-Medium", "High", "Low", LATER),
        ("type/docs",),
        [
            ("set_field", "Status"),
            ("set_field", "Effort"),
            ("comment", None),
            ("set_field", "Priority"),
        ],
        True,
        (False, True),
        False,
    )


def test_a_second_run_over_the_same_state_writes_nothing(roadmap: Roadmap) -> None:
    roadmap.issue("feat: one")
    roadmap.issue("feat: two")
    roadmap.run(FakeModel())
    assert roadmap.run(FakeModel()) == []

"""What the reason comment of intake holds: only the facts that the labels of the item do not
show (#4836). The type, scope, Value, Effort and a P2-Medium Priority are on the labels, so the
comment does not state them again. When no other fact is there, intake posts no comment.
"""

from __future__ import annotations

from devops_cli.config.constants import CONST_ROADMAP_INTAKE_REASON_MARKER
from devops_cli.roadmap.stores.store import Evidence, EvidenceKind
from tests.support.roadmap_intake import REGRESSION, FakeModel, Roadmap, possible_duplicate_line

RELATED_TITLE = "perf(tests): the invariant tests share one parse"


def test_an_item_with_no_related_item_and_the_usual_fields_gets_no_reason_comment(
    roadmap: Roadmap,
) -> None:
    number = roadmap.issue("feat(cli): export the board as CSV")
    writes = roadmap.run(FakeModel())
    assert (roadmap.comments(number), [(w.operation, w.key) for w in writes]) == (
        [],
        [
            ("label_issue", None),
            ("label_issue", None),
            ("set_fields", "Status"),
            ("set_fields", "Value"),
            ("set_fields", "Effort"),
            ("set_field", "Priority"),
        ],
    )


def test_an_item_with_a_related_item_gets_a_reason_comment_of_one_line(roadmap: Roadmap) -> None:
    umbrella = roadmap.finished("perf(ci): the gate finishes in 2 minutes")
    number = roadmap.issue(RELATED_TITLE)
    answer = {"related_to": umbrella, "related_reason": "it is the umbrella item."}
    roadmap.run(FakeModel(proposals={RELATED_TITLE: answer}))
    assert roadmap.comments(number) == [
        f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\n"
        f"- Related: #{umbrella}, which asks for a different change. `it is the umbrella item.`"
    ]


def test_a_priority_other_than_p2_medium_gives_its_reason_and_no_label_again(
    roadmap: Roadmap,
) -> None:
    """The model picks the type, a P1-High Priority, Value and Effort: the comment gives the
    reason of the Priority only, as the labels show the type, the Value, the Effort and the
    Priority value (#6198)."""
    number = roadmap.issue("The board is slow")
    proposal = {"type": "type/bug", "priority": "P1-High", "priority_reason": "users wait."}
    roadmap.run(FakeModel(proposals={"The board is slow": proposal}))
    assert roadmap.comments(number) == [
        f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\n- Priority: `users wait.`"
    ]


def test_related_number_in_body_writes_no_related_line_and_posts_no_comment_when_empty(
    roadmap: Roadmap,
) -> None:
    """When the candidate body already cites the related issue number, no `Related:` line is
    written and no empty comment is posted (#6198)."""
    umbrella = roadmap.finished("perf(ci): the gate finishes in 2 minutes")
    number = roadmap.issue(RELATED_TITLE, body=f"Split from #{umbrella}.")
    answer = {"related_to": umbrella, "related_reason": "it is the umbrella item."}
    plan = roadmap.plan(FakeModel(proposals={RELATED_TITLE: answer}))
    roadmap.run(FakeModel(proposals={RELATED_TITLE: answer}))
    (decision,) = plan.decisions
    assert (decision.reasons, decision.comment, roadmap.comments(number)) == ((), None, [])


def test_possible_duplicate_stays_when_body_references_its_number(roadmap: Roadmap) -> None:
    """Flag, never drop: a `Possible duplicate:` line stays even when the body cites #N (#6198)."""
    original = roadmap.finished("fix(cli): keep duplicate warnings")
    title = "fix(cli): duplicate check stays visible"
    number = roadmap.issue(title, body=f"Context mentions #{original}.")
    model = FakeModel(duplicates={title: "fix(cli): keep duplicate warnings"})
    roadmap.run(model)
    expected = possible_duplicate_line(original, "fix(cli): keep duplicate warnings")
    assert roadmap.comments(number) == [f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\n{expected}"]


def test_p0_grant_and_refusal_drop_label_value_and_keep_reason(roadmap: Roadmap) -> None:
    """P0 grant and refusal comments keep the reason without copying the Priority label (#6198)."""
    roadmap.store.seed_evidence(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="abc1234"))
    granted_num = roadmap.issue("fix: crash on start", "Introduced by abc1234.")
    refused_num = roadmap.issue("fix: crash on stop", "Introduced by def5678.")
    granted_proposal = REGRESSION | {"priority_reason": "breaks startup."}
    refused_proposal = {
        "type": "type/bug",
        "priority": "P1-High",
        "priority_reason": "blocks shutdown.",
        "evidence": {"kind": "regression_commit", "value": "def5678"},
    }
    roadmap.run(
        FakeModel(
            proposals={
                "fix: crash on start": granted_proposal,
                "fix: crash on stop": refused_proposal,
            }
        )
    )
    (granted_comment,) = roadmap.comments(granted_num)
    (refused_comment,) = roadmap.comments(refused_num)
    assert (
        "P0-Critical" in granted_comment,
        "`breaks startup.`" in granted_comment,
        "is evidence GitHub confirms" in granted_comment,
        granted_comment.count("P0"),
        "P1-High" in refused_comment,
        "`blocks shutdown.`" in refused_comment,
        "does not set P0" in refused_comment,
    ) == (False, True, True, 1, False, True, True)


def test_intake_reason_comment_contract_repeats_no_body_issue_reference_outside_duplicate(
    roadmap: Roadmap,
) -> None:
    """Contract: non-duplicate lines in an intake reason comment repeat no #N cited in the body
    and no Priority line copies the priority label value (#6198)."""
    from devops_cli.roadmap.body_hash import issue_references

    parent = roadmap.finished("feat(roadmap): parent issue")
    duplicate = roadmap.finished("fix(roadmap): duplicate issue")
    title = "fix(roadmap): contract comment"
    body = f"Split from #{parent}. Also see #{duplicate}."
    number = roadmap.issue(title, body=body)
    proposal = {
        "priority": "P1-High",
        "priority_reason": "high failure rate.",
        "related_to": parent,
        "related_reason": "same area.",
    }
    roadmap.run(FakeModel(proposals={title: proposal}))
    (comment,) = roadmap.comments(number)
    body_refs = set(issue_references(body))
    non_dup_lines = [
        line
        for line in comment.splitlines()
        if line.startswith("- ") and not line.startswith("- Possible duplicate:")
    ]
    assert non_dup_lines
    assert all(not (set(issue_references(line)) & body_refs) for line in non_dup_lines)
    assert all(
        "P1-High" not in line and "P0-Critical" not in line
        for line in non_dup_lines
        if line.startswith("- Priority:")
    )

    dup_num = roadmap.issue("fix(roadmap): contract duplicate", body=body)
    dup_model = FakeModel(
        duplicates={"fix(roadmap): contract duplicate": "fix(roadmap): duplicate issue"},
        proposals={"fix(roadmap): contract duplicate": {"duplicate_reason": "same fix."}},
    )
    roadmap.run(dup_model)
    (dup_comment,) = roadmap.comments(dup_num)
    assert f"#{duplicate}" in dup_comment

"""What the reason comment of intake holds: only the facts that the labels of the item do not
show (#4836). The type, scope, Value, Effort and a P2-Medium Priority are on the labels, so the
comment does not state them again. When no other fact is there, intake posts no comment.
"""

from __future__ import annotations

from devops_cli.config.constants import CONST_ROADMAP_INTAKE_REASON_MARKER
from tests.support.roadmap_intake import FakeModel, Roadmap

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
            ("set_field", "Status"),
            ("set_field", "Value"),
            ("set_field", "Effort"),
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
    reason of the Priority only, as the labels show the type, the Value and the Effort."""
    number = roadmap.issue("The board is slow")
    proposal = {"type": "type/bug", "priority": "P1-High", "priority_reason": "users wait."}
    roadmap.run(FakeModel(proposals={"The board is slow": proposal}))
    assert roadmap.comments(number) == [
        f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\n- Priority: P1-High. `users wait.`"
    ]

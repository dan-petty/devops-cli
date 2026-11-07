"""The type and scope labels that intake takes from the title of a candidate (#1335)."""

from __future__ import annotations

import pytest

from tests.support.roadmap_intake import FakeModel, Roadmap, labels_of

# ── The type and scope labels come from the title (#2715) ───────────────────────


@pytest.mark.parametrize(
    ("title", "labels"),
    [
        ("fix(security): redact a URL user name", ("type/bug", "scope/security")),
        ("feat(ci): run the audit on a schedule", ("type/feature", "scope/ci")),
        ("perf(ci): shorten the Tests check", ("type/infra", "scope/ci")),
        ("chore: update a pin", ("type/chore",)),
        ("fix(zzz-unknown): a scope that has no label", ("type/bug",)),
    ],
)
def test_the_title_gives_the_type_and_the_scope_label_and_the_model_picks_neither(
    roadmap: Roadmap, title: str, labels: tuple[str, ...]
) -> None:
    number = roadmap.issue(title)
    model = FakeModel(proposals={title: {"type": "type/security"}})
    roadmap.run(model)
    assert labels_of(roadmap, number) == labels


def test_a_scope_with_no_label_is_named_in_the_reason_comment(roadmap: Roadmap) -> None:
    number = roadmap.issue("fix(zzz-unknown): a scope that has no label")
    roadmap.run(FakeModel())
    (comment,) = roadmap.comments(number)
    assert ("scope/zzz-unknown" in comment, ".github/labels.yml" in comment) == (True, True)


def test_a_title_with_no_type_takes_the_type_the_model_picks_and_gets_no_scope(
    roadmap: Roadmap,
) -> None:
    number = roadmap.issue("The board is slow")
    roadmap.run(FakeModel(proposals={"The board is slow": {"type": "type/bug"}}))
    assert labels_of(roadmap, number) == ("type/bug",)


def test_a_type_or_scope_label_a_person_set_stays(roadmap: Roadmap) -> None:
    number = roadmap.issue("fix(security): redact a URL", labels=("type/docs", "scope/ai"))
    roadmap.run(FakeModel())
    assert labels_of(roadmap, number) == ("type/docs", "scope/ai")

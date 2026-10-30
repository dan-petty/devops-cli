"""The labels that the Conventional Commit title of a pull request gives (#2748).

`devops pr create` adds them with the rule of intake (#2715). No case reaches GitHub or runs `gh`:
the labels file and the pull request are in the in-memory roadmap.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.title_labels import TitleLabels, declared_label_names, title_labels

DECLARED = ("type/bug", "type/docs", "type/feature", "scope/ai", "scope/security")


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("fix(ai): a title", TitleLabels("type/bug", "scope/ai")),
        ("feat(security)!: a title", TitleLabels("type/feature", "scope/security")),
        ("docs: a title", TitleLabels("type/docs", None)),
        ("A plain title", TitleLabels(None, None)),
        ("fix(zzz-unknown): a title", TitleLabels("type/bug", None, "scope/zzz-unknown")),
        ("chore(ai): a title", TitleLabels(None, "scope/ai")),
    ],
)
def test_the_title_gives_the_declared_labels(title: str, expected: TitleLabels) -> None:
    assert title_labels(title, DECLARED) == expected


def test_the_labels_of_a_title_are_its_type_then_its_scope() -> None:
    assert title_labels("fix(ai): a title", DECLARED).labels == ("type/bug", "scope/ai")


def test_the_declared_names_come_from_the_labels_file() -> None:
    text = '- name: "type/bug"\n  color: "d73a4a"\n- name: "scope/ai"\n  color: "0e8a16"\n'
    assert declared_label_names(text) == ("type/bug", "scope/ai")

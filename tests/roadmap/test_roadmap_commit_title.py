"""The type and the scope of a Conventional Commit title (#2715), and the type that
`CONST_BRANCH_TYPES` does not list, with its correction (#4508)."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.commit_title import (
    commit_scope,
    commit_type,
    corrected_title,
    unlisted_type,
)


@pytest.mark.parametrize(
    ("title", "kind", "scope"),
    [
        ("fix(security): redact a URL", "fix", "security"),
        ("feat(k8s)!: drop a flag", "feat", "k8s"),
        ("chore: update a pin", "chore", None),
        ("docs(): an empty scope", "docs", None),
        ("fix(ci-gate): a hyphenated scope", "fix", "ci-gate"),
        ("The board is slow", None, None),
        ("wip(cli): not a type", None, None),
        ("fix(cli) no colon", None, None),
    ],
)
def test_a_title_gives_its_type_and_its_scope(
    title: str, kind: str | None, scope: str | None
) -> None:
    assert (commit_type(title), commit_scope(title)) == (kind, scope)


@pytest.mark.parametrize(
    ("title", "unlisted"),
    [
        ("security(ssh): verify node host keys", "security"),
        ("security: verify node host keys", "security"),
        ("wip(cli)!: not a type", "wip"),
        ("fix(security): redact a URL", None),
        ("The board is slow", None),
        ("Security: a word with a capital", None),
        ("Fix a bug: the colon is in the text", None),
    ],
)
def test_a_title_names_the_type_that_the_branch_types_do_not_list(
    title: str, unlisted: str | None
) -> None:
    assert unlisted_type(title) == unlisted


@pytest.mark.parametrize(
    ("title", "corrected"),
    [
        ("security(ssh): verify node host keys", "fix(security): verify node host keys"),
        ("security: verify node host keys", "fix(security): verify node host keys"),
        ("wip(cli): a type with no correction", None),
        ("fix(roadmap): a listed type", None),
        ("The board is slow", None),
    ],
)
def test_a_security_type_becomes_a_fix_with_the_security_scope(
    title: str, corrected: str | None
) -> None:
    assert corrected_title(title) == corrected

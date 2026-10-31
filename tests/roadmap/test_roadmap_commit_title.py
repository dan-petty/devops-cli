"""The type and the scope of a Conventional Commit title (#2715)."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.commit_title import commit_scope, commit_type


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

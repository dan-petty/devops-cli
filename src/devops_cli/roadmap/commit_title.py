"""The Conventional Commit parts of an issue title: its type and its scope (#2715).

The title of an item is `<type>(<scope>): <summary>`. CONTRIBUTING.md names the types, and the
`Semantic PR title` check holds the form of a pull request title. No maintained Python package
parses the form, so this module reads the two parts that the roadmap jobs use.
"""

from __future__ import annotations

from devops_cli.config.constants import CONST_BRANCH_TYPES


def commit_type(title: str) -> str | None:
    """The Conventional Commit type of `title`, or None when it has none."""
    head, colon, _ = title.partition(":")
    kind = head.partition("(")[0].removesuffix("!")
    return kind if colon and kind in CONST_BRANCH_TYPES else None


def commit_scope(title: str) -> str | None:
    """The scope of `title`, such as `security` for `fix(security): ...`, or None when the
    title has no type or no scope."""
    if commit_type(title) is None:
        return None
    _, opened, rest = title.partition(":")[0].partition("(")
    scope = rest.removesuffix("!").removesuffix(")") if opened else ""
    return scope.strip() or None

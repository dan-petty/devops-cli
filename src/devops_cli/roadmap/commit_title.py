"""The Conventional Commit parts of an issue title: its type and its scope (#2715).

The title of an item is `<type>(<scope>): <summary>`. CONTRIBUTING.md names the types, and the
`Semantic PR title` check holds the form of a pull request title. No maintained Python package
parses the form, so this module reads the two parts that the roadmap jobs use. It also reads a
type that `CONST_BRANCH_TYPES` does not list, and gives its correction (#4508).
"""

from __future__ import annotations

import re
from typing import Final

from devops_cli.config.constants import CONST_BRANCH_TYPES
from devops_cli.lang import MESSAGES

# A title type that `CONST_BRANCH_TYPES` does not list, and the listed type and scope that
# `devops roadmap retitle` writes in its place (#4508). `release-please-config.json` has no
# `security` section, so a security change is a fix with the scope `security`, which gives the
# label `scope/security` (#2768). Another unlisted type gets one comment, and a person corrects it.
_TITLE_TYPE_CORRECTIONS: Final[dict[str, str]] = {"security": "fix(security)"}

# The head of a title in the form `<type>(<scope>)!:`, whatever the type: lower-case letters, an
# optional scope and an optional `!`, then the colon.
_HEAD: Final[re.Pattern[str]] = re.compile(r"(?P<type>[a-z]+)(?:\([^()]*\))?!?:")


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


def commit_summary(title: str) -> str:
    """The summary of `title`: the text after its first colon, with no space at its ends. A title
    with no colon has no summary, and the text is empty."""
    return title.partition(":")[2].strip()


def unlisted_type(title: str) -> str | None:
    """The type of `title` when `CONST_BRANCH_TYPES` does not list it, such as `security` for
    `security(ssh): ...`, or None for a title with a listed type or with no type. The stage job
    cannot take an item with such a type, because its branch has no type (#4508)."""
    found = _HEAD.match(title.strip())
    if found is None or found["type"] in CONST_BRANCH_TYPES:
        return None
    return found["type"]


def corrected_title(title: str) -> str | None:
    """`title` with the type and scope of `_TITLE_TYPE_CORRECTIONS` in place of its unlisted
    type, and the same summary: `security(ssh): x` gives `fix(security): x` (#4508). None for a
    title with a listed type, with no type, or with a type that has no correction."""
    kind = unlisted_type(title)
    head = _TITLE_TYPE_CORRECTIONS.get(kind) if kind else None
    return None if head is None else f"{head}: {commit_summary(title)}"


def unlisted_type_reason(title: str) -> str | None:
    """Why a job cannot take an item whose `title` has an unlisted type, and what makes the type
    right: the title that `devops roadmap retitle` writes, or its comment for a type with no
    correction. None for a title with a listed type or with no type (#4508)."""
    kind = unlisted_type(title)
    if kind is None:
        return None
    texts = MESSAGES.roadmap
    corrected = corrected_title(title)
    then = (
        texts.title_type_next_comment
        if corrected is None
        else texts.title_type_next_correction.format(title=corrected)
    )
    return texts.title_type_unlisted.format(type=kind, then=then)

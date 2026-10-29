"""The branch form `<type>/<issue>-<slug>` and the issue that a branch names (#2337).

CONTRIBUTING.md (Naming) gives the form, the `branch-name` pre-commit hook refuses a commit on a
branch that breaks it, and `tests/test_branch_form.py` fails when the types or the slug pattern of
`config/constants.py` disagree with the hook or with `release-please-config.json`.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from devops_cli.config.constants import CONST_BRANCH_SLUG_PATTERN, CONST_BRANCH_TYPES

_SLUG = re.compile(CONST_BRANCH_SLUG_PATTERN)
_BRANCH = re.compile(
    rf"(?P<type>{'|'.join(CONST_BRANCH_TYPES)})/(?P<issue>[0-9]+)-(?P<slug>"
    rf"{CONST_BRANCH_SLUG_PATTERN})"
)


class BranchParts(NamedTuple):
    """The three parts of a branch in the form `<type>/<issue>-<slug>`."""

    type: str
    issue: int
    slug: str


def is_valid_slug(slug: str) -> bool:
    """Whether `slug` is lowercase letters and digits joined by single hyphens."""
    return _SLUG.fullmatch(slug) is not None


def branch_name(issue: int, type_: str, slug: str) -> str:
    """The name of the branch for `issue`: `<type>/<issue>-<slug>`."""
    return f"{type_}/{issue}-{slug}"


def parse_branch(branch: str | None) -> BranchParts | None:
    """The type, issue and slug of `branch`, or None for a branch that breaks the form (`main`, a
    detached head, a bot's branch). The number is read whole: `feat/23370-x` is issue 23370."""
    if branch is None:
        return None
    match = _BRANCH.fullmatch(branch)
    return BranchParts(match["type"], int(match["issue"]), match["slug"]) if match else None


def issue_of_branch(branch: str | None) -> int | None:
    """The issue that `branch` names, or None for a branch that breaks the form."""
    parts = parse_branch(branch)
    return parts.issue if parts else None

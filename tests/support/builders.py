"""Builders of the objects tests make most often (#1312, #1307 Q20).

Each is a plain function whose keyword-only overrides replace its defaults, and whose defaults
make a valid object. Each builds through the type's own constructor or parser, so an override the
type refuses raises the type's own error: pydantic's `ValidationError` for a model, and for a
changelog fragment the error `changelog.d/` is read with, naming `changelog.d/<issue>.md`. A model
builder takes only the model's field names, so a typo or an alias such as `file=` raises
`TypeError` naming it. URLs are on `example.com`, and an Item's or a candidate's default URL
follows its number.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, overload

from pydantic import BaseModel

from devops_cli.ai.review.adjudication import Verdict
from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.config.constants import CONST_CHANGELOG_FRAGMENTS_DIR, CONST_STATUS_VERIFIED
from devops_cli.release.changelog_fragments import ChangelogFragment, parse_changelog_fragment
from devops_cli.roadmap.store import Candidate, Item, Release

_ISSUES_URL = "https://example.com/octo/repo/issues"

_FINDING: dict[str, Any] = {
    "severity": "HIGH",
    "location": "src/app.py:10",
    "title": "SQL injection in search",
    "description": "User input reaches the query unchecked.",
    "fix": "Bind the value as a query parameter.",
}


@overload
def make_finding(*, saved: Literal[False] = False, **overrides: Any) -> Finding: ...


@overload
def make_finding(*, saved: Literal[True], **overrides: Any) -> SavedFinding: ...


@overload
def make_finding(*, saved: bool, **overrides: Any) -> Finding: ...


def make_finding(*, saved: bool = False, **overrides: Any) -> Finding:
    """A review finding with a severity, a location, a title, a description and a fix; with
    `saved`, the `SavedFinding` a review session writes."""
    return _validated(SavedFinding if saved else Finding, _FINDING, overrides)


def make_verdict(**overrides: Any) -> Verdict:
    """A person's verdict on a finding: VERIFIED, with a reason."""
    return Verdict(**{"status": CONST_STATUS_VERIFIED, "reason": "Reproduced.", **overrides})


def make_item(**overrides: Any) -> Item:
    """An open issue on the board, #1, with no board fields set."""
    number = overrides.get("number", 1)
    defaults = {"number": number, "title": "An item", "url": f"{_ISSUES_URL}/{number}"}
    return _validated(Item, defaults, overrides)


def make_release(**overrides: Any) -> Release:
    """An open Release, milestone 1, titled `v0.1.0`."""
    return _validated(Release, {"number": 1, "title": "v0.1.0"}, overrides)


def make_candidate(**overrides: Any) -> Candidate:
    """An open issue off the board, #2, in no Release."""
    number = overrides.get("number", 2)
    defaults = {"number": number, "title": "A candidate", "url": f"{_ISSUES_URL}/{number}"}
    return _validated(Candidate, defaults, overrides)


def make_changelog_fragment(
    *, issue: int = 1, text: str = "### Added\n- An entry.\n"
) -> ChangelogFragment:
    """The fragment `changelog.d/<issue>.md` holding `text`, parsed as `changelog.d/` is read."""
    return parse_changelog_fragment(Path(CONST_CHANGELOG_FRAGMENTS_DIR) / f"{issue}.md", text)


def _validated[ModelT: BaseModel](
    model: type[ModelT], defaults: dict[str, Any], overrides: dict[str, Any]
) -> ModelT:
    """`model` validated from `defaults` with `overrides` over them, refusing a key that is no
    field of `model` rather than letting validation drop it or read it as an alias."""
    unknown = sorted(overrides.keys() - model.model_fields.keys())
    if unknown:
        raise TypeError(f"{model.__name__} has no field named {', '.join(unknown)}")
    return model.model_validate({**defaults, **overrides})

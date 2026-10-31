"""The shared builders in `tests/support/builders.py` (#1312): each builds a valid object from its
defaults, takes keyword overrides, and refuses what its type refuses, with the type's own error."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

import pydantic
import pytest

from devops_cli.ai.review.adjudication import Verdict
from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.config.constants import CONST_STATUS_VERIFIED
from devops_cli.roadmap.store import Candidate, Item, Milestone
from tests.support.builders import (
    make_candidate,
    make_finding,
    make_item,
    make_milestone,
    make_verdict,
)

_BUILDERS = [
    pytest.param(make_finding, Finding, lambda built: not built.is_empty, id="finding"),
    pytest.param(
        partial(make_finding, saved=True),
        SavedFinding,
        lambda built: not built.is_empty,
        id="saved-finding",
    ),
    pytest.param(
        make_verdict, Verdict, lambda built: built.status == CONST_STATUS_VERIFIED, id="verdict"
    ),
    pytest.param(
        make_item, Item, lambda built: built.url.startswith("https://example.com/"), id="item"
    ),
    pytest.param(
        make_milestone, Milestone, lambda built: built.title == "2026-11-05", id="milestone"
    ),
    pytest.param(
        make_candidate,
        Candidate,
        lambda built: built.url.startswith("https://example.com/"),
        id="candidate",
    ),
]


@pytest.mark.parametrize(("build", "built_type", "is_valid"), _BUILDERS)
def test_each_builder_builds_a_valid_object_from_its_defaults(
    build: Callable[[], Any], built_type: type, is_valid: Callable[[Any], bool]
) -> None:
    """Each builder's defaults make an object of exactly its type that holds what makes it
    valid: a finding its own `is_empty` keeps, a milestone with a title and a URL on
    `example.com`."""
    built = build()
    assert (type(built), is_valid(built)) == (built_type, True)


@pytest.mark.parametrize(
    ("build", "read", "expected"),
    [
        pytest.param(
            partial(make_finding, title="Unbounded page size"),
            lambda built: built.title,
            "Unbounded page size",
            id="finding",
        ),
        pytest.param(
            partial(make_finding, saved=True, producer="architect"),
            lambda built: built.producer,
            "architect",
            id="saved-finding",
        ),
        pytest.param(
            partial(make_verdict, reason="Reproduced on main."),
            lambda built: built.reason,
            "Reproduced on main.",
            id="verdict",
        ),
        pytest.param(
            partial(make_item, number=7, status="Ready"),
            lambda built: (built.number, built.status, built.url),
            (7, "Ready", "https://example.com/octo/repo/issues/7"),
            id="item",
        ),
        pytest.param(
            partial(make_item, number=7, url="https://example.com/octo/repo/pull/7"),
            lambda built: built.url,
            "https://example.com/octo/repo/pull/7",
            id="item-url",
        ),
        pytest.param(
            partial(make_milestone, title="Q4 hardening", number=3),
            lambda built: (built.number, built.title),
            (3, "Q4 hardening"),
            id="milestone",
        ),
        pytest.param(
            partial(make_candidate, number=9, labels=("type/bug",)),
            lambda built: (built.labels, built.url),
            (("type/bug",), "https://example.com/octo/repo/issues/9"),
            id="candidate",
        ),
    ],
)
def test_an_override_reaches_the_built_object(
    build: Callable[[], Any], read: Callable[[Any], Any], expected: Any
) -> None:
    """A keyword override replaces the default it names, and an Item's or a candidate's default
    URL follows the number it is given."""
    assert read(build()) == expected


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(partial(make_finding, reportable="maybe"), id="finding"),
        pytest.param(partial(make_finding, saved=True, introduced="maybe"), id="saved-finding"),
        pytest.param(partial(make_item, number="many"), id="item"),
        pytest.param(partial(make_milestone, number="many"), id="milestone"),
        pytest.param(partial(make_candidate, number="many"), id="candidate"),
    ],
)
def test_an_override_the_model_rejects_raises_its_validation_error(
    build: Callable[[], Any],
) -> None:
    """A builder validates through the model, so a value the model refuses raises pydantic's
    `ValidationError`, never an object holding it."""
    with pytest.raises(pydantic.ValidationError) as raised:
        build()
    assert len(raised.value.errors()) > 0


@pytest.mark.parametrize(
    ("build", "unknown"),
    [
        pytest.param(partial(make_finding, file="src/app.py:3"), "file", id="finding-alias"),
        pytest.param(
            partial(make_finding, saved=True, persona_name="qa"), "persona_name", id="saved-finding"
        ),
        pytest.param(partial(make_item, nmuber=3), "nmuber", id="item"),
        pytest.param(partial(make_milestone, titel="Q4"), "titel", id="milestone"),
        pytest.param(partial(make_candidate, label=("type/bug",)), "label", id="candidate"),
    ],
)
def test_an_override_the_model_has_no_field_for_raises_a_type_error_naming_it(
    build: Callable[[], Any], unknown: str
) -> None:
    """A key that is no field of the model, a typo or an alias such as `file=`, raises
    `TypeError` naming it, rather than being dropped or read through the alias."""
    with pytest.raises(TypeError, match=unknown):
        build()

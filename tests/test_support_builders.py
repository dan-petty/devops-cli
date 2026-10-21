"""The shared builders in `tests/support/builders.py` (#1312): each builds a valid object from its
defaults, takes keyword overrides, and refuses what its type refuses, with the type's own error."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pydantic
import pytest
from packaging.version import Version

from devops_cli.ai.review.adjudication import Verdict
from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.config.constants import CONST_STATUS_VERIFIED
from devops_cli.exceptions.validation import ValidationError
from devops_cli.release.changelog_fragments import ChangelogFragment
from devops_cli.roadmap.store import Candidate, Item, Release
from tests.support.builders import (
    make_candidate,
    make_changelog_fragment,
    make_finding,
    make_item,
    make_release,
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
        make_release, Release, lambda built: isinstance(built.version, Version), id="release"
    ),
    pytest.param(
        make_candidate,
        Candidate,
        lambda built: built.url.startswith("https://example.com/"),
        id="candidate",
    ),
    pytest.param(
        make_changelog_fragment,
        ChangelogFragment,
        lambda built: built.categories == {"Added": ["- An entry."]},
        id="changelog-fragment",
    ),
]


@pytest.mark.parametrize(("build", "built_type", "is_valid"), _BUILDERS)
def test_each_builder_builds_a_valid_object_from_its_defaults(
    build: Callable[[], Any], built_type: type, is_valid: Callable[[Any], bool]
) -> None:
    """Each builder's defaults make an object of exactly its type that holds what makes it
    valid: a finding its own `is_empty` keeps, a Release title that parses as a version, a URL
    on `example.com`, a fragment with one entry."""
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
            partial(make_release, title="v2.1.0"),
            lambda built: built.version,
            Version("2.1.0"),
            id="release",
        ),
        pytest.param(
            partial(make_candidate, number=9, labels=("type/bug",)),
            lambda built: (built.labels, built.url),
            (("type/bug",), "https://example.com/octo/repo/issues/9"),
            id="candidate",
        ),
        pytest.param(
            partial(make_changelog_fragment, issue=42, text="### Fixed\n- A fix.\n"),
            lambda built: (built.path, built.issue, built.categories),
            (Path("changelog.d/42.md"), 42, {"Fixed": ["- A fix."]}),
            id="changelog-fragment",
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
        pytest.param(partial(make_release, number="many"), id="release"),
        pytest.param(partial(make_candidate, number="many"), id="candidate"),
    ],
)
def test_an_override_the_model_rejects_raises_its_validation_error(
    build: Callable[[], Any],
) -> None:
    """A builder validates through the model, so a value the model refuses raises pydantic's
    `ValidationError`, never an object holding it."""
    with pytest.raises(pydantic.ValidationError):
        build()


@pytest.mark.parametrize(
    ("build", "unknown"),
    [
        pytest.param(partial(make_finding, file="src/app.py:3"), "file", id="finding-alias"),
        pytest.param(
            partial(make_finding, saved=True, persona_name="qa"), "persona_name", id="saved-finding"
        ),
        pytest.param(partial(make_item, nmuber=3), "nmuber", id="item"),
        pytest.param(partial(make_release, titel="v2.0.0"), "titel", id="release"),
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


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        pytest.param(
            "An entry with no category.\n",
            "changelog.d/7.md:1 is outside a category",
            id="text-outside-a-category",
        ),
        pytest.param(
            "### Added\n\n",
            "changelog.d/7.md holds no changelog entry",
            id="a-heading-with-no-entry",
        ),
    ],
)
def test_a_fragment_the_reader_refuses_is_refused_by_the_builder_naming_its_file(
    text: str, refusal: str
) -> None:
    """The builder parses a fragment as `changelog.d/` is read, so it raises the reader's own
    error for that text, naming `changelog.d/<issue>.md`."""
    with pytest.raises(ValidationError) as refused:
        make_changelog_fragment(issue=7, text=text)
    assert (refused.value.details["path"], str(refused.value).startswith(refusal)) == (
        "changelog.d/7.md",
        True,
    )

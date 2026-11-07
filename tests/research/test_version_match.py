"""Tests for the match of a pinned version to the range of a GitHub advisory (#3987)."""

from __future__ import annotations

import pytest
from packaging.version import Version

from devops_cli.research.version_match import in_range, pinned_version


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("v45.0.0", "45.0.0"),
        ("2026.10.4", "2026.10.4"),
        ("1.19.1", "1.19.1"),
        ("v7", None),
        ("3.14", None),
        ("latest", None),
        ("9.1.2-alpine", None),
        ("0123456789abcdef0123456789abcdef01234567", None),
        ("", None),
    ],
)
def test_a_pin_names_one_release_only_with_three_numbers(text: str, expected: str | None) -> None:
    found = pinned_version(text)

    assert (None if found is None else str(found)) == expected


@pytest.mark.parametrize(
    ("version", "range_text", "expected"),
    [
        ("45.0.0", "<= 45.0.7", True),
        ("45.0.7", "<= 45.0.7", True),
        ("46.0.1", "<= 45.0.7", False),
        ("41.0.0", "< 41", False),
        ("40.9.9", "< 41", True),
        ("1.19.1", ">= 1.18.0, < 1.19.2", True),
        ("1.19.2", ">= 1.18.0, < 1.19.2", False),
        ("1.17.9", ">= 1.18.0, < 1.19.2", False),
        ("1.2.3", "= 1.2.3", True),
        ("1.2.4", "= 1.2.3", False),
        ("1.2.4", "> 1.2.3", True),
        ("1.2.3", ">= 0", True),
        ("3.5.4", ">= 3.0.0, < 3.3.15 || >= 3.4.0, < 3.4.10 || >= 3.5.0, < 3.5.4", False),
        ("3.5.3", ">= 3.0.0, < 3.3.15 || >= 3.4.0, < 3.4.10 || >= 3.5.0, < 3.5.4", True),
        ("3.4.0", "< 3.3.15 || >= 3.4.0", True),
    ],
)
def test_a_version_is_in_the_range_of_an_advisory_when_every_comparator_holds(
    version: str, range_text: str, expected: bool
) -> None:
    assert in_range(Version(version), range_text) is expected


@pytest.mark.parametrize(
    "range_text", ["", "  , ", "since 1.2", "< one", "3.2.0 through 3.2.11", "< 1.0 || "]
)
def test_a_range_that_cannot_be_read_is_an_error_and_not_a_miss(range_text: str) -> None:
    with pytest.raises(ValueError, match=r"."):
        in_range(Version("1.2.3"), range_text)

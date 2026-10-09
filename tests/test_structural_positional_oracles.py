"""Unit and integration tests for semantic validator deprecation and structural positional oracles."""

from __future__ import annotations

from devops_cli.ai.review_schema import (
    Finding,
    _merge_two_findings,
    canonicalize_finding_location,
)
from devops_cli.config.constants import (
    CONST_REVIEW_PROMPT_PLACEHOLDER_BASENAMES,
    CONST_REVIEW_TITLE_FILLER_WORDS,
)


def test_finding_positional_identifier_fields_and_aliases() -> None:
    """Verify Finding correctly parses finding_id, id, and index aliases."""
    f1 = Finding(finding_id=1, title="F1", location="src/a.py:10")
    f2 = Finding(id=2, title="F2", location="src/b.py:20")
    f3 = Finding(index=3, title="F3", location="src/c.py:30")
    f4 = Finding(title="F4", location="src/d.py:40")

    assert (f1.finding_id, f2.finding_id, f3.finding_id, f4.finding_id) == (1, 2, 3, None)


def test_finding_merge_preserves_positional_identifier() -> None:
    """Verify duplicate finding consolidation preserves finding_id."""
    base = Finding(finding_id=42, title="Bug A", location="src/a.py:10")
    other = Finding(finding_id=99, title="Bug A", location="src/a.py:10")
    merged = _merge_two_findings(base, other)

    assert (merged.finding_id, merged.title, merged.location) == (42, "Bug A", "src/a.py:10")

    base_no_id = Finding(title="Bug B", location="src/b.py:20")
    merged_other_id = _merge_two_findings(base_no_id, other)
    assert (merged_other_id.finding_id, merged_other_id.title) == (99, "Bug B")


def test_canonicalize_location_strict_structural_boundary() -> None:
    """Verify canonicalize_finding_location accepts valid path structures and rejects non-paths."""
    valid_locations = [
        ("src/app.py:10", "src/app.py:10"),
        ("src/app.py:10-20", "src/app.py:10-20"),
        ("uv.lock:jinja2", "uv.lock:jinja2"),
        ("Dockerfile:cve-1", "Dockerfile:cve-1"),
        ("packages/@scope/web.json:pkg", "packages/@scope/web.json:pkg"),
        ("Embedded location: src/core/config.py:42 in text", "src/core/config.py:42"),
    ]

    normalized = [canonicalize_finding_location(raw) for raw, _ in valid_locations]
    expected = [exp for _, exp in valid_locations]
    assert normalized == expected

    invalid_locations = [
        "In this function we should check bounds",
        "file path and line numbers where vulnerability occurs",
        "Let's review the authentication handler implementation",
        "We need to examine the query parser closely",
        "***",
        "## Section Title",
        "---",
        "path/to/file.ext:1-10",
        "src/file.py:5-15",
    ]

    rejected = [canonicalize_finding_location(raw) for raw in invalid_locations]
    assert rejected == [""] * len(invalid_locations)


def test_review_constants_centralization_and_integrity() -> None:
    """Verify that centralized review constants exist in config.constants and adhere to standards."""
    assert (
        isinstance(CONST_REVIEW_PROMPT_PLACEHOLDER_BASENAMES, frozenset),
        isinstance(CONST_REVIEW_TITLE_FILLER_WORDS, frozenset),
        len(CONST_REVIEW_PROMPT_PLACEHOLDER_BASENAMES) > 0,
        len(CONST_REVIEW_TITLE_FILLER_WORDS) > 0,
    ) == (True, True, True, True)

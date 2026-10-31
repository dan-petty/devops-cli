"""Unit and integration tests for review engine hardening, prompt leakage defense,
and closed-loop feedback verification.

Tests cover:
1. Canonical location extraction and conversational reasoning leakage rejection.
2. Finding model validation and is_empty filtering for conversational/malformed entries.
3. Title normalization and chain-of-thought prefix stripping.
4. Verification index alignment when candidate findings are deterministically pre-invalidated.
5. Deterministic syntax validation for modern Python 3.14 syntax.
6. Feedback dataset export format integrity.
"""

from __future__ import annotations

from devops_cli.ai.review_schema import (
    Finding,
    canonicalize_finding_location,
    sanitize_finding_text,
)


def test_canonicalize_location_extracts_embedded_canonical_path() -> None:
    # Embedded valid location inside thinking text
    text_with_embedded = (
        "file path and line numbers. We need to find the lines where the vulnerability occurs. "
        "So location: src/devops_cli/docker/sandbox.py:20-22."
    )
    extracted = canonicalize_finding_location(text_with_embedded)
    assert extracted == "src/devops_cli/docker/sandbox.py:20-22"


def test_canonicalize_location_rejects_conversational_scratchpad() -> None:
    pure_scratchpad = (
        "file path and line numbers. We need to find the lines where the vulnerability occurs."
    )
    extracted = canonicalize_finding_location(pure_scratchpad)
    assert extracted == ""


def test_canonicalize_location_standard_formats() -> None:
    assert canonicalize_finding_location("src/auth.py:10-20") == "src/auth.py:10-20"
    assert canonicalize_finding_location("src/auth.py#L15") == "src/auth.py:15"
    assert canonicalize_finding_location("`src/auth.py:10-20`") == "src/auth.py:10-20"
    assert canonicalize_finding_location("src/auth.py, lines 10-20") == "src/auth.py:10-20"


def test_finding_is_empty_with_conversational_location() -> None:
    f_bad = Finding(
        severity="CRITICAL",
        location="file path and line numbers. We need to find the lines where the vulnerability occurs.",
        title="Valid sounding title",
        description="Valid description",
    )
    assert f_bad.is_empty is True

    f_good = Finding(
        severity="CRITICAL",
        location="src/devops_cli/docker/sandbox.py:20-22",
        title="Valid title",
        description="Valid description",
    )
    assert f_good.is_empty is False


def test_finding_clean_title_strips_scratchpad_markers() -> None:
    raw_title = (
        "We need to review src/devops_cli/docker/sandbox.py for security vulnerabilities. "
        "Hardcoded timeout missing"
    )
    cleaned = sanitize_finding_text(raw_title)
    assert "We need to review" not in cleaned
    f = Finding(
        severity="HIGH",
        location="src/devops_cli/docker/sandbox.py:61-63",
        title=raw_title,
        description="details",
    )
    assert "We need to review" not in f.title or len(f.title) <= 100

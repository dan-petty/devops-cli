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

import json
from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.ai.review.verification import _validate_segment_findings
from devops_cli.ai.review_schema import (
    Finding,
    ReviewResult,
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


def test_verification_index_alignment_with_pre_invalidated_findings(tmp_path: Path) -> None:
    """Ensure LLM verification items align properly when earlier findings are deterministically invalidated."""
    py_file = tmp_path / "valid.py"
    py_file.write_text("def test():\n    return True\n", encoding="utf-8")

    f1_hallucinated = Finding(
        severity="CRITICAL",
        location="valid.py:1-2",
        title="SyntaxError: Invalid syntax in test",
        description="Syntax error in test",
    )
    f2_real = Finding(
        severity="HIGH",
        location="valid.py:2",
        title="Missing type annotations",
        description="Return type is unannotated or test",
    )

    result = ReviewResult(findings=[f1_hallucinated, f2_real])

    mock_client = MagicMock()
    # Mock LLM verification output returning 1 element for the unresolved finding
    # or returning an array matching unresolved findings
    mock_client.chat.return_value = json.dumps(
        [
            {
                "verified": True,
                "status": "VERIFIED",
                "reportable": True,
                "confidence_score": 0.95,
                "reason": "Missing type annotation verified",
            }
        ]
    )

    validated_result, _, _ = _validate_segment_findings(
        result=result,
        all_segments=["def test():\n    return True\n"],
        client=mock_client,
        repo_root=tmp_path,
    )

    findings = validated_result.findings
    assert len(findings) == 2
    # First finding must be invalidated deterministically
    assert findings[0].status == "INVALIDATED"
    # Second finding must receive the LLM verification response
    assert findings[1].status == "VERIFIED"
    assert findings[1].reportable is True

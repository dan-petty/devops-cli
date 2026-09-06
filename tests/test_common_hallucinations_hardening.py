"""Test suite for common hallucination engine hardening and anti-false-positive safety guards."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from devops_cli.ai.review.common_hallucinations import (
    _FORBIDDEN_COMMON_WORDS,
    CommonHallucinationEntry,
    HallucinationCategory,
    auto_record_invalidated_finding,
    calculate_hallucination_similarity,
    find_similar_hallucinations,
)
from devops_cli.ai.review_schema import Finding


def test_forbidden_common_words_contains_comprehensive_stop_words() -> None:
    """Verify that _FORBIDDEN_COMMON_WORDS contains common English stop words and structural descriptors."""
    expected_stop_words = {
        "this",
        "that",
        "which",
        "will",
        "could",
        "would",
        "from",
        "with",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "time",
        "pipeline",
        "runtime",
        "leading",
        "crash",
        "blocks",
        "causing",
        "potential",
        "entire",
        "when",
        "where",
        "what",
        "there",
        "their",
        "some",
        "such",
        "other",
    }
    for word in expected_stop_words:
        assert word in _FORBIDDEN_COMMON_WORDS, (
            f"Expected stop word '{word}' missing from _FORBIDDEN_COMMON_WORDS"
        )


def test_calculate_similarity_rejects_unrelated_path_traversal_against_pep758() -> None:
    """Verify that an unrelated path traversal finding does NOT match the PEP 758 syntax hallucination."""
    pep758_entry = CommonHallucinationEntry(
        id="HALLUCINATION-PEP758-EXCEPT",
        name="Python 3.14 PEP 758 Bracketless Multi-Exception Clause",
        category=HallucinationCategory.SYNTAX_GRAMMAR,
        description="Claiming bracketless except clauses are invalid syntax or Python 2.",
        signature_patterns=[
            r"(?:bracketless|unparenthesized)\s+except",
            r"except\s+[a-zA-Z0-9_]+,\s*[a-zA-Z0-9_]+.*(?:syntaxerror|invalid\s*syntax|python\s*2)",
        ],
        pattern_keywords=["pep758", "bracketless_except", "unparenthesized_except"],
        file_patterns=["*.py"],
        resolution="Valid Python 3.14+ PEP 758 unparenthesized multi-exception clause",
    )

    path_traversal_finding = Finding(
        severity="HIGH",
        location="src/devops_cli/security/vault_broker.py:26-44",
        title="Path traversal via percent-encoded '..' in parse_vault_uri",
        description=(
            "The parse_vault_uri function decodes the URI string but does not percent-decode "
            "the path component before performing the check. An attacker could use percent-encoded "
            "dots which this check would fail to catch, leading to entire pipeline crash at runtime."
        ),
        fix="Use urllib.parse.unquote before checking path parts",
    )

    match = calculate_hallucination_similarity(path_traversal_finding, pep758_entry)
    assert match.similarity_score == 0.0, (
        f"Expected 0.0 score, got {match.similarity_score} ({match.reason})"
    )


def test_calculate_similarity_rejects_ssrf_against_pep758() -> None:
    """Verify that an SSRF finding does NOT match a syntax grammar hallucination."""
    pep758_entry = CommonHallucinationEntry(
        id="HALLUCINATION-PEP758-EXCEPT",
        name="Python 3.14 PEP 758 Bracketless Multi-Exception Clause",
        category=HallucinationCategory.SYNTAX_GRAMMAR,
        description="Claiming bracketless except clauses are invalid syntax.",
        signature_patterns=[r"(?:bracketless|unparenthesized)\s+except"],
        pattern_keywords=["pep758", "bracketless_except", "unparenthesized_except"],
        file_patterns=["*.py"],
        resolution="Valid Python 3.14+ PEP 758 unparenthesized multi-exception clause",
    )

    ssrf_finding = Finding(
        severity="CRITICAL",
        location="src/devops_cli/ai/common_tools.py:58-70",
        title="Potential SSRF bypass when final URL is None",
        description=(
            "The web_fetch_tool checks the final host after a redirect using resp.url. "
            "If resp.url is None, final_host remains empty and private IP checks are skipped, "
            "which causes an internal network compromise."
        ),
        fix="Validate that final_host is present before completing fetch",
    )

    match = calculate_hallucination_similarity(ssrf_finding, pep758_entry)
    assert match.similarity_score == 0.0, (
        f"Expected 0.0 score, got {match.similarity_score} ({match.reason})"
    )


def test_calculate_similarity_matches_genuine_pep758_hallucination() -> None:
    """Verify that a genuine PEP 758 false-positive finding matches with high confidence."""
    pep758_entry = CommonHallucinationEntry(
        id="HALLUCINATION-PEP758-EXCEPT",
        name="Python 3.14 PEP 758 Bracketless Multi-Exception Clause",
        category=HallucinationCategory.SYNTAX_GRAMMAR,
        description="Claiming bracketless except clauses are invalid syntax or Python 2.",
        signature_patterns=[
            r"(?:bracketless|unparenthesized)\s+except",
            r"except\s+[a-zA-Z0-9_]+,\s*[a-zA-Z0-9_]+.*(?:syntaxerror|invalid\s*syntax|python\s*2)",
        ],
        pattern_keywords=["pep758", "bracketless_except", "unparenthesized_except"],
        file_patterns=["*.py"],
        resolution="Valid Python 3.14+ PEP 758 unparenthesized multi-exception clause",
    )

    syntax_finding = Finding(
        severity="CRITICAL",
        location="src/devops_cli/security/aibom.py:60-62",
        title="Syntax error in exception handling",
        description="The file contains a malformed except clause: except ValueError, OSError: which causes a SyntaxError in Python 3.11+",
        fix="Replace with except (ValueError, OSError):",
    )

    with NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write("try:\n    x = 1\nexcept ValueError, OSError:\n    pass\n")
        tf_path = Path(tf.name)

    try:
        match = calculate_hallucination_similarity(syntax_finding, pep758_entry, file_path=tf_path)
        assert match.similarity_score >= 0.7, (
            f"Expected match score >= 0.7, got {match.similarity_score}"
        )
    finally:
        tf_path.unlink(missing_ok=True)


def test_auto_record_does_not_corrupt_existing_entry_resolution() -> None:
    """Verify that auto_record_invalidated_finding does NOT overwrite canonical resolution of established entry."""
    with NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        tf.write("[]")
        catalog_path = Path(tf.name)

    try:
        # Create an unrelated finding that has an invalidation reason
        finding = Finding(
            severity="MEDIUM",
            location="src/devops_cli/security/complexity.py:260-265",
            title="Potential absolute path disclosure in findings",
            description="The run_complexity_scan function constructs location using py_file",
            invalidation_reason="Line 260 exceeds total file lines (222)",
        )

        # Record finding into isolated catalog
        auto_record_invalidated_finding(
            finding, reason="Line 260 exceeds total file lines (222)", target_file=catalog_path
        )

        # Check that PEP 758 entry in catalog (if present) does NOT have the corrupted resolution
        matches = find_similar_hallucinations(finding, threshold=0.5, target_file=catalog_path)
        for m in matches:
            if m.hallucination.id == "HALLUCINATION-PEP758-EXCEPT":
                assert "Line 260 exceeds" not in m.hallucination.resolution
    finally:
        catalog_path.unlink(missing_ok=True)

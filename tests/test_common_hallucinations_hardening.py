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
    verify_ground_truth_hallucination,
)
from devops_cli.ai.review.verification import (
    _check_benign_compliment,
    _check_early_hallucinations,
    _check_localhost_default_url_hallucination,
    _check_posix_signal_zero_liveness_hallucination,
    _check_pre_1_0_breaking_change_hallucination,
    _check_structural_tuple_equality_hallucination,
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


def test_verify_ground_truth_dependency_ecosystem(tmp_path: Path) -> None:
    """Verify that verify_ground_truth_hallucination accepts approved dependencies in pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\ndependencies = ["httpx2>=0.1.0", "pydantic>=2.0"]\n', encoding="utf-8"
    )
    source_file = tmp_path / "client.py"
    source_file.write_text("import httpx2\n", encoding="utf-8")

    entry = CommonHallucinationEntry(
        id="HALLUCINATION-UNTRUSTED-HTTPX2",
        name="Untrusted Dependency Claim for httpx2",
        category=HallucinationCategory.DEPENDENCY_ECOSYSTEM,
        description="Falsely claiming httpx2 is untrusted",
        signature_patterns=[r"httpx2"],
        pattern_keywords=["httpx2"],
        file_patterns=["*.py"],
        resolution="Approved package",
    )
    finding = Finding(
        severity="HIGH",
        location=f"{source_file}:1",
        title="Use of untrusted dependency httpx2",
        description="httpx2 is not recognized or verified",
    )

    result = verify_ground_truth_hallucination(finding, entry, source_file)
    assert result is True


def test_verify_ground_truth_test_mocks(tmp_path: Path) -> None:
    """Verify that verify_ground_truth_hallucination recognizes test mock fixture keywords."""
    test_file = tmp_path / "tests" / "test_auth.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text('API_KEY = "sk-gateway-mock-1234"\n', encoding="utf-8")

    entry = CommonHallucinationEntry(
        id="HALLUCINATION-TEST-FIXTURE-CREDENTIAL",
        name="Hardcoded Secret in Test Fixture",
        category=HallucinationCategory.TEST_MOCKS,
        description="Flagging mock tokens in test files",
        signature_patterns=[r"sk-gateway"],
        pattern_keywords=["sk-gateway"],
        file_patterns=["tests/*"],
        resolution="Test mock",
    )
    finding = Finding(
        severity="HIGH",
        location=f"{test_file}:1",
        title="Hardcoded API key sk-gateway in test",
        description="Exposed sk-gateway mock credential",
    )

    result = verify_ground_truth_hallucination(finding, entry, test_file)
    assert result is True


def test_verify_ground_truth_secret_scanning_masked(tmp_path: Path) -> None:
    """Verify verify_ground_truth_hallucination detects prompt sanitizer redaction markers."""
    code_file = tmp_path / "run_store.py"
    code_file.write_text('def connect(password="<masked-password>"):\n    pass\n', encoding="utf-8")

    entry = CommonHallucinationEntry(
        id="HALLUCINATION-MASKED-SECRET",
        name="Sanitized Masked Token Flagged as Secret",
        category=HallucinationCategory.SECRET_SCANNING,
        description="Flagging <masked-*> as hardcoded credential",
        signature_patterns=[r"<masked-"],
        pattern_keywords=["masked"],
        file_patterns=["*.py"],
        resolution="Prompt sanitizer placeholder",
    )
    finding = Finding(
        severity="HIGH",
        location=f"{code_file}:1",
        title="Hardcoded credentials in connect",
        description="Insecure default password=<masked-password>",
    )

    result = verify_ground_truth_hallucination(finding, entry, code_file)
    assert result is True


def test_check_structural_tuple_equality_hallucination(tmp_path: Path) -> None:
    """Verify that deterministic checker invalidates findings against structural tuple equality assertions."""
    test_file = tmp_path / "tests" / "test_invariants.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("assert (actual_a, actual_b) == (exp_a, exp_b)\n", encoding="utf-8")

    finding = Finding(
        severity="MEDIUM",
        location=f"{test_file}:1",
        title="Brittle tuple assertion logic in test suite",
        description="Consolidating assertions into a single tuple comparison reduces readability",
    )
    verdict = _check_structural_tuple_equality_hallucination(finding, test_file)
    assert (
        verdict is not None,
        getattr(verdict, "status", ""),
        getattr(verdict, "verified_by", ""),
    ) == (True, "INVALIDATED", "deterministic:structural_tuple_equality")


def test_deterministic_url_signal_breaking_checkers() -> None:
    """Verify deterministic checkers for localhost defaults, POSIX signal 0, and pre-1.0 breaking changes."""
    localhost_finding = Finding(
        severity="MEDIUM",
        location="src/devops_cli/config/settings.py:10",
        title="Potential SSRF via default localhost config URL",
        description="Arbitrary internal access risk using default localhost endpoint",
    )
    posix_finding = Finding(
        severity="LOW",
        location="src/devops_cli/core/process.py:42",
        title="Race condition in PID liveness check with os.kill signal 0",
        description="Process signal 0 checking is vulnerable to PID reuse race condition",
    )
    pre10_finding = Finding(
        severity="MEDIUM",
        location="src/devops_cli/commands/review.py:120",
        title="Breaking change in CLI flag backwards compatibility",
        description="Backward compatibility broken by altering flag naming",
    )
    doc_finding = Finding(
        severity="LOW",
        location="docs/SELF_IMPROVEMENT.md:50",
        title="Documentation explains calibration loop",
        description="The documentation correctly explains calibration loop across releases",
    )

    lh_verdict = _check_localhost_default_url_hallucination(localhost_finding)
    px_verdict = _check_posix_signal_zero_liveness_hallucination(posix_finding)
    p1_verdict = _check_pre_1_0_breaking_change_hallucination(pre10_finding)
    dc_verdict = _check_benign_compliment(doc_finding.title.lower(), doc_finding)
    early_verdict = _check_early_hallucinations(localhost_finding, ())

    assert (
        getattr(lh_verdict, "verified_by", ""),
        getattr(px_verdict, "verified_by", ""),
        getattr(p1_verdict, "verified_by", ""),
        getattr(dc_verdict, "verified_by", ""),
        getattr(early_verdict, "verified_by", ""),
    ) == (
        "deterministic:localhost_default_config",
        "deterministic:posix_signal_zero_liveness",
        "deterministic:pre_1_0_breaking_change",
        "deterministic:benign_compliment",
        "deterministic:localhost_default_config",
    )

"""Unit and integration tests for semantic validator deprecation and structural positional oracles."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.review.verification import (
    _bind_verdicts_to_findings,
    _match_verdict_by_positional_oracle,
)
from devops_cli.ai.review_schema import (
    Finding,
    _merge_two_findings,
    canonicalize_finding_location,
)
from devops_cli.config.constants import (
    CONST_AUTH_DISPATCH_PATTERNS,
    CONST_AUTH_HEADER_CLAIM_KEYWORDS,
    CONST_AUTH_HEADER_CODE_PATTERNS,
    CONST_COMPLIMENT_NEGATIONS,
    CONST_COMPLIMENT_PHRASES,
    CONST_FIXTURE_CREDENTIAL_KEYWORDS,
    CONST_HALLUCINATION_FORBIDDEN_WORDS,
    CONST_MASKED_SYNTAX_ERROR_PHRASES,
    CONST_MONOLOGUE_PREFIXES,
    CONST_REVIEW_PROMPT_PLACEHOLDER_BASENAMES,
    CONST_REVIEW_TITLE_FILLER_WORDS,
    CONST_UNINITIALIZED_CLAIM_KEYWORDS,
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


def test_match_verdict_by_positional_oracle_explicit_id() -> None:
    """Verify positional oracle matches exact finding.finding_id."""
    findings = [
        Finding(finding_id=101, title="Alpha", location="src/a.py:1"),
        Finding(finding_id=202, title="Beta", location="src/b.py:2"),
    ]
    bound: dict[int, dict[str, Any]] = {}

    idx1 = _match_verdict_by_positional_oracle(findings, bound, {"finding_id": 202})
    idx2 = _match_verdict_by_positional_oracle(findings, bound, {"id": 101})
    idx_missing = _match_verdict_by_positional_oracle(findings, bound, {"finding_id": 999})

    assert (idx1, idx2, idx_missing) == (1, 0, None)


def test_match_verdict_by_positional_oracle_indexed_offsets() -> None:
    """Verify positional oracle matches 1-indexed and 0-indexed positions."""
    findings = [
        Finding(title="Alpha", location="src/a.py:1"),
        Finding(title="Beta", location="src/b.py:2"),
    ]
    bound: dict[int, dict[str, Any]] = {}

    idx_one_based = _match_verdict_by_positional_oracle(findings, bound, {"finding_id": 2})
    idx_zero_based = _match_verdict_by_positional_oracle(findings, bound, {"index": 0})
    idx_invalid = _match_verdict_by_positional_oracle(findings, bound, {"finding_id": "not_an_int"})

    assert (idx_one_based, idx_zero_based, idx_invalid) == (1, 0, None)


def test_match_verdict_by_positional_oracle_ignores_already_bound() -> None:
    """Verify positional oracle skips finding index if already claimed in bound."""
    findings = [
        Finding(finding_id=1, title="Alpha", location="src/a.py:1"),
        Finding(finding_id=2, title="Beta", location="src/b.py:2"),
    ]
    bound = {0: {"title": "Alpha", "verified": True}}

    idx_already_bound = _match_verdict_by_positional_oracle(findings, bound, {"finding_id": 1})
    idx_unclaimed = _match_verdict_by_positional_oracle(findings, bound, {"finding_id": 2})

    assert (idx_already_bound, idx_unclaimed) == (None, 1)


def test_bind_verdicts_to_findings_positional_oracle_overcomes_title_drift() -> None:
    """Verify structural positional oracle binds successfully despite significant title rephrasing."""
    findings = [
        Finding(
            finding_id=1,
            title="SQL injection in get_user via raw string interpolation",
            location="src/db.py:10",
        ),
        Finding(
            finding_id=2,
            title="Insecure cookie flag missing in auth response",
            location="src/auth.py:20",
        ),
    ]

    verdicts = [
        {
            "finding_id": 2,
            "title": "Auth session cookie lacks secure flag configuration",
            "location": "src/auth.py:20",
            "status": "VERIFIED",
            "verified": True,
        },
        {
            "finding_id": 1,
            "title": "User query constructed with unescaped SQL parameter",
            "location": "src/db.py:10",
            "status": "INVALIDATED",
            "verified": False,
        },
    ]

    bound = _bind_verdicts_to_findings(findings, verdicts)

    assert (
        bound[0]["status"],
        bound[0]["title"],
        bound[1]["status"],
        bound[1]["title"],
    ) == (
        "INVALIDATED",
        "User query constructed with unescaped SQL parameter",
        "VERIFIED",
        "Auth session cookie lacks secure flag configuration",
    )


def test_bind_verdicts_to_findings_disordered_positional_binding() -> None:
    """Verify disordered verdicts bind cleanly to corresponding unresolved finding indices."""
    findings = [
        Finding(finding_id=1, title="Finding 1", location="a.py:1"),
        Finding(finding_id=2, title="Finding 2", location="b.py:2"),
        Finding(finding_id=3, title="Finding 3", location="c.py:3"),
    ]
    verdicts = [
        {"finding_id": 3, "status": "VERIFIED"},
        {"finding_id": 1, "status": "INVALIDATED"},
    ]

    bound = _bind_verdicts_to_findings(findings, verdicts)

    assert (sorted(bound.keys()), bound[0]["status"], bound[2]["status"]) == (
        [0, 2],
        "INVALIDATED",
        "VERIFIED",
    )


def test_bind_verdicts_to_findings_fallback_when_finding_id_omitted() -> None:
    """Verify fallback to title/location identity matching when finding_id is not provided."""
    findings = [
        Finding(title="Hardcoded token in client.py", location="src/client.py:15"),
        Finding(title="Missing timeout in request call", location="src/net.py:30"),
    ]
    verdicts = [
        {
            "title": "Missing timeout in request call",
            "location": "src/net.py:30",
            "status": "VERIFIED",
        },
        {
            "title": "Hardcoded token in client.py",
            "location": "src/client.py:15",
            "status": "INVALIDATED",
        },
    ]

    bound = _bind_verdicts_to_findings(findings, verdicts)

    assert (bound[0]["status"], bound[1]["status"]) == ("INVALIDATED", "VERIFIED")


def test_bind_verdicts_to_findings_duplicate_id_preserves_first_binding() -> None:
    """Verify duplicate finding_id does not overwrite already bound verdict."""
    findings = [Finding(finding_id=1, title="Issue A", location="a.py:1")]
    verdicts = [
        {"finding_id": 1, "status": "VERIFIED", "reason": "First verdict"},
        {"finding_id": 1, "status": "INVALIDATED", "reason": "Second duplicate verdict"},
    ]

    bound = _bind_verdicts_to_findings(findings, verdicts)

    assert (len(bound), bound[0]["status"], bound[0]["reason"]) == (1, "VERIFIED", "First verdict")


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
        isinstance(CONST_AUTH_HEADER_CLAIM_KEYWORDS, tuple),
        isinstance(CONST_AUTH_HEADER_CODE_PATTERNS, tuple),
        isinstance(CONST_AUTH_DISPATCH_PATTERNS, tuple),
        isinstance(CONST_FIXTURE_CREDENTIAL_KEYWORDS, tuple),
        isinstance(CONST_MASKED_SYNTAX_ERROR_PHRASES, tuple),
        isinstance(CONST_UNINITIALIZED_CLAIM_KEYWORDS, tuple),
        isinstance(CONST_MONOLOGUE_PREFIXES, str),
        isinstance(CONST_COMPLIMENT_PHRASES, str),
        isinstance(CONST_COMPLIMENT_NEGATIONS, str),
        isinstance(CONST_HALLUCINATION_FORBIDDEN_WORDS, frozenset),
    ) == (True, True, True, True, True, True, True, True, True, True, True, True)

    assert (
        len(CONST_REVIEW_PROMPT_PLACEHOLDER_BASENAMES) > 0,
        len(CONST_REVIEW_TITLE_FILLER_WORDS) > 0,
        len(CONST_AUTH_HEADER_CLAIM_KEYWORDS) > 0,
        len(CONST_FIXTURE_CREDENTIAL_KEYWORDS) > 0,
        len(CONST_HALLUCINATION_FORBIDDEN_WORDS) > 50,
    ) == (True, True, True, True, True)

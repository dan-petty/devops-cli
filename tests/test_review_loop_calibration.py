"""Regression tests for review feedback-loop calibration.

Each test here pins a defect observed in a real review session (`.data/reviews/`) where
the loop itself misbehaved: duplicate findings that were never consolidated, suppression
signatures broad enough to bury genuine defects, and a builtin catalog that silently
vanished because one record was malformed.
"""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    _build_builtin_hallucinations,
    _check_signature_match,
    _is_degenerate_signature,
    _synthesize_compound_signature,
    load_common_hallucinations,
)
from devops_cli.ai.review_schema import (
    SavedFinding,
    _extract_code_symbols,
    _share_distinctive_symbol,
    consolidate_duplicate_findings,
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Duplicate finding consolidation
# ─────────────────────────────────────────────────────────────────────────────


def _finding(
    title: str, location: str, description: str = "", severity: str = "MEDIUM"
) -> SavedFinding:
    """Build a minimal saved finding for consolidation tests."""
    return SavedFinding(
        severity=severity,
        location=location,
        title=title,
        description=description or title,
        fix="Apply the corrected implementation.",
    )


def test_same_defect_at_different_line_ranges_is_consolidated() -> None:
    """Near-identical titles in one file merge even when the cited line ranges differ.

    Personas routinely cite different (and often both wrong) line ranges for one defect.
    """
    findings = [
        _finding("TTL parameter ignored in cache set operation", "src/k8s/service.py:115-122"),
        _finding("TTL parameter ignored in cache setter", "src/k8s/service.py:162-170"),
    ]
    assert len(consolidate_duplicate_findings(findings)) == 1


def test_shared_title_symbol_with_overlapping_lines_is_consolidated() -> None:
    """Findings naming the same symbol over overlapping lines describe one defect."""
    findings = [
        _finding(
            "Uninitialized _watcher leads to ineffective stop()", "src/k8s/informer.py:44-112"
        ),
        _finding("Unused _watcher variable and incomplete stop logic", "src/k8s/informer.py:78-86"),
    ]
    assert len(consolidate_duplicate_findings(findings)) == 1


def test_distinct_defects_sharing_one_function_stay_separate() -> None:
    """Different defects that merely share an enclosing function are never merged.

    Dropping a real finding is costlier than leaving a duplicate, so consolidation must
    stay conservative when only the enclosing symbol is common.
    """
    findings = [
        _finding(
            "Secret leakage when executing via subprocess",
            "src/ai/mcp/server.py:45-66",
            "Output of `_run_mcp_cmd` may include credentials that are not masked.",
        ),
        _finding(
            "Potential memory exhaustion due to unbounded output capture",
            "src/ai/mcp/server.py:45-70",
            "`_run_mcp_cmd` captures unbounded stdout into memory.",
        ),
    ]
    assert len(consolidate_duplicate_findings(findings)) == 2


def test_findings_in_different_files_are_never_merged() -> None:
    """Identical titles in different files remain independent findings."""
    findings = [
        _finding("Cache read without lock", "src/k8s/service.py:152-160"),
        _finding("Cache read without lock", "src/ai/governance.py:152-160"),
    ]
    assert len(consolidate_duplicate_findings(findings)) == 2


def test_extract_code_symbols_keeps_identifiers_and_drops_prose() -> None:
    """Symbol extraction keeps distinctive identifiers and discards generic words."""
    symbols = _extract_code_symbols(
        "Uninitialized `_watcher` leads to ineffective stop() in the handler class"
    )
    assert "_watcher" in symbols
    assert "stop" in symbols
    assert not {"the", "class", "value"} & symbols


def test_share_distinctive_symbol_requires_specificity() -> None:
    """A shared generic token alone never establishes that two findings are duplicates."""
    generic_a = _finding("Missing value in result", "a.py:1-5")
    generic_b = _finding("Unexpected value in result", "a.py:1-5")
    assert _share_distinctive_symbol(generic_a, generic_b) is False

    specific_a = _finding("`_set_cached` ignores ttl", "a.py:1-5")
    specific_b = _finding("ttl argument unused by `_set_cached`", "a.py:1-5")
    assert _share_distinctive_symbol(specific_a, specific_b) is True


def test_real_review_session_duplicates_are_reduced(tmp_path: Path) -> None:
    """A recorded multi-persona session consolidates without losing distinct defects."""
    session = [
        _finding("Uninitialized _watcher leads to ineffective stop()", "k8s/informer.py:44-112"),
        _finding(
            "`_watcher` attribute never set, `stop()` may not terminate", "k8s/informer.py:1-161"
        ),
        _finding(
            "Unbounded in-memory cache may lead to memory exhaustion", "k8s/informer.py:1-161"
        ),
        _finding("ResourceInformer only supports Pod resources", "k8s/informer.py:1-161"),
    ]
    consolidated = consolidate_duplicate_findings(session)
    titles = " ".join(f.title for f in consolidated)

    # The two watcher/stop reports merge; the cache and Pod-only concerns survive.
    assert len(consolidated) == 3
    assert "Unbounded in-memory cache" in titles
    assert "only supports Pod resources" in titles


# ─────────────────────────────────────────────────────────────────────────────
# 2. Hallucination catalog safety
# ─────────────────────────────────────────────────────────────────────────────


def test_builtin_catalog_loads_completely() -> None:
    """Every builtin catalog record validates, so the baseline is actually in effect."""
    builtin = _build_builtin_hallucinations()
    raw = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "src/devops_cli/ai/review/common_hallucinations.json"
        ).read_text(encoding="utf-8")
    )
    assert len(builtin) == len(raw)
    assert builtin


def test_one_malformed_record_does_not_discard_the_baseline(tmp_path: Path) -> None:
    """A single invalid entry is skipped rather than silently emptying the catalog."""
    catalog = tmp_path / "common_hallucinations.json"
    catalog.write_text(
        json.dumps(
            [
                {
                    "id": "VALID-ENTRY",
                    "name": "Valid",
                    "category": "general",
                    "description": "d",
                    "resolution": "r",
                },
                {"id": "BROKEN-ENTRY", "name": "Broken", "category": "not_a_real_category"},
            ]
        ),
        encoding="utf-8",
    )
    entries = load_common_hallucinations(target_file=catalog, include_builtin=False)
    assert [e.id for e in entries] == ["VALID-ENTRY"]


def test_bare_word_signatures_are_rejected_at_match_time() -> None:
    """A single-word suppression signature never matches, so real findings survive.

    Auto-learning previously persisted words like 'unvalidated' as whole signatures,
    which matched nearly every genuine security finding.
    """
    assert _is_degenerate_signature("unvalidated") is True
    assert _is_degenerate_signature("traversal") is True
    assert _is_degenerate_signature(r"(?=.*\bfoo\b)(?=.*\bbar\b)") is False

    # A bare *code identifier* still names one specific symbol and remains valid.
    assert _is_degenerate_signature("DEFAULT_HTTP_BROKER") is False
    assert _is_degenerate_signature("FastMCP") is False

    text = "Unvalidated path traversal in the archive extraction routine"
    assert _check_signature_match(text, ["unvalidated"]) == []
    assert _check_signature_match(text, ["traversal"]) == []


def test_structured_signatures_still_match() -> None:
    """Legitimate multi-token signatures continue to match as before."""
    text = "Claiming the bracketless except clause is invalid syntax"
    assert _check_signature_match(text, [r"(?:bracketless|unparenthesized)\s+except"])


def test_invalid_signature_regex_does_not_fall_back_to_substring() -> None:
    """A malformed regex is skipped, never degraded into a broad substring match."""
    assert _check_signature_match("some server text", ["server("]) == []


def test_synthesized_signature_requires_two_distinctive_keywords() -> None:
    """Auto-learning emits a co-occurrence signature, or no signature at all."""
    assert _synthesize_compound_signature(["unvalidated"]) == []
    assert _synthesize_compound_signature(["error", "test"]) == []

    compound = _synthesize_compound_signature(["informer", "watcher"])
    assert len(compound) == 1
    assert _check_signature_match("the informer never assigns its watcher", compound)
    # Requires both tokens; one alone must not match.
    assert _check_signature_match("the informer runs fine", compound) == []


def test_confirmed_false_positives_are_catalogued() -> None:
    """The two false positives confirmed by hand are now recognised patterns."""
    catalog = {e.id: e for e in _build_builtin_hallucinations()}
    server_entry = catalog["HALLUCINATION-SERVER-CONSTRUCTOR-NO-AUTH"]
    consumer_entry = catalog["HALLUCINATION-DECLARATION-WITHOUT-CONSUMER"]

    server_claim = (
        "FastMCP server lacks authentication, exposing internal commands to external "
        "clients. The FastMCP server is instantiated without any authentication."
    )
    consumer_claim = (
        "Help strings reference nonexistent commands. The new fields describe commands "
        "that are not implemented in the CLI."
    )
    assert _check_signature_match(server_claim, server_entry.signature_patterns)
    assert _check_signature_match(consumer_claim, consumer_entry.signature_patterns)


def test_catalog_entries_carry_actionable_resolutions() -> None:
    """Every builtin entry explains why the pattern is a false positive."""
    assert all(
        isinstance(e, CommonHallucinationEntry) and e.resolution.strip()
        for e in _build_builtin_hallucinations()
    )

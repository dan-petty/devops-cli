"""Regression tests for review finding consolidation.

Each test here pins a defect observed in a real review session (`.data/reviews/`) where
duplicate findings were never consolidated, or distinct ones were merged.
"""

from __future__ import annotations

from pathlib import Path

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


def test_similar_titles_far_apart_stay_separate_without_a_shared_symbol() -> None:
    """Similar titles 40 lines apart are kept as two findings unless they name the same symbol.

    Personas do cite one defect at different, often wrong, line ranges. But two instances of
    one kind of defect look the same, and review pages carry no line numbers yet (#499), so
    the two cannot be told apart. A kept duplicate costs a line of the report; a wrong merge
    loses a defect (#512).
    """
    findings = [
        _finding("TTL parameter ignored in cache set operation", "src/k8s/service.py:115-122"),
        _finding("TTL parameter ignored in cache setter", "src/k8s/service.py:162-170"),
    ]
    assert len(consolidate_duplicate_findings(findings)) == 2


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

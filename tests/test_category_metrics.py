"""Unit tests for false-positive rate tracking across review runs."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.review.category_metrics import (
    collect_historical_category_metrics,
    compute_category_metrics,
    format_category_baseline_markdown,
    resolve_finding_category,
)
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding


def test_resolve_finding_category_explicit_and_inferred() -> None:
    """Verify category resolution with explicit values and semantic inference."""
    f_explicit = SavedFinding(
        id=1,
        title="Custom title",
        category="secret_scanning",
        location="src/app.py:1",
    )
    f_secret = SavedFinding(
        id=2,
        title="Masked secret placeholder found in config",
        location="src/auth.py:5",
    )
    f_syntax = SavedFinding(
        id=3,
        title="Python 3.14 pep758 bracketless except clause",
        location="src/parser.py:10",
    )
    f_mock = SavedFinding(
        id=4,
        title="dummy_token used in test mock credential",
        location="tests/test_mod.py:15",
    )
    f_dep = SavedFinding(
        id=5,
        title="httpx2 package dependency typosquat",
        location="pyproject.toml:20",
    )
    f_boundary = SavedFinding(
        id=6,
        title="cwe-400 uncontrolled_resource_consumption read_text out_of_bounds",
        location="src/utils.py:25",
    )
    f_mutable = SavedFinding(
        id=7,
        title="Mutable default_factory on model",
        location="src/core.py:30",
    )
    f_doc = SavedFinding(
        id=8,
        title="Anti-pattern example in documentation",
        location="src/doc.py:35",
    )
    f_general = SavedFinding(
        id=9,
        title="Unspecified architectural divergence",
        location="src/main.py:40",
    )

    actual = (
        resolve_finding_category(f_explicit),
        resolve_finding_category(f_secret),
        resolve_finding_category(f_syntax),
        resolve_finding_category(f_mock),
        resolve_finding_category(f_dep),
        resolve_finding_category(f_boundary),
        resolve_finding_category(f_mutable),
        resolve_finding_category(f_doc),
        resolve_finding_category(f_general),
    )
    expected = (
        "secret_scanning",
        "secret_scanning",
        "syntax_grammar",
        "test_mocks",
        "dependency_ecosystem",
        "boundary_errors",
        "mutable_defaults",
        "documentation_context",
        "general",
    )
    assert actual == expected


def test_compute_category_metrics_empty_and_mixed() -> None:
    """Verify compute_category_metrics with empty and diverse finding sets."""
    assert compute_category_metrics([]) == {}

    findings = [
        SavedFinding(
            id=1,
            category="secret_scanning",
            title="Secret 1",
            status="VERIFIED",
            location="a.py:1",
        ),
        SavedFinding(
            id=2,
            category="secret_scanning",
            title="Secret 2",
            status="INVALIDATED",
            location="a.py:2",
        ),
        SavedFinding(
            id=3,
            category="syntax_grammar",
            title="Syntax 1",
            status="INVALIDATED",
            location="b.py:1",
        ),
        SavedFinding(
            id=4,
            category="syntax_grammar",
            title="Syntax 2",
            status="INVALIDATED",
            location="b.py:2",
        ),
        SavedFinding(
            id=5,
            category="general",
            title="General 1",
            status="UNVERIFIED",
            location="c.py:1",
        ),
    ]

    metrics = compute_category_metrics(findings)
    actual = (
        set(metrics.keys()),
        metrics["secret_scanning"].total,
        metrics["secret_scanning"].invalidated,
        metrics["secret_scanning"].verified,
        metrics["secret_scanning"].false_positive_rate,
        metrics["syntax_grammar"].total,
        metrics["syntax_grammar"].invalidated,
        metrics["syntax_grammar"].false_positive_rate,
        metrics["general"].total,
        metrics["general"].unverified,
        metrics["general"].false_positive_rate,
    )
    expected = (
        {"secret_scanning", "syntax_grammar", "general"},
        2,
        1,
        1,
        50.0,
        2,
        2,
        100.0,
        1,
        1,
        0.0,
    )
    assert actual == expected


def test_collect_historical_category_metrics(tmp_path: Path) -> None:
    """Verify historical category metric aggregation across session directories."""
    assert (
        collect_historical_category_metrics(tmp_path / "nonexistent"),
        collect_historical_category_metrics(tmp_path),
    ) == (({}, 0, 0), ({}, 0, 0))

    sess1 = tmp_path / "sess1"
    sess1.mkdir()
    payload1 = ReviewSessionPayload(
        target="src/",
        timestamp="2026-09-25T10:00:00Z",
        findings=[
            SavedFinding(
                id=1,
                category="secret_scanning",
                title="Secret 1",
                status="INVALIDATED",
                location="a.py:1",
            ),
            SavedFinding(
                id=2,
                category="syntax_grammar",
                title="Syntax 1",
                status="VERIFIED",
                location="b.py:1",
            ),
        ],
    )
    (sess1 / "findings.json").write_text(payload1.model_dump_json(indent=2), encoding="utf-8")

    sess2 = tmp_path / "sess2"
    sess2.mkdir()
    payload2 = ReviewSessionPayload(
        target="src/",
        timestamp="2026-09-25T11:00:00Z",
        findings=[
            SavedFinding(
                id=3,
                category="secret_scanning",
                title="Secret 2",
                status="VERIFIED",
                location="a.py:2",
            ),
            SavedFinding(
                id=4,
                category="syntax_grammar",
                title="Syntax 2",
                status="INVALIDATED",
                location="b.py:2",
            ),
        ],
    )
    (sess2 / "findings.json").write_text(payload2.model_dump_json(indent=2), encoding="utf-8")

    history, total_sessions, total_findings = collect_historical_category_metrics(tmp_path)
    actual = (
        set(history.keys()),
        total_sessions,
        total_findings,
        history["secret_scanning"].total,
        history["secret_scanning"].invalidated,
        history["secret_scanning"].false_positive_rate,
        history["syntax_grammar"].total,
        history["syntax_grammar"].invalidated,
        history["syntax_grammar"].false_positive_rate,
    )
    expected = (
        {"secret_scanning", "syntax_grammar"},
        2,
        4,
        2,
        1,
        50.0,
        2,
        1,
        50.0,
    )
    assert actual == expected


def test_format_category_baseline_markdown(tmp_path: Path) -> None:
    """Verify markdown table formatting with and without historical baseline comparison."""
    assert format_category_baseline_markdown([], tmp_path) == []

    session_findings = [
        SavedFinding(
            id=1,
            category="secret_scanning",
            title="Secret Key Found",
            status="INVALIDATED",
            location="src/key.py:1",
        ),
        SavedFinding(
            id=2,
            category="test_mocks",
            title="Mock Spec Mismatch",
            status="VERIFIED",
            location="tests/mock.py:2",
        ),
    ]

    # Without prior historical reviews
    lines_no_history = format_category_baseline_markdown(session_findings, tmp_path)
    md_no_history = "\n".join(lines_no_history)
    assert (
        "## Category Verification & False-Positive Baseline" in md_no_history,
        "`secret_scanning`" in md_no_history,
        "100.0%" in md_no_history,
        "`test_mocks`" in md_no_history,
        "0.0%" in md_no_history,
        "— (baseline established)" in md_no_history,
    ) == (True, True, True, True, True, True)

    # With historical reviews creating a multi-session baseline
    sess_dir1 = tmp_path / "sess_prior1"
    sess_dir1.mkdir()
    prior_payload1 = ReviewSessionPayload(
        target="src/",
        timestamp="2026-09-24T12:00:00Z",
        findings=[
            SavedFinding(
                id=10,
                category="secret_scanning",
                title="Prior Secret",
                status="VERIFIED",
                location="src/key.py:1",
            ),
        ],
    )
    (sess_dir1 / "findings.json").write_text(
        prior_payload1.model_dump_json(indent=2), encoding="utf-8"
    )

    sess_dir2 = tmp_path / "sess_prior2"
    sess_dir2.mkdir()
    prior_payload2 = ReviewSessionPayload(
        target="src/",
        timestamp="2026-09-24T13:00:00Z",
        findings=[
            SavedFinding(
                id=11,
                category="secret_scanning",
                title="Prior Secret 2",
                status="VERIFIED",
                location="src/key.py:2",
            ),
        ],
    )
    (sess_dir2 / "findings.json").write_text(
        prior_payload2.model_dump_json(indent=2), encoding="utf-8"
    )

    lines_with_history = format_category_baseline_markdown(session_findings, tmp_path)
    md_with_history = "\n".join(lines_with_history)
    assert (
        "## Category Verification & False-Positive Baseline" in md_with_history,
        "`secret_scanning`" in md_with_history,
        "0.0% (0/2)" in md_with_history,
    ) == (True, True, True)


def test_pipeline_category_baseline_and_summary_integration(tmp_path: Path) -> None:
    """Verify ReviewPipelineOrchestrator baseline section rendering and summary table."""
    pipeline = ReviewPipelineOrchestrator(target_dir=tmp_path, session_id="test-session")
    findings = [
        SavedFinding(
            id=1,
            category="secret_scanning",
            title="Secret Invalidation",
            status="INVALIDATED",
            location="src/a.py:1",
            reportable=False,
        ),
        SavedFinding(
            id=2,
            category="general",
            title="Architecture Flaw",
            status="VERIFIED",
            location="src/b.py:1",
            reportable=True,
        ),
    ]

    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-session",
        generated_at="2026-09-25T12:00:00Z",
        reportable_findings=[f for f in findings if f.reportable],
        all_deps=[],
        all_nets=[],
        all_findings=findings,
    )

    assert (
        "## Category Verification & False-Positive Baseline" in report_md,
        "`secret_scanning`" in report_md,
        "`general`" in report_md,
    ) == (True, True, True)

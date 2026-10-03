"""Unit tests for false-positive rate tracking across review runs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review.category_metrics import (
    collect_historical_category_metrics,
    compute_category_metrics,
    format_category_baseline_markdown,
    resolve_finding_category,
)
from devops_cli.ai.review.history import review_subject
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import _save_findings_json
from devops_cli.ai.review_schema import Finding, ReviewResult, ReviewSessionPayload, SavedFinding

_SUBJECT = review_subject("branch", "feature", ["diff --git a/config.py b/config.py\n"])
_OLDER = "2026-10-01T09:00:00+00:00"
_NEWEST = "2026-10-01T12:00:00+00:00"


def _finding(status: str, category: str = "secret_exposure") -> SavedFinding:
    """A finding with a machine verdict, or none when UNVERIFIED."""
    return SavedFinding(
        title=f"{status.title()} {category} finding",
        location="config.py:1",
        category=category,
        status=status,
        verified_by=None if status == "UNVERIFIED" else "llm",
        reportable=status != "INVALIDATED",
    )


def _baseline(lines: list[str], category: str) -> tuple[str, str]:
    """The category's Historical Baseline FP Rate cell, and the note line under the table."""
    row = next(line for line in lines if line.startswith(f"| `{category}` |"))
    note = next(line for line in lines if line.startswith("_Baseline:"))
    return row.rstrip(" |").rsplit("| ", 1)[1], note


def test_resolve_finding_category_explicit_and_inferred() -> None:
    """Verify a finding's theme is the defect class its category, a CWE it cites, or its title
    names, and `other` when none names one (#948)."""
    findings = [
        SavedFinding(title="Custom title", category="secret_exposure", location="src/app.py:1"),
        SavedFinding(title="Hardcoded token", category="Secret Handling", location="a.py:1"),
        SavedFinding(title="Masked secret placeholder in config", location="src/auth.py:5"),
        SavedFinding(title="Escape", references=["CWE-22: Path Traversal"], location="b.py:2"),
        SavedFinding(title="cwe-400 unbounded read_text", location="src/utils.py:25"),
        SavedFinding(title="httpx2 package dependency typosquat", location="pyproject.toml:20"),
        SavedFinding(title="Anti-pattern example in documentation", location="src/doc.py:35"),
        SavedFinding(title="Unspecified architectural divergence", location="src/main.py:40"),
    ]

    assert [resolve_finding_category(f) for f in findings] == [
        "secret_exposure",
        "secret_exposure",
        "secret_exposure",
        "path_traversal",
        "resource_exhaustion",
        "supply_chain",
        "documentation",
        "other",
    ]


def test_compute_category_metrics_empty_and_mixed() -> None:
    """Verify compute_category_metrics with empty and diverse finding sets."""
    assert compute_category_metrics([]) == {}

    findings = [
        SavedFinding(
            id=1,
            category="secret_exposure",
            title="Secret 1",
            status="VERIFIED",
            location="a.py:1",
        ),
        SavedFinding(
            id=2,
            category="secret_exposure",
            title="Secret 2",
            status="INVALIDATED",
            location="a.py:2",
        ),
        SavedFinding(
            id=3,
            category="syntax_error",
            title="Syntax 1",
            status="INVALIDATED",
            location="b.py:1",
        ),
        SavedFinding(
            id=4,
            category="syntax_error",
            title="Syntax 2",
            status="INVALIDATED",
            location="b.py:2",
        ),
        SavedFinding(
            id=5,
            category="other",
            title="General 1",
            status="UNVERIFIED",
            location="c.py:1",
        ),
    ]

    metrics = compute_category_metrics(findings)
    actual = (
        set(metrics.keys()),
        metrics["secret_exposure"].total,
        metrics["secret_exposure"].invalidated,
        metrics["secret_exposure"].verified,
        metrics["secret_exposure"].false_positive_rate,
        metrics["syntax_error"].total,
        metrics["syntax_error"].invalidated,
        metrics["syntax_error"].false_positive_rate,
        metrics["other"].total,
        metrics["other"].unverified,
        metrics["other"].false_positive_rate,
    )
    expected = (
        {"secret_exposure", "syntax_error", "other"},
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
    missing_metrics, missing_history = collect_historical_category_metrics(tmp_path / "nonexistent")
    empty_metrics, empty_history = collect_historical_category_metrics(tmp_path)
    assert (missing_metrics, missing_history.sessions, empty_metrics, empty_history.sessions) == (
        {},
        (),
        {},
        (),
    )

    sess1 = tmp_path / "sess1"
    sess1.mkdir()
    payload1 = ReviewSessionPayload(
        generated_at="2026-09-25T10:00:00Z",
        subject=review_subject("path", "src/", ["first"]),
        findings=[
            SavedFinding(
                id=1,
                category="secret_exposure",
                title="Secret 1",
                status="INVALIDATED",
                location="a.py:1",
            ),
            SavedFinding(
                id=2,
                category="syntax_error",
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
        generated_at="2026-09-25T11:00:00Z",
        subject=review_subject("path", "src/", ["second"]),
        findings=[
            SavedFinding(
                id=3,
                category="secret_exposure",
                title="Secret 2",
                status="VERIFIED",
                location="a.py:2",
            ),
            SavedFinding(
                id=4,
                category="syntax_error",
                title="Syntax 2",
                status="INVALIDATED",
                location="b.py:2",
            ),
        ],
    )
    (sess2 / "findings.json").write_text(payload2.model_dump_json(indent=2), encoding="utf-8")

    metrics, history = collect_historical_category_metrics(tmp_path)
    actual = (
        set(metrics.keys()),
        len(history.counted),
        sum(len(s.raised) for s in history.counted),
        metrics["secret_exposure"].total,
        metrics["secret_exposure"].invalidated,
        metrics["secret_exposure"].false_positive_rate,
        metrics["syntax_error"].total,
        metrics["syntax_error"].invalidated,
        metrics["syntax_error"].false_positive_rate,
    )
    expected = (
        {"secret_exposure", "syntax_error"},
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
            category="secret_exposure",
            title="Secret Key Found",
            status="INVALIDATED",
            location="src/key.py:1",
        ),
        SavedFinding(
            id=2,
            category="testing",
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
        "`secret_exposure`" in md_no_history,
        "100.0%" in md_no_history,
        "`testing`" in md_no_history,
        "0.0%" in md_no_history,
        "— (baseline established)" in md_no_history,
    ) == (True, True, True, True, True, True)

    # With historical reviews creating a multi-session baseline
    sess_dir1 = tmp_path / "sess_prior1"
    sess_dir1.mkdir()
    prior_payload1 = ReviewSessionPayload(
        generated_at="2026-09-24T12:00:00Z",
        subject=review_subject("path", "src/", ["first"]),
        findings=[
            SavedFinding(
                id=10,
                category="secret_exposure",
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
        generated_at="2026-09-24T13:00:00Z",
        subject=review_subject("path", "src/", ["second"]),
        findings=[
            SavedFinding(
                id=11,
                category="secret_exposure",
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
        "`secret_exposure`" in md_with_history,
        "0.0% (0/2)" in md_with_history,
    ) == (True, True, True)


def test_pipeline_category_baseline_and_summary_integration(tmp_path: Path) -> None:
    """Verify ReviewPipelineOrchestrator baseline section rendering and summary table."""
    pipeline = ReviewPipelineOrchestrator(target_dir=tmp_path, session_id="test-session")
    findings = [
        SavedFinding(
            id=1,
            category="secret_exposure",
            title="Secret Invalidation",
            status="INVALIDATED",
            location="src/a.py:1",
            reportable=False,
        ),
        SavedFinding(
            id=2,
            category="other",
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
        "`secret_exposure`" in report_md,
        "`other`" in report_md,
    ) == (True, True, True)


def test_the_baseline_leaves_out_the_current_session_and_counts_each_subject_once(
    tmp_path: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify the current session, written before its report as the pipeline does, is left out
    of its own baseline, that the baseline reads every finding the earlier session raised, and
    that repeats of the earlier session's subject count once (#434's figure counted all three)."""
    reviews = tmp_path / "reviews"
    current = reviews / "current"
    current_findings = [_finding("INVALIDATED")]
    earlier = {
        "subject": _SUBJECT,
        "findings": [_finding("VERIFIED")],
        "candidates": [_finding("INVALIDATED"), _finding("VERIFIED")],
    }
    write_review_session(reviews / "earlier", generated_at=_OLDER, **earlier)

    def baseline() -> tuple[str, str]:
        lines = format_category_baseline_markdown(current_findings, reviews, exclude=current)
        return _baseline(lines, "secret_exposure")

    before_written = baseline()
    write_review_session(
        current, generated_at=_NEWEST, subject=_SUBJECT, candidates=current_findings
    )
    written = baseline()
    for name in ("repeat-1", "repeat-2"):
        write_review_session(reviews / name, generated_at="2026-10-01T10:00:00+00:00", **earlier)
    with_repeats = baseline()

    note = (
        "_Baseline: 1 earlier session(s), {} repeat session(s) collapsed, this session excluded._"
    )
    assert (before_written, written, with_repeats) == (
        ("50.0% (1/2)", note.format(0)),
        ("50.0% (1/2)", note.format(0)),
        ("50.0% (1/2)", note.format(2)),
    )


def test_the_baseline_shows_once_an_earlier_session_has_the_category(
    tmp_path: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a category no earlier session raised reads `baseline established`, and that a
    first re-review shows its earlier session's figures: the gate counted the current session,
    and its replacement must not hide the baseline when the only earlier session shares the
    current session's subject."""
    reviews = tmp_path / "reviews"
    current_findings = [
        _finding("INVALIDATED"),
        _finding("VERIFIED", "testing"),
    ]
    current = write_review_session(
        reviews / "current", generated_at=_NEWEST, subject=_SUBJECT, candidates=current_findings
    )

    def cells() -> tuple[str, str]:
        lines = format_category_baseline_markdown(current_findings, reviews, exclude=current)
        return _baseline(lines, "secret_exposure")[0], _baseline(lines, "testing")[0]

    first_review = cells()
    write_review_session(
        reviews / "earlier", generated_at=_OLDER, subject=_SUBJECT, findings=[_finding("VERIFIED")]
    )

    assert (first_review, cells()) == (
        ("— (baseline established)", "— (baseline established)"),
        ("0.0% (0/1)", "— (baseline established)"),
    )


def test_a_persona_loop_session_feeds_the_baseline_from_its_findings_json(tmp_path: Path) -> None:
    """Verify a session the persona loop wrote, with findings.json and no candidates.json,
    counts its findings.json findings in the baseline."""
    session = tmp_path / "reviews" / "persona-loop"
    session.mkdir(parents=True)
    findings = [
        Finding(
            title="Masked token in config",
            location="config.py:1",
            category="secret_exposure",
            status="INVALIDATED",
            verified_by="llm",
            reportable=False,
        ),
        Finding(
            title="Hardcoded password in settings",
            location="settings.py:9",
            category="secret_exposure",
            status="VERIFIED",
            verified=True,
            verified_by="llm",
        ),
    ]
    _save_findings_json(
        [(PERSONAS[Persona.DEVSECOPS], ReviewResult(findings=findings))], session, subject=_SUBJECT
    )

    metrics, history = collect_historical_category_metrics(tmp_path / "reviews")

    assert (
        (session / "candidates.json").exists(),
        len(history.counted),
        metrics["secret_exposure"].invalidated,
        metrics["secret_exposure"].total,
    ) == (False, 1, 1, 2)

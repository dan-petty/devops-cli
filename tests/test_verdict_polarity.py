"""Unit and integration tests for verdict polarity and field distribution assertions."""

from __future__ import annotations

import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.ai.review.pipeline import (
    ReviewPipelineOrchestrator,
)
from devops_cli.ai.review.profile import ReviewProfile, ReviewProfiler
from devops_cli.ai.review_schema import (
    Finding,
    ReviewResult,
    SavedFinding,
    _merge_two_findings,
    _parse_stringified_collection,
    compute_verdict_distributions,
    is_field_discriminating,
)
from devops_cli.config import DEFAULT_FINDING_STATUS


def test_finding_polarity_validation_success() -> None:
    """Verify polarity validation when distinct values or aliases are supplied."""
    f1 = Finding(
        severity="HIGH",
        location="src/auth.py:10",
        title="Insecure cookie flag",
        description="Secure flag not set on session cookie",
        fix="cookie.set_secure(True)",
        observed_value="secure=False",
        expected_value="secure=True",
    )
    f2 = Finding(
        severity="MEDIUM",
        location="src/db.py:20",
        title="Debug mode enabled",
        description="DB debug mode active",
        fix="debug=False",
        observed="True",
        expected="False",
    )
    f3 = Finding(
        severity="LOW",
        location="src/net.py:30",
        title="Default timeout too high",
        description="Timeout exceeds safe threshold",
        fix="timeout=5",
        actual_value="60",
        expected="5",
    )
    f4 = Finding(
        severity="LOW",
        location="src/app.py:5",
        title="Missing comment",
        description="Docstring missing",
        fix="# Add docstring",
    )

    actual = (
        (f1.observed_value, f1.expected_value),
        (f2.observed_value, f2.expected_value),
        (f3.observed_value, f3.expected_value),
        (f4.observed_value, f4.expected_value),
    )
    expected = (
        ("secure=False", "secure=True"),
        ("True", "False"),
        ("60", "5"),
        (None, None),
    )
    assert actual == expected


def test_finding_polarity_graceful_handling() -> None:
    """Verify polarity validation gracefully handles missing counterpart or identical values."""
    f_missing_exp = Finding(
        severity="HIGH",
        location="src/auth.py:10",
        title="Insecure cookie flag",
        description="Secure flag not set",
        fix="fix",
        observed_value="secure=False",
    )
    f_missing_obs = Finding(
        severity="HIGH",
        location="src/auth.py:10",
        title="Insecure cookie flag",
        description="Secure flag not set",
        fix="fix",
        expected_value="secure=True",
    )
    f_identical = Finding(
        severity="HIGH",
        location="src/auth.py:10",
        title="Contradictory polarity assertion",
        description="Values match",
        fix="fix",
        observed_value="secure=True",
        expected_value="secure=True",
    )
    f_identical_ws = Finding(
        severity="HIGH",
        location="src/auth.py:10",
        title="Contradictory polarity assertion with whitespace",
        description="Values match after stripping",
        fix="fix",
        observed="  mode=True  ",
        expected="mode=True",
    )

    actual = (
        (f_missing_exp.observed_value, f_missing_exp.expected_value, f_missing_exp.status),
        (f_missing_obs.observed_value, f_missing_obs.expected_value, f_missing_obs.status),
        (
            f_identical.status,
            f_identical.reportable,
            f_identical.verified,
            f_identical.verified_by,
            "identical to expected value" in (f_identical.invalidation_reason or ""),
        ),
        (
            f_identical_ws.status,
            f_identical_ws.reportable,
            f_identical_ws.verified,
            f_identical_ws.verified_by,
            "identical to expected value" in (f_identical_ws.invalidation_reason or ""),
        ),
    )
    expected = (
        (None, None, DEFAULT_FINDING_STATUS),
        (None, None, DEFAULT_FINDING_STATUS),
        ("INVALIDATED", False, False, "deterministic:verdict_polarity", True),
        ("INVALIDATED", False, False, "deterministic:verdict_polarity", True),
    )
    assert actual == expected


def test_review_result_graceful_polarity_deserialization() -> None:
    """Verify ReviewResult deserialization gracefully handles contradictory and asymmetric polarity."""
    payload = {
        "findings": [
            {
                "severity": "HIGH",
                "location": "src/auth.py:10",
                "title": "Finding with identical polarity",
                "description": "Values match",
                "fix": "fix()",
                "observed_value": "Available domains include `gh`, `k8s`",
                "expected_value": "Available domains include `gh`, `k8s`",
            },
            {
                "severity": "MEDIUM",
                "location": "src/config.py:20",
                "title": "Finding with orphan expected value",
                "description": "Orphan polarity",
                "fix": "fix()",
                "expected_value": "with proper validation",
            },
            {
                "severity": "LOW",
                "location": "src/util.py:30",
                "title": "Legitimate valid polarity finding",
                "description": "Distinct polarity",
                "fix": "fix()",
                "observed_value": "timeout=60",
                "expected_value": "timeout=5",
            },
        ],
        "summary": "Review complete",
    }
    result = ReviewResult.model_validate(payload)
    f0, f1, f2 = result.findings
    actual = (
        len(result.findings),
        (f0.status, f0.reportable, f0.verified, f0.verified_by),
        (f1.observed_value, f1.expected_value),
        (f2.observed_value, f2.expected_value, f2.status),
    )
    expected = (
        3,
        ("INVALIDATED", False, False, "deterministic:verdict_polarity"),
        (None, None),
        ("timeout=60", "timeout=5", DEFAULT_FINDING_STATUS),
    )
    assert actual == expected


def test_parse_stringified_collection_escapes() -> None:
    """Verify _parse_stringified_collection handles forward-slash escapes without SyntaxWarning."""
    raw_json = '["http:\\/\\/example.com", "path\\/to\\/file"]'
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        parsed = _parse_stringified_collection(raw_json)
    assert parsed == ["http://example.com", "path/to/file"]


def test_saved_finding_polarity_and_merge() -> None:
    """Verify SavedFinding persistence and merge consolidation polarity preservation."""
    sf = SavedFinding(
        id=1,
        title="Title",
        location="src/app.py:1",
        observed_value="observed_foo",
        expected_value="expected_bar",
    )
    assert (sf.observed_value, sf.expected_value) == ("observed_foo", "expected_bar")

    f_base = Finding(
        severity="HIGH",
        location="src/app.py:1-5",
        title="Base title",
        description="Base description",
        fix="fix_base()",
    )
    f_other = Finding(
        severity="HIGH",
        location="src/app.py:1-5",
        title="Other title",
        description="Other description",
        fix="fix_other()",
        observed_value="bad_val",
        expected_value="good_val",
    )
    merged = _merge_two_findings(f_base, f_other)
    assert (merged.observed_value, merged.expected_value) == ("bad_val", "good_val")


def test_compute_verdict_distributions_and_discriminating() -> None:
    """Verify compute_verdict_distributions and is_field_discriminating logic."""
    assert compute_verdict_distributions([]) == {
        "status": {},
        "reportable": {"true": 0, "false": 0},
        "verified": {"true": 0, "false": 0},
        "mitigated": {"true": 0, "false": 0},
        "citation_rates": {},
        "verification_note": {},
    }

    findings = [
        SavedFinding(
            id=1,
            title="F1",
            location="a.py:1",
            status="VERIFIED",
            reportable=True,
            verified=True,
            mitigated=False,
        ),
        SavedFinding(
            id=2,
            title="F2",
            location="a.py:2",
            status="INVALIDATED",
            reportable=False,
            verified=False,
            mitigated=False,
        ),
        SavedFinding(
            id=3,
            title="F3",
            location="a.py:3",
            status="MITIGATED",
            reportable=True,
            verified=True,
            mitigated=True,
        ),
    ]

    dist = compute_verdict_distributions(findings)
    actual_counts = (
        dist["status"],
        dist["reportable"],
        dist["verified"],
        dist["mitigated"],
    )
    expected_counts = (
        {"VERIFIED": 1, "INVALIDATED": 1, "MITIGATED": 1},
        {"true": 2, "false": 1},
        {"true": 2, "false": 1},
        {"true": 1, "false": 2},
    )
    assert actual_counts == expected_counts

    disc_status = is_field_discriminating(dist["status"])
    disc_reportable = is_field_discriminating(dist["reportable"])
    disc_non_discriminating = is_field_discriminating({"true": 5, "false": 0})
    disc_single_key = is_field_discriminating({"true": 5})

    assert (
        disc_status,
        disc_reportable,
        disc_non_discriminating,
        disc_single_key,
    ) == (True, True, False, False)


def test_pipeline_verdict_distributions_formatting(tmp_path: Path) -> None:
    """Verify console rows and markdown section generated by orchestrator."""
    pipeline = ReviewPipelineOrchestrator(target_dir=tmp_path, session_id="test-dist")
    findings = [
        SavedFinding(
            id=1,
            title="F1",
            location="a.py:1",
            status="VERIFIED",
            reportable=True,
            verified=True,
            mitigated=False,
        ),
        SavedFinding(
            id=2,
            title="F2",
            location="a.py:2",
            status="VERIFIED",
            reportable=True,
            verified=True,
            mitigated=False,
        ),
    ]

    rows = pipeline._format_verdict_distributions(findings)
    md_lines = pipeline._build_verdict_distributions_section(findings)
    md_text = "\n".join(md_lines)

    rows_dict = {row[0]: row[1] for row in rows}

    actual = (
        "Verdict Status" in rows_dict,
        "(does not discriminate)" in rows_dict["Verdict Reportable"],
        "(does not discriminate)" in rows_dict["Verdict Verified"],
        "## Verdict Field Distributions" in md_text,
        "(never discriminates)" in md_text,
    )
    expected = (True, True, True, True, True)
    assert actual == expected


def test_render_console_summary_table_integration(tmp_path: Path) -> None:
    """Verify _render_console_summary_table integrates verdict distribution rows."""
    pipeline = ReviewPipelineOrchestrator(target_dir=tmp_path, session_id="test-table")
    mock_console = MagicMock()
    with patch("devops_cli.ai.review.pipeline.print_table") as mock_print_table:
        pipeline._render_console_summary_table(
            console=mock_console,
            session_id="test-table",
            n_files=1,
            reportable_findings=[],
            all_deps=[],
            all_nets=[],
            all_findings=[],
            candidate_findings=[],
        )
        assert mock_print_table.called is True
        call_kwargs = mock_print_table.call_args.kwargs
        assert ("Review Summary", mock_console) == (
            call_kwargs.get("title"),
            call_kwargs.get("console"),
        )


def test_review_profile_verdict_distributions(tmp_path: Path) -> None:
    """Verify ReviewProfile and ReviewProfiler record and persist verdict distributions."""
    profiler = ReviewProfiler()
    test_dists: dict[str, dict[str, int | float]] = {
        "status": {"VERIFIED": 2, "INVALIDATED": 1},
        "reportable": {"true": 2, "false": 1},
        "verified": {"true": 2, "false": 1},
        "mitigated": {"false": 3},
        "citation_rates": {"unknown": 0.61, "llm": 0.85},
    }
    profiler.set_findings(
        candidates=3,
        verified=2,
        reported=2,
        verdict_distributions=test_dists,
    )
    profile = profiler.build(session_id="test_sess", target="src/")
    profile_path = profile.write(tmp_path)
    assert profile_path.exists() is True

    loaded_profile = ReviewProfile.load(tmp_path)
    assert loaded_profile is not None
    assert (
        profile.verdict_distributions["status"],
        profile.verdict_distributions["reportable"],
        profile.verdict_distributions["citation_rates"],
        loaded_profile.verdict_distributions["status"],
        loaded_profile.verdict_distributions["mitigated"],
        loaded_profile.verdict_distributions["citation_rates"],
    ) == (
        {"VERIFIED": 2, "INVALIDATED": 1},
        {"true": 2, "false": 1},
        {"unknown": 0.61, "llm": 0.85},
        {"VERIFIED": 2, "INVALIDATED": 1},
        {"false": 3},
        {"unknown": 0.61, "llm": 0.85},
    )

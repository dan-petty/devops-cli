"""Unit and integration tests for verdict polarity and field distribution assertions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from devops_cli.ai.review.pipeline import (
    ReviewPipelineOrchestrator,
    run_pipeline_self_test,
)
from devops_cli.ai.review.profile import ReviewProfile, ReviewProfiler
from devops_cli.ai.review.verification import (
    _apply_single_finding_verification,
    _check_verdict_polarity_hallucination,
    _deterministic_pre_verification,
)
from devops_cli.ai.review_schema import (
    Finding,
    SavedFinding,
    _merge_two_findings,
    compute_verdict_distributions,
    is_field_discriminating,
)


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


def test_finding_polarity_validation_errors() -> None:
    """Verify polarity validation failures on missing counterpart or identical values."""
    with pytest.raises(
        ValidationError,
        match="Both observed_value and expected_value must be provided",
    ):
        Finding(
            severity="HIGH",
            location="src/auth.py:10",
            title="Insecure cookie flag",
            description="Secure flag not set",
            fix="fix",
            observed_value="secure=False",
        )

    with pytest.raises(
        ValidationError,
        match="Both observed_value and expected_value must be provided",
    ):
        Finding(
            severity="HIGH",
            location="src/auth.py:10",
            title="Insecure cookie flag",
            description="Secure flag not set",
            fix="fix",
            expected_value="secure=True",
        )

    with pytest.raises(ValidationError, match="cannot be identical"):
        Finding(
            severity="HIGH",
            location="src/auth.py:10",
            title="Contradictory polarity assertion",
            description="Values match",
            fix="fix",
            observed_value="secure=True",
            expected_value="secure=True",
        )

    with pytest.raises(ValidationError, match="cannot be identical"):
        Finding(
            severity="HIGH",
            location="src/auth.py:10",
            title="Contradictory polarity assertion with whitespace",
            description="Values match after stripping",
            fix="fix",
            observed="  mode=True  ",
            expected="mode=True",
        )


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


def test_check_verdict_polarity_hallucination() -> None:
    """Verify deterministic pre-verification invalidation on identical polarity values."""
    f_valid = Finding(
        severity="HIGH",
        location="src/auth.py:10",
        title="Valid finding",
        description="Valid description",
        fix="fix()",
        observed_value="status=ERROR",
        expected_value="status=OK",
    )
    f_none = Finding(
        severity="HIGH",
        location="src/auth.py:10",
        title="None finding",
        description="None description",
        fix="fix()",
    )
    f_hallucinated = Finding.model_construct(
        severity="HIGH",
        location="src/auth.py:10",
        title="Contradictory finding",
        description="Contradictory description",
        fix="fix()",
        observed_value="ERROR",
        expected_value="ERROR",
    )

    r_valid = _check_verdict_polarity_hallucination(f_valid)
    r_none = _check_verdict_polarity_hallucination(f_none)
    r_hallucinated = _check_verdict_polarity_hallucination(f_hallucinated)

    assert (r_valid, r_none) == (None, None)
    assert r_hallucinated is not None
    assert (
        r_hallucinated.verified,
        r_hallucinated.reportable,
        r_hallucinated.status,
        "identical to expected value" in (r_hallucinated.invalidation_reason or ""),
    ) == (False, False, "INVALIDATED", True)


def test_deterministic_pre_verification_integration(tmp_path: Path) -> None:
    """Verify deterministic pre-verification catches contradictory polarity."""
    test_file = tmp_path / "app.py"
    test_file.write_text("status = 'OK'\n", encoding="utf-8")

    f_bad = Finding.model_construct(
        severity="HIGH",
        location="app.py:1",
        title="Bad polarity",
        description="Bad polarity",
        fix="fix",
        observed_value="same",
        expected_value="same",
    )
    result = _deterministic_pre_verification(f_bad, target_dir=tmp_path)
    assert (
        result.status,
        result.verified,
        result.reportable,
    ) == ("INVALIDATED", False, False)


def test_apply_single_finding_verification_polarity() -> None:
    """Verify LLM verification response parsing rejects identical polarity values."""
    target_f1 = Finding(
        severity="HIGH",
        location="app.py:1",
        title="Test Finding",
        description="Desc",
        fix="fix",
    )
    v_dict_bad = {
        "finding_id": 1,
        "status": "VERIFIED",
        "verified": True,
        "reportable": True,
        "reason": "Passed inspection",
        "observed_value": "IDENTICAL",
        "expected_value": "IDENTICAL",
    }
    res_bad = _apply_single_finding_verification(
        target_f1, v_dict_bad, now_iso="2026-09-25T12:00:00Z"
    )
    bad_res = (res_bad.status, res_bad.verified, res_bad.reportable)

    target_f2 = Finding(
        severity="HIGH",
        location="app.py:2",
        title="Test Finding 2",
        description="Desc 2",
        fix="fix 2",
    )
    v_dict_good = {
        "finding_id": 2,
        "status": "VERIFIED",
        "verified": True,
        "reportable": True,
        "reason": "Passed inspection",
        "observed_value": "VAL_A",
        "expected_value": "VAL_B",
    }
    res_good = _apply_single_finding_verification(
        target_f2, v_dict_good, now_iso="2026-09-25T12:00:00Z"
    )
    good_res = (
        res_good.status,
        res_good.verified,
        res_good.reportable,
        res_good.observed_value,
        res_good.expected_value,
    )

    assert (bad_res, good_res) == (
        ("INVALIDATED", False, False),
        ("VERIFIED", True, True, "VAL_A", "VAL_B"),
    )


def test_compute_verdict_distributions_and_discriminating() -> None:
    """Verify compute_verdict_distributions and is_field_discriminating logic."""
    assert compute_verdict_distributions([]) == {
        "status": {},
        "reportable": {"true": 0, "false": 0},
        "verified": {"true": 0, "false": 0},
        "mitigated": {"true": 0, "false": 0},
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


def test_pipeline_self_test_success(tmp_path: Path) -> None:
    """Verify run_pipeline_self_test and orchestrator.run_self_test succeed."""
    pipeline = ReviewPipelineOrchestrator(target_dir=tmp_path, session_id="test-self")
    actual = (
        run_pipeline_self_test(tmp_path),
        pipeline.run_self_test(),
    )
    expected = (True, True)
    assert actual == expected


def test_pipeline_self_test_failure_detection(tmp_path: Path) -> None:
    """Verify run_pipeline_self_test fails if engineered finding is not invalidated."""
    with patch(
        "devops_cli.ai.review.verification._check_verdict_polarity_hallucination",
        return_value=None,
    ):
        with pytest.raises(AssertionError, match="Pipeline self-test failed"):
            run_pipeline_self_test(tmp_path)


def test_review_profile_verdict_distributions(tmp_path: Path) -> None:
    """Verify ReviewProfile and ReviewProfiler record and persist verdict distributions."""
    profiler = ReviewProfiler()
    test_dists = {
        "status": {"VERIFIED": 2, "INVALIDATED": 1},
        "reportable": {"true": 2, "false": 1},
        "verified": {"true": 2, "false": 1},
        "mitigated": {"false": 3},
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
        loaded_profile.verdict_distributions["status"],
        loaded_profile.verdict_distributions["mitigated"],
    ) == (
        {"VERIFIED": 2, "INVALIDATED": 1},
        {"true": 2, "false": 1},
        {"VERIFIED": 2, "INVALIDATED": 1},
        {"false": 3},
    )

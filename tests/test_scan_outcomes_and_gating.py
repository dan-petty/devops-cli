"""Unit tests for scanner outcome statuses, applicability preflight, and gating enforcement."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.ai.review_schema import Finding
from devops_cli.commands.scan import app as scan_app
from devops_cli.security.base import ScanOutcome
from devops_cli.security.dive import DiveScanner
from devops_cli.security.pipeline import build_report
from devops_cli.security.popeye import PopeyeScanner

runner = CliRunner()


def test_scan_outcome_model_properties_and_equality() -> None:
    """ScanOutcome encapsulates status, findings, and reason while behaving as a list."""
    finding = Finding(
        severity="HIGH",
        location="src/auth.py:42",
        title="Hardcoded token",
        description="Found token in source",
        fix="Use environment variable",
    )
    outcome = ScanOutcome(status="ran", findings=[finding], reason="Completed scan")

    assert (outcome.status, outcome.reason, len(outcome), outcome[0].title) == (
        "ran",
        "Completed scan",
        1,
        "Hardcoded token",
    )
    assert outcome == ScanOutcome(status="ran", findings=[finding], reason="Completed scan")
    assert "ScanOutcome(status='ran'" in repr(outcome)


def test_dive_and_popeye_applicability_preflight(tmp_path: Path) -> None:
    """Dive and Popeye determine applicability before binary presence check."""
    dive = DiveScanner()
    popeye = PopeyeScanner()

    dive_dir_res = dive.is_applicable(tmp_path)
    dive_img_res = dive.is_applicable(tmp_path, image="alpine:latest")
    pop_no_ctx = popeye.is_applicable(tmp_path)
    pop_with_ctx = popeye.is_applicable(tmp_path, context="test-cluster")

    assert (
        dive_dir_res[0],
        dive_img_res,
        pop_no_ctx[0],
        pop_with_ctx,
    ) == (
        False,
        (True, ""),
        False,
        (True, ""),
    )

    with patch("devops_cli.security.base.check_binary", return_value=False):
        dive_outcome = dive.scan(tmp_path)
        popeye_outcome = popeye.scan(tmp_path)

        assert (dive_outcome.status, popeye_outcome.status) == (
            "not_applicable",
            "not_applicable",
        )


def test_single_scanner_commands_not_run_when_unavailable_or_failed(tmp_path: Path) -> None:
    """Single-scanner commands display 'not run' and never claim 'passed' when unrun."""
    unavail = ScanOutcome(
        status="unavailable",
        findings=[],
        reason="Binary 'semgrep' not found on PATH",
    )
    failed = ScanOutcome(
        status="failed",
        findings=[],
        reason="Exit 1: memory exhausted",
    )
    ran_clean = ScanOutcome(status="ran", findings=[], reason="")

    with patch("devops_cli.commands.scan.run_semgrep_scan", return_value=unavail):
        res_unavail = runner.invoke(scan_app, ["sast", str(tmp_path)])
        assert (
            res_unavail.exit_code,
            "Semgrep was not run" in res_unavail.output,
            "No static AST pattern flaws detected" in res_unavail.output,
        ) == (0, True, False)

    with patch("devops_cli.commands.scan.run_trivy_scan", return_value=failed):
        res_failed = runner.invoke(scan_app, ["trivy", str(tmp_path)])
        assert (
            res_failed.exit_code,
            "Trivy was not run (Exit 1: memory exhausted)" in res_failed.output,
        ) == (0, True)

    with patch("devops_cli.commands.scan.run_semgrep_scan", return_value=ran_clean):
        res_clean = runner.invoke(scan_app, ["sast", str(tmp_path)])
        assert (
            res_clean.exit_code,
            "No static AST pattern flaws detected" in res_clean.output,
        ) == (0, True)


def test_scan_report_gating_dive_findings(tmp_path: Path) -> None:
    """Dive container efficiency findings are non-gating and do not trip --fail-on."""
    dive_finding = Finding(
        severity="MEDIUM",
        location=f"{tmp_path}:efficiency",
        title="[DIVE:layer-inefficiency] Efficiency Score 0.85",
        description="Wasted bytes in container layers",
        fix="Combine RUN commands",
    )
    bandit_finding = Finding(
        severity="MEDIUM",
        location="app.py:10",
        title="[B101] assert used",
        description="Assert statement used in production code",
        fix="Replace with conditional",
    )

    dive_report = build_report(
        {"dive": ScanOutcome("ran", [dive_finding])},
        tmp_path,
    )
    assert (
        dive_report.findings[0].gating,
        dive_report.highest_severity(gating_only=True),
        dive_report.highest_severity(gating_only=False),
        dive_report.exceeds("LOW"),
        dive_report.exceeds("MEDIUM"),
    ) == (
        False,
        None,
        "MEDIUM",
        False,
        False,
    )

    combined_report = build_report(
        {
            "dive": ScanOutcome("ran", [dive_finding]),
            "bandit": ScanOutcome("ran", [bandit_finding]),
        },
        tmp_path,
    )
    assert (
        combined_report.highest_severity(gating_only=True),
        combined_report.exceeds("MEDIUM"),
    ) == (
        "MEDIUM",
        True,
    )


def test_scan_report_fail_on_evaluation(tmp_path: Path) -> None:
    """--fail-on triggers non-zero exit for failed scanners or missing explicit scanners."""
    mock_failed_scanner = MagicMock()
    mock_failed_scanner.name = "mock_failed"
    mock_failed_scanner.scan.return_value = ScanOutcome(
        status="failed", findings=[], reason="Process crashed"
    )

    mock_clean_scanner = MagicMock()
    mock_clean_scanner.name = "mock_clean"
    mock_clean_scanner.scan.return_value = ScanOutcome(status="ran", findings=[], reason="")

    mock_unavail_scanner = MagicMock()
    mock_unavail_scanner.name = "mock_unavail"
    mock_unavail_scanner.scan.return_value = ScanOutcome(
        status="unavailable", findings=[], reason="Binary not found"
    )

    with patch("devops_cli.commands.scan.global_scanner_registry") as mock_reg:
        mock_reg.list_scanners.return_value = ["mock_failed"]
        mock_reg.get.side_effect = lambda name: (
            mock_failed_scanner if name == "mock_failed" else None
        )

        res_fail = runner.invoke(scan_app, ["report", str(tmp_path), "--fail-on", "LOW"])
        assert (
            res_fail.exit_code,
            "Scanner(s) failed during execution: mock_failed" in res_fail.output,
        ) == (1, True)

    with patch("devops_cli.commands.scan.global_scanner_registry") as mock_reg:
        mock_reg.list_scanners.return_value = ["mock_clean", "mock_unavail"]
        mock_reg.get.side_effect = lambda name: {
            "mock_clean": mock_clean_scanner,
            "mock_unavail": mock_unavail_scanner,
        }.get(name)

        # Explicitly requesting an unavailable scanner with --fail-on must exit 1
        res_explicit = runner.invoke(
            scan_app,
            ["report", str(tmp_path), "--scanner", "mock_unavail", "--fail-on", "LOW"],
        )
        assert (
            res_explicit.exit_code,
            "Requested scanner(s) did not run: mock_unavail" in res_explicit.output,
        ) == (1, True)

        # Default run with optional missing scanner exits 0 and warns
        res_default = runner.invoke(
            scan_app,
            ["report", str(tmp_path), "--fail-on", "LOW"],
        )
        assert (
            res_default.exit_code,
            "Scanner 'mock_unavail' was not run" in res_default.output,
        ) == (0, True)

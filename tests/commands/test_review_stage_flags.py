"""Unit tests for review pipeline stage feature flags and resolution logic."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review.flags import ReviewStageFlags, resolve_stage_flags

pytestmark = [pytest.mark.usefixtures("keyring_store", "scanner_fake")]


def test_review_stage_flags_defaults() -> None:
    """Verify default ReviewStageFlags has all stages enabled."""
    flags = ReviewStageFlags()
    assert flags.pre_analysis is True
    assert flags.static_scan is True
    assert flags.group_analysis is True
    assert flags.reporting is True
    assert flags.any_enabled() is True
    assert flags.to_dict() == {
        "pre_analysis": True,
        "static_scan": True,
        "group_analysis": True,
        "reporting": True,
    }


def test_review_stage_flags_needs_model() -> None:
    """Verify needs_model() returns True if and only if group_analysis is True."""
    assert ReviewStageFlags(group_analysis=True).needs_model() is True
    assert ReviewStageFlags(group_analysis=False).needs_model() is False


def test_resolve_stage_flags_no_group_analysis() -> None:
    """Verify resolve_stage_flags with no_group_analysis=True."""
    flags = resolve_stage_flags(no_group_analysis=True)
    assert flags.group_analysis is False
    assert flags.needs_model() is False


def test_resolve_stage_flags_no_static_and_no_group_analysis() -> None:
    """Verify resolve_stage_flags with no_static_scan=True and no_group_analysis=True."""
    flags = resolve_stage_flags(no_static_scan=True, no_group_analysis=True)
    assert flags.static_scan is False
    assert flags.group_analysis is False
    assert flags.needs_model() is False


def test_resolve_stage_flags_no_options() -> None:
    """Verify default resolution enables all stages."""
    flags = resolve_stage_flags()
    assert flags == ReviewStageFlags()


def test_resolve_stage_flags_no_flags() -> None:
    """Verify --no-<stage> disables individual stages."""
    flags = resolve_stage_flags(
        no_pre_analysis=True,
        no_reporting=True,
    )
    assert flags.pre_analysis is False
    assert flags.static_scan is True
    assert flags.group_analysis is True
    assert flags.reporting is False


def test_resolve_stage_flags_only_flags() -> None:
    """Verify --<stage>-only enables only that stage and disables all others."""
    flags = resolve_stage_flags(static_scan_only=True)
    assert flags.pre_analysis is False
    assert flags.static_scan is True
    assert flags.group_analysis is False
    assert flags.reporting is False


def test_resolve_stage_flags_multiple_only_flags() -> None:
    """Verify multiple --<stage>-only flags enable the specified union of stages."""
    flags = resolve_stage_flags(
        static_scan_only=True,
        reporting_only=True,
    )
    assert flags.pre_analysis is False
    assert flags.static_scan is True
    assert flags.group_analysis is False
    assert flags.reporting is True


def test_resolve_stage_flags_conflicting_no_and_only() -> None:
    """Verify --no-<stage> takes precedence over --<stage>-only if both are passed for the same stage."""
    flags = resolve_stage_flags(
        static_scan_only=True,
        no_static_scan=True,
    )
    assert flags.static_scan is False
    assert flags.any_enabled() is False


def test_review_cli_stage_flags_propagation(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Verify CLI review commands pass resolved stage flags to workflow."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    file_path = tmp_path / "app.py"
    file_path.write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    result = cli("review", "path", str(file_path), "--no-pre-analysis", "--static-scan-only")
    assert result.exit_code == 0
    assert "pre-analysis metadata scan skipped" in result.output.lower()


def test_review_cli_no_group_analysis_propagation(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Verify CLI review commands pass --no-group-analysis flag to workflow."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    file_path = tmp_path / "app.py"
    file_path.write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    result = cli("review", "path", str(file_path), "--no-group-analysis", "--no-static-scan")
    assert result.exit_code == 0
    assert "without a model" in result.output


def test_orchestrator_stage_bypasses(tmp_path) -> None:
    """Verify ReviewPipelineOrchestrator respects stage flags and skips execution."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator

    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-flags-session",
        session_dir=tmp_path / "session",
        target_dir=tmp_path,
    )

    # 1. Skip pre-analysis
    flags_no_pre = ReviewStageFlags(pre_analysis=False)
    meta = orchestrator.run_pre_analysis_refresh(
        files=["main.py"],
        stage_flags=flags_no_pre,
    )
    assert meta == {}

    # 2. Skip static scanning in init_per_file_payloads
    test_file = tmp_path / "main.py"
    test_file.write_text("print('hello')\n")
    flags_no_static = ReviewStageFlags(static_scan=False)
    payloads = orchestrator.init_per_file_payloads(
        [str(test_file)],
        {},
        stage_flags=flags_no_static,
    )
    assert len(payloads) == 1
    assert payloads[0].findings == []

    # 3. Skip reporting
    flags_no_report = ReviewStageFlags(reporting=False)
    report_dict, report_md = orchestrator.generate_consolidated_report(
        payloads,
        stage_flags=flags_no_report,
    )
    assert report_dict == {}
    assert report_md == ""

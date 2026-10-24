"""Tests for Go static security analysis in review pipeline (#603)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review.pipeline import (
    _STATIC_ANALYZERS,
    ANALYZER_FAILED,
    ANALYZER_NOT_INSTALLED,
    ANALYZER_RAN,
    ReviewPipelineOrchestrator,
    _classify_scanner_files,
    _match_static_findings_to_files,
    _static_analyzer_states,
    _write_base_revision_lockfiles,
)
from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.config.commands import BIN_GOLANGCI_LINT
from devops_cli.security.base import ScanOutcome


def test_static_analyzers_contains_golangci_lint() -> None:
    """_STATIC_ANALYZERS includes golangci-lint with kind 'go'."""
    names = {name: (bin_name, kind) for name, bin_name, kind in _STATIC_ANALYZERS}
    assert "golangci-lint" in names
    assert names["golangci-lint"] == (BIN_GOLANGCI_LINT, "go")


def test_classify_scanner_files_classifies_go_files(tmp_path: Path) -> None:
    """_classify_scanner_files puts .go files into buckets.go and as_kind_map."""
    go_file = tmp_path / "main.go"
    py_file = tmp_path / "app.py"
    go_file.write_text("package main\n", encoding="utf-8")
    py_file.write_text("print(1)\n", encoding="utf-8")

    buckets = _classify_scanner_files([go_file, py_file])
    assert go_file in buckets.go
    assert py_file not in buckets.go
    assert buckets.as_kind_map()["go"] == buckets.go


def test_match_static_findings_to_files_filters_go_findings() -> None:
    """Findings are mapped to reviewed files and unreviewed files are filtered."""
    f1 = SavedFinding(
        severity="HIGH",
        location="pkg/handler/handler.go:20",
        title="[govet] error",
        description="error in handler",
        fix="fix handler",
    )
    f2 = SavedFinding(
        severity="HIGH",
        location="pkg/other/unreviewed.go:10",
        title="[errcheck] unchecked error",
        description="error in unreviewed",
        fix="fix unreviewed",
    )

    reviewed_files = ["pkg/handler/handler.go"]
    matched = _match_static_findings_to_files([f1, f2], reviewed_files)
    assert "pkg/handler/handler.go" in matched
    assert len(matched["pkg/handler/handler.go"]) == 1
    assert "pkg/other/unreviewed.go" not in matched


def test_write_base_revision_lockfiles_preserves_gomod(tmp_path: Path) -> None:
    """_write_base_revision_lockfiles copies go.mod for base revision Go files."""
    base_rev = MagicMock()

    def fake_read(rel_path: str) -> str | None:
        if rel_path == "go.mod":
            return "module example.com/repo\ngo 1.23\n"
        return None

    base_rev.read.side_effect = fake_read

    written_paths = ["pkg/server/server.go"]
    extra = _write_base_revision_lockfiles(base_rev, tmp_path, written_paths)
    assert "go.mod" in extra
    assert (tmp_path / "go.mod").is_file()
    assert "example.com/repo" in (tmp_path / "go.mod").read_text(encoding="utf-8")


def test_static_analyzer_states_for_golangci_lint() -> None:
    """_static_analyzer_states maps observed outcomes for golangci-lint."""
    go_path = Path("main.go")
    files_by_kind = {"go": [go_path]}

    outcomes_ran = {"golangci-lint": ScanOutcome("ran", [])}
    states_ran = _static_analyzer_states(files_by_kind, outcomes_ran)
    assert states_ran["golangci-lint"] == ANALYZER_RAN

    outcomes_failed = {"golangci-lint": ScanOutcome("failed", [], "typecheck error")}
    states_failed = _static_analyzer_states(files_by_kind, outcomes_failed)
    assert states_failed["golangci-lint"] == ANALYZER_FAILED

    outcomes_unavail = {
        "golangci-lint": ScanOutcome("unavailable", [], "Binary 'golangci-lint' not found")
    }
    states_unavail = _static_analyzer_states(files_by_kind, outcomes_unavail)
    assert states_unavail["golangci-lint"] == ANALYZER_NOT_INSTALLED


def test_run_static_scanners_executes_golangci_lint_for_go_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_run_static_scanners runs golangci-lint on go.mod root and filters findings."""
    (tmp_path / "go.mod").write_text("module example.com/test\ngo 1.23\n", encoding="utf-8")
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    go_file = pkg_dir / "worker.go"
    go_file.write_text("package pkg\n", encoding="utf-8")

    monkeypatch.setattr("devops_cli.ai.review.pipeline._scan_secrets", lambda *_, **__: [])
    monkeypatch.setattr("devops_cli.ai.review.pipeline._scan_semgrep", lambda *_, **__: [])

    orchestrator = ReviewPipelineOrchestrator(session_id="test-go", target_dir=tmp_path)

    fake_finding = Finding(
        severity="HIGH",
        location="pkg/worker.go:1",
        title="[govet] error",
        description="lost cancel",
        fix="call cancel",
    )
    fake_outcome = ScanOutcome("ran", [fake_finding])

    with patch(
        "devops_cli.security.golangci_lint.GolangciLintScanner.scan",
        return_value=fake_outcome,
    ) as mock_scan:
        findings_by_file = orchestrator._run_static_scanners(["pkg/worker.go"])
        assert mock_scan.called
        assert "pkg/worker.go" in findings_by_file
        assert len(findings_by_file["pkg/worker.go"]) == 1
        assert findings_by_file["pkg/worker.go"][0].title == "[govet] error"

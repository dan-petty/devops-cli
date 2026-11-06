"""Tests for Go static security analysis in review pipeline (#603)."""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.ai.analyze.symbols import BaseRevision
from devops_cli.ai.review.pipeline import (
    ANALYZER_FAILED,
    ANALYZER_NOT_INSTALLED,
    ANALYZER_RAN,
    STATIC_ANALYZERS,
    ReviewPipelineOrchestrator,
    classify_scanner_files,
    match_static_findings_to_files,
    static_analyzer_states,
    write_base_revision_lockfiles,
)
from devops_cli.ai.review_schema import SavedFinding
from devops_cli.config.commands import BIN_GOLANGCI_LINT
from devops_cli.security.base import ScanOutcome
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer


def test_static_analyzers_contains_golangci_lint() -> None:
    """STATIC_ANALYZERS includes golangci-lint with kind 'go'."""
    names = {name: (bin_name, kind) for name, bin_name, kind in STATIC_ANALYZERS}
    assert "golangci-lint" in names
    assert names["golangci-lint"] == (BIN_GOLANGCI_LINT, "go")


def test_classify_scanner_files_classifies_go_files(tmp_path: Path) -> None:
    """classify_scanner_files puts .go files into buckets.go and as_kind_map."""
    go_file = tmp_path / "main.go"
    py_file = tmp_path / "app.py"
    go_file.write_text("package main\n", encoding="utf-8")
    py_file.write_text("print(1)\n", encoding="utf-8")

    buckets = classify_scanner_files([go_file, py_file])
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
    matched = match_static_findings_to_files([f1, f2], reviewed_files)
    assert "pkg/handler/handler.go" in matched
    assert len(matched["pkg/handler/handler.go"]) == 1
    assert "pkg/other/unreviewed.go" not in matched


def test_write_base_revision_lockfiles_preserves_gomod(tmp_path: Path) -> None:
    """write_base_revision_lockfiles copies go.mod for base revision Go files."""

    def fake_read(rel_path: str) -> str | None:
        if rel_path == "go.mod":
            return "module example.com/repo\ngo 1.23\n"
        return None

    base_rev = BaseRevision(changes=(), read=fake_read)

    written_paths = ["pkg/server/server.go"]
    extra = write_base_revision_lockfiles(base_rev, tmp_path, written_paths)
    assert "go.mod" in extra
    assert (tmp_path / "go.mod").is_file()
    assert "example.com/repo" in (tmp_path / "go.mod").read_text(encoding="utf-8")


def test_static_analyzer_states_for_golangci_lint() -> None:
    """static_analyzer_states maps observed outcomes for golangci-lint."""
    go_path = Path("main.go")
    files_by_kind = {"go": [go_path]}

    outcomes_ran = {"golangci-lint": ScanOutcome("ran", [])}
    states_ran = static_analyzer_states(files_by_kind, outcomes_ran)
    assert states_ran["golangci-lint"] == ANALYZER_RAN

    outcomes_failed = {"golangci-lint": ScanOutcome("failed", [], "typecheck error")}
    states_failed = static_analyzer_states(files_by_kind, outcomes_failed)
    assert states_failed["golangci-lint"] == ANALYZER_FAILED

    outcomes_unavail = {
        "golangci-lint": ScanOutcome("unavailable", [], "Binary 'golangci-lint' not found")
    }
    states_unavail = static_analyzer_states(files_by_kind, outcomes_unavail)
    assert states_unavail["golangci-lint"] == ANALYZER_NOT_INSTALLED


def test_run_static_scanners_executes_golangci_lint_for_go_files(
    tmp_path: Path,
    scanner_fake: ScannerFake,
    process_fake: ProcessFake,
) -> None:
    """_run_static_scanners runs golangci-lint on go.mod root and filters findings."""
    (tmp_path / "go.mod").write_text("module example.com/test\ngo 1.23\n", encoding="utf-8")
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    go_file = pkg_dir / "worker.go"
    go_file.write_text("package pkg\n", encoding="utf-8")
    (tmp_path / "goroot" / "bin").mkdir(parents=True)
    (tmp_path / "gomodcache").mkdir()
    process_fake.answer(
        lambda call: Path(call.argv[0]).name == "go" and call.argv[1:2] == ("env",),
        ProcessAnswer(
            stdout=json.dumps(
                {"GOROOT": str(tmp_path / "goroot"), "GOMODCACHE": str(tmp_path / "gomodcache")}
            )
        ),
    )
    report = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "golangci-lint"}},
                "results": [
                    {
                        "ruleId": "govet",
                        "level": "error",
                        "message": {"text": "lost cancel"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "pkg/worker.go"},
                                    "region": {"startLine": 1},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    scanner_fake.script(BIN_GOLANGCI_LINT, ToolAnswer(stdout=json.dumps(report)))
    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-go", target_dir=tmp_path, tool_executor=scanner_fake
    )

    findings_by_file = orchestrator._run_static_scanners(["pkg/worker.go"])

    assert [f.title for f in findings_by_file["pkg/worker.go"]] == ["[govet] lost cancel"]

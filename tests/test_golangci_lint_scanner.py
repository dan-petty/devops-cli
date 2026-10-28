"""Unit tests for GolangciLintScanner integration (#603)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.security.base import ScanOutcome
from devops_cli.security.golangci_lint import (
    DEFAULT_LINTERS,
    OPTIONAL_LINTERS,
    GolangciLintScanner,
)
from devops_cli.security.registry import ScannerRegistry


def test_golangci_lint_scanner_registered_in_registry() -> None:
    """GolangciLintScanner exists in security.registry and is in default registry."""
    from devops_cli.security.registry import GolangciLintScanner as RegistryScanner

    assert RegistryScanner is GolangciLintScanner

    registry = ScannerRegistry(auto_load_defaults=True)
    scanner = registry.get("golangci-lint")
    assert scanner is not None
    assert isinstance(scanner, GolangciLintScanner)
    assert "golangci-lint" in registry.list_scanners()


def test_golangci_lint_default_linters_and_ordering() -> None:
    """Default linters are errcheck, govet, and staticcheck in that order."""
    assert DEFAULT_LINTERS == ("errcheck", "govet", "staticcheck")
    assert OPTIONAL_LINTERS == ("contextcheck",)

    scanner = GolangciLintScanner()
    assert scanner.linters == ["errcheck", "govet", "staticcheck"]
    assert tuple(scanner.DEFAULT_LINTERS) == ("errcheck", "govet", "staticcheck")
    assert tuple(scanner.OPTIONAL_LINTERS) == ("contextcheck",)


def test_golangci_lint_contextcheck_optional() -> None:
    """contextcheck is properly configured as opt-in."""
    scanner_default = GolangciLintScanner()
    assert "contextcheck" not in scanner_default.linters

    scanner_opt_in = GolangciLintScanner(enable_contextcheck=True)
    assert "contextcheck" in scanner_opt_in.linters
    assert scanner_opt_in.linters == ["errcheck", "govet", "staticcheck", "contextcheck"]


def test_golangci_lint_build_command() -> None:
    """build_command constructs the argument list with SARIF output and enabled linters."""
    scanner = GolangciLintScanner()
    cmd = scanner.build_command(Path("."))
    assert cmd[:3] == ["golangci-lint", "run", "--out-format"]
    assert cmd[3] == "sarif"
    assert "--disable-all" in cmd

    enable_indices = [i for i, arg in enumerate(cmd) if arg == "--enable"]
    enabled = [cmd[i + 1] for i in enable_indices]
    assert enabled == ["errcheck", "govet", "staticcheck"]


def test_golangci_lint_build_command_with_contextcheck() -> None:
    """build_command includes contextcheck when enabled."""
    scanner = GolangciLintScanner(enable_contextcheck=True)
    cmd = scanner.build_command(Path("."))
    enable_indices = [i for i, arg in enumerate(cmd) if arg == "--enable"]
    enabled = [cmd[i + 1] for i in enable_indices]
    assert enabled == ["errcheck", "govet", "staticcheck", "contextcheck"]


def test_golangci_lint_sarif_output_conversion() -> None:
    """SARIF output is parsed into Finding models using from_sarif and to_finding."""
    sample_sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "golangci-lint",
                        "version": "1.64.6",
                        "rules": [
                            {
                                "id": "govet",
                                "shortDescription": {"text": "govet analysis issue"},
                                "properties": {"security-severity": "7.5"},
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "govet",
                        "level": "error",
                        "message": {"text": "cancel function not called on all paths"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "pkg/worker/worker.go"},
                                    "region": {"startLine": 42},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }

    scanner = GolangciLintScanner()
    findings = scanner.parse_output(sample_sarif, Path("."))
    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, Finding)
    assert finding.location == "pkg/worker/worker.go:42"
    assert "cancel function not called" in finding.title
    assert finding.severity == "HIGH"


def test_golangci_lint_missing_binary_records_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing golangci-lint binary records unavailable state."""
    (tmp_path / "go.mod").write_text("module example.com/test\ngo 1.23\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    outcome = GolangciLintScanner().scan(tmp_path)

    assert isinstance(outcome, ScanOutcome)
    assert outcome.status == "unavailable"
    assert outcome.findings == []
    assert "golangci-lint" in outcome.reason


def test_golangci_lint_missing_go_records_failed(tmp_path: Path) -> None:
    """Missing go toolchain records failed state, never zero findings."""
    (tmp_path / "go.mod").write_text("module example.com/test\ngo 1.23\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")

    scanner = GolangciLintScanner()

    def fake_check_binary(name: str) -> bool:
        return name != "go"

    with patch("devops_cli.security.golangci_lint.check_binary", side_effect=fake_check_binary):
        outcome = scanner.scan(tmp_path)

    assert isinstance(outcome, ScanOutcome)
    assert outcome.status == "failed"
    assert outcome.findings == []
    assert "go" in outcome.reason


def test_golangci_lint_typecheck_failure_records_failed(tmp_path: Path) -> None:
    """Typecheck or package loading error records failed state."""
    (tmp_path / "go.mod").write_text("module example.com/test\ngo 1.23\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")

    fake_proc = MagicMock()
    fake_proc.returncode = 1
    fake_proc.stdout = ""
    fake_proc.stderr = "typechecking error: expected declaration, found 'EOF'"

    scanner = GolangciLintScanner()
    with (
        patch("devops_cli.security.golangci_lint.check_binary", return_value=True),
        patch.object(scanner, "_check_binary", return_value=True),
        patch.object(scanner, "_run_tool", return_value=fake_proc),
    ):
        outcome = scanner.scan(tmp_path)

    assert isinstance(outcome, ScanOutcome)
    assert outcome.status == "failed"
    assert outcome.findings == []
    assert "typechecking error" in outcome.reason


def test_golangci_lint_is_applicable(tmp_path: Path) -> None:
    """Scanner is applicable only when Go files or go.mod exist."""
    scanner = GolangciLintScanner()
    app, reason = scanner.is_applicable(tmp_path)
    assert not app
    assert "No Go source files" in reason

    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")
    app2, reason2 = scanner.is_applicable(tmp_path)
    assert app2
    assert reason2 == ""

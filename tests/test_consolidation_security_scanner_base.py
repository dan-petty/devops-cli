"""Test suite for declarative BaseSecurityScanner and ScannerRegistry."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from devops_cli.ai.review_schema import Finding
from devops_cli.security.base import BaseSecurityScanner
from devops_cli.security.registry import ScannerRegistry


class MockDummyScanner(BaseSecurityScanner):
    """Test scanner implementation."""

    name = "mock_tool"
    binary_name = "mock-tool-bin"

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        return [self.binary_name, "--target", str(target_path)]

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        if not isinstance(data, list):
            return []
        findings: list[Finding] = []
        for item in data:
            findings.append(
                Finding(
                    severity=item.get("sev", "LOW"),
                    location=f"{target_path.name}:{item.get('line', 1)}",
                    title=item.get("title", "Issue"),
                    description=item.get("desc", "Description"),
                    fix="Fix it",
                )
            )
        return findings

    def fallback_scan(self, target_path: Path) -> list[Finding]:
        return [
            Finding(
                severity="INFO",
                location=f"{target_path.name}:1",
                title="Fallback finding",
                description="Triggered fallback",
                fix="Install mock tool",
            )
        ]


def test_scanner_executes_successfully(tmp_path: Path) -> None:
    """When binary is available, scanner runs subprocess and parses output."""
    scanner = MockDummyScanner()
    fake_data = [{"sev": "HIGH", "line": 42, "title": "Critical flaw", "desc": "Buffer overflow"}]

    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch("devops_cli.security.base.run_json_subprocess", return_value=fake_data),
    ):
        findings = scanner.scan(tmp_path)
        assert len(findings) == 1
        assert findings[0].severity == "HIGH"
        assert "42" in findings[0].location
        assert findings[0].title == "Critical flaw"


def test_scanner_falls_back_when_binary_missing(tmp_path: Path) -> None:
    """When binary is not found, executes fallback scan."""
    scanner = MockDummyScanner()

    with patch("devops_cli.security.base.check_binary", return_value=False):
        findings = scanner.scan(tmp_path)
        assert len(findings) == 1
        assert findings[0].title == "Fallback finding"


def test_scanner_falls_back_on_subprocess_error(tmp_path: Path) -> None:
    """When subprocess fails, catches exception and runs fallback."""
    scanner = MockDummyScanner()

    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch(
            "devops_cli.security.base.run_json_subprocess",
            side_effect=RuntimeError("Process execution failed"),
        ),
    ):
        findings = scanner.scan(tmp_path)
        assert len(findings) == 1
        assert findings[0].title == "Fallback finding"


def test_scanner_registry_lifecycle(tmp_path: Path) -> None:
    """Registry correctly registers, retrieves, lists, and executes batch scans."""
    registry = ScannerRegistry()
    scanner = MockDummyScanner()

    registry.register(scanner)
    assert registry.get("mock_tool") is scanner
    assert "mock_tool" in registry.list_scanners()

    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch("devops_cli.security.base.run_json_subprocess", return_value=[]),
    ):
        results = registry.scan_all(tmp_path)
        assert "mock_tool" in results
        assert results["mock_tool"] == []

    # Scanner raises exception in scan_all
    with patch.object(scanner, "scan", side_effect=RuntimeError("Scanner crashed")):
        err_results = registry.scan_all(tmp_path)
        assert err_results["mock_tool"] == []

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


ALL_EXPECTED_SCANNER_NAMES = [
    "bandit",
    "checkov",
    "dive",
    "gitleaks",
    "kubeconform",
    "kubelinter",
    "pluto",
    "popeye",
    "semgrep",
    "tflint",
    "trivy",
]


def test_all_11_scanners_registered_in_global_registry() -> None:
    """Verify 100% of all 11 security scanners are registered in global_scanner_registry."""
    from devops_cli.security.registry import global_scanner_registry

    registered = global_scanner_registry.list_scanners()
    for name in ALL_EXPECTED_SCANNER_NAMES:
        assert name in registered, f"Scanner '{name}' is not registered in global_scanner_registry"
        scanner = global_scanner_registry.get(name)
        assert scanner is not None
        assert isinstance(scanner, BaseSecurityScanner)
        assert scanner.name == name
        assert scanner.binary_name != ""


def test_all_11_scanner_classes_inherit_base_security_scanner() -> None:
    """Verify each of the 11 scanner classes subclasses BaseSecurityScanner."""
    from devops_cli.security import (
        BanditScanner,
        CheckovScanner,
        DiveScanner,
        GitleaksScanner,
        KubeconformScanner,
        KubelinterScanner,
        PlutoScanner,
        PopeyeScanner,
        SemgrepScanner,
        TflintScanner,
        TrivyScanner,
    )

    classes = [
        BanditScanner,
        CheckovScanner,
        DiveScanner,
        GitleaksScanner,
        KubeconformScanner,
        KubelinterScanner,
        PlutoScanner,
        PopeyeScanner,
        SemgrepScanner,
        TflintScanner,
        TrivyScanner,
    ]
    for cls in classes:
        assert issubclass(cls, BaseSecurityScanner)
        instance = cls()
        assert instance.name != ""
        assert instance.binary_name != ""


def test_scanner_dry_run_simulation(tmp_path: Path) -> None:
    """Verify scanners handle dry-run execution by returning simulated findings without subprocess."""
    from devops_cli.security import (
        BanditScanner,
        GitleaksScanner,
        KubelinterScanner,
        PlutoScanner,
        PopeyeScanner,
        SemgrepScanner,
        TrivyScanner,
    )

    test_file = tmp_path / "app.py"
    test_file.write_text("import os\n", encoding="utf-8")

    dry_run_scanners = [
        BanditScanner(),
        GitleaksScanner(),
        KubelinterScanner(),
        PlutoScanner(),
        PopeyeScanner(),
        SemgrepScanner(),
        TrivyScanner(),
    ]

    with patch("devops_cli.dry_run.state.is_dry_run", return_value=True):
        for scanner in dry_run_scanners:
            findings = scanner.scan(test_file)
            assert isinstance(findings, list)
            assert len(findings) >= 1
            assert any(
                "DRY-RUN" in f.title.upper() or "SIMULATED" in f.title.upper() for f in findings
            )


def test_scanner_fallback_when_binary_unavailable(tmp_path: Path) -> None:
    """Verify all 11 scanners gracefully execute fallback when their external binary is missing."""
    from devops_cli.security.registry import global_scanner_registry

    test_file = tmp_path / "test.yaml"
    test_file.write_text("apiVersion: v1\nkind: Pod\n", encoding="utf-8")

    with patch("devops_cli.security.base.check_binary", return_value=False):
        for name in ALL_EXPECTED_SCANNER_NAMES:
            scanner = global_scanner_registry.get(name)
            assert scanner is not None
            findings = scanner.scan(test_file)
            assert isinstance(findings, list)

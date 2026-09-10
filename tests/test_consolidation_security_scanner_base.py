"""Test suite for declarative BaseSecurityScanner and ScannerRegistry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.security.base import BaseSecurityScanner
from devops_cli.security.registry import ScannerRegistry, global_scanner_registry


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
    mock_proc = MagicMock(returncode=0, stdout=json.dumps(fake_data), stderr="")

    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch("devops_cli.security.base.run_subprocess", return_value=mock_proc),
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
            "devops_cli.security.base.run_subprocess",
            side_effect=RuntimeError("Process execution failed"),
        ),
    ):
        findings = scanner.scan(tmp_path)
        assert len(findings) == 1
        assert findings[0].title == "Fallback finding"


def test_scanner_falls_back_on_nonzero_exit_with_malformed_output(tmp_path: Path) -> None:
    """When process returns non-zero exit code with malformed output, trigger fallback."""
    scanner = MockDummyScanner()
    mock_proc = MagicMock(returncode=1, stdout="Fatal Error: corrupted config", stderr="fatal")

    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch("devops_cli.security.base.run_subprocess", return_value=mock_proc),
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

    mock_proc = MagicMock(returncode=0, stdout="[]", stderr="")
    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch("devops_cli.security.base.run_subprocess", return_value=mock_proc),
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
        instance = cls()  # type: ignore[abstract]
        assert instance.name != ""
        assert instance.binary_name != ""


def test_all_11_scanners_dry_run_simulation(tmp_path: Path) -> None:
    """Verify all 11 scanners handle dry-run execution by returning simulated findings."""
    test_file = tmp_path / "app.py"
    test_file.write_text("import os\n", encoding="utf-8")

    with patch("devops_cli.dry_run.state.is_dry_run", return_value=True):
        for name in ALL_EXPECTED_SCANNER_NAMES:
            scanner = global_scanner_registry.get(name)
            assert scanner is not None
            findings = scanner.scan(test_file)
            assert isinstance(findings, list)
            assert len(findings) >= 1
            assert any(
                "DRY-RUN" in f.title.upper() or "SIMULATED" in f.title.upper() for f in findings
            )


def test_scanner_fallback_when_binary_unavailable(tmp_path: Path) -> None:
    """Verify all 11 scanners gracefully execute fallback when their external binary is missing."""
    test_file = tmp_path / "test.yaml"
    test_file.write_text("apiVersion: v1\nkind: Pod\n", encoding="utf-8")

    with patch("devops_cli.security.base.check_binary", return_value=False):
        for name in ALL_EXPECTED_SCANNER_NAMES:
            scanner = global_scanner_registry.get(name)
            assert scanner is not None
            findings = scanner.scan(test_file)
            assert isinstance(findings, list)


_SAMPLE_STDOUTS: dict[str, str] = {
    "bandit": json.dumps(
        {
            "results": [
                {
                    "test_id": "B101",
                    "filename": "app.py",
                    "line_number": 10,
                    "issue_severity": "HIGH",
                    "issue_text": "assert used",
                    "more_info": "",
                }
            ]
        }
    ),
    "checkov": json.dumps(
        {
            "results": {
                "failed_checks": [
                    {
                        "check_id": "CKV_DOCKER_1",
                        "file_path": "/Dockerfile",
                        "file_line_range": [1, 2],
                        "check_name": "Root user",
                        "severity": "HIGH",
                        "guideline": "Use non-root",
                    }
                ]
            }
        }
    ),
    "dive": json.dumps(
        {
            "image": {
                "efficiencyScore": 0.80,
                "wastedBytes": 60000000,
                "sizeBytes": 200000000,
            }
        }
    ),
    "gitleaks": json.dumps(
        [
            {
                "RuleID": "generic-api-key",
                "File": "secret.py",
                "StartLine": 5,
                "Secret": "abc",
                "Description": "Secret leaked",
            }
        ]
    ),
    "kubeconform": (
        '{"filename": "pod.yaml", "status": "Invalid", "msg": "schema error"}\n'
        '{"filename": "svc.yaml", "status": "Invalid", "msg": "port error"}\n'
    ),
    "kubelinter": json.dumps(
        {
            "Reports": [
                {
                    "Check": "no-read-only-root-fs",
                    "Object": {"K8sObject": {"GroupVersionKind": {"Kind": "Deployment"}}},
                    "Diagnostic": {"Message": "Root filesystem writeable"},
                }
            ],
            "Summary": {},
        }
    ),
    "pluto": json.dumps(
        {
            "items": [
                {
                    "name": "deprecated-deploy",
                    "namespace": "default",
                    "api": {"version": "extensions/v1beta1", "kind": "Deployment"},
                    "deprecated": True,
                    "deprecated_in": "v1.16.0",
                    "removed": True,
                    "removed_in": "v1.22.0",
                    "replacement": "apps/v1",
                }
            ]
        }
    ),
    "popeye": json.dumps(
        {
            "popeye": {
                "sanitizers": [
                    {
                        "sanitizer": "deployment",
                        "issues": {
                            "default/web": [
                                {
                                    "group": "__root__",
                                    "gvr": "apps/v1/deployments",
                                    "level": 2,
                                    "message": "Container has no resource limits",
                                }
                            ]
                        },
                    }
                ]
            }
        }
    ),
    "semgrep": json.dumps(
        {
            "results": [
                {
                    "check_id": "rules.exec",
                    "path": "test.py",
                    "start": {"line": 15},
                    "end": {"line": 15},
                    "extra": {"message": "Dynamic code execution", "severity": "ERROR"},
                }
            ]
        }
    ),
    "tflint": json.dumps(
        {
            "issues": [
                {
                    "rule": {"name": "terraform_deprecated_syntax"},
                    "message": "Deprecated syntax",
                    "range": {"filename": "main.tf", "start": {"line": 20}},
                    "call": None,
                }
            ]
        }
    ),
    "trivy": json.dumps(
        {
            "Results": [
                {
                    "Target": "Dockerfile",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2023-1234",
                            "PkgName": "curl",
                            "InstalledVersion": "7.68.0",
                            "Severity": "CRITICAL",
                            "Title": "Curl buffer overflow",
                        }
                    ],
                }
            ]
        }
    ),
}


@pytest.mark.parametrize("scanner_name", ALL_EXPECTED_SCANNER_NAMES)
def test_scanner_contract_execution_and_parsing(scanner_name: str, tmp_path: Path) -> None:
    """Verify binary-present contract execution and output parsing for all 11 adapters."""
    scanner = global_scanner_registry.get(scanner_name)
    assert scanner is not None

    test_file = tmp_path / "test_target.py"
    test_file.write_text("content = True\n", encoding="utf-8")

    sample_stdout = _SAMPLE_STDOUTS.get(scanner_name, "[]")
    mock_proc = MagicMock(returncode=0, stdout=sample_stdout, stderr="")

    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch("devops_cli.security.base.run_subprocess", return_value=mock_proc),
    ):
        findings = scanner.scan(test_file, image="ubuntu:latest")
        assert isinstance(findings, list)
        assert len(findings) >= 1, (
            f"Scanner '{scanner_name}' failed to produce normalized findings from sample output"
        )


def test_kubeconform_ndjson_preserves_multiple_records(tmp_path: Path) -> None:
    """Verify Kubeconform NDJSON multi-line stream output parses all records without loss."""
    scanner = global_scanner_registry.get("kubeconform")
    assert scanner is not None

    test_manifest = tmp_path / "manifest.yaml"
    test_manifest.write_text("apiVersion: v1\nkind: Pod\n", encoding="utf-8")

    ndjson_stdout = (
        '{"filename": "pod1.yaml", "status": "Invalid", "msg": "spec missing"}\n'
        '{"filename": "pod2.yaml", "status": "Invalid", "msg": "port invalid"}\n'
    )
    mock_proc = MagicMock(returncode=0, stdout=ndjson_stdout, stderr="")

    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch("devops_cli.security.base.run_subprocess", return_value=mock_proc),
    ):
        findings = scanner.scan(test_manifest)
        assert len(findings) == 2
        assert any("pod1.yaml" in f.location for f in findings)
        assert any("pod2.yaml" in f.location for f in findings)


def test_dive_scanner_skips_directory_without_image(tmp_path: Path) -> None:
    """Verify Dive scanner skips filesystem directories when no image is specified."""
    scanner = global_scanner_registry.get("dive")
    assert scanner is not None

    dir_path = tmp_path / "my_project"
    dir_path.mkdir()

    with patch("devops_cli.security.base.check_binary", return_value=True):
        findings = scanner.scan(dir_path)
        assert findings == []

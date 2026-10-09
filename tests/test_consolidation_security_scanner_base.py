"""Test suite for declarative BaseSecurityScanner and ScannerRegistry."""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_SCANNER_STDOUT_EXCERPT_CHARS,
)
from devops_cli.security.base import BaseSecurityScanner, materialize_targets
from devops_cli.security.dive import DiveAnalysisResult
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


class _NoPatternsScanner(BaseSecurityScanner):
    """A scanner with no built-in patterns, so a failed run is reported as failed."""

    name = "no_patterns_tool"
    binary_name = "no-patterns-bin"

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        return [self.binary_name, str(target_path)]

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        return []


def _failed_reason(tmp_path: Path, stdout: str, stderr: str) -> tuple[str, str]:
    """Run _NoPatternsScanner on output exiting 1, returning the outcome's status and reason."""
    proc = MagicMock(returncode=1, stdout=stdout, stderr=stderr)
    with patch("devops_cli.security.base.run_subprocess", return_value=proc):
        outcome = _NoPatternsScanner().scan(tmp_path)
    return outcome.status, outcome.reason


def test_a_failed_scan_says_its_output_was_not_json_and_quotes_it(tmp_path: Path) -> None:
    """Verify the reason names non-JSON stdout and quotes its start on one line, then stderr."""
    reason = _failed_reason(
        tmp_path,
        stdout='Working... ━━━━ 100% 0:00:20\n{\n  "errors": []\n}\n',
        stderr="[main]\tINFO\tprofile include tests: None\n",
    )

    assert reason == (
        "failed",
        "Scanner exited with code 1; output was not JSON, starting "
        '"Working... ━━━━ 100% 0:00:20 { "errors": [] }"; '
        "stderr: [main] INFO profile include tests: None",
    )


def test_a_failed_scan_quotes_a_bounded_start_of_its_output(tmp_path: Path) -> None:
    """Verify the quote and the whole reason are cut short, keeping as much stderr as fits."""
    status, reason = _failed_reason(tmp_path, stdout="x" * 500, stderr="e" * 500)

    assert (status, len(reason), reason.partition('"')[2].partition('"')[0], reason[-12:]) == (
        "failed",
        CONST_MAX_ERROR_DETAIL_LENGTH,
        "x" * (CONST_SCANNER_STDOUT_EXCERPT_CHARS - 1) + "…",
        "e" * 11 + "…",
    )


def test_a_failed_scan_masks_its_output_before_cutting_the_quote(tmp_path: Path) -> None:
    """Verify a token the quote's cut would split is masked whole, so no part of it remains."""
    token = "ghp_" + "Q7rT2xW9yB4nM6kP1sD8fG3hJ5lZ0cV2aE7u"
    status, reason = _failed_reason(tmp_path, stdout="x" * 87 + " " + token, stderr="")

    assert (status, token[:11] in reason, reason.partition('"')[2].partition('"')[0]) == (
        "failed",
        False,
        "x" * 87 + " <masked-git…",
    )


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

    # A scanner that raises is recorded as failed; only named, registered scanners run
    other = MagicMock()
    other.name = "other_tool"
    registry.register(other)
    with patch.object(scanner, "scan", side_effect=RuntimeError("Scanner crashed")):
        err_results = registry.scan_all(tmp_path, names=["mock_tool", "unregistered"])
    assert (
        {name: (o.status, o.reason) for name, o in err_results.items()},
        other.scan.call_count,
    ) == (
        {"mock_tool": ("failed", "Scanner crashed")},
        0,
    )


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
            findings = scanner.scan(test_file, image="ubuntu:latest", context="test-cluster")
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
    # Dive writes its analysis to a file, so its adapter reads it through `run_dive_analysis`.
    dive_analysis = DiveAnalysisResult(
        image_name="ubuntu:latest",
        status="ran",
        efficiency_score=0.80,
        wasted_bytes=60_000_000,
        total_bytes=200_000_000,
    )

    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch("devops_cli.security.base.run_subprocess", return_value=mock_proc),
        patch("devops_cli.security.dive.run_dive_analysis", return_value=dive_analysis),
    ):
        findings = scanner.scan(test_file, image="ubuntu:latest", context="test-cluster")
        assert isinstance(findings, list)
        assert len(findings) >= 1, (
            f"Scanner '{scanner_name}' failed to produce normalized findings from sample output"
        )


def test_kubelinter_contract_finding_names_its_check(tmp_path: Path) -> None:
    """kube-linter writes `Check` beside `Diagnostic`, and the title names it."""
    scanner = global_scanner_registry.get("kubelinter")
    assert scanner is not None
    test_file = tmp_path / "test_target.py"
    test_file.write_text("content = True\n", encoding="utf-8")
    mock_proc = MagicMock(returncode=0, stdout=_SAMPLE_STDOUTS["kubelinter"], stderr="")

    with (
        patch("devops_cli.security.base.check_binary", return_value=True),
        patch("devops_cli.security.base.run_subprocess", return_value=mock_proc),
    ):
        findings = scanner.scan(test_file)

    assert [finding.title for finding in findings] == [
        "[no-read-only-root-fs] Root filesystem writeable"
    ]


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


def test_materialized_targets_are_hard_links_else_copies_and_replace_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A target is hard-linked under the working directory at its path in the tree, or copied
    when the link fails, as across filesystems; a file already there, such as one devops-cli
    handed the scanner, is never replaced (#1079). Each is named `./<its path>`, and a result
    reported with or without the `./` maps back to the tree's file."""
    tree = tmp_path / "tree"
    (tree / "src").mkdir(parents=True)
    linked, copied, taken = (tree / "src" / name for name in ("linked.py", "copied.py", "taken.py"))
    for target in (linked, copied, taken):
        target.write_text(target.name, encoding="utf-8")
    workdir = tmp_path / "work"
    (workdir / "src").mkdir(parents=True)
    (workdir / "src" / "taken.py").write_text("devops-cli's own", encoding="utf-8")
    link = os.link

    def cross_device_for_copied(source: Any, destination: Any, **kwargs: Any) -> None:
        if Path(source).name == "copied.py":
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        link(source, destination, **kwargs)

    monkeypatch.setattr(os, "link", cross_device_for_copied)
    staged = materialize_targets([linked, copied, taken], tree, workdir)

    assert (
        staged.names,
        [staged.origin(name) for name in ("src/linked.py", "./src/copied.py")],
        (workdir / "src" / "linked.py").samefile(linked),
        (workdir / "src" / "copied.py").samefile(copied),
        (workdir / "src" / "copied.py").read_text(encoding="utf-8"),
        (workdir / "src" / "taken.py").read_text(encoding="utf-8"),
    ) == (
        [os.path.join(os.curdir, "src", name) for name in ("linked.py", "copied.py")],
        [str(linked), str(copied)],
        True,
        False,
        "copied.py",
        "devops-cli's own",
    )

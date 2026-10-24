"""Unit tests for SecOps & K8s security scanners (Trivy, Kube-linter, Popeye, Pluto)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.commands.scan import scan_trivy as scan_main
from devops_cli.security.kubelinter import parse_kubelinter_json, run_kubelinter_scan
from devops_cli.security.pluto import PlutoScanner, parse_pluto_json, run_pluto_scan
from devops_cli.security.popeye import parse_popeye_json, run_popeye_scan
from devops_cli.security.trivy import parse_trivy_json, run_trivy_scan
from tests.support.fakes.scanners import ScannerFake, ScannerRun
from tests.support.fakes.tool_executor import ToolAnswer


def test_trivy_parser() -> None:
    data = {
        "Results": [
            {
                "Target": "requirements.txt",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2026-1001",
                        "PkgName": "urllib3",
                        "InstalledVersion": "1.26.0",
                        "FixedVersion": "1.26.5",
                        "Severity": "HIGH",
                        "Title": "HTTP Header Injection",
                        "Description": "CRLF Injection flaw",
                    }
                ],
                "Misconfigurations": [
                    {
                        "ID": "KSV001",
                        "Title": "Privilege Elevation Allowed",
                        "Message": "Container allows root elevation",
                        "Severity": "HIGH",
                    }
                ],
                "Secrets": [
                    {
                        "RuleID": "aws-secret-key",
                        "Title": "AWS Secret Access Key",
                        "Severity": "CRITICAL",
                    }
                ],
            }
        ]
    }
    findings = parse_trivy_json(data)
    assert len(findings) == 3
    assert any("CVE-2026-1001" in f.title for f in findings)
    assert any("KSV001" in f.title for f in findings)
    assert any("[SECRET]" in f.title for f in findings)


def test_trivy_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    findings = run_trivy_scan(target=tmp_path, scan_type="fs")
    assert [f.title for f in findings] == ["[DRY-RUN] Simulated Trivy Vulnerability Scan Result"]


def test_kubelinter_parser() -> None:
    data = {
        "Reports": [
            {
                "Check": "run-as-non-root",
                "Diagnostic": {"Message": "container 'web' has no runAsNonRoot set"},
                "Object": {
                    "K8sObject": {
                        "GroupVersionKind": {"Kind": "Deployment"},
                        "Name": "nginx-web",
                        "Namespace": "production",
                    }
                },
            }
        ]
    }
    findings = parse_kubelinter_json(data, target_path="k8s/deployment.yaml")
    assert [(f.title, f.location.rpartition(":")[2]) for f in findings] == [
        (
            "[run-as-non-root] container 'web' has no runAsNonRoot set",
            "Deployment/production/nginx-web",
        )
    ]


def test_kubelinter_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    findings = run_kubelinter_scan(target=tmp_path)
    assert [f.title for f in findings] == ["[DRY-RUN] Simulated Kube-linter Manifest Audit"]


def test_popeye_parser() -> None:
    data = {
        "popeye": {
            "sanitizers": [
                {
                    "sanitizer": "pods",
                    "issues": {
                        "default/web-pod": [
                            {
                                "level": 3,
                                "message": "Container has no CPU limits",
                            }
                        ]
                    },
                }
            ]
        }
    }
    findings = parse_popeye_json(data)
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert "PODS" in findings[0].title


def test_popeye_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    findings = run_popeye_scan(workdir=tmp_path)
    assert [f.title for f in findings] == ["[DRY-RUN] Simulated Popeye Kubernetes Cluster Scan"]


def test_pluto_parser() -> None:
    data = {
        "items": [
            {
                "name": "ingress-lb",
                "kind": "Ingress",
                "apiVersion": "extensions/v1beta1",
                "replacement": "networking.k8s.io/v1",
                "deprecated": True,
                "removed": True,
                "filepath": "k8s/ingress.yaml",
            }
        ]
    }
    findings = parse_pluto_json(data)
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert "networking.k8s.io/v1" in findings[0].fix


def test_pluto_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    findings = run_pluto_scan(target=tmp_path)
    assert [f.title for f in findings] == ["[DRY-RUN] Simulated Pluto Deprecated K8s API Detection"]


def test_devops_scan_dry_run() -> None:
    res = scan_main(target=Path("."), scan_type="fs", dry_run=True)
    assert res is not None
    assert res.status == "DRY_RUN"


def test_kubelinter_scanner_execution(tmp_path: Path) -> None:
    """Verify kubelinter subprocess execution and exit 127 handling."""
    import json
    import subprocess
    from unittest.mock import patch

    kl_json = json.dumps(
        {
            "Reports": [
                {
                    "Check": "run-as-non-root",
                    "Diagnostic": {"Message": "no runAsNonRoot"},
                    "Object": {
                        "K8sObject": {
                            "GroupVersionKind": {"Kind": "Deployment"},
                            "Name": "web",
                            "Namespace": "prod",
                        }
                    },
                }
            ]
        }
    )
    mock_kl_proc = subprocess.CompletedProcess(
        args=["kube-linter"], returncode=0, stdout=kl_json, stderr=""
    )
    with patch("devops_cli.security.kubelinter.run_subprocess", return_value=mock_kl_proc):
        kl_findings = run_kubelinter_scan(tmp_path)
        assert len(kl_findings) == 1
        assert "run-as-non-root" in kl_findings[0].title

    mock_127 = subprocess.CompletedProcess(
        args=["cmd"], returncode=127, stdout="", stderr="not found"
    )
    with patch("devops_cli.security.kubelinter.run_subprocess", return_value=mock_127):
        assert run_kubelinter_scan(tmp_path) == []


def test_pluto_scanner_execution(tmp_path: Path) -> None:
    """Verify pluto subprocess execution, command building, and exit 127 handling."""
    import json
    import subprocess
    from unittest.mock import patch

    from devops_cli.config.commands import BIN_PLUTO

    scanner = PlutoScanner()
    manifest_file = tmp_path / "deployment.yaml"
    manifest_file.touch()

    assert (
        scanner.build_command(tmp_path),
        scanner.build_command(manifest_file),
    ) == (
        [BIN_PLUTO, "detect-files", "-d", str(tmp_path), "-o", "json"],
        [BIN_PLUTO, "detect", str(manifest_file), "-o", "json"],
    )

    pluto_json = json.dumps(
        {
            "items": [
                {
                    "name": "ingress-lb",
                    "kind": "Ingress",
                    "apiVersion": "extensions/v1beta1",
                    "replacement": "networking.k8s.io/v1",
                    "deprecated": True,
                    "removed": True,
                }
            ]
        }
    )
    mock_pluto_proc = subprocess.CompletedProcess(
        args=["pluto"], returncode=0, stdout=pluto_json, stderr=""
    )
    with patch("devops_cli.security.pluto.run_subprocess", return_value=mock_pluto_proc):
        pluto_findings = run_pluto_scan(tmp_path)
        assert (len(pluto_findings), pluto_findings[0].severity) == (1, "HIGH")

    mock_127 = subprocess.CompletedProcess(
        args=["cmd"], returncode=127, stdout="", stderr="not found"
    )
    with patch("devops_cli.security.pluto.run_subprocess", return_value=mock_127):
        assert run_pluto_scan(tmp_path) == []


def test_popeye_scanner_execution(tmp_path: Path) -> None:
    """Verify popeye subprocess execution and exit 127 handling."""
    import json
    import subprocess
    from unittest.mock import patch

    popeye_json = json.dumps(
        {
            "popeye": {
                "sanitizers": [
                    {
                        "sanitizer": "pods",
                        "issues": {"default/pod-1": [{"level": 3, "message": "No CPU limit"}]},
                    }
                ]
            }
        }
    )
    mock_popeye_proc = subprocess.CompletedProcess(
        args=["popeye"], returncode=0, stdout=popeye_json, stderr=""
    )
    with patch("devops_cli.security.popeye.run_subprocess", return_value=mock_popeye_proc):
        popeye_findings = run_popeye_scan(workdir=tmp_path)
        assert len(popeye_findings) == 1
        assert popeye_findings[0].severity == "HIGH"

    mock_127 = subprocess.CompletedProcess(
        args=["cmd"], returncode=127, stdout="", stderr="not found"
    )
    with patch("devops_cli.security.popeye.run_subprocess", return_value=mock_127):
        assert run_popeye_scan(workdir=tmp_path) == []


def test_secops_scanners_dry_run(tmp_path: Path) -> None:
    """Verify dry run branches for kubelinter, pluto, and popeye."""
    from unittest.mock import patch

    with patch("devops_cli.security.kubelinter.is_dry_run", return_value=True):
        assert len(run_kubelinter_scan(tmp_path)) == 1

    with patch("devops_cli.security.pluto.is_dry_run", return_value=True):
        assert len(run_pluto_scan(tmp_path)) == 1

    with patch("devops_cli.security.popeye.is_dry_run", return_value=True):
        assert len(run_popeye_scan(workdir=tmp_path)) == 1


def test_kubelinter_locations_are_relative_to_the_nested_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a finding scanned from a worktree under `.claude/worktrees/` names the manifest
    inside that worktree, not a path through the checkout around it (#582)."""
    _, nested = nested_worktree
    manifest = nested / "k8s" / "deployment.yaml"
    manifest.parent.mkdir()
    manifest.write_text("kind: Deployment\n", encoding="utf-8")
    report = {
        "Check": "run-as-non-root",
        "Diagnostic": {"Message": 'container "web" is not set to runAsNonRoot'},
        "Object": {"K8sObject": {"GroupVersionKind": {"Kind": "Deployment"}, "Name": "web"}},
    }
    monkeypatch.chdir(nested)

    findings = parse_kubelinter_json({"Reports": [report]}, target_path=str(manifest))

    assert [finding.location for finding in findings] == ["k8s/deployment.yaml:Deployment/web"]


def test_a_kubelinter_finding_names_the_manifest_in_its_own_checkout_from_any_directory(
    nested_worktree: tuple[Path, Path],
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A review of another checkout names a kube-linter finding by the path of the manifest in
    that checkout. The location was relative to the checkout of the working directory, so a review
    started outside the checkout named the manifest by its file name alone (#2098)."""
    _, nested = nested_worktree
    manifest = nested / "k8s" / "deployment.yaml"
    manifest.parent.mkdir()
    manifest.write_text("kind: Deployment\n", encoding="utf-8")
    report = {
        "Check": "run-as-non-root",
        "Diagnostic": {"Message": 'container "web" is not set to runAsNonRoot'},
        "Object": {
            "K8sObject": {"GroupVersionKind": {"Kind": "Deployment"}, "Name": "web"},
            "Metadata": {"FilePath": str(manifest)},
        },
    }
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))

    findings = parse_kubelinter_json({"Reports": [report]})

    assert [finding.location for finding in findings] == ["k8s/deployment.yaml:Deployment/web"]


def test_a_kubelinter_finding_names_a_manifest_that_no_checkout_holds_by_its_file_name(
    tmp_path: Path,
) -> None:
    """A manifest that no working tree holds is named by its file name alone (#2098)."""
    manifest = tmp_path / "k8s" / "deployment.yaml"
    manifest.parent.mkdir()
    manifest.write_text("kind: Deployment\n", encoding="utf-8")
    report = {
        "Check": "run-as-non-root",
        "Diagnostic": {"Message": 'container "web" is not set to runAsNonRoot'},
        "Object": {
            "K8sObject": {"GroupVersionKind": {"Kind": "Deployment"}, "Name": "web"},
            "Metadata": {"FilePath": str(manifest)},
        },
    }

    findings = parse_kubelinter_json({"Reports": [report]})

    assert [finding.location for finding in findings] == ["deployment.yaml:Deployment/web"]


def test_popeye_starts_in_the_directory_its_caller_gives(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """Popeye reads the cluster and starts in the directory that the command gives, not in the
    working directory of the process (#2098)."""
    scanner_fake.script(
        "popeye",
        ToolAnswer(stdout=json.dumps({"popeye": {"sanitizers": []}}), version="0.22.1"),
    )
    workdir = tmp_path / "command-directory"
    workdir.mkdir()

    outcome = run_popeye_scan(workdir=workdir)

    assert (outcome.status, scanner_fake.runs) == (
        "ran",
        [ScannerRun(["popeye", "-o", "json", "-s", "error,warn"], str(workdir))],
    )

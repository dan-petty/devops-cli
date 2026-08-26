"""Unit tests for SecOps & K8s security scanners (Trivy, Kube-linter, Popeye, Pluto)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.commands.scan import main as scan_main
from devops_cli.security.kubelinter import parse_kubelinter_json, run_kubelinter_scan
from devops_cli.security.pluto import parse_pluto_json, run_pluto_scan
from devops_cli.security.popeye import parse_popeye_json, run_popeye_scan
from devops_cli.security.trivy import parse_trivy_json, run_trivy_scan


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


def test_trivy_dry_run() -> None:
    findings = run_trivy_scan(target=Path("."), scan_type="fs")
    # dry run should execute or return simulated/empty
    assert isinstance(findings, list)


def test_kubelinter_parser() -> None:
    data = {
        "Reports": [
            {
                "Diagnostic": {
                    "Message": "container 'web' has no runAsNonRoot set",
                    "Check": "run-as-non-root",
                },
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
    assert len(findings) == 1
    assert "run-as-non-root" in findings[0].title
    assert "Deployment/nginx-web" in findings[0].location


def test_kubelinter_dry_run() -> None:
    findings = run_kubelinter_scan(target=Path("."))
    assert isinstance(findings, list)


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


def test_popeye_dry_run() -> None:
    findings = run_popeye_scan()
    assert isinstance(findings, list)


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


def test_pluto_dry_run() -> None:
    findings = run_pluto_scan(target=Path("."))
    assert isinstance(findings, list)


def test_devops_scan_dry_run() -> None:
    res = scan_main(target=Path("."), scan_type="fs", dry_run=True)
    assert res is not None
    assert res.status == "DRY_RUN"


def test_secops_scanners_mocked_execution(tmp_path: Path) -> None:
    """Verify kubelinter, pluto, popeye, and trivy execution with mocked subprocess output and return codes."""
    import json
    import subprocess
    from unittest.mock import patch

    # 1. Kubelinter subprocess execution
    kl_json = json.dumps(
        {
            "Reports": [
                {
                    "Diagnostic": {"Message": "no runAsNonRoot", "Check": "run-as-non-root"},
                    "Object": {
                        "K8sObject": {"Kind": "Deployment", "Name": "web", "Namespace": "prod"}
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

    # Kubelinter 127 (not installed)
    mock_127 = subprocess.CompletedProcess(
        args=["cmd"], returncode=127, stdout="", stderr="not found"
    )
    with patch("devops_cli.security.kubelinter.run_subprocess", return_value=mock_127):
        assert run_kubelinter_scan(tmp_path) == []

    # 2. Pluto subprocess execution
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
        assert len(pluto_findings) == 1
        assert pluto_findings[0].severity == "HIGH"

    # Pluto 127
    with patch("devops_cli.security.pluto.run_subprocess", return_value=mock_127):
        assert run_pluto_scan(tmp_path) == []

    # 3. Popeye subprocess execution
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
        popeye_findings = run_popeye_scan()
        assert len(popeye_findings) == 1
        assert popeye_findings[0].severity == "HIGH"

    # Popeye 127
    with patch("devops_cli.security.popeye.run_subprocess", return_value=mock_127):
        assert run_popeye_scan() == []

    # 4. Dry run branches
    with patch("devops_cli.security.kubelinter.is_dry_run", return_value=True):
        assert len(run_kubelinter_scan(tmp_path)) == 1

    with patch("devops_cli.security.pluto.is_dry_run", return_value=True):
        assert len(run_pluto_scan(tmp_path)) == 1

    with patch("devops_cli.security.popeye.is_dry_run", return_value=True):
        assert len(run_popeye_scan()) == 1

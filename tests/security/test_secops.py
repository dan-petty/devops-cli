"""Unit tests for SecOps & K8s security scanners (Trivy, Kube-linter, Popeye, Pluto)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.commands.scan import scan_trivy as scan_main
from devops_cli.config.commands import BIN_KUBELINTER
from devops_cli.dry_run.state import set_dry_run
from devops_cli.security.kubelinter import parse_kubelinter_json, run_kubelinter_scan
from devops_cli.security.pluto import parse_pluto_json, run_pluto_scan
from devops_cli.security.popeye import run_popeye_scan
from devops_cli.security.registry import ScannerRegistry
from devops_cli.security.tool_executor import KubeApiNetwork
from devops_cli.security.trivy import parse_trivy_json, run_trivy_scan
from tests.support.fakes.scanners import ScannerFake
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


def test_the_registry_scans_iac_files_with_the_misconfiguration_scan_of_trivy(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """The registry holds `trivy-config` in place of Checkov. A scan with every Trivy scanner
    starts Trivy once with `fs` and once with `config` over the target, and each misconfiguration
    that `trivy config` reports is a finding of `trivy-config` (#2214)."""
    dockerfile = {
        "Target": "Dockerfile",
        "Misconfigurations": [
            {
                "ID": "DS-0002",
                "Title": "Image user should not be 'root'",
                "Severity": "HIGH",
                "Resolution": "Add 'USER <non root user name>' line to the Dockerfile",
            }
        ],
    }
    scanner_fake.script("trivy", ToolAnswer(stdout=json.dumps({"Results": [dockerfile]})))
    registry = ScannerRegistry(auto_load_defaults=True)

    outcomes = registry.scan_all(tmp_path, names=["trivy", "trivy-config"])

    assert (
        "checkov" in registry.list_scanners(),
        [run.argv[:3] for run in scanner_fake.runs],
        [(f.severity, f.title) for f in outcomes["trivy-config"].findings],
    ) == (
        False,
        [["trivy", "fs", str(tmp_path)], ["trivy", "config", str(tmp_path)]],
        [("HIGH", "[DS-0002] Image user should not be 'root'")],
    )


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


def test_popeye_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    findings = run_popeye_scan()
    assert [f.title for f in findings] == ["[DRY-RUN] Simulated Popeye Kubernetes Cluster Scan"]


def test_pluto_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    findings = run_pluto_scan(target=tmp_path)
    assert [f.title for f in findings] == ["[DRY-RUN] Simulated Pluto Deprecated K8s API Detection"]


def test_devops_scan_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    scan_main(target=Path("."), scan_type="fs", dry_run=True)
    out = capsys.readouterr().out
    assert "trivy" in out


def test_kubelinter_scanner_execution(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """Verify kubelinter execution and exit 127 handling."""
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
    scanner_fake.script(BIN_KUBELINTER, ToolAnswer(stdout=kl_json))
    kl_findings = run_kubelinter_scan(tmp_path)

    scanner_fake.script(BIN_KUBELINTER, ToolAnswer(exit_code=127, stderr="not found"))
    after_127 = run_kubelinter_scan(tmp_path)

    assert (len(kl_findings), "run-as-non-root" in kl_findings[0].title, after_127) == (
        1,
        True,
        [],
    )


def test_secops_scanners_dry_run(tmp_path: Path) -> None:
    """Verify dry run branches for kubelinter, pluto, and popeye."""
    set_dry_run(True)

    assert (
        len(run_kubelinter_scan(tmp_path)),
        len(run_pluto_scan(tmp_path)),
        len(run_popeye_scan()),
    ) == (1, 1, 1)


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


# The manifests of Pluto's recorded run: Kubernetes removed both APIs, and has no replacement for
# PodSecurityPolicy.
_REMOVED_APIS = """apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  name: web
  namespace: shop
spec: {}
---
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: restricted
spec: {}
"""

_PLUTO_FINDINGS = [
    Finding(
        severity="HIGH",
        location="deploy.yaml:Deployment/shop/web",
        title="[Removed API] Deployment 'web' uses extensions/v1beta1",
        description=(
            "Deployment 'web' uses extensions/v1beta1, which Kubernetes removed in v1.16.0. "
            "Use apps/v1."
        ),
        fix="Change apiVersion from extensions/v1beta1 to apps/v1.",
        confidence_score=None,
    ),
    Finding(
        severity="HIGH",
        location="deploy.yaml:PodSecurityPolicy/restricted",
        title="[Removed API] PodSecurityPolicy 'restricted' uses policy/v1beta1",
        description=(
            "PodSecurityPolicy 'restricted' uses policy/v1beta1, which Kubernetes removed in "
            "v1.25.0. Kubernetes has no replacement API."
        ),
        fix="Remove PodSecurityPolicy 'restricted': no Kubernetes API replaces policy/v1beta1.",
        confidence_score=None,
    ),
]


def _manifests(tmp_path: Path) -> Path:
    """The directory `k8s` of a tree, holding the manifests of Pluto's recorded run."""
    manifests = tmp_path / "tree" / "k8s"
    manifests.mkdir(parents=True)
    (manifests / "deploy.yaml").write_text(_REMOVED_APIS, encoding="utf-8")
    return manifests


def test_pluto_reports_each_object_with_its_api_at_its_manifest(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """Pluto walks `.` from the directory of the manifests, so the `filePath` of its report is the
    manifest's path. Each finding names the kind, namespace and name of the object and the API that
    Kubernetes removed, and an API that has no replacement says so (#1434, #1045)."""
    manifests = _manifests(tmp_path)
    recorded = scanner_fake.script_run_with_findings("pluto", tree=manifests.parent)

    outcome = run_pluto_scan(manifests, kubernetes_version="v1.33.0")

    assert (scanner_fake.runs, outcome.status, outcome.findings) == (
        [recorded],
        "ran",
        _PLUTO_FINDINGS,
    )


def test_pluto_names_its_manifest_relative_to_the_scratch_directory_of_a_review(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """Pluto writes `filePath` as its working directory joined to the path that it walked, so a
    review's run from a scratch directory names the manifest relative to that directory (#1434)."""
    manifest = _manifests(tmp_path) / "deploy.yaml"
    tree = manifest.parent.parent
    scanner_fake.script_run_with_findings("pluto", tree=tree)

    run_pluto_scan(manifest, isolated=True, tree=tree, kubernetes_version="v1.33.0")

    [run] = scanner_fake.runs
    assert run.argv == [
        "pluto",
        "detect",
        os.path.relpath(manifest, run.cwd),
        "-o",
        "json",
        "--target-versions",
        "k8s=v1.33.0",
    ]


def test_pluto_reads_a_file_path_that_climbs_out_of_its_working_directory(tmp_path: Path) -> None:
    """From a scratch directory, the `filePath` of Pluto's report climbs out of it with `..`. The
    finding names the manifest that the path leads to (#1434)."""
    manifest = _manifests(tmp_path) / "deploy.yaml"
    item = {
        "name": "web",
        "filePath": f"{tmp_path}/scratch/../tree/k8s/deploy.yaml",
        "namespace": "shop",
        "api": {
            "version": "extensions/v1beta1",
            "kind": "Deployment",
            "deprecated-in": "v1.9.0",
            "removed-in": "v1.16.0",
            "replacement-api": "apps/v1",
            "replacement-available-in": "v1.9.0",
            "component": "k8s",
        },
        "deprecated": True,
        "removed": True,
        "replacementAvailable": True,
    }

    findings = parse_pluto_json({"items": [item]}, target_path=str(manifest))

    assert findings == _PLUTO_FINDINGS[:1]


def test_popeye_reports_each_issue_of_its_report_at_warn_level(
    scanner_fake: ScannerFake,
) -> None:
    """Popeye runs at warn level over the namespace that it gets, with the network profile
    `kube-api`, from a new empty directory that does not stay after the scan (#2132). Each issue
    of its report is a finding at its linter, resource and container, with the severity of its
    level (#1434)."""
    scanner_fake.snapshot_workdirs = True
    recorded = scanner_fake.script_run_with_findings("popeye")

    outcome = run_popeye_scan(namespace="argocd")

    deployment = "argocd/argocd-applicationset-controller"
    pod = "argocd/argocd-application-controller-0"
    fix_deployment = f"Review and adjust Kubernetes specification for {deployment}"
    fix_pod = f"Review and adjust Kubernetes specification for {pod}"
    selector = (
        "[POP-508] No pods match controller selector: "
        "app.kubernetes.io/name=argocd-applicationset-controller,app.kubernetes.io/instance=argocd"
    )
    memory = "[POP-110] Memory Current/Request (791Mi/256Mi) reached user 80% threshold (308%)"
    (run,) = scanner_fake.runs
    assert (
        run.argv,
        run.workdir_files,
        Path(run.cwd).exists(),
        [request.network for request in scanner_fake.requests],
        outcome.status,
        outcome.findings,
    ) == (
        recorded.argv,
        {},
        False,
        [KubeApiNetwork()],
        "ran",
        [
            Finding(
                severity="MEDIUM",
                location=f"k8s:deployments/{deployment}",
                title="[POP-500] Zero scale detected",
                description=f"Popeye linter 'deployments' on {deployment}: "
                "[POP-500] Zero scale detected",
                fix=fix_deployment,
                confidence_score=None,
            ),
            Finding(
                severity="MEDIUM",
                location=f"k8s:deployments/{deployment}/applicationset-controller",
                title="[POP-106] No resources requests/limits defined",
                description=f"Popeye linter 'deployments' on {deployment}: "
                "[POP-106] No resources requests/limits defined",
                fix=fix_deployment,
                confidence_score=None,
            ),
            Finding(
                severity="HIGH",
                location=f"k8s:deployments/{deployment}",
                title=selector,
                description=f"Popeye linter 'deployments' on {deployment}: {selector}",
                fix=fix_deployment,
                confidence_score=None,
            ),
            Finding(
                severity="MEDIUM",
                location=f"k8s:pods/{pod}/application-controller",
                title="[POP-103] No liveness probe",
                description=f"Popeye linter 'pods' on {pod}: [POP-103] No liveness probe",
                fix=fix_pod,
                confidence_score=None,
            ),
            Finding(
                severity="MEDIUM",
                location=f"k8s:pods/{pod}",
                title="[POP-301] Connects to API Server? ServiceAccount token is mounted",
                description=f"Popeye linter 'pods' on {pod}: "
                "[POP-301] Connects to API Server? ServiceAccount token is mounted",
                fix=fix_pod,
                confidence_score=None,
            ),
            Finding(
                severity="MEDIUM",
                location=f"k8s:pods/{pod}",
                title=memory,
                description=f"Popeye linter 'pods' on {pod}: {memory}",
                fix=fix_pod,
                confidence_score=None,
            ),
        ],
    )


def test_popeye_scans_the_whole_cluster_when_it_gets_no_namespace(
    scanner_fake: ScannerFake,
) -> None:
    """With no namespace, Popeye runs at warn level over every namespace of the current context,
    with `-A`."""
    scanner_fake.script_run_with_findings("popeye")

    run_popeye_scan()

    assert [run.argv for run in scanner_fake.runs] == [["popeye", "-o", "json", "-l", "warn", "-A"]]

"""Tests for the kube-linter adapter: each report keeps its own check, message, file and object.

The fixture is `kube-linter lint k8s --format json` (kube-linter 0.8.3) over the tree at
da50329, trimmed, with each `FilePath` made relative: 7 reports from 4 checks in 3 files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review_schema import Finding, consolidate_duplicate_findings
from devops_cli.security.kubelinter import parse_kubelinter_json
from devops_cli.security.pipeline import build_report
from devops_cli.security.sarif import to_sarif

_FIXTURE = Path(__file__).parent / "fixtures" / "kubelinter" / "k8s-da50329.json"


def _reports() -> dict[str, Any]:
    """The recorded kube-linter JSON."""
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def in_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run from a working tree, so each relative `FilePath` resolves inside it."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def k8s_findings(in_tree: None) -> list[Finding]:
    """The fixture parsed as a scan of the `k8s` directory."""
    return parse_kubelinter_json(_reports(), target_path="k8s")


def test_each_title_names_its_own_check_and_message(k8s_findings: list[Finding]) -> None:
    """A title is `[<check>] <message>`, the form the Bandit and Semgrep adapters write."""
    assert [finding.title for finding in k8s_findings] == [
        f"[{report['Check']}] {report['Diagnostic']['Message']}" for report in _reports()["Reports"]
    ]


def test_each_location_names_its_own_file_and_object(k8s_findings: list[Finding]) -> None:
    """A directory scan names each manifest and the object as `Kind/namespace/name`."""
    assert [finding.location for finding in k8s_findings] == [
        "k8s/cloudflared/deployment.yaml:Deployment/cloudflared/cloudflared",
        "k8s/registry/deployment.yaml:Deployment/registry/registry",
        "k8s/registry/deployment.yaml:Deployment/registry/registry",
        "k8s/monitoring/service-aliases.yaml:Service/monitoring/prometheus",
        "k8s/monitoring/service-aliases.yaml:Service/monitoring/kube-prometheus-kube-prome-prometheus",
        "k8s/monitoring/service-aliases.yaml:Service/monitoring/kube-prometheus-grafana",
        "k8s/monitoring/service-aliases.yaml:Service/monitoring/pyroscope",
    ]


def test_the_category_is_the_class_the_check_names_or_a_misconfiguration(
    k8s_findings: list[Finding],
) -> None:
    """`no-anti-affinity` names reliability; checks whose words name no class are a
    security misconfiguration, which is what kube-linter checks a manifest for."""
    checks = [report["Check"] for report in _reports()["Reports"]]
    assert {(check, f.category) for check, f in zip(checks, k8s_findings, strict=True)} == {
        ("no-anti-affinity", "reliability"),
        ("no-read-only-root-fs", "security_misconfiguration"),
        ("run-as-non-root", "security_misconfiguration"),
        ("dangling-service", "security_misconfiguration"),
    }


def test_the_fix_is_kube_linters_remediation(k8s_findings: list[Finding]) -> None:
    """kube-linter says how to fix each check; the adapter passes that on."""
    assert [finding.fix for finding in k8s_findings] == [
        report["Remediation"] for report in _reports()["Reports"]
    ]


@pytest.mark.usefixtures("in_tree")
def test_a_report_without_a_remediation_gets_the_template_fix() -> None:
    """The template names the object and the check it should resolve."""
    report = _reports()["Reports"][0]
    del report["Remediation"]

    (finding,) = parse_kubelinter_json({"Reports": [report]})

    assert finding.fix == (
        "Update K8s manifest spec for Deployment 'cloudflared' to resolve no-anti-affinity"
    )


@pytest.mark.usefixtures("in_tree")
def test_an_object_without_a_namespace_is_named_by_kind_and_name() -> None:
    """kube-linter reports `Namespace: ""` for a manifest without one; no namespace is guessed."""
    report = _reports()["Reports"][0]
    report["Object"]["K8sObject"]["Namespace"] = ""

    (finding,) = parse_kubelinter_json({"Reports": [report]})

    assert (finding.location, finding.description) == (
        "k8s/cloudflared/deployment.yaml:Deployment/cloudflared",
        "object has 2 replicas but does not specify inter pod anti-affinity "
        "for Deployment 'cloudflared'.",
    )


def test_a_scan_report_keeps_every_finding_under_its_own_rule(
    k8s_findings: list[Finding],
) -> None:
    """Two Services with one message in one file are two findings and two report rows, the
    JSON rows name their objects apart, and SARIF declares one rule per check."""
    report = build_report({"kubelinter": k8s_findings}, Path("k8s"))
    sarif_rules = to_sarif(report.findings)["runs"][0]["tool"]["driver"]["rules"]
    json_clusters = report.as_dict()["clusters"]

    assert (
        len(report.findings),
        len({json.dumps(cluster, sort_keys=True) for cluster in json_clusters}),
        {finding.rule_id for finding in report.findings},
        sorted(rule["id"] for rule in sarif_rules),
    ) == (
        7,
        7,
        {"dangling-service", "no-anti-affinity", "no-read-only-root-fs", "run-as-non-root"},
        ["dangling-service", "no-anti-affinity", "no-read-only-root-fs", "run-as-non-root"],
    )


def test_a_review_keeps_two_checks_on_one_object(k8s_findings: list[Finding]) -> None:
    """The registry Deployment's two checks are two candidates, not one merged one."""
    assert len(consolidate_duplicate_findings(k8s_findings)) == 7

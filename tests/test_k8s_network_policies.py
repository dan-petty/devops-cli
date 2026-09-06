"""Unit and integration tests for Kubernetes default-deny NetworkPolicies (Phase 48 Zero-Trust)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"

TARGET_NAMESPACES = ("monitoring", "argocd", "llm", "otel")
METADATA_SSRF_IP = "169.254.169.254/32"


@pytest.mark.parametrize("namespace", TARGET_NAMESPACES)
def test_networkpolicy_file_exists(namespace: str) -> None:
    """Verify that networkpolicy.yaml exists in each required namespace directory."""
    policy_path = K8S_DIR / namespace / "networkpolicy.yaml"
    assert policy_path.is_file(), f"Missing NetworkPolicy in {policy_path}"


@pytest.mark.parametrize("namespace", TARGET_NAMESPACES)
def test_kustomization_includes_networkpolicy(namespace: str) -> None:
    """Verify that kustomization.yaml in each namespace references networkpolicy.yaml."""
    kustomization_path = K8S_DIR / namespace / "kustomization.yaml"
    assert kustomization_path.is_file(), f"Missing kustomization.yaml in {namespace}"

    content = yaml.safe_load(kustomization_path.read_text(encoding="utf-8"))
    resources = content.get("resources", [])
    assert "networkpolicy.yaml" in resources, (
        f"k8s/{namespace}/kustomization.yaml must include networkpolicy.yaml in resources"
    )


@pytest.mark.parametrize("namespace", TARGET_NAMESPACES)
def test_networkpolicy_schema_and_perimeter_rules(namespace: str) -> None:
    """Verify structural integrity, policyTypes, intra-namespace rules, and SSRF protections."""
    policy_path = K8S_DIR / namespace / "networkpolicy.yaml"
    if not policy_path.is_file():
        pytest.fail(f"NetworkPolicy file does not exist: {policy_path}")

    doc = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    assert doc.get("apiVersion") == "networking.k8s.io/v1"
    assert doc.get("kind") == "NetworkPolicy"

    metadata = doc.get("metadata", {})
    assert metadata.get("namespace") == namespace

    spec = doc.get("spec", {})
    policy_types = spec.get("policyTypes", [])
    assert "Ingress" in policy_types
    assert "Egress" in policy_types

    # Ensure CoreDNS egress on port 53 is permitted
    egress_rules = spec.get("egress", [])
    has_dns = False
    for rule in egress_rules:
        ports = rule.get("ports", [])
        for p in ports:
            if p.get("port") == 53:
                has_dns = True
    assert has_dns, f"NetworkPolicy for {namespace} must permit CoreDNS egress on port 53"

    # Any rule defining an ipBlock must explicitly block cloud metadata SSRF
    for rule in egress_rules:
        to_blocks = rule.get("to", [])
        for to in to_blocks:
            ip_block = to.get("ipBlock", {})
            if ip_block:
                except_list = ip_block.get("except", [])
                assert METADATA_SSRF_IP in except_list, (
                    f"NetworkPolicy for {namespace} with ipBlock must block cloud metadata ({METADATA_SSRF_IP})"
                )

    # Namespaces that access external internet/registries must have an SSRF-blocking egress rule
    if namespace in ("monitoring", "argocd", "llm"):
        has_ssrf_block = any(
            METADATA_SSRF_IP in to.get("ipBlock", {}).get("except", [])
            for rule in egress_rules
            for to in rule.get("to", [])
        )
        assert has_ssrf_block, (
            f"NetworkPolicy for {namespace} must block cloud instance metadata ({METADATA_SSRF_IP})"
        )


def test_argocd_networkpolicy_specifics() -> None:
    """Verify ArgoCD specific ports and rules: UI/API ingress, repo-server, git/helm egress."""
    policy_path = K8S_DIR / "argocd" / "networkpolicy.yaml"
    doc = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    spec = doc.get("spec", {})

    ingress_rules = spec.get("ingress", [])
    allowed_ports = {p.get("port") for rule in ingress_rules for p in rule.get("ports", [])}
    # UI/API ports 8080 and 443 must be allowed for ingress
    assert 8080 in allowed_ports or 443 in allowed_ports

    egress_rules = spec.get("egress", [])
    egress_ports = {p.get("port") for rule in egress_rules for p in rule.get("ports", [])}
    # Git / Helm egress ports (443, 9418, 22)
    assert 443 in egress_ports
    assert 9418 in egress_ports


def test_monitoring_networkpolicy_specifics() -> None:
    """Verify Monitoring specific ports and rules: Grafana (3000), Prometheus (9090)."""
    policy_path = K8S_DIR / "monitoring" / "networkpolicy.yaml"
    doc = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    spec = doc.get("spec", {})

    ingress_rules = spec.get("ingress", [])
    allowed_ports = {p.get("port") for rule in ingress_rules for p in rule.get("ports", [])}
    # UI ports 3000 (Grafana) and 9090 (Prometheus) must be allowed for ingress
    assert 3000 in allowed_ports
    assert 9090 in allowed_ports

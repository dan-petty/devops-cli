"""Unit tests for the Kubernetes Cloudflare Tunnel (cloudflared) manifests."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"
CLOUDFLARED_DIR = K8S_DIR / "cloudflared"


def test_cloudflared_manifest_files_exist() -> None:
    """Verify all expected cloudflared Kubernetes manifests exist."""
    expected_files = [
        CLOUDFLARED_DIR / "deployment.yaml",
        CLOUDFLARED_DIR / "networkpolicy.yaml",
        CLOUDFLARED_DIR / "kustomization.yaml",
    ]
    for file_path in expected_files:
        assert file_path.is_file(), f"Expected file does not exist: {file_path}"
    # The token comes from the keyring (`devops k8s push-secrets`), not a template to fill in.
    assert not (CLOUDFLARED_DIR / "secret.example.yaml").exists()


def test_cloudflared_kustomization_and_namespace_registration() -> None:
    """Verify root k8s/kustomization.yaml and namespaces.yaml register cloudflared.

    Regression test: the cloudflared sub-kustomization previously existed but was
    never listed as a resource in the root kustomization, so `kubectl apply -k k8s/`
    silently skipped its Deployment and NetworkPolicy (only the bare namespace from
    namespaces.yaml was ever applied).
    """
    root_kust = yaml.safe_load((K8S_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    assert "cloudflared" in root_kust.get("resources", [])

    cloudflared_kust = yaml.safe_load(
        (CLOUDFLARED_DIR / "kustomization.yaml").read_text(encoding="utf-8")
    )
    assert cloudflared_kust.get("namespace") == "cloudflared"
    assert "deployment.yaml" in cloudflared_kust.get("resources", [])
    assert "networkpolicy.yaml" in cloudflared_kust.get("resources", [])

    namespaces_doc = list(
        yaml.safe_load_all((K8S_DIR / "namespaces.yaml").read_text(encoding="utf-8"))
    )
    namespace_names = {
        doc["metadata"]["name"] for doc in namespaces_doc if doc and doc.get("kind") == "Namespace"
    }
    assert "cloudflared" in namespace_names


def test_cloudflared_traefik_egress_rule_has_no_port_restriction() -> None:
    """Verify the Traefik egress rule keeps a bare peer selector with no `ports:`.

    Regression test: this cluster's kube-router NetworkPolicy engine silently fails
    to enforce (as "allow") egress rules that combine a peer selector (`to:`) with a
    `ports:` restriction in the same rule, causing traffic matching such a rule to be
    refused as if no rule existed. Re-adding a `ports:` restriction to this specific
    rule would reintroduce the "connection refused" bug reaching Traefik.
    """
    policy = yaml.safe_load((CLOUDFLARED_DIR / "networkpolicy.yaml").read_text(encoding="utf-8"))
    egress_rules = policy["spec"]["egress"]
    traefik_rules = [rule for rule in egress_rules if "to" in rule]
    assert len(traefik_rules) == 1, "Expected exactly one egress rule with a `to:` peer selector"

    traefik_rule = traefik_rules[0]
    assert "ports" not in traefik_rule

    peer = traefik_rule["to"][0]
    assert peer["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"] == "kube-system"
    assert peer["podSelector"]["matchLabels"]["app.kubernetes.io/name"] == "traefik"

"""Unit tests for the Kubernetes Cloudflare Tunnel (cloudflared) manifests."""

from __future__ import annotations

import yaml
from packaging.version import Version

from devops_cli.tools_lock import load_tools_lock
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
CLOUDFLARED_DIR = K8S_DIR / "cloudflared"

# The first cloudflared release built with Go 1.27.3, which rejects the eight eMudhra
# intermediate certificates whose private keys are weak (#2322).
CLOUDFLARED_FIRST_SAFE_VERSION = Version("2026.10.2")


def test_cloudflared_manifest_files_exist() -> None:
    """Verify all expected cloudflared Kubernetes manifests exist."""
    expected_files = [
        CLOUDFLARED_DIR / "deployment.yaml",
        CLOUDFLARED_DIR / "pdb.yaml",
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
    rule would reintroduce the "connection refused" bug reaching Traefik. The API server rule
    pairs an ipBlock peer with `ports:`, which kube-router enforces, as Argo CD's has since #1371.
    """
    policy = yaml.safe_load((CLOUDFLARED_DIR / "networkpolicy.yaml").read_text(encoding="utf-8"))
    egress_rules = policy["spec"]["egress"]
    traefik_rules = [
        rule for rule in egress_rules if any("podSelector" in peer for peer in rule.get("to", []))
    ]
    assert len(traefik_rules) == 1, "Expected exactly one egress rule with a pod selector peer"

    traefik_rule = traefik_rules[0]
    assert "ports" not in traefik_rule

    peer = traefik_rule["to"][0]
    assert peer["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"] == "kube-system"
    assert peer["podSelector"]["matchLabels"]["app.kubernetes.io/name"] == "traefik"


def test_cloudflared_deployment_runs_a_release_that_rejects_the_compromised_emudhra_intermediates() -> (
    None
):
    """Verify the Deployment's image tag is at or above the first release built with Go 1.27.3.

    Regression test (#2322): cloudflared 2026.9.3 and older trust eight eMudhra intermediate
    certificates with weak private keys. The container runs with `--no-autoupdate`, so only a
    change of this tag removes the trust.
    """
    deployment = yaml.safe_load((CLOUDFLARED_DIR / "deployment.yaml").read_text(encoding="utf-8"))
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert [container["name"] for container in containers] == ["cloudflared"]

    repository, _, tag = containers[0]["image"].partition(":")
    assert repository == "cloudflare/cloudflared"
    assert Version(tag) >= CLOUDFLARED_FIRST_SAFE_VERSION


def test_cloudflared_tools_lock_installs_a_release_that_rejects_the_compromised_emudhra_intermediates() -> (
    None
):
    """Verify the lock pins cloudflared at or above the first safe release, and fetches that release.

    Regression test (#2322): `version` names the install directory, and each `sha256` only checks
    the bytes of its own `url`. A bump of `version` that leaves a `url` at the old release would
    install the old build under the new version, and the checksum would pass.
    """
    cloudflared = load_tools_lock().binary["cloudflared"]

    assert Version(cloudflared.version) >= CLOUDFLARED_FIRST_SAFE_VERSION
    assert {
        platform: artifact.url.startswith(
            f"https://github.com/cloudflare/cloudflared/releases/download/{cloudflared.version}/"
        )
        for platform, artifact in cloudflared.platforms.items()
    } == dict.fromkeys(("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64"), True)


def _kustomized_documents() -> list[dict]:
    """Every document that `k8s/cloudflared/kustomization.yaml` lists as a resource."""
    kustomization = yaml.safe_load(
        (CLOUDFLARED_DIR / "kustomization.yaml").read_text(encoding="utf-8")
    )
    return [
        doc
        for resource in kustomization["resources"]
        for doc in yaml.safe_load_all((CLOUDFLARED_DIR / resource).read_text(encoding="utf-8"))
        if doc
    ]


def _pod_labels() -> dict[str, str]:
    deployment = yaml.safe_load((CLOUDFLARED_DIR / "deployment.yaml").read_text(encoding="utf-8"))
    return deployment["spec"]["template"]["metadata"]["labels"]


def test_cloudflared_replicas_prefer_different_nodes() -> None:
    """Verify the pod template asks the scheduler to put the two replicas on different nodes.

    Regression test (#1023): with no anti-affinity, both tunnel connectors could land on one node,
    and the loss or drain of that node cut all external ingress. The term is preferred, not
    required, so a replica still starts while only one node can take it.
    """
    deployment = yaml.safe_load((CLOUDFLARED_DIR / "deployment.yaml").read_text(encoding="utf-8"))
    anti_affinity = (
        deployment["spec"]["template"]["spec"].get("affinity", {}).get("podAntiAffinity", {})
    )
    preferred = anti_affinity.get("preferredDuringSchedulingIgnoredDuringExecution", [])
    terms = [entry["podAffinityTerm"] for entry in preferred]
    labels = _pod_labels()

    assert (
        deployment["spec"]["replicas"] >= 2,
        [term["topologyKey"] for term in terms],
        [term["labelSelector"]["matchLabels"].items() <= labels.items() for term in terms],
        [term["labelSelector"]["matchLabels"].get("app.kubernetes.io/name") for term in terms],
        "requiredDuringSchedulingIgnoredDuringExecution" in anti_affinity,
    ) == (True, ["kubernetes.io/hostname"], [True], ["cloudflared"], False)


def test_cloudflared_drain_keeps_one_tunnel_replica_available() -> None:
    """Verify the kustomization applies a PodDisruptionBudget that keeps one replica up.

    Regression test (#1023): with no PodDisruptionBudget, a drain could evict both tunnel
    connectors at once and cut all external ingress. A pod that is not ready never blocks a
    drain (`unhealthyPodEvictionPolicy: AlwaysAllow`), because it serves no traffic.
    """
    budgets = [doc for doc in _kustomized_documents() if doc.get("kind") == "PodDisruptionBudget"]

    assert [
        (
            budget["apiVersion"],
            budget["spec"].get("minAvailable"),
            budget["spec"].get("unhealthyPodEvictionPolicy"),
            budget["spec"]["selector"]["matchLabels"].items() <= _pod_labels().items(),
        )
        for budget in budgets
    ] == [("policy/v1", 1, "AlwaysAllow", True)]

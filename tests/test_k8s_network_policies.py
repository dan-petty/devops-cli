"""Unit and integration tests for Kubernetes default-deny NetworkPolicies (Phase 48 Zero-Trust)."""

from __future__ import annotations

import ipaddress
from pathlib import Path

import pytest
import yaml

from devops_cli.commands.k8s.networking import _PROXY_TARGETS_INFRA, _resolve_stacks
from devops_cli.commands.k8s.stack_lifecycle import _KUSTOMIZATIONS_BY_STACK, _MANIFESTS_BY_STACK
from tests.k8s_manifests import kustomized_objects, manifest_objects

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"

# The NetworkPolicies `devops k8s deploy-stack` does not apply: (namespace, name) to the file that
# declares the policy and the issue that owns its deploy path, or the path that applies it instead.
# An Argo CD Application is such a path, never a deploy-stack one: a cluster without Argo CD gets
# only what deploy-stack applies (#913). Delete an entry once its policy gains a deploy-stack path
# or leaves its file; the guard below fails until then.
UNDEPLOYED_NETWORK_POLICIES: dict[tuple[str, str], tuple[str, str]] = {
    ("llm", "vllm-profiles-perimeter"): (
        "k8s/llm/profiles/networkpolicy.yaml",
        "#820, which deletes it with the vLLM leftovers",
    ),
    ("llm", "portkey-perimeter"): (
        "k8s/llm/portkey/networkpolicy.yaml",
        "Argo CD's llm Application; deploy-stack does not deploy Portkey",
    ),
    ("llm", "valkey-runs-perimeter"): (
        "k8s/llm/valkey-runs.yaml",
        "Argo CD's llm Application; a person applies the file for `devops ai runs` (k8s/README.md)",
    ),
}

TARGET_NAMESPACES = ("monitoring", "argocd", "llm", "otel", "devops")
METADATA_SSRF_IP = "169.254.169.254/32"
TRAEFIK_PEER = {
    "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}},
    "podSelector": {"matchLabels": {"app.kubernetes.io/name": "traefik"}},
}
# The monitoring ports Traefik routes to (k8s/ingress/ingress-routes.yaml), plus Pyroscope (#943).
MONITORING_TRAEFIK_PORTS = [80, 3000, 4040, 8080, 8081, 8082, 9090, 9100, 9400, 12345]


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


def _deploy_stack_network_policies() -> set[tuple[str, str]]:
    """(namespace, name) of every NetworkPolicy `deploy-stack --stack all` applies without Argo CD.

    It applies the root kustomization, then each stack's kustomizations, then its manifest files.
    """
    stacks = _resolve_stacks("all")
    kustomizations = [
        K8S_DIR,
        *(K8S_DIR / entry for stack in stacks for entry in _KUSTOMIZATIONS_BY_STACK.get(stack, ())),
    ]
    manifests = [
        REPO_ROOT / path for stack in stacks for path in _MANIFESTS_BY_STACK.get(stack, [])
    ]
    return {
        policy
        for kustomization in kustomizations
        for policy in kustomized_objects(kustomization, "NetworkPolicy")
    } | {policy for manifest in manifests for policy in manifest_objects(manifest, "NetworkPolicy")}


def test_every_network_policy_has_a_deploy_stack_path_or_an_owned_exemption() -> None:
    """deploy-stack applies every NetworkPolicy under k8s/, or an exemption names its owner (#913).

    Each namespace's kustomization lists its policy, yet a native deploy never applied
    `monitoring-default-perimeter`: nothing deploy-stack applies named the file. An exemption fails
    once its policy gains a deploy-stack path or leaves the file it names, so the list only shrinks.
    """
    declared = {
        policy
        for path in K8S_DIR.rglob("*.y*ml")
        for policy in manifest_objects(path, "NetworkPolicy")
    }
    applied = _deploy_stack_network_policies()
    exempted = set(UNDEPLOYED_NETWORK_POLICIES)
    assert (
        sorted(declared - applied - exempted),
        sorted(exempted & applied),
        sorted(
            policy
            for policy, (path, _owner) in UNDEPLOYED_NETWORK_POLICIES.items()
            if policy not in manifest_objects(REPO_ROOT / path, "NetworkPolicy")
        ),
    ) == ([], [], [])


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
    # UI/API ports 8080 and 443 must both be allowed for ingress
    assert 8080 in allowed_ports
    assert 443 in allowed_ports

    egress_rules = spec.get("egress", [])
    egress_ports = {p.get("port") for rule in egress_rules for p in rule.get("ports", [])}
    # Git / Helm egress ports (443, 9418, 22)
    assert 443 in egress_ports
    assert 9418 in egress_ports
    assert 22 in egress_ports


def test_monitoring_networkpolicy_specifics() -> None:
    """Verify Monitoring specific ports and rules: Grafana (3000), Prometheus (9090), Pyroscope (4040), cloudflared (2000)."""
    policy_path = K8S_DIR / "monitoring" / "networkpolicy.yaml"
    doc = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    spec = doc.get("spec", {})

    ingress_rules = spec.get("ingress", [])
    allowed_ports = {p.get("port") for rule in ingress_rules for p in rule.get("ports", [])}
    egress_rules = spec.get("egress", [])
    egress_ports = {p.get("port") for rule in egress_rules for p in rule.get("ports", [])}
    # UI ports 3000 (Grafana), 9090 (Prometheus), 4040 (Pyroscope) allowed for ingress, and 2000 (cloudflared) for egress
    assert (
        3000 in allowed_ports,
        9090 in allowed_ports,
        4040 in allowed_ports,
        2000 in egress_ports,
    ) == (True, True, True, True)


def test_monitoring_ingress_admits_no_world_cidr() -> None:
    """Verify the monitoring perimeter admits Traefik by its selector and no address range (#953).

    The cluster's policy engine, kube-router, matches an ingress `ipBlock` against the source
    addresses of pods. The `0.0.0.0/0` peer next to the Traefik peer therefore admitted every pod
    in the cluster to Prometheus, which has no authentication and accepts remote writes, and to
    Grafana, which admits anonymous Viewers. Any range wider than one address admits pods the
    same way, so an RFC 1918 range in its place fails too. External clients reach these ports
    through cloudflared, which forwards only to Traefik.
    """
    doc = yaml.safe_load((K8S_DIR / "monitoring" / "networkpolicy.yaml").read_text("utf-8"))
    ingress = doc["spec"]["ingress"]
    cidrs = [
        peer["ipBlock"]["cidr"]
        for rule in ingress
        for peer in rule.get("from", [])
        if "ipBlock" in peer
    ]
    traefik_rules = [
        (rule["from"], sorted(port["port"] for port in rule.get("ports", [])))
        for rule in ingress
        if TRAEFIK_PEER in rule.get("from", [])
    ]

    assert (
        [cidr for cidr in cidrs if ipaddress.ip_network(cidr).num_addresses > 1],
        traefik_rules,
    ) == ([], [([TRAEFIK_PEER], MONITORING_TRAEFIK_PORTS)])


@pytest.mark.parametrize("namespace", ("argocd", "otel"))
def test_ingress_admits_no_world_cidr(namespace: str) -> None:
    """Verify ingress perimeter defines no ingress ipBlocks (#1371).

    kube-router matches ingress CIDRs against pod addresses, so an ingress 0.0.0.0/0
    admitted every pod in the cluster.
    """
    doc = yaml.safe_load((K8S_DIR / namespace / "networkpolicy.yaml").read_text("utf-8"))
    cidrs = [
        peer["ipBlock"]["cidr"]
        for rule in doc["spec"]["ingress"]
        for peer in rule.get("from", [])
        if "ipBlock" in peer
    ]
    assert cidrs == []


def test_argocd_api_server_egress_admits_6443_through_ipblock() -> None:
    """Verify Argo CD's API-server egress admits 6443 through an ipBlock peer (#1371).

    Namespace-only selectors (default, kube-system) never match the node IP the
    `kubernetes` service resolves to. An ipBlock peer with metadata SSRF protection
    allows Argo CD to reach the API server on 6443.
    """
    doc = yaml.safe_load((K8S_DIR / "argocd" / "networkpolicy.yaml").read_text("utf-8"))
    egress = doc["spec"]["egress"]
    rule = next(r for r in egress if any(p.get("port") == 6443 for p in r.get("ports", [])))
    ip_blocks = [to["ipBlock"] for to in rule.get("to", []) if "ipBlock" in to]
    assert (
        len(ip_blocks),
        ip_blocks[0]["cidr"],
        METADATA_SSRF_IP in ip_blocks[0].get("except", []),
    ) == (1, "0.0.0.0/0", True)


def test_otel_rule_4_admits_traefik_on_8888() -> None:
    """Verify otel rule 4 admits Traefik on 8888 for otel-metrics route (#1371)."""
    doc = yaml.safe_load((K8S_DIR / "otel" / "networkpolicy.yaml").read_text("utf-8"))
    rule_4 = doc["spec"]["ingress"][3]
    ports = [p["port"] for p in rule_4.get("ports", [])]
    from_peers = rule_4.get("from", [])
    assert (
        8888 in ports,
        TRAEFIK_PEER in from_peers,
    ) == (True, True)


def test_readme_proxy_caveat_names_every_monitoring_proxy_target() -> None:
    """Verify k8s/README.md's proxy caveat names every monitoring Service it applies to (#953).

    With no address range in the perimeter, a `k8s://` address the API server proxies reaches a
    monitoring pod only while that pod runs on the control-plane node. `configure-urls
    --addressing proxy` writes one for each monitoring target in `_PROXY_TARGETS_INFRA`, and the
    caveat named Grafana and Prometheus but not Pyroscope.
    """
    readme = (K8S_DIR / "README.md").read_text("utf-8").splitlines()
    caveat = next(line for line in readme if line.startswith("- `--addressing proxy`"))
    unnamed = [
        key
        for key, namespace, _, _ in _PROXY_TARGETS_INFRA
        if namespace == "monitoring" and key.split(".")[0].capitalize() not in caveat
    ]

    assert unnamed == []


OTEL_COLLECTOR_PEER = {
    "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "otel"}},
    "podSelector": {
        "matchLabels": {
            "app.kubernetes.io/name": "opentelemetry-collector",
            "app.kubernetes.io/instance": "otel-collector",
        }
    },
}
MONITORING_NAMESPACE_PEER = {
    "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "monitoring"}}
}


def test_loki_ingress_from_otel_admits_only_the_collector() -> None:
    """Verify Loki's 3100 ingress names the collector's pods in `otel`, not the whole namespace (#1100).

    Loki runs with `auth_enabled: false`, so a namespace-only `otel` peer let Jaeger, or any
    workload later deployed to `otel`, push and query logs. A peer that combines the namespace
    selector with the collector release's pod labels, with `ports` in the same rule, was
    checked against this cluster's kube-router before the change: the labelled pod connected
    and an unlabelled pod in the same namespace was refused, from the same node and another.
    """
    doc = yaml.safe_load((K8S_DIR / "logging" / "networkpolicy.yaml").read_text("utf-8"))
    loki_rules = [
        (rule["from"], rule.get("ports"))
        for rule in doc["spec"]["ingress"]
        if {"protocol": "TCP", "port": 3100} in rule.get("ports", [])
    ]

    assert loki_rules == [
        (
            [MONITORING_NAMESPACE_PEER, OTEL_COLLECTOR_PEER],
            [{"protocol": "TCP", "port": 3100}],
        )
    ]


def test_loki_otel_peer_names_the_collector_release_the_stack_installs() -> None:
    """Verify the `otel` peer's pod labels are the ones the collector release is installed with
    (#1100). The chart labels its pods `app.kubernetes.io/instance` with the release name and
    `app.kubernetes.io/name` with the chart name unless the values override it, so renaming the
    release or overriding the name would cut the collector off from Loki without a failure."""
    from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK

    collectors = [
        release
        for releases in _HELM_RELEASES_BY_STACK.values()
        for release in releases
        if release["chart"] == "open-telemetry/opentelemetry-collector"
    ]
    values = yaml.safe_load(Path(collectors[0]["values"]).read_text("utf-8")) or {}
    labels = OTEL_COLLECTOR_PEER["podSelector"]["matchLabels"]

    assert [(c["namespace"], c["name"]) for c in collectors] == [
        ("otel", labels["app.kubernetes.io/instance"])
    ]
    assert (values.get("nameOverride"), collectors[0]["chart"].rsplit("/", 1)[1]) == (
        None,
        labels["app.kubernetes.io/name"],
    )

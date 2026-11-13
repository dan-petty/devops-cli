"""Unit and integration tests for Kubernetes default-deny NetworkPolicies (Phase 48 Zero-Trust)."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.commands.k8s.networking import _PROXY_TARGETS_INFRA
from tests.support.k8s_tree import TREE
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"


TARGET_NAMESPACES = (
    "monitoring",
    "argocd",
    "llm",
    "otel",
    "devops",
    "argo-workflows",
    "gitea",
    "mattermost",
    "cert-manager",
    "cnpg-system",
)
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


@pytest.mark.parametrize("namespace", TARGET_NAMESPACES)
def test_networkpolicy_schema_and_perimeter_rules(namespace: str) -> None:
    """Verify structural integrity, policyTypes, intra-namespace rules, and SSRF protections."""
    policy_path = K8S_DIR / namespace / "networkpolicy.yaml"
    if not policy_path.is_file():
        pytest.fail(f"NetworkPolicy file does not exist: {policy_path}")

    docs = [
        d
        for d in yaml.safe_load_all(policy_path.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("kind") == "NetworkPolicy"
    ]
    doc = docs[0]
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
    for d in docs:
        for rule in d.get("spec", {}).get("egress", []):
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
    assert (8080 in allowed_ports, 443 in allowed_ports) == (True, True)

    egress_rules = spec.get("egress", [])
    egress_ports = {p.get("port") for rule in egress_rules for p in rule.get("ports", [])}
    # Git / Helm egress ports (443, 22), 9418 removed (#1122)
    assert (443 in egress_ports, 22 in egress_ports, 9418 not in egress_ports) == (
        True,
        True,
        True,
    )


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


@pytest.mark.parametrize(
    "namespace", ("argocd", "otel", "argo-workflows", "gitea", "cert-manager", "cnpg-system")
)
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


@pytest.mark.parametrize(
    "namespace", ["argocd", "cloudflared", "argo-workflows", "cert-manager", "cnpg-system"]
)
def test_api_server_egress_admits_6443_through_ipblock(namespace: str) -> None:
    """Argo CD reconciles through the API server (#1371), cloudflared carries the tunnel's
    `k8s.<domain>` TCP route to it (#1595), and the Argo Workflows controller and the executors
    of its Workflows reach it (#1535). cert-manager and the Barman Cloud plugin are controllers
    that work only through it (#4764).

    Namespace-only selectors (default, kube-system) never match the node IP the
    `kubernetes` service resolves to. An ipBlock peer with metadata SSRF protection
    allows the pods to reach the API server on 6443.
    """
    doc = yaml.safe_load((K8S_DIR / namespace / "networkpolicy.yaml").read_text("utf-8"))
    egress = doc["spec"]["egress"]
    rule = next(r for r in egress if any(p.get("port") == 6443 for p in r.get("ports", [])))
    ip_blocks = [to["ipBlock"] for to in rule.get("to", []) if "ipBlock" in to]
    assert (
        len(ip_blocks),
        ip_blocks[0]["cidr"],
        METADATA_SSRF_IP in ip_blocks[0].get("except", []),
    ) == (1, "0.0.0.0/0", True)


def _peer_namespace_and_pods(peer: dict[str, Any]) -> tuple[str | None, dict[str, str] | None]:
    """The namespace a peer names (None: the policy's own) and its pod labels (None: any pod)."""
    namespace = peer.get("namespaceSelector", {}).get("matchLabels", {})
    pods = peer.get("podSelector")
    return namespace.get("kubernetes.io/metadata.name"), (
        pods.get("matchLabels") or None if pods is not None else None
    )


def test_gitea_perimeter_admits_only_its_http_port_from_traefik_argocd_and_its_namespace() -> None:
    """Gitea answers on TCP 3000 only, from Traefik (the tunnel's path), Argo CD's repo server
    (#1082) and its own namespace, and reaches only DNS and its own namespace (#1081). No peer
    is an address range, and no rule admits the SSH ports 22 and 2222."""
    spec = yaml.safe_load((K8S_DIR / "gitea" / "networkpolicy.yaml").read_text("utf-8"))["spec"]
    ingress = [
        (
            sorted((_peer_namespace_and_pods(peer) for peer in rule.get("from", [])), key=str),
            [(port["protocol"], port["port"]) for port in rule.get("ports", [])],
        )
        for rule in spec["ingress"]
    ]
    egress = [
        (
            [_peer_namespace_and_pods(peer) for peer in rule.get("to", [])],
            [(port["protocol"], port["port"]) for port in rule.get("ports", [])],
        )
        for rule in spec["egress"]
    ]
    admitted_ports = {port for _, ports in ingress for _, port in ports}

    assert (
        spec["podSelector"],
        spec["policyTypes"],
        ingress,
        egress,
        admitted_ports & {22, 2222},
    ) == (
        {},
        ["Ingress", "Egress"],
        [
            (
                sorted(
                    [
                        ("kube-system", {"app.kubernetes.io/name": "traefik"}),
                        ("argocd", {"app.kubernetes.io/name": "argocd-repo-server"}),
                        (None, None),
                    ],
                    key=str,
                ),
                [("TCP", 3000)],
            )
        ],
        [
            ([("kube-system", {"k8s-app": "kube-dns"})], [("UDP", 53), ("TCP", 53)]),
            ([(None, None)], []),
        ],
        set(),
    )


def test_devops_egress_to_otel_admits_only_otlp_http() -> None:
    """devops-cli sends OTLP over HTTP only (#1319), so the devops perimeter opens only the
    collector's OTLP/HTTP port, 4318, to the otel namespace, and not its gRPC port, 4317."""
    doc = yaml.safe_load((K8S_DIR / "devops" / "networkpolicy.yaml").read_text(encoding="utf-8"))
    otel_ports = [
        (port["protocol"], port["port"])
        for rule in doc["spec"]["egress"]
        if any(
            peer.get("namespaceSelector", {}).get("matchLabels", {})
            == {"kubernetes.io/metadata.name": "otel"}
            for peer in rule.get("to", [])
        )
        for port in rule.get("ports", [])
    ]

    assert otel_ports == [("TCP", 4318)]


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


def _namespace_pod_peer(namespace: str, name: str, instance: str) -> dict[str, Any]:
    return {
        "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": namespace}},
        "podSelector": {
            "matchLabels": {
                "app.kubernetes.io/name": name,
                "app.kubernetes.io/instance": instance,
            }
        },
    }


OTEL_COLLECTOR_PEER = _namespace_pod_peer("otel", "opentelemetry-collector", "otel-collector")
GRAFANA_PEER = _namespace_pod_peer("monitoring", "grafana", "grafana")
ALLOY_COLLECTOR_PEERS = [
    _namespace_pod_peer("monitoring", collector, f"k8s-monitoring-{collector}")
    for collector in ("alloy-logs", "alloy-metrics", "alloy-singleton")
]
MONITORING_NAMESPACE_PEER = {
    "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "monitoring"}}
}


def test_loki_ingress_from_otel_admits_only_the_collector() -> None:
    """Verify Loki's 3100 ingress names Grafana, the Alloy collectors, and the OTel collector (#1100, #1133).

    Loki runs with `auth_enabled: false`, so namespace-only `monitoring` or `otel` peers let any
    workload in those namespaces push and query logs. Each peer combines the namespace selector
    with the release's pod labels, with `ports` in the same rule, and a namespace-only `monitoring`
    peer is rejected.
    """
    doc = yaml.safe_load((K8S_DIR / "logging" / "networkpolicy.yaml").read_text("utf-8"))
    loki_rules = [
        (rule["from"], rule.get("ports"))
        for rule in doc["spec"]["ingress"]
        if {"protocol": "TCP", "port": 3100} in rule.get("ports", [])
    ]
    peers = [peer for from_peers, _ in loki_rules for peer in from_peers]

    assert (
        loki_rules,
        MONITORING_NAMESPACE_PEER in peers,
    ) == (
        [
            (
                [GRAFANA_PEER, *ALLOY_COLLECTOR_PEERS, OTEL_COLLECTOR_PEER],
                [{"protocol": "TCP", "port": 3100}],
            )
        ],
        False,
    )


def test_loki_otel_peer_names_the_collector_release_the_stack_installs() -> None:
    """Verify the `otel` peer's pod labels are the ones the collector release is installed with
    (#1100). The chart labels its pods `app.kubernetes.io/instance` with the release name and
    `app.kubernetes.io/name` with the chart name unless the values override it, so renaming the
    release or overriding the name would cut the collector off from Loki without a failure."""
    from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK

    collectors = [
        release
        for releases in HELM_RELEASES_BY_STACK.values()
        for release in releases
        if release["chart"] == "open-telemetry/opentelemetry-collector"
    ]
    (values_file,) = collectors[0]["values"]
    values = yaml.safe_load(TREE.path(values_file).read_text("utf-8")) or {}
    labels = OTEL_COLLECTOR_PEER["podSelector"]["matchLabels"]

    assert [(c["namespace"], c["name"]) for c in collectors] == [
        ("otel", labels["app.kubernetes.io/instance"])
    ]
    assert (values.get("nameOverride"), collectors[0]["chart"].rsplit("/", 1)[1]) == (
        None,
        labels["app.kubernetes.io/name"],
    )


def _extract_metadata_names(selector: dict[str, Any]) -> list[str]:
    names: list[str] = []
    match_labels = selector.get("matchLabels", {})
    if isinstance(match_labels, dict) and "kubernetes.io/metadata.name" in match_labels:
        names.append(match_labels["kubernetes.io/metadata.name"])
    for expr in selector.get("matchExpressions", []):
        if isinstance(expr, dict) and expr.get("key") == "kubernetes.io/metadata.name":
            names.extend(expr.get("values", []))
    return names


def _extract_namespace_selectors(data: Any) -> list[str]:
    """Recursively find all kubernetes.io/metadata.name values inside namespaceSelector objects."""
    names: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "namespaceSelector" and isinstance(v, dict):
                names.extend(_extract_metadata_names(v))
            else:
                names.extend(_extract_namespace_selectors(v))
    elif isinstance(data, list):
        for item in data:
            names.extend(_extract_namespace_selectors(item))
    return names


def test_every_network_policy_namespace_selector_names_a_declared_or_builtin_namespace() -> None:
    """Verify every kubernetes.io/metadata.name in a namespaceSelector under k8s/ names a declared or built-in namespace (#1656).

    A selector that names a namespace that does not exist matches zero pods and states an
    intent that the policy does not enforce.
    """
    declared = {
        doc["metadata"]["name"]
        for doc in yaml.safe_load_all((K8S_DIR / "namespaces.yaml").read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "Namespace"
    }
    allowed = declared | {"kube-system", "default"}

    violations: list[tuple[str, str]] = []
    for path in sorted(K8S_DIR.rglob("*.y*ml")):
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        for doc in docs:
            for namespace in _extract_namespace_selectors(doc):
                if namespace not in allowed:
                    violations.append((str(path.relative_to(K8S_DIR)), namespace))

    assert violations == []


def test_mattermost_pod_has_no_ipblock_egress_peer() -> None:
    """No policy with an ipBlock egress peer selects a pod labelled app: mattermost (#1391)."""
    mattermost_dir = K8S_DIR / "mattermost"
    policy_path = mattermost_dir / "networkpolicy.yaml"
    assert policy_path.is_file(), f"Missing NetworkPolicy in {mattermost_dir}"

    docs = [
        doc
        for doc in yaml.safe_load_all(policy_path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "NetworkPolicy"
    ]
    for doc in docs:
        spec = doc.get("spec", {})
        egress_rules = spec.get("egress", [])
        has_ipblock = any(
            to_block.get("ipBlock") for rule in egress_rules for to_block in rule.get("to", [])
        )
        if has_ipblock:
            pod_selector = spec.get("podSelector", {})
            match_labels = pod_selector.get("matchLabels", {})
            assert match_labels.get("app") != "mattermost"
            assert pod_selector != {}


def test_monitoring_egress_allows_mattermost_port_8065() -> None:
    """The monitoring perimeter allows egress to namespace mattermost on TCP port 8065 (#1392)."""
    policy_path = K8S_DIR / "monitoring" / "networkpolicy.yaml"
    docs = [
        doc
        for doc in yaml.safe_load_all(policy_path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "NetworkPolicy"
    ]
    ports: list[int] = []
    for doc in docs:
        for rule in doc.get("spec", {}).get("egress", []):
            targets = [
                peer.get("namespaceSelector", {})
                .get("matchLabels", {})
                .get("kubernetes.io/metadata.name")
                for peer in rule.get("to", [])
            ]
            if "mattermost" in targets:
                ports.extend(p.get("port") for p in rule.get("ports", []) if "port" in p)
    assert 8065 in ports


def test_mattermost_ingress_admits_alertmanager_port_8065() -> None:
    """The mattermost perimeter admits TCP 8065 only from alertmanager in monitoring (#1392)."""
    policy_path = K8S_DIR / "mattermost" / "networkpolicy.yaml"
    docs = [
        doc
        for doc in yaml.safe_load_all(policy_path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "NetworkPolicy"
    ]
    peers = [
        peer
        for doc in docs
        for rule in doc.get("spec", {}).get("ingress", [])
        if 8065 in [p.get("port") for p in rule.get("ports", [])]
        for peer in rule.get("from", [])
    ]
    matches = [
        peer
        for peer in peers
        if peer.get("namespaceSelector", {})
        .get("matchLabels", {})
        .get("kubernetes.io/metadata.name")
        == "monitoring"
        and peer.get("podSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/name")
        == "alertmanager"
    ]
    assert len(matches) == 1


def test_argocd_egress_allows_mattermost_port_8065() -> None:
    """The argocd perimeter allows egress to mattermost on TCP port 8065 (#1393)."""
    policy_path = K8S_DIR / "argocd" / "networkpolicy.yaml"
    docs = [
        doc
        for doc in yaml.safe_load_all(policy_path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "NetworkPolicy"
    ]
    ports: list[int] = []
    for doc in docs:
        for rule in doc.get("spec", {}).get("egress", []):
            targets = [
                peer.get("namespaceSelector", {})
                .get("matchLabels", {})
                .get("kubernetes.io/metadata.name")
                for peer in rule.get("to", [])
            ]
            if "mattermost" in targets:
                ports.extend(p.get("port") for p in rule.get("ports", []) if "port" in p)
    assert 8065 in ports


def test_mattermost_ingress_admits_argocd_notifications_controller_port_8065() -> None:
    """The mattermost perimeter admits TCP 8065 from argocd-notifications-controller (#1393)."""
    policy_path = K8S_DIR / "mattermost" / "networkpolicy.yaml"
    docs = [
        doc
        for doc in yaml.safe_load_all(policy_path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "NetworkPolicy"
    ]
    peers = [
        peer
        for doc in docs
        for rule in doc.get("spec", {}).get("ingress", [])
        if 8065 in [p.get("port") for p in rule.get("ports", [])]
        for peer in rule.get("from", [])
    ]
    matches = [
        peer
        for peer in peers
        if peer.get("namespaceSelector", {})
        .get("matchLabels", {})
        .get("kubernetes.io/metadata.name")
        == "argocd"
        and peer.get("podSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/name")
        == "argocd-notifications-controller"
    ]
    assert len(matches) == 1


def test_mattermost_egress_allows_devops_port_8000() -> None:
    """The mattermost pod allows egress to namespace devops on TCP port 8000 (#1395)."""
    policy_path = K8S_DIR / "mattermost" / "networkpolicy.yaml"
    docs = [
        doc
        for doc in yaml.safe_load_all(policy_path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "NetworkPolicy"
    ]
    egress_rules = [
        rule
        for doc in docs
        if doc.get("spec", {})
        .get("podSelector", {})
        .get("matchLabels", {})
        .get("app.kubernetes.io/name")
        == "mattermost"
        for rule in doc.get("spec", {}).get("egress", [])
    ]
    ports: list[int] = []
    for rule in egress_rules:
        targets = [
            peer.get("namespaceSelector", {})
            .get("matchLabels", {})
            .get("kubernetes.io/metadata.name")
            for peer in rule.get("to", [])
        ]
        if "devops" in targets:
            ports.extend(p.get("port") for p in rule.get("ports", []) if "port" in p)
    assert 8000 in ports


def test_roadmap_service_ingress_admits_mattermost_port_8000() -> None:
    """The roadmap-service ingress policy admits TCP 8000 from mattermost pods in mattermost (#1395)."""
    policy_path = K8S_DIR / "devops" / "roadmap-service" / "networkpolicy.yaml"
    docs = [
        doc
        for doc in yaml.safe_load_all(policy_path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "NetworkPolicy"
    ]
    peers = [
        peer
        for doc in docs
        for rule in doc.get("spec", {}).get("ingress", [])
        if 8000 in [p.get("port") for p in rule.get("ports", [])]
        for peer in rule.get("from", [])
    ]
    matches = [
        peer
        for peer in peers
        if peer.get("namespaceSelector", {})
        .get("matchLabels", {})
        .get("kubernetes.io/metadata.name")
        == "mattermost"
        and peer.get("podSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/name")
        == "mattermost"
    ]
    assert len(matches) == 1


def _devops_policies() -> dict[str, dict[str, Any]]:
    """Each NetworkPolicy under `k8s/devops/`, by name."""
    policies: dict[str, dict[str, Any]] = {}
    for path in sorted((K8S_DIR / "devops").rglob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if isinstance(doc, dict) and doc.get("kind") == "NetworkPolicy":
                policies[doc["metadata"]["name"]] = doc["spec"]
    return policies


def _public_egress_rule(spec: dict[str, Any]) -> dict[str, Any]:
    """The egress rule of a policy whose peer is the address range 0.0.0.0/0."""
    (rule,) = (
        rule
        for rule in spec["egress"]
        if any(peer.get("ipBlock", {}).get("cidr") == "0.0.0.0/0" for peer in rule["to"])
    )
    return rule


def test_the_default_perimeter_of_devops_skips_the_crawl4ai_and_searxng_pods() -> None:
    """A browser that renders hostile pages must reach neither the gateway nor the cache Valkey,
    and the search service needs neither. So `devops-default-perimeter` selects every pod of the
    namespace but `crawl4ai` and `searxng`, the shape that `portkey-perimeter` uses (#3884, #3924).
    Each pod has its own policy."""
    selector = _devops_policies()["devops-default-perimeter"]["podSelector"]

    assert selector == {
        "matchExpressions": [
            {
                "key": "app.kubernetes.io/name",
                "operator": "NotIn",
                "values": ["crawl4ai", "searxng"],
            }
        ]
    }


def test_the_crawl4ai_perimeter_admits_only_the_roadmap_service_on_11235() -> None:
    """The service answers on TCP 11235 to the pods of `roadmap-service` and to no other peer. The
    peer is a pod selector alone: kube-router refused a namespace and pod selector peer paired with
    `ports` (#3884)."""
    spec = _devops_policies()["crawl4ai-perimeter"]

    assert (spec["podSelector"], spec["policyTypes"], spec["ingress"]) == (
        {"matchLabels": {"app.kubernetes.io/name": "crawl4ai"}},
        ["Ingress", "Egress"],
        [
            {
                "from": [
                    {"podSelector": {"matchLabels": {"app.kubernetes.io/name": "roadmap-service"}}}
                ],
                "ports": [{"protocol": "TCP", "port": 11235}],
            }
        ],
    )


def test_the_crawl4ai_perimeter_reaches_only_dns_and_the_public_web() -> None:
    """The pod resolves names through CoreDNS and reaches TCP 80 and 443 at public addresses. The
    address range of the public rule is the one of the default perimeter, with every private,
    shared, link-local, metadata and special-purpose range removed. This policy is the main control
    against a request to an internal address, and the filter of the application is the second
    (#3884)."""
    policies = _devops_policies()
    spec = policies["crawl4ai-perimeter"]
    public = _public_egress_rule(spec)
    default_public = _public_egress_rule(policies["devops-default-perimeter"])
    other_rules = [rule for rule in spec["egress"] if rule is not public]

    assert (public["to"], public["ports"], other_rules) == (
        default_public["to"],
        [{"protocol": "TCP", "port": 80}, {"protocol": "TCP", "port": 443}],
        [
            {
                "to": [
                    {
                        "namespaceSelector": {
                            "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                        }
                    }
                ],
                "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
            }
        ],
    )


def test_the_crawl4ai_excepted_ranges_hold_every_private_range() -> None:
    """The ranges that the public rule removes cover RFC 1918, shared address space, link-local,
    the cloud metadata address and the IETF protocol and benchmarking ranges."""
    removed = _public_egress_rule(_devops_policies()["crawl4ai-perimeter"])["to"][0]["ipBlock"][
        "except"
    ]

    assert sorted(removed) == sorted(
        [
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "100.64.0.0/10",
            "169.254.0.0/16",
            METADATA_SSRF_IP,
            "192.0.0.0/24",
            "198.18.0.0/15",
        ]
    )


def test_only_the_roadmap_service_may_send_to_port_11235() -> None:
    """Of the pods in namespace devops, the `roadmap-service` pod alone has an egress rule to the
    pods of `crawl4ai` on 11235. A Job pod (`devops-cli-job`) keeps no such rule, so it cannot call
    the fetch service (#3884)."""
    senders = {
        name: (spec["podSelector"], [peer["podSelector"] for peer in rule["to"]])
        for name, spec in _devops_policies().items()
        for rule in spec.get("egress", [])
        if 11235 in [port.get("port") for port in rule.get("ports", [])]
        and "crawl4ai-perimeter" != name
    }

    assert senders == {
        "roadmap-service-to-crawl4ai": (
            {"matchLabels": {"app.kubernetes.io/name": "roadmap-service"}},
            [{"matchLabels": {"app.kubernetes.io/name": "crawl4ai"}}],
        )
    }


def test_the_searxng_perimeter_admits_only_the_roadmap_service_on_8080() -> None:
    """The service has no limiter and no login, so the policy is its access control: the pods of
    `roadmap-service` reach TCP 8080 and no other peer does. The peer is a pod selector alone
    (kube-router refused a namespace and pod selector peer paired with `ports`) (#3924)."""
    spec = _devops_policies()["searxng-perimeter"]

    assert (spec["podSelector"], spec["policyTypes"], spec["ingress"]) == (
        {"matchLabels": {"app.kubernetes.io/name": "searxng"}},
        ["Ingress", "Egress"],
        [
            {
                "from": [
                    {"podSelector": {"matchLabels": {"app.kubernetes.io/name": "roadmap-service"}}}
                ],
                "ports": [{"protocol": "TCP", "port": 8080}],
            }
        ],
    )


def test_the_searxng_perimeter_reaches_only_dns_and_public_https() -> None:
    """The engines answer on HTTPS, so the pod reaches CoreDNS and TCP 443 at public addresses. The
    address range of the public rule is the one of the default perimeter, with every private,
    shared, link-local, metadata and special-purpose range removed (#3924)."""
    policies = _devops_policies()
    spec = policies["searxng-perimeter"]
    public = _public_egress_rule(spec)
    default_public = _public_egress_rule(policies["devops-default-perimeter"])
    other_rules = [rule for rule in spec["egress"] if rule is not public]

    assert (public["to"], public["ports"], other_rules) == (
        default_public["to"],
        [{"protocol": "TCP", "port": 443}],
        [
            {
                "to": [
                    {
                        "namespaceSelector": {
                            "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                        }
                    }
                ],
                "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
            }
        ],
    )


def test_only_the_roadmap_service_may_send_to_port_8080_of_searxng() -> None:
    """Of the pods in namespace devops, the `roadmap-service` pod alone has an egress rule to the
    pods of `searxng` on 8080. A Job pod (`devops-cli-job`) keeps no such rule, so it cannot call
    the search service (#3924)."""
    senders = {
        name: (spec["podSelector"], [peer["podSelector"] for peer in rule["to"]])
        for name, spec in _devops_policies().items()
        for rule in spec.get("egress", [])
        if 8080 in [port.get("port") for port in rule.get("ports", [])]
        and "searxng-perimeter" != name
    }

    assert senders == {
        "searxng-clients": (
            {"matchLabels": {"app.kubernetes.io/name": "roadmap-service"}},
            [{"matchLabels": {"app.kubernetes.io/name": "searxng"}}],
        )
    }


def _policies_in(path: Path) -> dict[str, dict[str, Any]]:
    """The spec of each NetworkPolicy in a file, by name."""
    return {
        doc["metadata"]["name"]: doc["spec"]
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "NetworkPolicy"
    }


_DNS_EGRESS = {
    "to": [
        {
            "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}},
            "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
        }
    ],
    "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
}
_API_SERVER_EGRESS = {
    "to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": [METADATA_SSRF_IP]}}],
    "ports": [{"protocol": "TCP", "port": 443}, {"protocol": "TCP", "port": 6443}],
}


def test_the_cert_manager_perimeter_admits_monitoring_on_9402_and_reaches_dns_and_the_api() -> None:
    """Every pod of namespace cert-manager takes only the metrics scrape of monitoring on 9402,
    and reaches only CoreDNS and the API server. The issuers are self-signed, so no pod calls an
    ACME server (#4764)."""
    spec = _policies_in(K8S_DIR / "cert-manager" / "networkpolicy.yaml")[
        "cert-manager-default-perimeter"
    ]

    assert (spec["podSelector"], spec["policyTypes"], spec["ingress"], spec["egress"]) == (
        {},
        ["Ingress", "Egress"],
        [
            {
                "from": [
                    {
                        "namespaceSelector": {
                            "matchLabels": {"kubernetes.io/metadata.name": "monitoring"}
                        }
                    }
                ],
                "ports": [{"protocol": "TCP", "port": 9402}],
            }
        ],
        [_DNS_EGRESS, _API_SERVER_EGRESS],
    )


def test_only_the_cert_manager_webhook_takes_any_peer_and_only_on_10250() -> None:
    """The API server calls the webhook from the host network of the control-plane node. No
    selector names that address, and kube-router admits host traffic only to pods on the same
    node, so the rule names no peer. It selects the webhook pods alone and opens TCP 10250 alone
    (#4764)."""
    spec = _policies_in(K8S_DIR / "cert-manager" / "networkpolicy-webhook.yaml")[
        "cert-manager-webhook"
    ]

    assert (spec["podSelector"], spec["policyTypes"], spec["ingress"]) == (
        {
            "matchLabels": {
                "app.kubernetes.io/name": "webhook",
                "app.kubernetes.io/component": "webhook",
            }
        },
        ["Ingress"],
        [{"ports": [{"protocol": "TCP", "port": 10250}]}],
    )


def test_monitoring_egress_allows_cert_manager_port_9402() -> None:
    """The cert-manager pods carry the `prometheus.io/*` keys, so Alloy scrapes them on 9402, and
    the monitoring perimeter lets the scrape out (#4764)."""
    spec = yaml.safe_load((K8S_DIR / "monitoring" / "networkpolicy.yaml").read_text("utf-8"))[
        "spec"
    ]
    ports = [
        (port["protocol"], port["port"])
        for rule in spec["egress"]
        if {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "cert-manager"}}}
        in rule.get("to", [])
        for port in rule.get("ports", [])
    ]

    assert ports == [("TCP", 9402)]


def test_only_the_cloudnative_pg_operator_reaches_the_barman_cloud_plugin() -> None:
    """The operator calls the gRPC server of the plugin over mutual TLS on 9090. The instance
    pods talk to the plugin sidecar in their own pod, so no other peer is admitted. The plugin
    reaches only CoreDNS and the API server (#4764)."""
    spec = _policies_in(K8S_DIR / "cnpg-system" / "networkpolicy.yaml")["plugin-barman-cloud"]

    assert (spec["podSelector"], spec["policyTypes"], spec["ingress"], spec["egress"]) == (
        {"matchLabels": {"app.kubernetes.io/name": "plugin-barman-cloud"}},
        ["Ingress", "Egress"],
        [
            {
                "from": [
                    {"podSelector": {"matchLabels": {"app.kubernetes.io/name": "cloudnative-pg"}}}
                ],
                "ports": [{"protocol": "TCP", "port": 9090}],
            }
        ],
        [_DNS_EGRESS, _API_SERVER_EGRESS],
    )

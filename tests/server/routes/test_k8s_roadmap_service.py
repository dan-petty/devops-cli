"""Tests for the roadmap service Kubernetes manifests under k8s/devops/roadmap-service/ (#1083)."""

from __future__ import annotations

import functools
import itertools
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_SERVICE_STOP_CUT_SECONDS,
    CONST_SERVICE_STOP_DRAIN_SECONDS,
    CONST_SERVICE_STOP_GRACE_SECONDS,
    WebhookExposure,
)
from devops_cli.server.routes.webhooks import WEBHOOK_PROVIDERS
from devops_cli.telemetry.exporter import OtlpSignal
from tests.support.fakes.otlp import FakeCollector
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
DEVOPS_DIR = K8S_DIR / "devops"
ROADMAP_SERVICE_DIR = DEVOPS_DIR / "roadmap-service"


@functools.cache
def _doc(name: str) -> Any:
    return yaml.load(
        (ROADMAP_SERVICE_DIR / name).read_text(encoding="utf-8"), Loader=yaml.CSafeLoader
    )


def _pod_spec() -> dict[str, Any]:
    return _doc("deployment.yaml")["spec"]["template"]["spec"]


def _container() -> dict[str, Any]:
    (container,) = _pod_spec()["containers"]
    return container


def test_deployment_spec_and_container() -> None:
    deployment = _doc("deployment.yaml")
    spec = deployment["spec"]
    pod = _pod_spec()
    container = _container()
    args = container["args"]
    arg_pairs = list(itertools.pairwise(args))

    assert (
        deployment["metadata"]["name"],
        deployment["metadata"]["namespace"],
        spec["replicas"],
        spec["strategy"]["type"],
        container["name"],
        container["image"],
        "--service" in args,
        ("--host", "0.0.0.0") in arg_pairs,  # nosec B104  # the pod binds all its interfaces
        ("--workers", "1") in arg_pairs,
        pod["serviceAccountName"],
        pod["terminationGracePeriodSeconds"],
    ) == (
        "roadmap-service",
        "devops",
        1,
        "Recreate",
        "service",
        "ghcr.io/dan-petty/devops-cli/service",
        True,
        True,
        True,
        "roadmap-service",
        CONST_SERVICE_STOP_GRACE_SECONDS,
    )


def test_the_grace_period_covers_both_waits_of_the_stop_and_no_hook_uses_it_first() -> None:
    """Kubernetes kills the pod at the end of its grace period, so the period covers the drain
    wait and the cut wait of the stop. uvicorn starts the drain on SIGTERM, and a preStop hook
    would use the period first (#4485)."""
    assert (
        CONST_SERVICE_STOP_GRACE_SECONDS
        > CONST_SERVICE_STOP_DRAIN_SECONDS + CONST_SERVICE_STOP_CUT_SECONDS,
        "lifecycle" in _container(),
    ) == (True, False)


def test_security_context_is_restricted() -> None:
    pod_sc = _pod_spec()["securityContext"]
    container_sc = _container()["securityContext"]

    assert (
        pod_sc["runAsNonRoot"],
        pod_sc["runAsUser"],
        pod_sc["runAsGroup"],
        pod_sc["fsGroup"],
        pod_sc["seccompProfile"]["type"],
        container_sc["allowPrivilegeEscalation"],
        container_sc["readOnlyRootFilesystem"],
        container_sc["capabilities"]["drop"],
    ) == (True, 1000, 1000, 1000, "RuntimeDefault", False, True, ["ALL"])


def test_every_pod_of_the_deployment_exports_its_metrics_under_one_series_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prometheus names a series by its `service.name` (`job`) and `service.instance.id`
    (`instance`). The host name of the pod changes at each restart, so the Deployment sets one
    instance id in the standard `OTEL_RESOURCE_ATTRIBUTES`: the series of a new pod continues the
    series of the pod before it. The metric Resource keeps no `host.name`, which the collector
    would key a metric stream by (#1629, #4697)."""
    env = {e["name"]: e.get("value") for e in _container()["env"]}
    monkeypatch.setenv("OTEL_SERVICE_NAME", env["OTEL_SERVICE_NAME"])
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", env["OTEL_RESOURCE_ATTRIBUTES"])
    pods = ("roadmap-service-5557bc6b97-4m96n", "roadmap-service-7fcb98569d-2szh4")
    resources = []
    for pod in pods:
        collector = FakeCollector()
        client = collector.client(service_name=env["OTEL_SERVICE_NAME"])
        client.host_name = pod
        client.increment_counter("devops_cli_ai_requests_total", 1, attributes={})
        (payload,) = collector.payloads(OtlpSignal.METRICS)
        resources.append(
            {
                a["key"]: next(iter(a["value"].values()))
                for a in payload["resourceMetrics"][0]["resource"]["attributes"]
            }
        )

    assert resources[0] == resources[1]
    assert "host.name" not in resources[0]


def test_ingress_has_class_traefik_one_host_and_a_prefix_path_for_each_tunnel_provider() -> None:
    """The public Ingress routes exactly the webhook path of each provider the router marks as
    reached through the tunnel (#1386). A cluster provider has no public path."""
    ingress = _doc("ingress.yaml")
    rules = ingress["spec"]["rules"]
    assert (len(rules), ingress["spec"]["ingressClassName"]) == (1, "traefik")

    rule = rules[0]
    routed = [
        (
            entry["path"],
            entry["pathType"],
            entry["backend"]["service"]["name"],
            entry["backend"]["service"]["port"]["number"],
        )
        for entry in rule["http"]["paths"]
    ]
    expected = [
        (provider.path, "Prefix", "roadmap-service", 8000)
        for provider in WEBHOOK_PROVIDERS.values()
        if provider.exposure is WebhookExposure.TUNNEL
    ]
    assert (rule["host"], routed) == ("hooks.example.com", expected)


def test_networkpolicy_admits_traefik_monitoring_and_mattermost_on_8000() -> None:
    policy = _doc("networkpolicy.yaml")
    spec = policy["spec"]
    ingress_rules = spec["ingress"]

    from_peers = [peer for rule in ingress_rules for peer in rule.get("from", [])]
    ports = [p["port"] for rule in ingress_rules for p in rule.get("ports", [])]

    has_traefik = any(
        peer.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name")
        == "kube-system"
        and peer.get("podSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/name")
        == "traefik"
        for peer in from_peers
    )
    has_monitoring = any(
        peer.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name")
        == "monitoring"
        for peer in from_peers
    )
    has_mattermost = any(
        peer.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name")
        == "mattermost"
        and peer.get("podSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/name")
        == "mattermost"
        for peer in from_peers
    )

    assert (
        policy["metadata"]["name"],
        spec["podSelector"]["matchLabels"],
        spec["policyTypes"],
        has_traefik,
        has_monitoring,
        has_mattermost,
        set(ports),
    ) == (
        "roadmap-service-ingress",
        {"app.kubernetes.io/name": "roadmap-service"},
        ["Ingress"],
        True,
        True,
        True,
        {8000},
    )


def test_monitoring_networkpolicy_has_egress_rule_to_devops_on_8000() -> None:
    mon_policy = yaml.load(
        (K8S_DIR / "monitoring" / "networkpolicy.yaml").read_text(encoding="utf-8"),
        Loader=yaml.CSafeLoader,
    )
    devops_egress = [
        rule
        for rule in mon_policy["spec"]["egress"]
        if any(
            to.get("namespaceSelector", {})
            .get("matchLabels", {})
            .get("kubernetes.io/metadata.name")
            == "devops"
            for to in rule.get("to", [])
        )
    ]

    assert (
        len(devops_egress),
        devops_egress[0]["ports"],
    ) == (1, [{"protocol": "TCP", "port": 8000}])

"""Tests for the roadmap service Kubernetes manifests under k8s/devops/roadmap-service/ (#1083)."""

from __future__ import annotations

import functools
import itertools
from typing import Any

import pytest
import yaml

from devops_cli.config import options as opt
from devops_cli.config.constants import WebhookExposure
from devops_cli.config.env import OPTION_TO_ENV_VAR
from devops_cli.config.settings import Settings
from devops_cli.server.routes.webhooks import WEBHOOK_PROVIDERS
from devops_cli.telemetry.tracer import OTelTelemetryClient
from tests.support.paths import REPO_ROOT
from tests.support.telemetry_capture import Captured

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
        0,
        "Recreate",
        "service",
        "ghcr.io/dan-petty/devops-cli/service",
        True,
        True,
        True,
        "devops-cli",
        150,
    )


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


def test_credentials_arrive_only_through_secret_devops_cli() -> None:
    container = _container()
    secret_env = {"GH_TOKEN", "GITHUB_TOKEN"} | {
        OPTION_TO_ENV_VAR[o] for o in opt.SECRET_CONFIG_OPTIONS if o in OPTION_TO_ENV_VAR
    }
    literal = [
        e["name"] for e in container.get("env", []) if e["name"] in secret_env and "value" in e
    ]
    assert (container["envFrom"], literal) == ([{"secretRef": {"name": "devops-cli"}}], [])


def test_pvc_mounted_at_home_data_dir_under_home_and_sync_options() -> None:
    pvc = _doc("pvc.yaml")
    pod = _pod_spec()
    container = _container()

    pvc_volumes = {
        v["name"]
        for v in pod["volumes"]
        if v.get("persistentVolumeClaim", {}).get("claimName") == "roadmap-service-home"
    }
    home_mount = next(m for m in container["volumeMounts"] if m["name"] in pvc_volumes)
    env = {e["name"]: e.get("value") for e in container["env"]}

    sync_options = pvc["metadata"]["annotations"]["argocd.argoproj.io/sync-options"].split(",")

    assert (
        home_mount["mountPath"],
        env["DEVOPS_CLI_DATA_DIR"].startswith("/home/devops"),
        env["DEVOPS_CLI_CONFIG"],
        env["OTEL_SERVICE_NAME"],
        "Prune=false" in sync_options,
        "Delete=false" in sync_options,
        pvc["spec"]["storageClassName"],
        pvc["spec"]["resources"]["requests"]["storage"],
    ) == (
        "/home/devops",
        True,
        "/config/devops-cli.yaml",
        "roadmap-service",
        True,
        True,
        "local-path",
        "1Gi",
    )


def test_every_pod_of_the_deployment_exports_its_metrics_under_one_series_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prometheus names a series by its `service.name` (`job`) and `service.instance.id`
    (`instance`). The host name of the pod changes at each restart, so the Deployment sets one
    instance id in the standard `OTEL_RESOURCE_ATTRIBUTES`: the series of a new pod continues the
    series of the pod before it, and `host.name` still names the pod (#1629)."""
    env = {e["name"]: e.get("value") for e in _container()["env"]}
    monkeypatch.setenv("OTEL_SERVICE_NAME", env["OTEL_SERVICE_NAME"])
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", env["OTEL_RESOURCE_ATTRIBUTES"])
    pods = ("roadmap-service-5557bc6b97-4m96n", "roadmap-service-7fcb98569d-2szh4")
    identities = []
    for pod in pods:
        client = OTelTelemetryClient(
            endpoint="http://127.0.0.1:9", service_name=env["OTEL_SERVICE_NAME"]
        )
        client.host_name = pod
        sink = Captured()
        monkeypatch.setattr(client, "_send_payload", sink)
        client.increment_counter("devops_cli_ai_requests_total", 1, attributes={})
        client.flush()
        (payload,) = sink.payloads
        resource = {
            a["key"]: next(iter(a["value"].values()))
            for a in payload["resourceMetrics"][0]["resource"]["attributes"]
        }
        identities.append(
            (resource["service.name"], resource["service.instance.id"], resource["host.name"])
        )

    assert identities == [("roadmap-service", "roadmap-service", pod) for pod in pods]


def test_pod_annotations_name_port_8000() -> None:
    annotations = _doc("deployment.yaml")["spec"]["template"]["metadata"]["annotations"]
    assert (annotations.get("prometheus.io/scrape"), annotations.get("prometheus.io/port")) == (
        "true",
        "8000",
    )


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


def test_networkpolicy_admits_only_traefik_and_monitoring_on_8000() -> None:
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

    assert (
        policy["metadata"]["name"],
        spec["podSelector"]["matchLabels"],
        spec["policyTypes"],
        has_traefik,
        has_monitoring,
        set(ports),
    ) == (
        "roadmap-service-ingress",
        {"app.kubernetes.io/name": "roadmap-service"},
        ["Ingress"],
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


def test_configmap_validates_as_settings_with_repos_and_the_github_app() -> None:
    target = DEVOPS_DIR / "configmap.example.yaml"
    cm = yaml.load(target.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    raw = yaml.safe_load(cm["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(raw)

    assert (
        bool(settings.service.repos),
        bool(settings.service.github_app.bot_login),
        settings.telemetry.enabled,
        settings.telemetry.endpoint,
        settings.ai.tasks.analysis.context_window,
    ) == (
        True,
        True,
        True,
        "http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318",
        65536,
    )


def test_kustomizations_list_manifests_and_directory() -> None:
    devops_kust = yaml.load(
        (DEVOPS_DIR / "kustomization.yaml").read_text(encoding="utf-8"),
        Loader=yaml.CSafeLoader,
    )
    rs_kust = _doc("kustomization.yaml")
    expected_manifests = sorted(
        p.name for p in ROADMAP_SERVICE_DIR.glob("*.yaml") if p.name != "kustomization.yaml"
    )

    assert (
        "roadmap-service" in devops_kust["resources"],
        sorted(rs_kust["resources"]),
        len(expected_manifests),
        all((ROADMAP_SERVICE_DIR / m).is_file() for m in rs_kust["resources"]),
    ) == (True, expected_manifests, 5, True)

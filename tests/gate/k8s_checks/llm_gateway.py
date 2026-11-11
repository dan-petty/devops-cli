"""The config map of the LLM gateway, the hash in its name (#2164), and its span export (#4518)."""

from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import yaml

from tests.gate.k8s_render import kustomize

GATEWAY_DIR = Path("k8s/llm/gateway")


# The LiteLLM config; the gateway kustomization generates ConfigMap llm-gateway-config from it.
GATEWAY_CONFIG = GATEWAY_DIR / "config.yaml"


LLM_DIR = Path("k8s/llm")


def _rendered_gateway(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the gateway Deployment and the ConfigMap its config volume names, as
    `kubectl apply -k <directory>` applies them; the ConfigMap is empty when none has that name."""
    documents = [doc for doc in yaml.safe_load_all(kustomize(directory).stdout) if doc]
    deployment = next(
        doc
        for doc in documents
        if doc["kind"] == "Deployment" and doc["metadata"]["name"] == "llm-gateway"
    )
    volumes = {v["name"]: v for v in deployment["spec"]["template"]["spec"]["volumes"]}
    configmaps = {doc["metadata"]["name"]: doc for doc in documents if doc["kind"] == "ConfigMap"}
    return deployment, configmaps.get(volumes["config-volume"]["configMap"]["name"], {})


@pytest.mark.parametrize("directory", [LLM_DIR, GATEWAY_DIR], ids=["argo-cd", "deploy-stack"])
def check_the_gateway_mounts_a_config_map_named_by_a_hash_of_its_config(directory: Path) -> None:
    """Argo CD's `llm` Application renders `k8s/llm` with Kustomize, and deploy-stack applies
    `k8s/llm/gateway` with `kubectl apply -k`. Both give the gateway ConfigMap
    `llm-gateway-config-<hash>`, which holds `config.yaml` as git has it, and write that name into
    the Deployment's config volume. Before #1929 the name had no hash, so a changed config left
    the pod template as it was, and the gateway served the old config until a person restarted it.
    """
    _, configmap = _rendered_gateway(directory)
    name = configmap.get("metadata", {}).get("name", "")

    assert (
        re.fullmatch(r"llm-gateway-config-[a-z0-9]{10}", name) is not None,
        configmap.get("data"),
    ) == (True, {"config.yaml": GATEWAY_CONFIG.read_text(encoding="utf-8")})


def check_a_changed_gateway_config_changes_only_the_config_map_name_in_the_pod_template(
    tmp_path: Path,
) -> None:
    """A change to `config.yaml` alone changes the gateway's pod template, so Kubernetes rolls the
    Deployment onto the new config and no `kubectl rollout restart` is necessary (#1929). The
    template changes in the name of its config volume's ConfigMap and in nothing else."""
    before, after = tmp_path / "before", tmp_path / "after"
    shutil.copytree(GATEWAY_DIR, before)
    shutil.copytree(GATEWAY_DIR, after)
    config = after / "config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("cooldown_time: 30", "cooldown_time: 60"),
        encoding="utf-8",
    )
    (old, old_configmap), (new, new_configmap) = _rendered_gateway(before), _rendered_gateway(after)

    def unnamed(deployment: dict[str, Any]) -> dict[str, Any]:
        template = copy.deepcopy(deployment["spec"]["template"])
        for volume in template["spec"]["volumes"]:
            volume.get("configMap", {}).pop("name", None)
        return template

    assert (
        old["spec"]["template"] == new["spec"]["template"],
        unnamed(old) == unnamed(new),
        old_configmap["metadata"]["name"] == new_configmap["metadata"]["name"],
        yaml.safe_load(new_configmap["data"]["config.yaml"])["router_settings"]["cooldown_time"],
    ) == (False, True, False, 60)


# The Argo CD Application of the OpenTelemetry Collector chart: its name is the Helm release name.
COLLECTOR_APP = Path("k8s/argocd/apps/otel-collector.yaml")


# The perimeter of namespace `otel`, which admits OTLP to the Collector.
COLLECTOR_POLICY = Path("k8s/otel/networkpolicy.yaml")


# The port of the Collector's OTLP/HTTP receiver (`k8s/otel/values.yaml`).
OTLP_HTTP_PORT = 4318


def _collector() -> tuple[str, str, str]:
    """The namespace, the Helm release and the Service name of the Collector. The chart names its
    Service `<release>-<chart>`, as Helm's `fullname` does when the release name does not hold the
    chart name and no override is set."""
    app = yaml.safe_load(COLLECTOR_APP.read_text(encoding="utf-8"))
    (chart,) = [source["chart"] for source in app["spec"]["sources"] if "chart" in source]
    release = app["metadata"]["name"]
    service = release if chart in release else f"{release}-{chart}"
    return app["spec"]["destination"]["namespace"], release, service


def check_the_gateway_sends_spans_without_content_to_the_collector_service() -> None:
    """The gateway's `otel` callback sends spans over OTLP/HTTP to the Service of the Collector,
    whose trace pipeline deletes key data (#4518). `turn_off_message_logging` keeps prompt and
    reply text off every span. LiteLLM metrics and events stay off: the metrics and logs
    pipelines of the Collector delete no key data."""
    deployment, configmap = _rendered_gateway(GATEWAY_DIR)
    settings = yaml.safe_load(configmap["data"]["config.yaml"])["litellm_settings"]
    (container,) = deployment["spec"]["template"]["spec"]["containers"]
    env = {variable["name"]: variable.get("value") for variable in container["env"]}
    endpoint = urlsplit(env.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "")
    namespace, _, service = _collector()

    assert (
        sorted(settings["callbacks"]),
        settings.get("turn_off_message_logging"),
        env.get("OTEL_EXPORTER_OTLP_PROTOCOL"),
        (endpoint.scheme, endpoint.hostname, endpoint.port, endpoint.path),
        env.get("LITELLM_OTEL_INTEGRATION_ENABLE_METRICS", "false"),
        env.get("LITELLM_OTEL_INTEGRATION_ENABLE_EVENTS", "false"),
    ) == (
        ["otel", "prometheus"],
        True,
        "http/protobuf",
        ("http", f"{service}.{namespace}.svc.cluster.local", OTLP_HTTP_PORT, ""),
        "false",
        "false",
    )


def check_the_gateway_reaches_only_the_collector_pods_on_the_otlp_port() -> None:
    """The gateway's egress admits OTLP/HTTP to the Collector pods alone, so no span goes past the
    rule that deletes key data, such as to Tempo in the same namespace. The Collector's perimeter
    admits the port from every namespace."""
    namespace, release, _ = _collector()
    documents = [doc for doc in yaml.safe_load_all(kustomize(LLM_DIR).stdout) if doc]
    policies = {
        doc["metadata"]["name"]: doc["spec"] for doc in documents if doc["kind"] == "NetworkPolicy"
    }
    collector_ingress = [
        rule["from"]
        for rule in yaml.safe_load(COLLECTOR_POLICY.read_text(encoding="utf-8"))["spec"]["ingress"]
        if {"protocol": "TCP", "port": OTLP_HTTP_PORT} in rule.get("ports", [])
    ]

    assert (
        [
            rule["to"]
            for rule in policies["llm-gateway-perimeter"]["egress"]
            if {"protocol": "TCP", "port": OTLP_HTTP_PORT} in rule.get("ports", [])
        ],
        collector_ingress,
    ) == (
        [
            [
                {
                    "namespaceSelector": {
                        "matchLabels": {"kubernetes.io/metadata.name": namespace}
                    },
                    "podSelector": {
                        "matchLabels": {
                            "app.kubernetes.io/name": "opentelemetry-collector",
                            "app.kubernetes.io/instance": release,
                        }
                    },
                }
            ]
        ],
        [[{"namespaceSelector": {}}]],
    )

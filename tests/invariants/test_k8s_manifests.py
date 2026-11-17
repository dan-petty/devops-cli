"""Kubernetes manifest invariants: what the committed manifests under `k8s/` must hold."""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest
import yaml
from packaging.version import Version

from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK
from devops_cli.config.constants import CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS
from devops_cli.config.defaults import (
    DEFAULT_AI_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
)
from devops_cli.config.env import keyring_names, option_env_vars
from devops_cli.config.settings import RoadmapFixPlanConfig
from devops_cli.k8s.cluster_secrets import (
    CLUSTER_SECRETS,
    DEVOPS_CACHE_VALKEY_AUTH_KEY,
    GRAFANA_RENDERER_AUTH_KEY,
    GRAFANA_SECURITY_KEY,
    LLM_GATEWAY_MASTER_KEY,
    MATTERMOST_DB_AUTH_KEY,
    SEARXNG_SERVER_KEY,
    KeyringSource,
    keyring_only_keys,
    keyring_sources,
)
from tests.support.k8s_tree import (
    POD_SPEC_PATHS,
    application_sources,
    chart_values,
    manifests,
    pinned_charts,
    pod_spec,
    release_values,
    value_at,
)
from tests.support.paths import REPO_ROOT

# The Proxy Read Timeout of the Cloudflare edge, which only an Enterprise zone can change.
CLOUDFLARE_PROXY_READ_TIMEOUT_SECONDS = 125

# The time that a fix-plan attempt can take after its budget: one model run that started before
# the budget ended (the longest run of the attempt on #5350 on 2026-11-13 took 757 s), and the
# push, the comment and the result line after it.
FIX_PLAN_STOP_MARGIN_SECONDS = 1200

# The first Ollama release that runs a multimodal embedding model, such as embeddinggemma-2,
# through llama-server, its runner on Linux. 0.40.0 ran that model on Apple MLX only (#2395).
OLLAMA_FIRST_LLAMA_SERVER_EMBEDDING_RELEASE = Version("0.40.4")

# The first Traefik chart that ships Traefik v3.7.16, the release that fixes every advisory
# published against v3.7.x up to GHSA-hrpp-p4fc-wwf8 (2026-10-21). The 41.x charts end at v3.7.14,
# so only chart 42 carries the later fixes (#1659).
TRAEFIK_FIRST_CHART_WITH_V3_7_16 = Version("42.1.1")


def test_a_gateway_attempt_ends_before_the_deadline_of_the_call() -> None:
    """The timeouts nest, and the inner one ends first (#5965). The gateway ends a stuck attempt
    before the client ends the call, so the gateway can retry it or fall back. Each default call
    deadline ends before the stage margin and the runner Job deadline. The client deadline still
    frees the slot of a tier through `cancel_on_disconnect` (#2869)."""
    config = yaml.safe_load((REPO_ROOT / "k8s/llm/gateway/config.yaml").read_text(encoding="utf-8"))
    runner = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    attempts = [config["router_settings"]["timeout"]] + [
        deployment["litellm_params"]["timeout"]
        for deployment in config["model_list"]
        if "timeout" in deployment["litellm_params"]
    ]
    calls = (DEFAULT_AI_REQUEST_TIMEOUT_SECONDS, DEFAULT_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS)
    runner_deadline = runner["spec"]["jobTemplate"]["spec"]["activeDeadlineSeconds"]

    assert (
        max(attempts) < min(calls),
        DEFAULT_AI_REQUEST_TIMEOUT_SECONDS
        < min(CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS, runner_deadline),
        config["general_settings"]["cancel_on_disconnect"],
    ) == (True, True, True)


def test_a_cooled_deepseek_deployment_is_checked_again_before_its_cooldown_ends() -> None:
    """The health check of each checked deployment ends before the next check cycle starts, and
    a deployment with its own `cooldown_time` stays cooled for at least one full cycle (#5990).
    So a deployment that cooled after a failure gets a new verdict before it gets calls again,
    and a deployment that still stalls stays out of the routing."""
    config = yaml.safe_load((REPO_ROOT / "k8s/llm/gateway/config.yaml").read_text(encoding="utf-8"))
    general = config["general_settings"]
    interval = general["health_check_interval"]
    checked = [
        m["model_info"]
        for m in config["model_list"]
        if m["model_name"] in general["background_health_check_model_groups"]
    ]
    cooled = [info for info in checked if "cooldown_time" in info]

    assert (
        bool(cooled),
        all(info["health_check_timeout"] < interval for info in checked),
        all(info["cooldown_time"] >= interval + info["health_check_timeout"] for info in cooled),
    ) == (True, True, True)


def test_the_fix_plan_time_budget_ends_before_the_deadline_of_each_job_template() -> None:
    """A Job of `devops k8s run-job` gets the deadline of its CronJob template. The time budget of
    the step fix-plan stops the attempt at the next model call, so the budget, one more model run
    and the push and the comment after it end before that deadline (#5363)."""

    def deadline(name: str) -> int:
        manifest = yaml.safe_load((REPO_ROOT / "k8s/devops" / name).read_text(encoding="utf-8"))
        return int(manifest["spec"]["jobTemplate"]["spec"]["activeDeadlineSeconds"])

    deadlines = {name: deadline(name) for name in ("cronjob.yaml", "cronjob-runner.yaml")}

    end = RoadmapFixPlanConfig().time_budget_seconds + FIX_PLAN_STOP_MARGIN_SECONDS

    assert {name: end < limit for name, limit in deadlines.items()} == dict.fromkeys(
        deadlines, True
    )


def test_the_gateway_keeps_a_streamed_chat_reply_open_under_the_edge_timeout() -> None:
    """A streamed reply with no data for 125 s is cut at the edge, so the gateway writes a
    keepalive comment sooner, the time before the first token included (#2365)."""
    config = yaml.safe_load((REPO_ROOT / "k8s/llm/gateway/config.yaml").read_text(encoding="utf-8"))

    interval = config["litellm_settings"].get("sse_keepalive_ping_interval_seconds")

    assert isinstance(interval, int | float)
    assert 0 < interval < CLOUDFLARE_PROXY_READ_TIMEOUT_SECONDS


def test_every_ollama_tier_runs_one_release_that_serves_multimodal_embedding_models() -> None:
    """Each tier keeps its models in the node's /var/lib/ollama, and a node that moves to another
    tier reads that store with the other tier's release, so every tier and its init container run
    one image: a release that runs embeddinggemma-2 on Linux (#2395)."""
    profiles = REPO_ROOT / "k8s/llm/profiles/ollama-profiles.yaml"
    tiers = [doc for doc in yaml.safe_load_all(profiles.read_text(encoding="utf-8")) if doc]
    images = {
        container["image"]
        for tier in tiers
        for container in [
            *tier["spec"]["template"]["spec"].get("initContainers", []),
            *tier["spec"]["template"]["spec"]["containers"],
        ]
    }

    assert len(images) == 1
    repository, tag_and_digest = next(iter(images)).split(":", 1)
    tag, _, digest = tag_and_digest.partition("@")
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
    assert repository == "ollama/ollama"
    assert Version(tag) >= OLLAMA_FIRST_LLAMA_SERVER_EMBEDDING_RELEASE


def test_traefik_runs_a_chart_that_ships_traefik_v3_7_16() -> None:
    """Traefik v3.7.14, v3.7.15 and v3.7.16 fix twelve advisories against v3.7.13. Chart 41.7.1,
    the last 41.x chart, ships v3.7.14 only, and chart 42.1.1 is the first that ships v3.7.16
    (#1659). The chart takes the Traefik image from its appVersion, so the values set no image
    tag: a tag there could hold an older release than the chart."""
    application = yaml.safe_load(
        (REPO_ROOT / "k8s/argocd/apps/traefik.yaml").read_text(encoding="utf-8")
    )
    values = yaml.safe_load(
        (REPO_ROOT / "k8s/ingress/traefik-values.yaml").read_text(encoding="utf-8")
    )
    chart_source = next(source for source in application["spec"]["sources"] if "chart" in source)

    assert (
        chart_source["repoURL"],
        chart_source["chart"],
        Version(str(chart_source["targetRevision"])) >= TRAEFIK_FIRST_CHART_WITH_V3_7_16,
        values.get("image", {}).get("tag"),
    ) == ("https://traefik.github.io/charts", "traefik", True, None)


def test_no_ingress_routes_to_loki_in_the_logging_namespace() -> None:
    """loki-ingress sent host loki.<domain> on the Traefik web entry point to Loki in namespace
    logging, but the logging-default-perimeter policy admits port 3100 only from logging, from
    Grafana and the Alloy collectors in monitoring, and from the OpenTelemetry Collector in otel.
    It has no peer for Traefik, so each request failed. #1632 decided to keep the policy closed,
    for a Traefik peer would open the Loki API, with auth_enabled false, to each client that
    reaches Traefik, and delete the Ingress (#2439)."""
    names = {
        document["metadata"]["name"]
        for document in yaml.safe_load_all(
            (REPO_ROOT / "k8s/ingress/ingress-routes.yaml").read_text(encoding="utf-8")
        )
        if document and document.get("kind") == "Ingress"
    }

    assert "loki-ingress" not in names


def test_no_ingress_is_in_the_logging_namespace() -> None:
    """The logging-default-perimeter policy has no peer for Traefik, so an Ingress that routes to
    a Service in namespace logging would open the Loki API, with auth_enabled false, to each
    client that reaches Traefik (#1632). No Ingress under k8s/ is in namespace logging, so none
    routes to it (#2439)."""
    assert (
        sorted(
            f"{relative}:{document['metadata']['name']}"
            for relative, document in manifests()
            if document["kind"] == "Ingress" and document["metadata"].get("namespace") == "logging"
        )
        == []
    )


def _backend_services(node: Any) -> Iterator[str]:
    """The name of each Service that an Ingress backend names, at any depth."""
    if isinstance(node, list):
        for item in node:
            yield from _backend_services(item)
    elif isinstance(node, dict):
        service = node.get("service")
        if isinstance(service, dict) and service.get("name"):
            yield str(service["name"])
        for value in node.values():
            yield from _backend_services(value)


def test_no_ingress_routes_to_the_grafana_image_renderer() -> None:
    """Grafana calls the image renderer by the DNS name of its Service in namespace monitoring,
    and the renderer calls Grafana back by the Grafana Service (#5185). No Ingress names the
    Service of the renderer, so only the cluster reaches it. The Ingress of Grafana shows that
    the scan reads the backends."""
    routed = {
        name
        for _, document in manifests()
        if document["kind"] == "Ingress"
        for name in _backend_services(document.get("spec"))
    }

    assert ("grafana-image-renderer" in routed, "grafana" in routed) == (False, True)


# ── Service account tokens (#1652) ───────────────────────────────────────────
#
# Kubernetes mounts a token of the pod's ServiceAccount into each pod, unless the pod spec, or the
# ServiceAccount when the pod spec does not set it, has `automountServiceAccountToken: false`. A
# pod that does not call the API mounts no token. A pod keeps its token when a Role or ClusterRole
# binds its ServiceAccount, or when _TOKEN_EXCEPTIONS names it with a reason. The checks read files
# only and render no chart.

# What a pod does with its token: it mounts none, it mounts one that a role binds, or it mounts
# one that no role binds.
TokenUse = Literal["none", "bound", "unbound"]

# A Secret of this type holds a token of a ServiceAccount, which a pod can mount as a volume.
_TOKEN_SECRET_TYPE = "kubernetes.io/service-account-token"


@dataclass(frozen=True)
class TokenSite:
    """One pod that a chart makes, as `helm template` of the pinned chart shows.

    `mounts` tells, from the values, whether the chart makes the pod and the pod mounts a token.
    `role` names the Role or ClusterRole with rules that the chart binds to the pod's
    ServiceAccount, for a pod that calls the API.
    """

    pod: str
    mounts: Callable[[dict[str, Any]], bool]
    role: str = ""


def _when(*switches: tuple[str, bool]) -> Callable[[dict[str, Any]], bool]:
    """A pod that the chart makes when each switch is true, and that has no token value."""
    return lambda values: all(value_at(values, path, default) for path, default in switches)


def _token(
    path: str, default: bool, *switches: tuple[str, bool]
) -> Callable[[dict[str, Any]], bool]:
    """A pod that the chart makes when each switch is true, and that mounts the token unless the
    value at the path is false. Each value has the chart's default."""
    made = _when(*switches)
    return lambda values: made(values) and value_at(values, path, default) is not False


def _loki(values: dict[str, Any]) -> bool:
    """Loki chart 21.2.3 sets the field on the single binary pod from
    `singleBinary.automountServiceAccountToken`, or else from `defaults.automountServiceAccountToken`,
    which is true by default. The pod field wins over `serviceAccount.automountServiceAccountToken`,
    which counts only when neither value is a bool."""
    for path, default in (
        ("singleBinary.automountServiceAccountToken", None),
        ("defaults.automountServiceAccountToken", True),
    ):
        field = value_at(values, path, default)
        if isinstance(field, bool):
            return field
    return value_at(values, "serviceAccount.automountServiceAccountToken", True) is not False


def _gitea(values: dict[str, Any]) -> bool:
    """Gitea 12.7.0 runs as ServiceAccount `default` unless `serviceAccount.create` is true, and
    sets the token value only on the ServiceAccount that it makes."""
    own_account = value_at(values, "serviceAccount.create", False)
    return not (
        own_account
        and value_at(values, "serviceAccount.automountServiceAccountToken", False) is False
    )


def _alloy_collectors(values: dict[str, Any]) -> tuple[TokenSite, ...]:
    """Each k8s-monitoring Alloy collector. Alloy finds its targets, reads events and tails logs
    through the API, and the Alloy operator binds a ClusterRole of the collector's name."""
    collectors = value_at(values, "collectors", {}) or {}
    return tuple(
        TokenSite(f"collectors.{name}", _when(), f"ClusterRole k8s-monitoring-{name}")
        for name in collectors
    )


# The pods of each chart that an Application installs, with the values that make them and that
# turn their token off. A key is the chart name; a chart update does not change the table (owner,
# 2026-11-16, #6063). A callable entry reads the pods from the values. Argo CD runs the hook Jobs
# and never the test pods of a chart.
_CHART_TOKENS: dict[
    str, tuple[TokenSite, ...] | Callable[[dict[str, Any]], tuple[TokenSite, ...]]
] = {
    "argo-cd": (
        TokenSite(
            "application-controller",
            _token("controller.automountServiceAccountToken", True),
            "ClusterRole argocd-application-controller",
        ),
        TokenSite(
            "applicationset-controller",
            _token("applicationSet.automountServiceAccountToken", True),
            "Role argocd-applicationset-controller",
        ),
        TokenSite(
            "commit-server",
            _token(
                "commitServer.automountServiceAccountToken", False, ("commitServer.enabled", False)
            ),
        ),
        TokenSite(
            "dex",
            _token("dex.automountServiceAccountToken", True, ("dex.enabled", True)),
            "Role argocd-dex-server",
        ),
        TokenSite(
            "notifications",
            _token(
                "notifications.automountServiceAccountToken", True, ("notifications.enabled", True)
            ),
            "Role argocd-notifications-controller",
        ),
        TokenSite(
            "redis", _token("redis.automountServiceAccountToken", True, ("redis.enabled", True))
        ),
        TokenSite(
            "redis-secret-init",
            _when(("redisSecretInit.enabled", True)),
            "Role argocd-redis-secret-init",
        ),
        # The chart binds the Role argocd-repo-server, which has no rules.
        TokenSite("repo-server", _token("repoServer.automountServiceAccountToken", True)),
        TokenSite(
            "server",
            _token("server.automountServiceAccountToken", True),
            "ClusterRole argocd-server",
        ),
    ),
    "argo-workflows": (
        TokenSite("server", _when(("server.enabled", True)), "ClusterRole argo-workflows-server"),
        TokenSite("workflow-controller", _when(), "Role argo-workflows-workflow-controller"),
    ),
    "argocd-image-updater": (TokenSite("controller", _when(), "ClusterRole argocd-image-updater"),),
    # Each pod takes the token value of its ServiceAccount: the values leave the pod field unset.
    # The start-up check Job is a post-install hook, which Argo CD runs.
    "cert-manager": (
        TokenSite(
            "controller",
            _token("serviceAccount.automountServiceAccountToken", True),
            "ClusterRole cert-manager-controller-certificates",
        ),
        TokenSite(
            "webhook",
            _token("webhook.serviceAccount.automountServiceAccountToken", True),
            "ClusterRole cert-manager-webhook:subjectaccessreviews",
        ),
        TokenSite(
            "cainjector",
            _token(
                "cainjector.serviceAccount.automountServiceAccountToken",
                True,
                ("cainjector.enabled", True),
            ),
            "ClusterRole cert-manager-cainjector",
        ),
        TokenSite(
            "startupapicheck",
            _token(
                "startupapicheck.serviceAccount.automountServiceAccountToken",
                True,
                ("startupapicheck.enabled", True),
            ),
            "Role cert-manager-startupapicheck:create-cert",
        ),
    ),
    "cloudnative-pg": (TokenSite("cloudnative-pg", _when(), "ClusterRole cnpg-cloudnative-pg"),),
    # Chart 4.8.4 mounts the token only for pod labels, pod UIDs or DRA, which the values leave off.
    "dcgm-exporter": (
        TokenSite("dcgm-exporter", _token("serviceAccount.automountServiceAccountToken", False)),
    ),
    "gitea": (TokenSite("gitea", _gitea),),
    # The dashboards sidecar lists the dashboard ConfigMaps.
    "grafana": (
        TokenSite("grafana", _token("automountServiceAccountToken", True), "Role grafana"),
        # The image renderer runs as ServiceAccount `default` and calls no API.
        TokenSite(
            "image-renderer",
            _token(
                "imageRenderer.automountServiceAccountToken",
                False,
                ("imageRenderer.enabled", False),
            ),
        ),
    ),
    "k8s-monitoring": lambda values: (
        TokenSite("alloy-operator", _when(), "ClusterRole k8s-monitoring-alloy-operator"),
        TokenSite(
            "kube-state-metrics",
            _when(("telemetryServices.kube-state-metrics.deploy", False)),
            "ClusterRole k8s-monitoring-kube-state-metrics",
        ),
        TokenSite(
            "node-exporter",
            _token(
                "telemetryServices.node-exporter.serviceAccount.automountServiceAccountToken",
                False,
                ("telemetryServices.node-exporter.deploy", False),
            ),
        ),
        TokenSite("add-finalizer", _when(), "Role k8s-monitoring-add-finalizer"),
        TokenSite(
            "remove-alloy-and-finalizer", _when(), "Role k8s-monitoring-remove-alloy-and-finalizer"
        ),
        *_alloy_collectors(values),
    ),
    # The chart binds the ClusterRole loki-clusterrole, which has no rules while the rules sidecar
    # is off. The canary and the gateway have token values of their own.
    "loki": (
        TokenSite("loki", _loki),
        TokenSite(
            "canary",
            _token("lokiCanary.automountServiceAccountToken", False, ("lokiCanary.enabled", True)),
        ),
        TokenSite(
            "gateway",
            _token("gateway.automountServiceAccountToken", False, ("gateway.enabled", True)),
        ),
    ),
    "mattermost-operator": (
        TokenSite("mattermost-operator", _when(), "ClusterRole mattermost-operator"),
    ),
    "open-webui": (
        TokenSite("open-webui", _token("serviceAccount.automountServiceAccountToken", False)),
    ),
    "opentelemetry-collector": (
        TokenSite("collector", _token("serviceAccount.automountServiceAccountToken", True)),
    ),
    # Chart 0.9.0 has no token value. The plugin watches ObjectStores and writes the Role of each
    # database through the API.
    "plugin-barman-cloud": (
        TokenSite("plugin-barman-cloud", _when(), "ClusterRole plugin-barman-cloud"),
    ),
    "prometheus-operator-crds": (),
    "prometheus": (
        TokenSite(
            "alertmanager",
            _token(
                "alertmanager.automountServiceAccountToken", True, ("alertmanager.enabled", True)
            ),
        ),
        TokenSite("kube-state-metrics", _when(("kube-state-metrics.enabled", True))),
        TokenSite("node-exporter", _when(("prometheus-node-exporter.enabled", True))),
        TokenSite("pushgateway", _when(("prometheus-pushgateway.enabled", True))),
        TokenSite("server", _when(), "ClusterRole prometheus-server"),
    ),
    # Storage v2 finds the members of the cluster through the API.
    "pyroscope": (TokenSite("pyroscope", _when(), "Role pyroscope-discovery"),),
    # Chart 1.20.0 has no token value.
    "qdrant": (TokenSite("qdrant", _when()),),
    "tempo": (TokenSite("tempo", _token("serviceAccount.automountServiceAccountToken", True)),),
    "traefik": (TokenSite("traefik", _when(), "ClusterRole traefik-kube-system"),),
}

# The pods that mount a ServiceAccount token that no role in the tree or in their chart binds,
# each with its reason. A key is `<values file>:<pod>` for a chart pod or
# `<manifest>:<kind>/<name>` for a manifest pod.
_TOKEN_EXCEPTIONS: dict[str, str] = {
    "k8s/llm/values-qdrant.yaml:qdrant": (
        "Qdrant does not call the API, but chart 1.20.0 sets automountServiceAccountToken on "
        "neither its pod nor its ServiceAccount and has no value for it. qdrant/qdrant-helm#506 "
        "asks for the value. Remove this entry when a chart release adds it."
    ),
}

# The pods that mounted a token they did not use before #1652, so that a reader that finds no pod
# cannot pass.
_EXPECTED_TOKENLESS_PODS = frozenset(
    {
        "k8s/argocd/values.yaml:redis",
        "k8s/argocd/values.yaml:repo-server",
        "k8s/cloudflared/deployment.yaml:Deployment/cloudflared",
        "k8s/gitea/values.yaml:gitea",
        "k8s/gpu-feature-discovery/daemonset.yaml:DaemonSet/gpu-feature-discovery",
        "k8s/llm/gateway/deployment.yaml:Deployment/llm-gateway",
        "k8s/llm/portkey/deployment.yaml:Deployment/portkey",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-16gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-24gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-32gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-48gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-24gib-embed-gpu0",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-24gib-embed-gpu1",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-64gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-72gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-96gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-128gib",
        "k8s/llm/valkey-runs.yaml:Deployment/valkey-runs",
        "k8s/llm/valkey.yaml:Deployment/valkey",
        "k8s/logging/loki-values.yaml:loki",
        "k8s/monitoring/grafana-values.yaml:image-renderer",
        "k8s/monitoring/prometheus-values.yaml:alertmanager",
        "k8s/otel/tempo-values.yaml:tempo",
        "k8s/otel/values.yaml:collector",
    }
)


def _holds_token(volume: dict[str, Any], token_secrets: frozenset[str]) -> bool:
    """Whether a volume holds a token: a projected `serviceAccountToken` source, or one of the
    token Secrets, as a Secret volume or a projected Secret source."""
    sources = value_at(volume, "projected.sources", []) or []
    return value_at(volume, "secret.secretName") in token_secrets or any(
        "serviceAccountToken" in source or value_at(source, "secret.name") in token_secrets
        for source in sources
    )


def mounts_token(
    pod: dict[str, Any], account: dict[str, Any] | None, token_secrets: frozenset[str] = frozenset()
) -> bool:
    """Whether a pod mounts a token of its ServiceAccount.

    A volume that holds a token gives the pod one whatever the field says. `token_secrets` names
    the Secrets of type kubernetes.io/service-account-token in the pod's namespace. Else the pod
    field wins, then the field of the ServiceAccount, and Kubernetes mounts the token when neither
    sets it."""
    if any(_holds_token(volume, token_secrets) for volume in pod.get("volumes") or []):
        return True
    if "automountServiceAccountToken" in pod:
        return pod["automountServiceAccountToken"] is not False
    return (account or {}).get("automountServiceAccountToken") is not False


def _chart_sites(chart: str, values: dict[str, Any]) -> tuple[TokenSite, ...]:
    """The pods of a chart for these values."""
    sites = _CHART_TOKENS[chart]
    return sites(values) if callable(sites) else sites


def _chart_token_use() -> dict[str, TokenUse]:
    """What each chart pod does with its token, keyed `<values file>:<pod>`."""
    return {
        f"{relative}:{site.pod}": (
            "none" if not site.mounts(values) else "bound" if site.role else "unbound"
        )
        for chart, relative, values in chart_values()
        for site in _chart_sites(chart, values)
    }


def _manifest_token_use() -> dict[str, TokenUse]:
    """What each manifest pod does with its token, keyed `<file>:<kind>/<name>`.

    A pod in a namespace runs as the ServiceAccount it names, or as `default`. A role binds it
    when a RoleBinding or ClusterRoleBinding under k8s/ names that ServiceAccount. A token Secret
    is a Secret under k8s/ of type kubernetes.io/service-account-token.
    """
    documents = list(manifests())
    accounts = {
        (document["metadata"].get("namespace"), document["metadata"]["name"]): document
        for _, document in documents
        if document["kind"] == "ServiceAccount"
    }
    token_secrets = {
        (document["metadata"].get("namespace"), document["metadata"]["name"])
        for _, document in documents
        if document["kind"] == "Secret" and document.get("type") == _TOKEN_SECRET_TYPE
    }
    bound = {
        (subject.get("namespace"), subject["name"])
        for _, document in documents
        if document["kind"] in {"RoleBinding", "ClusterRoleBinding"}
        for subject in document.get("subjects") or []
        if subject.get("kind") == "ServiceAccount"
    }
    use: dict[str, TokenUse] = {}
    for relative, document in documents:
        pod = pod_spec(document)
        if pod is None:
            continue
        namespace = document["metadata"].get("namespace")
        account = (namespace, pod.get("serviceAccountName", "default"))
        secrets = frozenset(name for space, name in token_secrets if space == namespace)
        use[f"{relative}:{document['kind']}/{document['metadata']['name']}"] = (
            "none"
            if not mounts_token(pod, accounts.get(account), secrets)
            else "bound"
            if account in bound
            else "unbound"
        )
    return use


@pytest.mark.parametrize(
    ("pod", "account", "mounts"),
    [
        ({}, None, True),
        ({}, {}, True),
        ({}, {"automountServiceAccountToken": False}, False),
        ({"automountServiceAccountToken": False}, None, False),
        ({"automountServiceAccountToken": False}, {"automountServiceAccountToken": True}, False),
        ({"automountServiceAccountToken": True}, {"automountServiceAccountToken": False}, True),
    ],
    ids=["no-account", "account-unset", "account-off", "pod-off", "pod-off-wins", "pod-on-wins"],
)
def test_the_pod_field_wins_over_the_service_account_field(
    pod: dict[str, Any], account: dict[str, Any] | None, mounts: bool
) -> None:
    """Pin the check on literal pods: Kubernetes reads the ServiceAccount only when the pod spec
    does not set the field."""
    assert mounts_token(pod, account) is mounts


@pytest.mark.parametrize(
    ("volume", "mounts"),
    [
        ({"projected": {"sources": [{"serviceAccountToken": {"path": "token"}}]}}, True),
        ({"secret": {"secretName": "robot-token"}}, True),
        ({"projected": {"sources": [{"secret": {"name": "robot-token"}}]}}, True),
        ({"secret": {"secretName": "robot-config"}}, False),
        ({"projected": {"sources": [{"configMap": {"name": "robot-token"}}]}}, False),
        ({"emptyDir": {}}, False),
    ],
    ids=[
        "projected-token",
        "token-secret",
        "projected-token-secret",
        "other-secret",
        "projected-config-map",
        "empty-dir",
    ],
)
def test_a_token_volume_mounts_a_token_when_the_field_is_off(
    volume: dict[str, Any], mounts: bool
) -> None:
    """Pin the check on literal pods: a projected `serviceAccountToken` source, or a Secret of type
    kubernetes.io/service-account-token, gives the pod a token that the API server accepts. The
    field `automountServiceAccountToken` does not stop it."""
    pod = {"automountServiceAccountToken": False, "volumes": [{"name": "token", **volume}]}

    assert mounts_token(pod, None, frozenset({"robot-token"})) is mounts


def test_the_chart_table_names_each_chart_that_an_application_pins() -> None:
    """A chart with no entry in _CHART_TOKENS could mount a token that no check sees, and an entry
    for a chart that no Application installs fails too."""
    assert sorted({chart for chart, _ in pinned_charts()} ^ _CHART_TOKENS.keys()) == []


def test_the_pods_that_do_not_call_the_api_mount_no_token() -> None:
    """Each pod that mounted a token it did not use before #1652 mounts none."""
    use = _manifest_token_use() | _chart_token_use()
    assert sorted(pod for pod in _EXPECTED_TOKENLESS_PODS if use.get(pod) != "none") == []


def test_every_manifest_pod_with_a_token_has_a_role_or_a_named_exception() -> None:
    """Each manifest pod mounts no token, or a role binds its ServiceAccount, or it is named."""
    assert (
        sorted(
            pod
            for pod, use in _manifest_token_use().items()
            if use == "unbound" and pod not in _TOKEN_EXCEPTIONS
        )
        == []
    )


def test_every_chart_pod_with_a_token_has_a_role_or_a_named_exception() -> None:
    """Each chart pod mounts no token, or the chart binds a role to it, or it is named."""
    assert (
        sorted(
            pod
            for pod, use in _chart_token_use().items()
            if use == "unbound" and pod not in _TOKEN_EXCEPTIONS
        )
        == []
    )


def test_every_exception_names_a_pod_with_a_token_that_no_role_binds() -> None:
    """An exception names a pod that the checks find, and that pod still mounts a token with no
    role. A stale entry, for a pod that has gone or that lost its token, would hide a later change.
    """
    use = _manifest_token_use() | _chart_token_use()
    assert (
        sorted(pod for pod in _TOKEN_EXCEPTIONS if use.get(pod) != "unbound"),
        sorted(pod for pod, reason in _TOKEN_EXCEPTIONS.items() if not reason.strip()),
    ) == ([], [])


# ── What the readers of the tree see (#1652) ─────────────────────────────────
#
# tests/support/k8s_tree.py reads the files under k8s/ and the values files of the Applications.
# Argo CD also takes chart values from options of the Application, and Kustomize changes objects
# with patches and transformers. The readers see none of these, so the tree uses only the options
# that leave the objects of a check as the files show them.

# The options of an Application source that the readers read, or that change no object.
_READ_CHART_SOURCE_OPTIONS = frozenset({"repoURL", "chart", "targetRevision", "helm"})
_READ_HELM_OPTIONS = frozenset({"valueFiles"})
_READ_PATH_SOURCE_OPTIONS = frozenset({"repoURL", "targetRevision", "path", "ref"})

# The keys of a kustomization that change no object that a check reads. A patch is read apart.
_READ_KUSTOMIZATION_KEYS = frozenset(
    {
        "apiVersion",
        "kind",
        "resources",
        "namespace",
        "configMapGenerator",
        "generatorOptions",
        "sortOptions",
        "patches",
    }
)

# The kinds that the checks of the tree read: the workloads, and the objects that give a pod its
# token, its role or its claim.
_CHECKED_KINDS = frozenset(POD_SPEC_PATHS) | {
    "ServiceAccount",
    "Secret",
    "RoleBinding",
    "ClusterRoleBinding",
    "PersistentVolumeClaim",
}


def unread_source_options(source: dict[str, Any]) -> list[str]:
    """The options of an Application source that change objects that the readers do not see."""
    chart = "chart" in source
    read = _READ_CHART_SOURCE_OPTIONS if chart else _READ_PATH_SOURCE_OPTIONS
    helm = (source.get("helm") or {}) if chart else {}
    return sorted(
        [option for option in source if option not in read]
        + [f"helm.{option}" for option in helm if option not in _READ_HELM_OPTIONS]
    )


def _patched_kinds(directory: Path, patch: dict[str, Any]) -> frozenset[str]:
    """The kinds that a patch changes: the kind of its target, or else the kind of each object in
    the patch. Empty for a patch whose kind the test cannot tell."""
    if kind := value_at(patch, "target.kind"):
        return frozenset({kind})
    text = patch.get("patch") or (directory / patch.get("path", "")).read_text(encoding="utf-8")
    documents = list(yaml.safe_load_all(text))
    if not documents or not all(isinstance(document, dict) for document in documents):
        return frozenset()
    kinds = {document.get("kind") for document in documents}
    return frozenset() if None in kinds else frozenset(kinds)


def unread_kustomization_keys(directory: Path, kustomization: dict[str, Any]) -> list[str]:
    """The keys of a kustomization that change objects that the readers do not see, and each
    patch of an object that a check reads or of a kind that the test cannot tell."""
    unread = [key for key in kustomization if key not in _READ_KUSTOMIZATION_KEYS]
    for patch_entry in kustomization.get("patches") or []:
        kinds = _patched_kinds(directory, patch_entry)
        if not kinds:
            unread.append("patch of no kind")
        unread.extend(f"patch of {kind}" for kind in sorted(kinds & _CHECKED_KINDS))
    return sorted(unread)


@pytest.mark.parametrize(
    ("source", "unread"),
    [
        ({"chart": "tempo", "helm": {"valueFiles": ["$values/k8s/otel/tempo-values.yaml"]}}, []),
        ({"chart": "argo-cd", "helm": {"valuesObject": {"redis": {}}}}, ["helm.valuesObject"]),
        ({"chart": "argo-cd", "helm": {"values": "redis: {}"}}, ["helm.values"]),
        ({"chart": "argo-cd", "helm": {"parameters": []}}, ["helm.parameters"]),
        ({"path": "k8s/llm", "targetRevision": "main"}, []),
        ({"path": "k8s/llm", "kustomize": {"patches": []}}, ["kustomize"]),
        ({"path": "k8s/llm", "helm": {"valueFiles": []}}, ["helm"]),
    ],
    ids=[
        "value-files",
        "values-object",
        "values",
        "parameters",
        "path",
        "path-kustomize",
        "path-helm",
    ],
)
def test_an_application_source_option_that_the_readers_do_not_see_is_named(
    source: dict[str, Any], unread: list[str]
) -> None:
    """Pin the check on literal sources: inline chart values and the options of a path source
    change objects that the readers do not see."""
    assert unread_source_options(source) == unread


@pytest.mark.parametrize(
    ("kustomization", "unread"),
    [
        (
            {"patches": [{"patch": "$patch: delete\nkind: Ingress\nmetadata: {name: web}\n"}]},
            [],
        ),
        (
            {"patches": [{"patch": "kind: Deployment\nmetadata: {name: valkey}\n"}]},
            ["patch of Deployment"],
        ),
        (
            {"patches": [{"target": {"kind": "ServiceAccount"}, "patch": "[]"}]},
            ["patch of ServiceAccount"],
        ),
        ({"patches": [{"target": {"name": "valkey"}, "patch": "[]"}]}, ["patch of no kind"]),
        ({"patchesStrategicMerge": ["valkey.yaml"]}, ["patchesStrategicMerge"]),
        ({"replacements": []}, ["replacements"]),
    ],
    ids=[
        "delete-ingress",
        "merge-deployment",
        "target-service-account",
        "target-no-kind",
        "strategic-merge",
        "replacements",
    ],
)
def test_a_kustomization_change_that_the_readers_do_not_see_is_named(
    kustomization: dict[str, Any], unread: list[str]
) -> None:
    """Pin the check on literal kustomizations: a patch of a workload, a ServiceAccount, a Secret,
    a binding or a claim changes an object that a check reads from its file."""
    assert unread_kustomization_keys(REPO_ROOT, kustomization) == unread


def test_the_readers_see_each_value_and_patch_that_reaches_a_checked_object() -> None:
    """Argo CD and Kustomize give a checked object nothing that the readers do not see: each
    chart source takes its values from its values files only, and no kustomization patches a
    checked object."""
    assert (
        sorted(
            f"{source.get('chart') or source.get('path')}: {option}"
            for source in application_sources()
            for option in unread_source_options(source)
        ),
        sorted(
            f"{relative}: {key}"
            for relative, document in manifests()
            if document["kind"] == "Kustomization"
            for key in unread_kustomization_keys((REPO_ROOT / relative).parent, document)
        ),
    ) == ([], [])


# =============================================================================
# Secret References and Table Alignment (#1322)
# =============================================================================

K8S_DIR = REPO_ROOT / "k8s"
TABLE_REFS = {secret.ref for secret in CLUSTER_SECRETS}


def _secret_references(node: Any) -> Iterator[str]:
    """Secret names a manifest or values document references, at any depth."""
    if isinstance(node, list):
        for item in node:
            yield from _secret_references(item)
        return
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        if key in ("secretKeyRef", "secretRef") and isinstance(value, dict) and value.get("name"):
            yield str(value["name"])
        elif str(key).lower().endswith("existingsecret") and isinstance(value, str) and value:
            yield value
        elif key == "secretName" and isinstance(value, str) and value:
            yield value
        else:
            yield from _secret_references(value)


def _values_namespaces() -> dict[str, str]:
    return {
        str(value.resolve()): release["namespace"]
        for releases in HELM_RELEASES_BY_STACK.values()
        for release in releases
        for value in release_values(release)
    }


@functools.cache
def yaml_documents(root: Path) -> tuple[tuple[Path, Any], ...]:
    """Every YAML document under root, parsed once with libyaml's safe loader."""
    return tuple(
        (path, document)
        for path in sorted(root.rglob("*.yaml"))
        for document in yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    )


def referenced_secrets(root: Path) -> set[str]:
    """`namespace/name` of every Secret a YAML file under root references."""
    values_namespaces = _values_namespaces()
    found: set[str] = set()
    for path, document in yaml_documents(root):
        names = set(_secret_references(document))
        metadata = document.get("metadata") if isinstance(document, dict) else None
        namespace = (metadata or {}).get("namespace") or values_namespaces.get(
            str(path.resolve()), "?"
        )
        found.update(f"{namespace}/{name}" for name in names)
    return found


def operator_generated_secrets(root: Path) -> set[str]:
    """`namespace/name` of the application Secret that CloudNativePG creates for each Cluster
    under root that names no `bootstrap.initdb.secret`: `<cluster>-app`, made at run time."""
    found: set[str] = set()
    for _path, document in yaml_documents(root):
        if not isinstance(document, dict) or document.get("kind") != "Cluster":
            continue
        if not str(document.get("apiVersion", "")).startswith("postgresql.cnpg.io/"):
            continue
        initdb = document.get("spec", {}).get("bootstrap", {}).get("initdb", {})
        if "secret" not in initdb:
            metadata = document["metadata"]
            found.add(f"{metadata['namespace']}/{metadata['name']}-app")
    return found


def test_every_secret_referenced_under_k8s_has_a_table_row() -> None:
    """The table holds every Secret that a push writes. The application Secret of a CloudNativePG
    Cluster that names no secret is the operator's to create, so it has no row (#1635)."""
    references = referenced_secrets(K8S_DIR) - operator_generated_secrets(K8S_DIR)
    assert (references - TABLE_REFS, len(references) >= 5) == (set(), True)


def _secret_key_references(node: Any) -> Iterator[tuple[str, str]]:
    """`(Secret name, key)` of every `secretKeyRef` in a document, at any depth."""
    if isinstance(node, list):
        for item in node:
            yield from _secret_key_references(item)
    elif isinstance(node, dict):
        ref = node.get("secretKeyRef")
        if isinstance(ref, dict) and ref.get("name") and ref.get("key"):
            yield str(ref["name"]), str(ref["key"])
        for value in node.values():
            yield from _secret_key_references(value)


def test_every_secret_key_that_a_manifest_reads_from_a_table_secret_is_a_table_entry() -> None:
    """A pod that reads a key of a Secret of the table reads a key that the push writes. Without
    the key, the pod cannot start (#4354)."""
    keys = {secret.ref: {entry.key for entry in secret.entries} for secret in CLUSTER_SECRETS}
    missing: set[str] = set()
    read = 0
    for _path, document in yaml_documents(K8S_DIR):
        namespace = ((document or {}).get("metadata") or {}).get("namespace")
        for name, key in _secret_key_references(document):
            ref = f"{namespace}/{name}"
            if ref in keys:
                read += 1
                if key not in keys[ref]:
                    missing.add(f"{ref} {key}")
    assert (missing, read >= 3) == (set(), True)


def test_only_a_cluster_without_an_initdb_secret_has_an_operator_generated_secret(
    tmp_path: Path,
) -> None:
    (tmp_path / "databases.yaml").write_text(
        "apiVersion: postgresql.cnpg.io/v1\nkind: Cluster\n"
        "metadata: {name: generated, namespace: tools}\n"
        "spec: {bootstrap: {initdb: {database: d, owner: o}}}\n"
        "---\n"
        "apiVersion: postgresql.cnpg.io/v1\nkind: Cluster\n"
        "metadata: {name: pushed, namespace: tools}\n"
        "spec: {bootstrap: {initdb: {database: d, owner: o, secret: {name: pushed}}}}\n",
        encoding="utf-8",
    )
    assert operator_generated_secrets(tmp_path) == {"tools/generated-app"}


def test_a_reference_without_a_row_fails_the_guard(tmp_path: Path) -> None:
    (tmp_path / "values.yaml").write_text(
        "metadata: {namespace: tools}\nfooExistingSecret: unlisted\n"
        "env: [{valueFrom: {secretKeyRef: {name: also-unlisted, key: k}}}]\n"
        "extraSecretMounts: [{secretName: mounted-unlisted}]\n",
        encoding="utf-8",
    )
    assert referenced_secrets(tmp_path) - TABLE_REFS == {
        "tools/unlisted",
        "tools/also-unlisted",
        "tools/mounted-unlisted",
    }


def test_keyring_sources_are_managed_keys_or_declared_keyring_only() -> None:
    sources = [
        source
        for secret in CLUSTER_SECRETS
        for entry in secret.entries
        for source in keyring_sources(entry)
    ]
    managed = set(keyring_names().values())
    assert (
        all(keyring_names()[s.option] == s.key for s in sources if s.option),
        {s.key for s in sources if not s.option} == keyring_only_keys(),
        keyring_only_keys() & managed,
        keyring_only_keys(),
    ) == (
        True,
        True,
        frozenset(),
        frozenset(
            {
                LLM_GATEWAY_MASTER_KEY,
                DEVOPS_CACHE_VALKEY_AUTH_KEY,
                MATTERMOST_DB_AUTH_KEY,
                SEARXNG_SERVER_KEY,
                GRAFANA_RENDERER_AUTH_KEY,
                GRAFANA_SECURITY_KEY,
            }
        ),
    )


def test_env_name_keys_of_devops_cli_feed_their_options() -> None:
    devops_cli = next(s for s in CLUSTER_SECRETS if s.ref == "devops/devops-cli")
    option_keys = [e.key for e in devops_cli.entries if e.key.startswith("DEVOPS_CLI_")]
    option_of = {variable: key for key, variable in option_env_vars().items()}
    assert {key: option_of.get(key) for key in option_keys} == {
        "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY": "service.github_app.private_key",
        "DEVOPS_CLI_AI_API_KEY": "ai.api_key",
        "DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS": "service.webhook_secrets",
        "DEVOPS_CLI_FIRECRAWL_API_KEY": "firecrawl.api_key",
        "DEVOPS_CLI_VALKEY_PASSWORD": "valkey.password",
        "DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN": "mattermost.command_token",
        "DEVOPS_CLI_CRAWL4AI_API_TOKEN": "crawl4ai.api_token",
        "DEVOPS_CLI_MCP_STAGE_TOKEN": "mcp.stage_token",
        "DEVOPS_CLI_MCP_IMPLEMENT_TOKEN": "mcp.implement_token",
        "DEVOPS_CLI_QDRANT_API_KEY": "qdrant.api_key",
    }


def _manifest_workloads() -> set[str]:
    return {
        f"{str(document.get('kind', '')).lower()}/{document['metadata'].get('name')}"
        for _, document in yaml_documents(K8S_DIR)
        if isinstance(document, dict) and isinstance(document.get("metadata"), dict)
    }


# The workloads that a chart makes beside the one with the name of its release, each with its
# values file and the value that turns it on (#5185).
_CHART_WORKLOADS: dict[str, tuple[str, str]] = {
    "deployment/grafana-image-renderer": (
        "k8s/monitoring/grafana-values.yaml",
        "imageRenderer.enabled",
    ),
}


def _chart_workloads() -> set[str]:
    """The workloads of _CHART_WORKLOADS that the values turn on."""
    values = {relative: chart for _, relative, chart in chart_values()}
    return {
        workload
        for workload, (relative, switch) in _CHART_WORKLOADS.items()
        if value_at(values.get(relative), switch) is True
    }


def test_every_restart_target_is_a_manifest_workload_or_helm_release() -> None:
    releases = {r["name"] for rs in HELM_RELEASES_BY_STACK.values() for r in rs}
    targets = [w for secret in CLUSTER_SECRETS for w in secret.restarts]
    workloads = _manifest_workloads() | _chart_workloads()
    assert [str(t) for t in targets if str(t) not in workloads and t.name not in releases] == []


def test_each_chart_workload_is_a_restart_target() -> None:
    """An entry of _CHART_WORKLOADS that no Secret restarts, or that its values turn off, would
    let a wrong restart target pass."""
    targets = {str(w) for secret in CLUSTER_SECRETS for w in secret.restarts}
    assert sorted(_CHART_WORKLOADS.keys() - (_chart_workloads() & targets)) == []


@pytest.mark.usefixtures("keyring_store")
def test_no_table_secret_is_copied_back_by_sync(process_fake: Any) -> None:
    from devops_cli.k8s.credentials import sync_k8s_credentials
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        ["kubectl", "get", "secret"],
        ProcessAnswer(stdout=json.dumps({"data": {}})),
    )
    sync_k8s_credentials(stack="all", save_to_keyring=False)
    read = [
        f"{call.argv[5]}/{call.argv[3]}"
        for call in process_fake.calls
        if len(call.argv) >= 6 and call.argv[:3] == ("kubectl", "get", "secret")
    ]
    assert (set(read) & TABLE_REFS, bool(read)) == (set(), True)


def _readme_row(secret: Any, entry: Any) -> str:
    source = entry.source
    label = f"keyring `{source.key}`" if isinstance(source, KeyringSource) else source.label
    absent = "fail" if entry.required else "skip with a warning"
    if isinstance(source, KeyringSource):
        generator = entry.generator
        if generator is not None:
            body = (
                f"{generator.nbytes * 2} hex"
                if generator.encoding == "hex"
                else f"`token_urlsafe({generator.nbytes})`"
            )
            absent = (
                f"generate `{generator.prefix}` + {body}"
                if generator.prefix
                else f"generate {body}"
            )
        adopt = f"adopt from `{entry.adopt_from}`" if entry.adopt_from else "adopt the live value"
        absent = f"{adopt}; else {absent}"
    restarts = ", ".join(f"`{w}`" for w in secret.restarts) or "none"
    required = "yes" if entry.required else "no"
    cells = [f"`{secret.ref}`", f"`{entry.key}`", label, required, absent, secret.stack, restarts]
    return "| " + " | ".join(cells) + " |"


def test_readme_lists_the_table() -> None:
    readme = (K8S_DIR / "README.md").read_text(encoding="utf-8")
    rows = [_readme_row(s, e) for s in CLUSTER_SECRETS for e in s.entries]
    assert [row for row in rows if row not in readme] == []

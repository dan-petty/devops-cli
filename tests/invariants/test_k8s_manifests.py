"""Kubernetes manifest invariants: what the committed manifests under `k8s/` must hold."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest
import yaml
from packaging.version import Version

from tests.support.k8s_tree import (
    POD_SPEC_PATHS,
    application_sources,
    chart_values,
    manifests,
    pinned_charts,
    pod_spec,
    value_at,
)
from tests.support.paths import REPO_ROOT

# The Proxy Read Timeout of the Cloudflare edge, which only an Enterprise zone can change.
CLOUDFLARE_PROXY_READ_TIMEOUT_SECONDS = 125

# The first Ollama release that runs a multimodal embedding model, such as embeddinggemma-2,
# through llama-server, its runner on Linux. 0.40.0 ran that model on Apple MLX only (#2395).
OLLAMA_FIRST_LLAMA_SERVER_EMBEDDING_RELEASE = Version("0.40.4")

# The first Traefik chart that ships Traefik v3.7.16, the release that fixes every advisory
# published against v3.7.x up to GHSA-hrpp-p4fc-wwf8 (2026-10-21). The 41.x charts end at v3.7.14,
# so only chart 42 carries the later fixes (#1659).
TRAEFIK_FIRST_CHART_WITH_V3_7_16 = Version("42.1.1")


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
    repository, tag = next(iter(images)).split(":")
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


def test_loki_runs_the_grafana_community_chart_whose_loki_fixes_cve_2026_21729() -> None:
    """`grafana/loki` in grafana.github.io/helm-charts became the Grafana Enterprise Logs chart,
    and its newest version still runs Loki 3.6. CVE-2026-21729 affects Loki before 3.7.0: one
    `detected_fields` request with a very large limit makes Loki allocate memory until it stops.
    The open-source chart moved to grafana-community/helm-charts, and its 20.0.2 runs Loki 3.7.9
    (#1632). The Argo CD Application installs that chart from a repository that its project
    admits. The chart takes the Loki image from its appVersion, so the Application gives the
    chart the values file and no other value, and the values set no Loki image: `loki.image` and
    `singleBinary.image` can set an older tag or digest. The values keep no
    `monitoring.selfMonitoring`, which that chart removed in 9.0.0."""
    apps = REPO_ROOT / "k8s/argocd/apps"
    application = yaml.safe_load((apps / "loki.yaml").read_text(encoding="utf-8"))
    projects = {
        doc["metadata"]["name"]: doc["spec"]
        for doc in yaml.safe_load_all((apps / "projects.yaml").read_text(encoding="utf-8"))
        if doc
    }
    values = yaml.safe_load(
        (REPO_ROOT / "k8s/logging/loki-values.yaml").read_text(encoding="utf-8")
    )
    chart_source = next(source for source in application["spec"]["sources"] if "chart" in source)

    assert {
        "chart": (chart_source["repoURL"], chart_source["chart"], chart_source["targetRevision"]),
        "project admits the repository": chart_source["repoURL"]
        in projects[application["spec"]["project"]]["sourceRepos"],
        "helm": chart_source.get("helm"),
        "loki.image": values.get("loki", {}).get("image"),
        "singleBinary.image": values.get("singleBinary", {}).get("image"),
        "monitoring.selfMonitoring": values.get("monitoring", {}).get("selfMonitoring"),
    } == {
        "chart": ("https://grafana-community.github.io/helm-charts", "loki", "20.0.2"),
        "project admits the repository": True,
        "helm": {"valueFiles": ["$values/k8s/logging/loki-values.yaml"]},
        "loki.image": None,
        "singleBinary.image": None,
        "monitoring.selfMonitoring": None,
    }


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
    """Loki chart 20.0.2 sets the field on the single binary pod from
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
# turn their token off. A key is the chart and the version that the entry was read from, which is
# the version that the Application pins. A callable entry reads the pods from the values. Argo CD
# runs the hook Jobs and never the test pods of a chart.
_CHART_TOKENS: dict[
    tuple[str, str], tuple[TokenSite, ...] | Callable[[dict[str, Any]], tuple[TokenSite, ...]]
] = {
    ("argo-cd", "10.9.6"): (
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
    ("argo-workflows", "2.0.13"): (
        TokenSite("server", _when(("server.enabled", True)), "ClusterRole argo-workflows-server"),
        TokenSite("workflow-controller", _when(), "Role argo-workflows-workflow-controller"),
    ),
    ("argocd-image-updater", "1.3.1"): (
        TokenSite("controller", _when(), "ClusterRole argocd-image-updater"),
    ),
    # Chart 4.8.4 mounts the token only for pod labels, pod UIDs or DRA, which the values leave off.
    ("dcgm-exporter", "4.8.4"): (
        TokenSite("dcgm-exporter", _token("serviceAccount.automountServiceAccountToken", False)),
    ),
    ("gitea", "12.7.0"): (TokenSite("gitea", _gitea),),
    # The dashboards sidecar lists the dashboard ConfigMaps.
    ("grafana", "14.0.1"): (
        TokenSite("grafana", _token("automountServiceAccountToken", True), "Role grafana"),
    ),
    ("k8s-monitoring", "4.5.2"): lambda values: (
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
    ("loki", "20.0.2"): (
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
    ("open-webui", "16.6.0"): (
        TokenSite("open-webui", _token("serviceAccount.automountServiceAccountToken", False)),
    ),
    ("opentelemetry-collector", "0.175.0"): (
        TokenSite("collector", _token("serviceAccount.automountServiceAccountToken", True)),
    ),
    ("prometheus-operator-crds", "32.0.1"): (),
    ("prometheus", "29.35.0"): (
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
    ("pyroscope", "2.3.1"): (TokenSite("pyroscope", _when(), "Role pyroscope-discovery"),),
    # Chart 1.19.1 has no token value.
    ("qdrant", "1.19.1"): (TokenSite("qdrant", _when()),),
    ("tempo", "3.1.0"): (
        TokenSite("tempo", _token("serviceAccount.automountServiceAccountToken", True)),
    ),
    ("traefik", "42.1.3"): (TokenSite("traefik", _when(), "ClusterRole traefik-kube-system"),),
}

# The pods that mount a ServiceAccount token that no role in the tree or in their chart binds,
# each with its reason. A key is `<values file>:<pod>` for a chart pod or
# `<manifest>:<kind>/<name>` for a manifest pod.
_TOKEN_EXCEPTIONS: dict[str, str] = {
    "k8s/coredns/deployment-patch.yaml:Deployment/coredns": (
        "k3s makes the CoreDNS Deployment, its ServiceAccount coredns and the ClusterRoleBinding "
        "system:coredns, and CoreDNS reads Services and EndpointSlices through the API. The file "
        "patches only the resources of that Deployment, so the tree does not show the binding."
    ),
    "k8s/llm/values-qdrant.yaml:qdrant": (
        "Qdrant does not call the API, but chart 1.19.1 sets automountServiceAccountToken on "
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
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-48gib-slow",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-64gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-72gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-96gib",
        "k8s/llm/profiles/ollama-profiles.yaml:DaemonSet/ollama-128gib",
        "k8s/llm/valkey-runs.yaml:Deployment/valkey-runs",
        "k8s/llm/valkey.yaml:Deployment/valkey",
        "k8s/logging/loki-values.yaml:loki",
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
    """The pods of a chart for these values. The table names each chart at one version."""
    (sites,) = (sites for (name, _), sites in _CHART_TOKENS.items() if name == chart)
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


def test_the_chart_table_names_each_chart_at_the_version_that_an_application_pins() -> None:
    """A chart with no entry in _CHART_TOKENS could mount a token that no check sees. A chart
    release can move the value that sets the pod field, as Loki 20.0.2 did (#1632), so an entry
    names the version that it was read from. A chart bump fails here until the entry is read
    again from the new version, and an entry for a chart that no Application installs fails too.
    """
    assert sorted(pinned_charts() ^ _CHART_TOKENS.keys(), key=str) == []


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
    for patch in kustomization.get("patches") or []:
        kinds = _patched_kinds(directory, patch)
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

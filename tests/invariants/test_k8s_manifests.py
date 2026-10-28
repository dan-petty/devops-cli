"""Kubernetes manifest invariants: what the committed manifests under `k8s/` must hold."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import pytest
import yaml
from packaging.version import Version

from tests.support.k8s_tree import chart_values, manifests, pod_spec, value_at
from tests.support.paths import REPO_ROOT

# The Proxy Read Timeout of the Cloudflare edge, which only an Enterprise zone can change.
CLOUDFLARE_PROXY_READ_TIMEOUT_SECONDS = 125

# The first Ollama release that runs a multimodal embedding model, such as embeddinggemma-2,
# through llama-server, its runner on Linux. 0.40.0 ran that model on Apple MLX only (#2395).
OLLAMA_FIRST_LLAMA_SERVER_EMBEDDING_RELEASE = Version("0.40.4")


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
# binds its ServiceAccount, or when CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS names it with a
# reason. The checks read files only and render no chart.

# What a pod does with its token: it mounts none, it mounts one that a role binds, or it mounts
# one that no role binds.
TokenUse = Literal["none", "bound", "unbound"]


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
# turn their token off, read from the chart at the version the Application pins. A callable entry
# reads the pods from the values. Argo CD runs the hook Jobs and never the test pods of a chart.
CHART_TOKENS: dict[
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
    # Chart 4.8.4 mounts the token only for pod labels, pod UIDs or DRA, which the values leave off.
    "dcgm-exporter": (
        TokenSite("dcgm-exporter", _token("serviceAccount.automountServiceAccountToken", False)),
    ),
    "gitea": (TokenSite("gitea", _gitea),),
    # The dashboards sidecar lists the dashboard ConfigMaps.
    "grafana": (
        TokenSite("grafana", _token("automountServiceAccountToken", True), "Role grafana"),
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
    "open-webui": (
        TokenSite("open-webui", _token("serviceAccount.automountServiceAccountToken", False)),
    ),
    "opentelemetry-collector": (
        TokenSite("collector", _token("serviceAccount.automountServiceAccountToken", True)),
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
    # Chart 1.19.1 has no token value.
    "qdrant": (TokenSite("qdrant", _when()),),
    "tempo": (TokenSite("tempo", _token("serviceAccount.automountServiceAccountToken", True)),),
    "traefik": (TokenSite("traefik", _when(), "ClusterRole traefik-kube-system"),),
}

# The pods that mounted a token they did not use before #1652, so that a reader that finds no pod
# cannot pass.
EXPECTED_TOKENLESS_PODS = frozenset(
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


def mounts_token(pod: dict[str, Any], account: dict[str, Any] | None) -> bool:
    """Whether a pod mounts a token of its ServiceAccount: the pod field wins, then the field of
    the ServiceAccount, and Kubernetes mounts the token when neither sets it."""
    if "automountServiceAccountToken" in pod:
        return pod["automountServiceAccountToken"] is not False
    return (account or {}).get("automountServiceAccountToken") is not False


def _chart_sites(chart: str, values: dict[str, Any]) -> tuple[TokenSite, ...]:
    """The pods of a chart for these values."""
    sites = CHART_TOKENS[chart]
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
    when a RoleBinding or ClusterRoleBinding under k8s/ names that ServiceAccount.
    """
    documents = list(manifests())
    accounts = {
        (document["metadata"].get("namespace"), document["metadata"]["name"]): document
        for _, document in documents
        if document["kind"] == "ServiceAccount"
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
        account = (document["metadata"].get("namespace"), pod.get("serviceAccountName", "default"))
        use[f"{relative}:{document['kind']}/{document['metadata']['name']}"] = (
            "none"
            if not mounts_token(pod, accounts.get(account))
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


def test_every_chart_an_application_installs_states_its_pods() -> None:
    """A chart with no entry in CHART_TOKENS could mount a token that no check sees."""
    assert sorted({chart for chart, _, _ in chart_values()} - CHART_TOKENS.keys()) == []


def test_the_pods_that_do_not_call_the_api_mount_no_token() -> None:
    """Each pod that mounted a token it did not use before #1652 mounts none."""
    use = _manifest_token_use() | _chart_token_use()
    assert sorted(pod for pod in EXPECTED_TOKENLESS_PODS if use.get(pod) != "none") == []


def test_every_manifest_pod_with_a_token_has_a_role_or_a_named_exception() -> None:
    """Each manifest pod mounts no token, or a role binds its ServiceAccount, or it is named."""
    from devops_cli.config.constants import CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS

    assert (
        sorted(
            pod
            for pod, use in _manifest_token_use().items()
            if use == "unbound" and pod not in CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS
        )
        == []
    )


def test_every_chart_pod_with_a_token_has_a_role_or_a_named_exception() -> None:
    """Each chart pod mounts no token, or the chart binds a role to it, or it is named."""
    from devops_cli.config.constants import CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS

    assert (
        sorted(
            pod
            for pod, use in _chart_token_use().items()
            if use == "unbound" and pod not in CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS
        )
        == []
    )


def test_every_exception_names_a_pod_with_a_token_that_no_role_binds() -> None:
    """An exception names a pod that the checks find, and that pod still mounts a token with no
    role. A stale entry, for a pod that has gone or that lost its token, would hide a later change.
    """
    from devops_cli.config.constants import CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS

    use = _manifest_token_use() | _chart_token_use()
    assert (
        sorted(
            pod for pod in CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS if use.get(pod) != "unbound"
        ),
        sorted(
            pod
            for pod, reason in CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS.items()
            if not reason.strip()
        ),
    ) == ([], [])

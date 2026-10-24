"""Gitea, the homelab's internal forge and container registry (#1081).

Each test reads committed files only. It starts no program and reaches no cluster or network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from devops_cli.commands.k8s.networking import _resolve_stacks
from devops_cli.commands.k8s.stack_lifecycle import (
    _HELM_RELEASES_BY_STACK,
    _HELM_REPOS_BY_STACK,
    _KUSTOMIZATIONS_BY_STACK,
    _MANIFESTS_BY_STACK,
)
from devops_cli.config.constants import (
    CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK,
    CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER,
)
from devops_cli.config.defaults import DEFAULT_K8S_DIR
from devops_cli.k8s.cluster_secrets import DETACHED_STACKS
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
GITEA_DIR = K8S_DIR / "gitea"
APPS_DIR = K8S_DIR / "argocd" / "apps"
CHART_REPO = "https://dl.gitea.com/charts/"
CHART_VERSION = "12.7.0"
GITEA_VERSION = "1.27.3"
REPO_URL = "https://github.com/dan-petty/devops-cli"
IN_CLUSTER_HOST = "gitea-http.gitea.svc.cluster.local"
CLUSTER = "https://kubernetes.default.svc"
FINALIZERS = ["resources-finalizer.argocd.argoproj.io"]
LEAF_SYNC_POLICY = {
    "automated": {"enabled": True, "prune": True, "selfHeal": True},
    "retry": {
        "limit": 5,
        "backoff": {"duration": "5s", "factor": 2, "maxDuration": "3m"},
    },
}
KEEP = "Prune=false,Delete=false"
NOT_ON_THE_CONTROL_PLANE = {
    "nodeAffinity": {
        "requiredDuringSchedulingIgnoredDuringExecution": {
            "nodeSelectorTerms": [
                {
                    "matchExpressions": [
                        {"key": "node-role.kubernetes.io/control-plane", "operator": "DoesNotExist"}
                    ]
                }
            ]
        }
    }
}


def _yaml(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _documents(path: Path) -> list[dict[str, Any]]:
    return [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]


def _values() -> dict[str, Any]:
    return _yaml(GITEA_DIR / "values.yaml")


def _projects() -> dict[str, dict[str, Any]]:
    return {doc["metadata"]["name"]: doc["spec"] for doc in _documents(APPS_DIR / "projects.yaml")}


def _strings(node: Any) -> list[str]:
    """Every key and string value at any depth of a YAML document."""
    if isinstance(node, dict):
        return [s for key, value in node.items() for s in (str(key), *_strings(value))]
    if isinstance(node, list):
        return [s for item in node for s in _strings(item)]
    return [node] if isinstance(node, str) else []


# ── Argo CD and deploy-stack ─────────────────────────────────────────────────


def test_the_gitea_application_runs_the_pinned_chart_that_deploy_stack_installs() -> None:
    """One Helm source at an exact chart version, and the values file read from this repository
    at the revision every leaf Application tracks. The Application that runs Gitea never reads
    Gitea."""
    app = _yaml(APPS_DIR / "gitea.yaml")
    (release,) = _HELM_RELEASES_BY_STACK["gitea"]

    assert (
        app["metadata"]["finalizers"],
        app["spec"]["project"],
        app["spec"]["sources"],
        app["spec"]["destination"],
        app["spec"]["syncPolicy"],
        release,
        _HELM_REPOS_BY_STACK["gitea"],
    ) == (
        FINALIZERS,
        "homelab",
        [
            {
                "repoURL": CHART_REPO,
                "chart": "gitea",
                "targetRevision": CHART_VERSION,
                "helm": {"valueFiles": ["$values/k8s/gitea/values.yaml"]},
            },
            {"repoURL": REPO_URL, "targetRevision": "main", "ref": "values"},
        ],
        {"server": CLUSTER, "namespace": "gitea"},
        LEAF_SYNC_POLICY,
        {
            "name": "gitea",
            "chart": "gitea-charts/gitea",
            "namespace": "gitea",
            "values": str(DEFAULT_K8S_DIR / "gitea" / "values.yaml"),
            "version": CHART_VERSION,
        },
        {"gitea-charts": CHART_REPO},
    )


def test_the_gitea_manifests_application_renders_the_perimeter_deploy_stack_applies() -> None:
    app = _yaml(APPS_DIR / "gitea-manifests.yaml")

    assert (
        app["metadata"]["finalizers"],
        app["spec"]["project"],
        app["spec"]["source"],
        app["spec"]["destination"],
        app["spec"]["syncPolicy"],
        _yaml(GITEA_DIR / "kustomization.yaml")["resources"],
        _MANIFESTS_BY_STACK["gitea"],
        _KUSTOMIZATIONS_BY_STACK.get("gitea"),
    ) == (
        FINALIZERS,
        "homelab",
        {"repoURL": REPO_URL, "targetRevision": "main", "path": "k8s/gitea"},
        {"server": CLUSTER, "namespace": "gitea"},
        LEAF_SYNC_POLICY,
        ["networkpolicy.yaml"],
        [DEFAULT_K8S_DIR / "gitea" / "networkpolicy.yaml"],
        None,
    )


def test_the_projects_admit_the_chart_repository_and_the_gitea_namespace() -> None:
    """`homelab` holds both Gitea Applications. `homelab-system` holds Application `ingress`,
    which renders the Ingress of the git host in namespace `gitea`."""
    projects = _projects()
    gitea = {"server": CLUSTER, "namespace": "gitea"}

    assert (
        CHART_REPO in projects["homelab"]["sourceRepos"],
        gitea in projects["homelab"]["destinations"],
        gitea in projects["homelab-system"]["destinations"],
        {"group": "", "kind": "Secret", "name": "gitea-admin"}
        in projects["homelab"]["orphanedResources"]["ignore"],
    ) == (True, True, True, True)


def test_gitea_is_a_stack_of_its_own_that_stack_all_deploys() -> None:
    """Its rows are pushed only with stack `gitea` or `all`, so a deploy of another stack never
    needs the Gitea admin password. Its deploy also sets the git host on Application `ingress`."""
    assert (
        _resolve_stacks("gitea"),
        "gitea" in _resolve_stacks("all"),
        "gitea" in DETACHED_STACKS,
        CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK["gitea"],
    ) == (["gitea"], True, False, ("ingress",))


def test_the_gitea_namespace_enforces_restricted_pod_security_and_keeps_its_data() -> None:
    (namespace,) = [
        doc for doc in _documents(K8S_DIR / "namespaces.yaml") if doc["metadata"]["name"] == "gitea"
    ]
    labels = namespace["metadata"]["labels"]

    assert (
        {
            mode: labels[f"pod-security.kubernetes.io/{mode}"]
            for mode in ("enforce", "warn", "audit")
        },
        namespace["metadata"]["annotations"]["argocd.argoproj.io/sync-options"],
    ) == ({"enforce": "restricted", "warn": "restricted", "audit": "restricted"}, KEEP)


# ── Chart values ─────────────────────────────────────────────────────────────


def test_gitea_runs_one_pod_on_sqlite_in_wal_mode_with_no_bundled_service() -> None:
    """The bundled PostgreSQL and Valkey charts are Bitnami's, on `bitnamilegacy` images.
    `Recreate` never runs two pods on the one SQLite file, as the chart's RollingUpdate with
    `maxSurge: 100%` would."""
    values = _values()
    config = values["gitea"]["config"]

    assert (
        {
            name: values[name]["enabled"]
            for name in ("postgresql", "postgresql-ha", "valkey", "valkey-cluster")
        },
        values["replicaCount"],
        values["strategy"],
        config["database"],
        config["session"],
        config["cache"],
        config["queue"],
        "APP_DATA_PATH" in config["server"],
        "ROOT" in config.get("repository", {}),
    ) == (
        {"postgresql": False, "postgresql-ha": False, "valkey": False, "valkey-cluster": False},
        1,
        {"type": "Recreate"},
        {"DB_TYPE": "sqlite3", "SQLITE_JOURNAL_MODE": "WAL"},
        {"PROVIDER": "db"},
        {"ADAPTER": "memory"},
        {"TYPE": "level"},
        False,
        False,
    )


def test_gitea_keeps_its_data_on_a_claim_that_argo_cd_never_deletes() -> None:
    """A pod that mounts a local-path claim never runs on the control-plane node (#1634)."""
    values = _values()

    assert (values["persistence"], values["affinity"]) == (
        {
            "enabled": True,
            "create": True,
            "claimName": "gitea-shared-storage",
            "size": "10Gi",
            "storageClass": "local-path",
            "accessModes": ["ReadWriteOnce"],
            "annotations": {
                "helm.sh/resource-policy": "keep",
                "argocd.argoproj.io/sync-options": KEEP,
            },
        },
        NOT_ON_THE_CONTROL_PLANE,
    )


def test_gitea_is_a_locked_forge_with_its_container_registry_on() -> None:
    """Nobody registers or reads without signing in, a repository is private and only the API
    creates one, nothing reaches outside the cluster, and SSH is off: the rootless image would
    otherwise start its own SSH server on 2222. Packages are on: they hold the container
    registry."""
    config = _values()["gitea"]["config"]

    assert (
        config["service"],
        config["repository"],
        config["mirror"],
        config["actions"],
        config["packages"],
        {key: config["server"][key] for key in ("DISABLE_SSH", "START_SSH_SERVER", "OFFLINE_MODE")},
    ) == (
        {"DISABLE_REGISTRATION": True, "REQUIRE_SIGNIN_VIEW": True},
        {
            "DEFAULT_PRIVATE": "private",
            "ENABLE_PUSH_CREATE_USER": False,
            "ENABLE_PUSH_CREATE_ORG": False,
            "DISABLE_MIGRATIONS": True,
        },
        {"ENABLED": False},
        {"ENABLED": False},
        {"ENABLED": True},
        {"DISABLE_SSH": True, "START_SSH_SERVER": False, "OFFLINE_MODE": True},
    )


def test_gitea_builds_public_urls_from_each_request_and_its_values_name_no_domain() -> None:
    """`ROOT_URL` is the in-cluster address, which the pods and Argo CD use. A request through
    the tunnel arrives with its own host and `X-Forwarded-Proto: https`, and with
    `PUBLIC_URL_DETECTION = auto` Gitea builds that request's clone URLs and registry token
    realm from them. The chart renders no Ingress, and no value names the placeholder domain,
    which the Argo CD gate refuses in a values file (#1290, #1343)."""
    values = _values()
    server = values["gitea"]["config"]["server"]

    assert (
        {key: server[key] for key in ("DOMAIN", "ROOT_URL", "PUBLIC_URL_DETECTION")},
        values["ingress"],
        values["service"],
        [s for s in _strings(values) if CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER in s.lower()],
    ) == (
        {
            "DOMAIN": IN_CLUSTER_HOST,
            "ROOT_URL": f"http://{IN_CLUSTER_HOST}:3000/",
            "PUBLIC_URL_DETECTION": "auto",
        },
        {"enabled": False},
        {"http": {"type": "ClusterIP", "port": 3000}},
        [],
    )


def test_gitea_runs_rootless_and_non_root_with_a_read_only_root_and_bounded_resources() -> None:
    """The security contexts follow the gateway's (k8s/llm/gateway/deployment.yaml). The chart's
    connection test pod stays out of the render: it runs `busybox:latest` with no security
    context."""
    values = _values()

    assert (
        values["image"],
        values["podSecurityContext"],
        values["containerSecurityContext"],
        values["resources"],
        values["test"],
    ) == (
        {"tag": GITEA_VERSION, "rootless": True},
        {
            "runAsNonRoot": True,
            "runAsUser": 1000,
            "runAsGroup": 1000,
            "fsGroup": 1000,
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
        {"requests": {"cpu": "100m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "1Gi"}},
        {"enabled": False},
    )


def test_the_admin_comes_from_the_pushed_secret_with_no_password_in_git() -> None:
    """Each start sets the admin's password to the Secret's, so a pushed rotation takes effect
    when push-secrets restarts Gitea."""
    admin = _values()["gitea"]["admin"]

    assert admin == {"existingSecret": "gitea-admin", "passwordMode": "keepUpdated"}


# ── The git host ─────────────────────────────────────────────────────────────


def test_the_git_host_routes_through_traefik_to_the_http_service_with_no_tls() -> None:
    """TLS ends at Cloudflare. deploy-stack sets the configured domain on the host (#1290)."""
    (ingress,) = [
        doc
        for doc in _documents(K8S_DIR / "ingress" / "ingress-routes.yaml")
        if doc["kind"] == "Ingress" and doc["metadata"]["namespace"] == "gitea"
    ]

    assert (
        ingress["metadata"]["name"],
        ingress["metadata"]["annotations"],
        ingress["spec"],
    ) == (
        "gitea-ingress",
        {"traefik.ingress.kubernetes.io/router.entrypoints": "web"},
        {
            "ingressClassName": "traefik",
            "rules": [
                {
                    "host": "git.example.com",
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {"name": "gitea-http", "port": {"number": 3000}}
                                },
                            }
                        ]
                    },
                }
            ],
        },
    )

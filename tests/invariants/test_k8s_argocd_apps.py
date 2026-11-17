"""Tests for Argo CD application manifests, GitOps topology, data safety, and domain overlays."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from devops_cli.commands.k8s import stack_lifecycle
from devops_cli.commands.k8s.stack_lifecycle import (
    HELM_RELEASES_BY_STACK,
    KUSTOMIZATIONS_BY_STACK,
    MANIFESTS_BY_STACK,
    StackRelease,
)
from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS
from tests.support.k8s_tree import TREE, release_values
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
ARGOCD_DIR = K8S_DIR / "argocd"
APPS_DIR = ARGOCD_DIR / "apps"
BOOTSTRAP_DIR = ARGOCD_DIR / "bootstrap"
FINALIZER = "resources-finalizer.argocd.argoproj.io"
_PRE_POST_DELETE_JQ = (
    '.metadata.finalizers[] | select(startswith("pre-delete-finalizer.argocd.argoproj.io") '
    'or startswith("post-delete-finalizer.argocd.argoproj.io"))'
)


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else {}


def _all_applications() -> dict[str, dict[str, Any]]:
    apps: dict[str, dict[str, Any]] = {
        "bootstrap": _load_yaml(BOOTSTRAP_DIR / "bootstrap.yaml"),
        "cluster": _load_yaml(BOOTSTRAP_DIR / "cluster.yaml"),
    }
    for p in sorted(APPS_DIR.glob("*.yaml")):
        if p.name == "projects.yaml":
            continue
        data = _load_yaml(p)
        apps[data["metadata"]["name"]] = data
    return apps


# ── Applications & Topology ──────────────────────────────────────────────────


def _assert_helm_app_matches_release(app: dict[str, Any], release: StackRelease, name: str) -> None:
    # cert-manager publishes its chart versions with a leading `v` (v1.21.3).
    semver_re = re.compile(r"^v?\d+\.\d+\.\d+$")
    sources = app.get("spec", {}).get("sources", [])
    helm_sources = [s for s in sources if "chart" in s]
    assert len(helm_sources) == 1, f"{name} expected 1 Helm source"
    h = helm_sources[0]

    target_rev = str(h["targetRevision"])
    assert semver_re.match(target_rev), f"{name} helm version {target_rev} not pinned semver"

    expected_chart_name = release["chart"].split("/")[-1]
    assert h["chart"] == expected_chart_name
    assert app["spec"]["destination"]["namespace"] == release["namespace"]

    # The chart gets the same values files in the same order from Argo CD and from deploy-stack.
    value_files = h.get("helm", {}).get("valueFiles", [])
    expected = [
        f"$values/{value.relative_to(REPO_ROOT).as_posix()}" for value in release_values(release)
    ]
    assert value_files == expected, name


def _kustomization_manifest_files(kust_dir: Path) -> list[Path]:
    """Find all concrete manifest files referenced by a kustomization recursively."""
    kust_file = kust_dir / "kustomization.yaml"
    if not kust_file.is_file():
        return []
    doc = yaml.safe_load(kust_file.read_text(encoding="utf-8")) or {}
    files: list[Path] = []
    for res in doc.get("resources", []):
        res_path = (kust_dir / res).resolve()
        if res_path.is_file():
            files.append(res_path)
        elif res_path.is_dir() and (res_path / "kustomization.yaml").is_file():
            files.extend(_kustomization_manifest_files(res_path))
    return files


def test_helm_sources_pinned_versions() -> None:
    apps = _all_applications()
    helm_releases_map: dict[str, StackRelease] = {
        r["name"]: r for releases in HELM_RELEASES_BY_STACK.values() for r in releases
    }

    for name, expected in helm_releases_map.items():
        assert name in apps, f"Missing Helm app {name}"
        _assert_helm_app_matches_release(apps[name], expected, name)


def test_every_application_in_argocd_apps_maps_to_deploy_stack_counterpart() -> None:
    """Every Application in k8s/argocd/apps maps to a deploy-stack counterpart (#1675).

    Each chart maps to a release with the same chart, namespace and values files, and each path maps
    to a deploy-stack manifest list or kustomization. argocd-image-updater is the only allowed
    exception (docs/CLUSTER.md, Service Image Updates; task-1485).
    """
    helm_releases_map: dict[str, StackRelease] = {
        r["name"]: r for releases in HELM_RELEASES_BY_STACK.values() for r in releases
    }
    post_helm_by_stack: dict[str, tuple[Path, ...]] = getattr(
        stack_lifecycle, "POST_HELM_BY_STACK", {}
    )
    post_helm = [
        *(TREE.path(p).resolve() for paths in post_helm_by_stack.values() for p in paths),
        *(
            (TREE.path("devops") / p).resolve()
            for paths in stack_lifecycle.PRODUCT_POST_HELM_BY_STACK.values()
            for p in paths
        ),
    ]
    deploy_stack_kustomizations = {
        (REPO_ROOT / "k8s").resolve(),
        *((REPO_ROOT / "k8s" / k).resolve() for ks in KUSTOMIZATIONS_BY_STACK.values() for k in ks),
        *(p for p in post_helm if p.is_dir()),
    }
    manifest_paths = [
        *(TREE.path(p).resolve() for ms in MANIFESTS_BY_STACK.values() for p in ms),
        *(
            (TREE.path("devops") / p).resolve()
            for ms in stack_lifecycle.PRODUCT_MANIFESTS_BY_STACK.values()
            for p in ms
        ),
    ]
    # A manifest path that is a directory is applied with `kubectl apply -k`, so it applies the
    # files its kustomization lists.
    deploy_stack_manifests = {
        *(p for p in manifest_paths if p.is_file()),
        *(f for p in manifest_paths if p.is_dir() for f in _kustomization_manifest_files(p)),
        *(p for p in post_helm if p.is_file()),
    }

    for app_path_file in sorted(APPS_DIR.glob("*.yaml")):
        if app_path_file.name == "projects.yaml":
            continue
        app = _load_yaml(app_path_file)
        name = app["metadata"]["name"]
        if name == "argocd-image-updater":
            continue

        spec = app["spec"]
        if "sources" in spec:
            assert name in helm_releases_map, f"{name} has no deploy-stack release"
            _assert_helm_app_matches_release(app, helm_releases_map[name], name)
        elif "source" in spec and "path" in spec["source"]:
            target_path = (REPO_ROOT / spec["source"]["path"]).resolve()
            if target_path in deploy_stack_kustomizations:
                continue
            manifests = _kustomization_manifest_files(target_path)
            assert manifests, f"{name} path {target_path} contains no manifests"
            missing = [
                m.relative_to(REPO_ROOT).as_posix()
                for m in manifests
                if m not in deploy_stack_manifests
            ]
            assert not missing, f"{name} manifests missing from deploy-stack: {missing}"

    llm_app = _load_yaml(APPS_DIR / "llm.yaml")
    assert llm_app["spec"]["syncPolicy"].get("syncOptions") == ["SkipDryRunOnMissingResource=true"]


def test_finalizers_on_applications() -> None:
    apps = _all_applications()
    no_finalizer_apps = {"bootstrap", "cluster", "argocd"}

    for name, app in apps.items():
        finalizers = app.get("metadata", {}).get("finalizers", [])
        if name in no_finalizer_apps:
            assert FINALIZER not in finalizers, f"{name} must not have {FINALIZER}"
        else:
            assert FINALIZER in finalizers, f"{name} must have {FINALIZER}"


# ── Data Safety ──────────────────────────────────────────────────────────────


def test_chart_pvc_and_crd_safety_values() -> None:
    grafana_val = _load_yaml(K8S_DIR / "monitoring" / "grafana-values.yaml")
    grafana_opts = grafana_val["persistence"]["annotations"]["argocd.argoproj.io/sync-options"]
    assert ("Prune=false" in grafana_opts, "Delete=false" in grafana_opts) == (
        True,
        True,
    )
    assert grafana_val.get("admin", {}).get("existingSecret") == "grafana-admin"
    assert "adminPassword" not in grafana_val.get("admin", {})

    prom_val = _load_yaml(K8S_DIR / "monitoring" / "prometheus-values.yaml")
    prom_opts = prom_val["server"]["persistentVolume"]["annotations"][
        "argocd.argoproj.io/sync-options"
    ]
    assert ("Prune=false" in prom_opts, "Delete=false" in prom_opts) == (True, True)

    webui_val = _load_yaml(K8S_DIR / "llm" / "values-open-webui.yaml")
    webui_opts = webui_val["persistence"]["annotations"]["argocd.argoproj.io/sync-options"]
    assert ("Prune=false" in webui_opts, "Delete=false" in webui_opts) == (True, True)

    loki_val = _load_yaml(K8S_DIR / "logging" / "loki-values.yaml")
    assert loki_val["singleBinary"]["persistence"]["enableStatefulSetAutoDeletePVC"] is False

    argocd_val = _load_yaml(K8S_DIR / "argocd" / "values.yaml")
    crd_opts = argocd_val["crds"]["annotations"]["argocd.argoproj.io/sync-options"]
    assert (
        "ServerSideApply=true" in crd_opts,
        "Prune=false" in crd_opts,
        "Delete=false" in crd_opts,
    ) == (
        True,
        True,
        True,
    )


# ── Deploy-time homelab values (#1290) ───────────────────────────────────────


def test_the_app_of_apps_keeps_the_hosts_deploy_stack_sets_on_the_homelab_applications() -> None:
    """`cluster` leaves the Kustomize overrides of the homelab Applications to deploy-stack,
    and leaves pre/post-delete finalizers to Argo CD (#1674)."""
    from devops_cli.config.constants import (
        CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS as HOMELAB_APPLICATIONS,
    )

    spec = _load_yaml(BOOTSTRAP_DIR / "cluster.yaml")["spec"]
    assert (
        spec.get("ignoreDifferences"),
        "RespectIgnoreDifferences=true" in spec["syncPolicy"].get("syncOptions", []),
    ) == (
        [
            {
                "group": "argoproj.io",
                "kind": "Application",
                "name": name,
                "namespace": "argocd",
                "jsonPointers": ["/spec/source/kustomize"],
            }
            for name in HOMELAB_APPLICATIONS
        ]
        + [
            {
                "group": "argoproj.io",
                "kind": "Application",
                "jqPathExpressions": [_PRE_POST_DELETE_JQ],
            }
        ],
        True,
    )


def test_the_app_of_apps_applies_the_homelab_applications_server_side() -> None:
    """A sync of `cluster` keeps the overrides on the homelab Applications with any sync options.

    Client-side apply deletes a field that the last-applied annotation holds and git does not,
    and `RespectIgnoreDifferences` writes the overrides into that annotation. So a manual sync
    without the option deleted them, and every public host returned 404 (#1817). Server-side
    apply deletes only the fields of its own field manager, and the overrides belong to
    deploy-stack's `kubectl-patch` and to Image Updater. The migration manager moves the fields
    of the controller's client-side apply entry into its server-side apply entry, so a field
    that git removes from these Applications also leaves the cluster.
    """
    from devops_cli.config.constants import (
        CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS as HOMELAB_APPLICATIONS,
    )

    annotations = {
        name: app["metadata"].get("annotations") or {} for name, app in _all_applications().items()
    }
    server_side = sorted(
        name
        for name, values in annotations.items()
        if "ServerSideApply=true" in values.get("argocd.argoproj.io/sync-options", "").split(",")
    )
    assert (
        server_side,
        annotations["cluster"].get("argocd.argoproj.io/client-side-apply-migration-manager"),
    ) == (sorted(HOMELAB_APPLICATIONS), "argocd-controller")


def test_no_homelab_application_sets_kustomize_overrides_in_git() -> None:
    """Git leaves the field to deploy-stack, so the two never contend for it."""
    from devops_cli.config.constants import (
        CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS as HOMELAB_APPLICATIONS,
    )

    apps = _all_applications()
    assert [
        name for name in HOMELAB_APPLICATIONS if "kustomize" in apps[name]["spec"]["source"]
    ] == []


def test_deploy_stack_installs_the_barman_cloud_plugin_after_the_operator_and_cert_manager() -> (
    None
):
    """The plugin chart renders a cert-manager Issuer and Certificates, and the plugin must run in
    the namespace of the CloudNativePG operator. So stack `infra` installs it after both, in
    `cnpg-system`, and no other stack lists the three releases (#4764)."""
    releases = {
        stack: [release["name"] for release in stack_releases]
        for stack, stack_releases in HELM_RELEASES_BY_STACK.items()
    }
    namespaces = {
        release["name"]: release["namespace"]
        for stack_releases in HELM_RELEASES_BY_STACK.values()
        for release in stack_releases
    }
    infra = releases["infra"]
    elsewhere = {name for stack, names in releases.items() if stack != "infra" for name in names}

    assert (
        infra.index("cloudnative-pg") < infra.index("plugin-barman-cloud"),
        infra.index("cert-manager") < infra.index("plugin-barman-cloud"),
        namespaces["cert-manager"],
        namespaces["plugin-barman-cloud"] == namespaces["cloudnative-pg"],
        elsewhere & {"cloudnative-pg", "cert-manager", "plugin-barman-cloud"},
    ) == (True, True, "cert-manager", True, set())


def test_cert_manager_keeps_its_crds_and_its_leader_election_in_its_namespace() -> None:
    """The chart installs the CRDs and keeps them when the release goes. The leader election
    lease stays in namespace cert-manager, so the chart writes no Role in kube-system (#4764)."""
    values = _load_yaml(K8S_DIR / "cert-manager" / "values.yaml")

    assert (values["crds"], values["global"]["leaderElection"]["namespace"]) == (
        {"enabled": True, "keep": True},
        "cert-manager",
    )


def test_mattermost_operator_run_as_user() -> None:
    """k8s/mattermost/mattermost-operator-values.yaml sets numeric runAsUser and runAsGroup (#2932)."""
    values = _load_yaml(K8S_DIR / "mattermost" / "mattermost-operator-values.yaml")
    pod_sec = values.get("podSecurityContext", {})
    assert pod_sec.get("runAsNonRoot") is True
    assert pod_sec.get("runAsUser") == 65532
    assert pod_sec.get("runAsGroup") == 65532


def test_mattermost_container_security_context() -> None:
    """k8s/mattermost/mattermost.yaml sets containerSecurityContext for restricted PodSecurity (#2937)."""
    doc = _load_yaml(K8S_DIR / "mattermost" / "mattermost.yaml")
    pod_template = doc.get("spec", {}).get("podTemplate", {})
    csc = pod_template.get("containerSecurityContext", {})
    assert csc.get("allowPrivilegeEscalation") is False
    assert csc.get("capabilities", {}).get("drop") == ["ALL"]


def test_mattermost_namespaces_in_namespaces_yaml() -> None:
    """k8s/namespaces.yaml declares mattermost, cnpg-system, mattermost-operator and cert-manager with restricted Pod Security."""
    docs = [
        d
        for d in yaml.safe_load_all((K8S_DIR / "namespaces.yaml").read_text(encoding="utf-8"))
        if d
    ]
    by_name = {d["metadata"]["name"]: d for d in docs if d.get("kind") == "Namespace"}
    for ns_name in ("mattermost", "cnpg-system", "mattermost-operator", "cert-manager"):
        assert ns_name in by_name, f"Missing namespace {ns_name} in k8s/namespaces.yaml"
        labels = by_name[ns_name]["metadata"].get("labels", {})
        assert labels.get("pod-security.kubernetes.io/enforce") == "restricted"
        assert labels.get("pod-security.kubernetes.io/warn") == "restricted"
        assert labels.get("pod-security.kubernetes.io/audit") == "restricted"
        annos = by_name[ns_name]["metadata"].get("annotations", {})
        assert annos.get("argocd.argoproj.io/sync-options") == "Prune=false,Delete=false"


_NOTIFICATIONS_SECRET = "argocd-notifications-secret"


def _notifier(notifiers: dict[str, Any], name: str) -> Any:
    """The settings of a notifier, parsed from the string that the ConfigMap holds."""
    assert isinstance(notifiers[name], str), name
    return yaml.safe_load(notifiers[name])


def test_argocd_github_notifier_reads_the_keys_of_the_secret_push() -> None:
    """Each `$key` of a notifier is a key that the push writes and the README lists (#3779)."""
    notifiers = _load_yaml(K8S_DIR / "argocd" / "values.yaml")["notifications"]["notifiers"]
    assert _notifier(notifiers, "service.github") == {
        "appID": "$github-appID",
        "installationID": "$github-installationID",
        "privateKey": "$github-privateKey",
    }
    read = set(re.findall(r"\$([\w-]+)", "\n".join(notifiers.values())))
    pushed = {
        entry.key
        for secret in CLUSTER_SECRETS
        if (secret.namespace, secret.name) == ("argocd", _NOTIFICATIONS_SECRET)
        for entry in secret.entries
    }
    required = {
        entry.key
        for secret in CLUSTER_SECRETS
        if (secret.namespace, secret.name) == ("argocd", _NOTIFICATIONS_SECRET)
        for entry in secret.entries
        if entry.required
    }
    readme = (K8S_DIR / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(rf"\| `argocd/{_NOTIFICATIONS_SECRET}` \| `([\w-]+)` \|", readme))
    assert read == {
        "mattermost-deploys-url",
        "github-appID",
        "github-installationID",
        "github-privateKey",
    }
    assert read <= pushed
    assert read <= listed
    # The engine builds every notifier together: one that lacks a key fails them all (#3779).
    assert {"github-appID", "github-installationID", "github-privateKey"} <= required


def test_argocd_notifications_no_leaked_identities() -> None:
    """Argo CD notifications values hold no channel ID, homelab host, or webhook token (#1393)."""
    text = (K8S_DIR / "argocd" / "values.yaml").read_text(encoding="utf-8")
    assert "hooks/" not in text
    assert "channel_id" not in text.lower()

"""Tests for Argo CD application manifests, GitOps topology, data safety, and domain overlays."""

from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.commands.k8s import stack_lifecycle
from devops_cli.commands.k8s.stack_lifecycle import (
    _HELM_RELEASES_BY_STACK,
    _KUSTOMIZATIONS_BY_STACK,
    _MANIFESTS_BY_STACK,
)
from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS
from tests.k8s_manifests import kustomize, kustomized_objects
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
ARGOCD_DIR = K8S_DIR / "argocd"
APPS_DIR = ARGOCD_DIR / "apps"
BOOTSTRAP_DIR = ARGOCD_DIR / "bootstrap"
FINALIZER = "resources-finalizer.argocd.argoproj.io"
REPO_URL = "https://github.com/dan-petty/devops-cli"


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else {}


def _load_yaml_all(path: Path) -> list[dict[str, Any]]:
    return [
        dict(d) for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)
    ]


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


def test_application_projects_and_destinations() -> None:
    apps = _all_applications()
    system_apps = {"ingress", "gpu-feature-discovery", "traefik"}

    for name, app in apps.items():
        project = app["spec"]["project"]
        dest = app["spec"]["destination"]
        dest_ns = dest["namespace"]
        dest_srv = dest["server"]

        assert dest_srv == "https://kubernetes.default.svc"
        if name in ("bootstrap", "cluster"):
            assert project == "default"
        elif name in system_apps:
            assert project == "homelab-system"
        else:
            assert project == "homelab"
            assert dest_ns not in ("kube-system", "default")


def test_automated_sync_policies() -> None:
    apps = _all_applications()
    for name, app in apps.items():
        sync = app["spec"]["syncPolicy"]
        automated = sync.get("automated", {})
        retry = sync.get("retry", {})
        assert automated.get("prune") is True, f"{name} automated.prune is not True"
        assert automated.get("selfHeal") is True, f"{name} automated.selfHeal is not True"
        assert retry.get("limit") == 5, f"{name} retry.limit is not 5"


def _check_app_git_sources(name: str, spec: dict[str, Any]) -> None:
    if "source" in spec:
        source = spec["source"]
        assert (source["repoURL"], source["targetRevision"]) == (
            REPO_URL,
            "main",
        ), f"{name} bad revision {source.get('targetRevision')}"
        return
    git_sources = [s for s in spec.get("sources", []) if "chart" not in s]
    expected_count = 2 if name == "argocd" else 1
    assert len(git_sources) == expected_count, f"{name} expected {expected_count} git sources"
    for git_s in git_sources:
        assert (git_s["repoURL"], git_s["targetRevision"]) == (
            REPO_URL,
            "main",
        ), f"{name} bad revision {git_s.get('targetRevision')}"


def test_git_sources_and_revisions() -> None:
    for name, app in _all_applications().items():
        _check_app_git_sources(name, app["spec"])


def _assert_helm_app_matches_release(
    app: dict[str, Any], release: dict[str, str], name: str
) -> None:
    semver_re = re.compile(r"^\d+\.\d+\.\d+$")
    sources = app.get("spec", {}).get("sources", [])
    helm_sources = [s for s in sources if "chart" in s]
    assert len(helm_sources) == 1, f"{name} expected 1 Helm source"
    h = helm_sources[0]

    target_rev = str(h["targetRevision"])
    assert semver_re.match(target_rev), f"{name} helm version {target_rev} not pinned semver"
    assert target_rev == release["version"]

    expected_chart_name = release["chart"].split("/")[-1]
    assert h["chart"] == expected_chart_name
    assert app["spec"]["destination"]["namespace"] == release["namespace"]

    value_files = h.get("helm", {}).get("valueFiles", [])
    raw_val = Path(release["values"])
    rel_val = raw_val.relative_to(REPO_ROOT) if raw_val.is_absolute() else raw_val
    expected_rel_path = f"$values/{rel_val.as_posix()}"
    assert value_files == [expected_rel_path]


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
    helm_releases_map: dict[str, dict[str, str]] = {
        r["name"]: r for releases in _HELM_RELEASES_BY_STACK.values() for r in releases
    }

    for name, expected in helm_releases_map.items():
        assert name in apps, f"Missing Helm app {name}"
        _assert_helm_app_matches_release(apps[name], expected, name)


def test_every_application_in_argocd_apps_maps_to_deploy_stack_counterpart() -> None:
    """Every Application in k8s/argocd/apps maps to a deploy-stack counterpart (#1675).

    Each chart maps to a release with the same version and values file, and each path maps
    to a deploy-stack manifest list or kustomization. argocd-image-updater is the only allowed
    exception (k8s/README.md Service Image Updates; task-1485).
    """
    helm_releases_map: dict[str, dict[str, str]] = {
        r["name"]: r for releases in _HELM_RELEASES_BY_STACK.values() for r in releases
    }
    post_helm_by_stack: dict[str, tuple[Path, ...]] = getattr(
        stack_lifecycle, "_POST_HELM_BY_STACK", {}
    )
    post_helm = [
        (REPO_ROOT / "k8s" / p).resolve() for paths in post_helm_by_stack.values() for p in paths
    ]
    deploy_stack_kustomizations = {
        (REPO_ROOT / "k8s").resolve(),
        *(
            (REPO_ROOT / "k8s" / k).resolve()
            for ks in _KUSTOMIZATIONS_BY_STACK.values()
            for k in ks
        ),
        *(p for p in post_helm if p.is_dir()),
    }
    deploy_stack_manifests = {
        *(
            (REPO_ROOT / p if not p.is_absolute() else p).resolve()
            for ms in _MANIFESTS_BY_STACK.values()
            for p in ms
        ),
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


def _assert_kustomization_resources(p: Path, name: str) -> None:
    kust = p / "kustomization.yaml"
    if not kust.exists():
        return
    kust_data = _load_yaml(kust)
    for res in kust_data.get("resources", []):
        if not res.startswith("$"):
            res_p = p / res
            assert res_p.exists(), f"{name} resource {res_p} does not exist"


def test_the_collector_starts_after_the_tempo_it_exports_traces_to() -> None:
    """The collector's `otlp_grpc/tempo` exporter has a Tempo to reach when the collector
    starts, in both deploy paths, so its first export does not log a burst of `connection
    refused` that reads later like an outage (#409): `deploy-stack` installs tempo before
    otel-collector, and the cluster app-of-apps syncs the otel-collector Application in a later
    sync wave than tempo's."""
    exporter = _load_yaml(K8S_DIR / "otel" / "values.yaml")["config"]["exporters"][
        "otlp_grpc/tempo"
    ]["endpoint"]
    waves = {
        name: int(app["metadata"].get("annotations", {}).get("argocd.argoproj.io/sync-wave", "0"))
        for name, app in _all_applications().items()
        if name in {"tempo", "otel-collector"}
    }
    order = [release["name"] for release in _HELM_RELEASES_BY_STACK["infra"]]

    assert (
        exporter.startswith("tempo.otel."),
        order.index("tempo") < order.index("otel-collector"),
        waves["tempo"] < waves["otel-collector"],
    ) == (True, True, True)


def test_paths_and_kustomizations_exist() -> None:
    apps = _all_applications()
    for name, app in apps.items():
        spec = app["spec"]
        if "source" in spec and "path" in spec["source"]:
            p = REPO_ROOT / spec["source"]["path"]
            assert p.exists(), f"{name} path {p} does not exist"
            _assert_kustomization_resources(p, name)


def test_finalizers_on_applications() -> None:
    apps = _all_applications()
    no_finalizer_apps = {"bootstrap", "cluster", "argocd"}

    for name, app in apps.items():
        finalizers = app.get("metadata", {}).get("finalizers", [])
        if name in no_finalizer_apps:
            assert FINALIZER not in finalizers, f"{name} must not have {FINALIZER}"
        else:
            assert FINALIZER in finalizers, f"{name} must have {FINALIZER}"


def test_projects_whitelists_and_orphaned_resources() -> None:
    projects_doc = _load_yaml_all(APPS_DIR / "projects.yaml")
    proj_map = {
        doc["metadata"]["name"]: doc for doc in projects_doc if doc.get("kind") == "AppProject"
    }

    assert set(proj_map.keys()) == {"homelab", "homelab-system"}

    for proj in proj_map.values():
        whitelist = proj["spec"].get("clusterResourceWhitelist", [])
        assert {"group": "*", "kind": "*"} in whitelist

    homelab = proj_map["homelab"]["spec"]
    assert homelab.get("orphanedResources", {}).get("warn") is True

    ignored = homelab.get("orphanedResources", {}).get("ignore", [])
    ignored_tuples = {
        (ig.get("group", ""), ig.get("kind", ""), ig.get("name", "")) for ig in ignored
    }

    for secret in CLUSTER_SECRETS:
        assert ("", "Secret", secret.name) in ignored_tuples

    # deploy-stack applies it from config.yaml, so no Application owns it (#1290).
    # default AppProject is created by Argo CD itself, so no Application tracks it (#1104).
    expected_ignored = {
        ("", "ConfigMap", "devops-cli-config"),
        ("", "Secret", "argocd-initial-admin-secret"),
        ("", "Secret", "argocd-redis"),
        ("", "Secret", "sh.helm.release.v1.*"),
        ("", "Secret", "agent-grant-*"),
        ("", "PersistentVolumeClaim", ""),
        ("batch", "Job", "devops-cli-*"),
        ("argoproj.io", "AppProject", "default"),
    }
    assert expected_ignored.issubset(ignored_tuples)

    destinations = {
        (d.get("server", ""), d.get("namespace", "")) for d in homelab.get("destinations", [])
    }
    assert ("https://kubernetes.default.svc", "agents") in destinations


# ── Ownership & No Duplicates ────────────────────────────────────────────────


def test_this_repository_passes_the_argocd_gate() -> None:
    """The repository passes the offline Argo CD gate, verifying all applications at the head (#1343)."""
    from devops_cli.k8s.argocd_gate import check_argocd_gate

    built = check_argocd_gate(REPO_ROOT)
    assert len(built) >= 23


def test_rendered_raw_objects_single_ownership() -> None:
    from devops_cli.k8s.argocd_gate import discover_path_applications

    apps = _all_applications()
    raw_leaf_apps = discover_path_applications(REPO_ROOT, APPS_DIR)

    seen_objects: dict[tuple[str, str, str, str], str] = {}
    namespaces_declared: list[str] = []

    for app_name, dir_path in raw_leaf_apps.items():
        assert app_name in apps
        proc = kustomize(dir_path)
        docs = list(yaml.load_all(proc.stdout, Loader=yaml.CSafeLoader))
        for doc in docs:
            if not doc:
                continue
            kind = doc.get("kind", "")
            meta = doc.get("metadata", {})
            name = meta.get("name", "")
            ns = meta.get("namespace", apps[app_name]["spec"]["destination"]["namespace"])
            group = (
                doc.get("apiVersion", "").split("/")[0] if "/" in doc.get("apiVersion", "") else ""
            )

            key = (group, kind, ns, name)
            if (
                group == ""
                and kind == "ConfigMap"
                and ns == "monitoring"
                and name.startswith("grafana-")
            ):
                continue
            assert key not in seen_objects, (
                f"Object {key} already owned by {seen_objects.get(key)}, conflict in {app_name}"
            )
            seen_objects[key] = app_name

            if kind == "Namespace":
                namespaces_declared.append(name)

    assert len(namespaces_declared) == len(set(namespaces_declared)), (
        "Duplicate namespaces declared"
    )


# ── Data Safety ──────────────────────────────────────────────────────────────


def test_namespace_and_pvc_data_safety() -> None:
    from devops_cli.k8s.argocd_gate import discover_path_applications

    raw_leaf_apps = list(discover_path_applications(REPO_ROOT, APPS_DIR).values())

    for dir_path in raw_leaf_apps:
        proc = kustomize(dir_path)
        docs = list(yaml.load_all(proc.stdout, Loader=yaml.CSafeLoader))
        for doc in docs:
            if not doc:
                continue
            kind = doc.get("kind", "")
            if kind in ("Namespace", "PersistentVolumeClaim"):
                annos = doc.get("metadata", {}).get("annotations", {})
                sync_opts = annos.get("argocd.argoproj.io/sync-options", "")
                assert "Prune=false" in sync_opts, (
                    f"{kind}/{doc['metadata']['name']} missing Prune=false"
                )
                assert "Delete=false" in sync_opts, (
                    f"{kind}/{doc['metadata']['name']} missing Delete=false"
                )


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


def test_argocd_enables_the_web_terminal() -> None:
    """The chart grants argocd-server pods/exec only when `exec.enabled` renders as "true"."""
    argocd_val = _load_yaml(ARGOCD_DIR / "values.yaml")
    assert argocd_val["configs"]["cm"]["exec.enabled"] == "true"


# ── Perimeters & Network Policies ────────────────────────────────────────────


def test_exactly_one_application_renders_argocd_default_perimeter() -> None:
    """The argocd-default-perimeter NetworkPolicy is rendered by exactly one Application (#1673)."""
    apps = _all_applications()
    rendering_apps: list[str] = []
    for name, app in apps.items():
        spec = app.get("spec", {})
        sources = list(spec.get("sources", []))
        if "source" in spec and isinstance(spec["source"], dict):
            sources.append(spec["source"])
        for src in sources:
            rel_path = src.get("path")
            if not rel_path:
                continue
            p = REPO_ROOT / rel_path
            if (p / "kustomization.yaml").is_file() or (p / "kustomization.yml").is_file():
                policies = kustomized_objects(p, "NetworkPolicy")
                if ("argocd", "argocd-default-perimeter") in policies:
                    rendering_apps.append(name)
    assert rendering_apps == ["argocd"]

    otel_kust = _load_yaml(K8S_DIR / "otel" / "kustomization.yaml")
    assert "networkpolicy.yaml" in otel_kust.get("resources", [])


def test_applicationset_controller_disabled_with_zero_replicas() -> None:
    """The ApplicationSet controller Deployment renders 0 replicas and avoids the obsolete enabled key (#1673)."""
    values = _load_yaml(ARGOCD_DIR / "values.yaml")
    appset = values.get("applicationSet", {})
    assert (
        appset.get("replicas"),
        "enabled" in appset,
    ) == (0, False)


# ── Domain Overlays ──────────────────────────────────────────────────────────


def test_homelab_domain_overlays() -> None:
    for overlay in ("devops", "ingress"):
        overlay_dir = K8S_DIR / "overlays" / "homelab" / overlay
        proc = kustomize(overlay_dir)
        assert proc.returncode == 0, f"Overlay {overlay} failed to build: {proc.stderr}"

        docs = [d for d in yaml.load_all(proc.stdout, Loader=yaml.CSafeLoader) if d]
        assert len(docs) > 0, f"No documents rendered for overlay {overlay}"
        for doc in docs:
            assert "kind" in doc
            assert "metadata" in doc


# ── Deploy-time homelab values (#1290) ───────────────────────────────────────


def test_the_app_of_apps_keeps_the_hosts_deploy_stack_sets_on_the_homelab_applications() -> None:
    """`cluster` leaves the Kustomize overrides of the homelab Applications to deploy-stack,
    and leaves pre/post-delete finalizers to Argo CD (#1674)."""
    from devops_cli.config.constants import (
        CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS as HOMELAB_APPLICATIONS,
    )
    from devops_cli.config.constants import (
        CONST_K8S_ARGOCD_PRE_POST_DELETE_FINALIZERS_JQ as PRE_POST_DELETE_JQ,
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
                "jqPathExpressions": [PRE_POST_DELETE_JQ],
            }
        ],
        True,
    )


@pytest.mark.live("jq")
def test_cluster_app_of_apps_ignores_pre_and_post_delete_finalizers_jq() -> None:
    """The jqPathExpression matches pre- and post-delete finalizers, preserving resources-finalizer (#1674)."""
    import json
    import shutil
    import subprocess

    from devops_cli.config.constants import (
        CONST_K8S_ARGOCD_PRE_POST_DELETE_FINALIZERS_JQ as PRE_POST_DELETE_JQ,
    )

    spec = _load_yaml(BOOTSTRAP_DIR / "cluster.yaml")["spec"]
    diff_entries = [
        d
        for d in spec.get("ignoreDifferences", [])
        if d.get("group") == "argoproj.io"
        and d.get("kind") == "Application"
        and "jqPathExpressions" in d
    ]
    assert len(diff_entries) == 1
    (entry,) = diff_entries
    assert entry.get("jqPathExpressions") == [PRE_POST_DELETE_JQ]

    jq_bin = shutil.which("jq")
    if jq_bin:
        sample_doc = {
            "metadata": {
                "finalizers": [
                    "resources-finalizer.argocd.argoproj.io",
                    "pre-delete-finalizer.argocd.argoproj.io",
                    "pre-delete-finalizer.argocd.argoproj.io/cleanup",
                    "post-delete-finalizer.argocd.argoproj.io",
                    "post-delete-finalizer.argocd.argoproj.io/cleanup",
                    "custom.example.com/finalizer",
                ]
            }
        }
        proc = subprocess.run(
            [jq_bin, "-r", PRE_POST_DELETE_JQ],
            input=json.dumps(sample_doc),
            text=True,
            capture_output=True,
            check=True,
        )
        selected = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        assert selected == [
            "pre-delete-finalizer.argocd.argoproj.io",
            "pre-delete-finalizer.argocd.argoproj.io/cleanup",
            "post-delete-finalizer.argocd.argoproj.io",
            "post-delete-finalizer.argocd.argoproj.io/cleanup",
        ]
        assert "resources-finalizer.argocd.argoproj.io" not in selected
        assert "custom.example.com/finalizer" not in selected


def test_no_homelab_application_sets_kustomize_overrides_in_git() -> None:
    """Git leaves the field to deploy-stack, so the two never contend for it."""
    from devops_cli.config.constants import (
        CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS as HOMELAB_APPLICATIONS,
    )

    apps = _all_applications()
    assert [
        name for name in HOMELAB_APPLICATIONS if "kustomize" in apps[name]["spec"]["source"]
    ] == []


# ── Argo CD Image Updater (#1485) ────────────────────────────────────────────


def test_image_updater_runs_the_pinned_argo_helm_chart_in_the_argocd_namespace() -> None:
    """Its project admits the chart repository and the namespace; the chart brings the CRD."""
    spec = _all_applications()["argocd-image-updater"]["spec"]
    homelab = next(
        doc["spec"]
        for doc in _load_yaml_all(APPS_DIR / "projects.yaml")
        if doc["metadata"]["name"] == spec["project"]
    )
    chart = spec["sources"][0]
    assert (
        chart,
        spec["destination"],
        chart["repoURL"] in homelab["sourceRepos"],
        spec["destination"] in homelab["destinations"],
        {"group": "*", "kind": "*"} in homelab["clusterResourceWhitelist"],
    ) == (
        {
            "repoURL": "https://argoproj.github.io/argo-helm",
            "chart": "argocd-image-updater",
            "targetRevision": "1.3.1",
            "helm": {"valueFiles": ["$values/k8s/argocd/image-updater-values.yaml"]},
        },
        {"server": "https://kubernetes.default.svc", "namespace": "argocd"},
        True,
        True,
        True,
    )


def test_image_updater_keeps_only_application_devops_on_the_digest_of_service_latest() -> None:
    """One ImageUpdater, with no git write-back, so the digest goes onto the Application.

    The chart renders `extraObjects` as written. Without `writeBackConfig` the method is
    `argocd`: Image Updater sets `spec.source.kustomize.images` on the Application it selects,
    which the `cluster` app-of-apps leaves alone, and commits nothing.
    """
    values = _load_yaml(ARGOCD_DIR / "image-updater-values.yaml")
    (updater,) = values["extraObjects"]
    (ref,) = updater["spec"]["applicationRefs"]
    assert (
        values,
        [name for name in _all_applications() if fnmatch.fnmatchcase(name, ref["namePattern"])],
    ) == (
        {
            "extraObjects": [
                {
                    "apiVersion": "argocd-image-updater.argoproj.io/v1alpha1",
                    "kind": "ImageUpdater",
                    "metadata": {"name": "devops", "namespace": "argocd"},
                    "spec": {
                        "applicationRefs": [
                            {
                                "namePattern": "devops",
                                "images": [
                                    {
                                        "alias": "service",
                                        "imageName": "ghcr.io/dan-petty/devops-cli/service:latest",
                                        "commonUpdateSettings": {"updateStrategy": "digest"},
                                    }
                                ],
                            }
                        ]
                    },
                }
            ]
        },
        ["devops"],
    )


def test_no_application_renders_the_devops_cli_config_map_and_no_commit_holds_it() -> None:
    """The ConfigMap is rendered from the active config at deploy time, never from git."""
    rendered = kustomize(K8S_DIR / "overlays" / "homelab" / "devops").stdout
    objects = [
        (d["kind"], d["metadata"]["name"])
        for d in yaml.load_all(rendered, Loader=yaml.CSafeLoader)
        if d
    ]
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "k8s/devops/configmap.yaml"],
        cwd=REPO_ROOT,
        check=False,
    ).returncode
    tracked = subprocess.run(
        ["git", "ls-files", "k8s/devops/configmap.yaml"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert (("ConfigMap", "devops-cli-config") in objects, ignored, tracked) == (
        False,
        0,
        "",
    )

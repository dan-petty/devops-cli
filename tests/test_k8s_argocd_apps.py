"""Tests for Argo CD application manifests, GitOps topology, data safety, and domain overlays."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK
from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS

REPO_ROOT = Path(__file__).resolve().parent.parent
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


def test_git_sources_and_revisions() -> None:
    apps = _all_applications()

    for name, app in apps.items():
        spec = app["spec"]
        if "source" in spec:
            source = spec["source"]
            assert (source["repoURL"], source["targetRevision"]) == (REPO_URL, "main"), (
                f"{name} bad revision {source.get('targetRevision')}"
            )
        elif "sources" in spec:
            git_sources = [s for s in spec["sources"] if "chart" not in s]
            assert len(git_sources) == 1, f"{name} expected 1 git source"
            git_s = git_sources[0]
            assert (git_s["repoURL"], git_s["ref"], git_s["targetRevision"]) == (
                REPO_URL,
                "values",
                "main",
            ), f"{name} bad revision {git_s.get('targetRevision')}"


def test_helm_sources_pinned_versions() -> None:
    apps = _all_applications()
    semver_re = re.compile(r"^\d+\.\d+\.\d+$")

    helm_releases_map: dict[str, dict[str, str]] = {}
    for releases in _HELM_RELEASES_BY_STACK.values():
        for r in releases:
            helm_releases_map[r["name"]] = r
    helm_releases_map["traefik"] = {
        "name": "traefik",
        "chart": "traefik/traefik",
        "namespace": "kube-system",
        "values": "k8s/ingress/traefik-values.yaml",
        "version": "41.6.0",
    }

    for name, expected in helm_releases_map.items():
        assert name in apps, f"Missing Helm app {name}"
        app = apps[name]
        spec = app["spec"]
        sources = spec.get("sources", [])
        helm_sources = [s for s in sources if "chart" in s]
        assert len(helm_sources) == 1, f"{name} expected 1 Helm source"
        h = helm_sources[0]

        target_rev = str(h["targetRevision"])
        assert semver_re.match(target_rev), f"{name} helm version {target_rev} not pinned semver"
        assert target_rev == expected["version"]

        expected_chart_name = expected["chart"].split("/")[-1]
        assert h["chart"] == expected_chart_name
        assert app["spec"]["destination"]["namespace"] == expected["namespace"]

        value_files = h.get("helm", {}).get("valueFiles", [])
        raw_val = Path(expected["values"])
        rel_val = raw_val.relative_to(REPO_ROOT) if raw_val.is_absolute() else raw_val
        expected_rel_path = f"$values/{rel_val.as_posix()}"
        assert value_files == [expected_rel_path]


def _assert_kustomization_resources(p: Path, name: str) -> None:
    kust = p / "kustomization.yaml"
    if not kust.exists():
        return
    kust_data = _load_yaml(kust)
    for res in kust_data.get("resources", []):
        if not res.startswith("$"):
            res_p = p / res
            assert res_p.exists(), f"{name} resource {res_p} does not exist"


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

    assert ("", "Secret", "argocd-initial-admin-secret") in ignored_tuples
    assert ("", "Secret", "argocd-redis") in ignored_tuples
    assert ("", "Secret", "sh.helm.release.v1.*") in ignored_tuples
    assert ("", "PersistentVolumeClaim", "") in ignored_tuples
    assert ("batch", "Job", "devops-cli-*") in ignored_tuples


# ── Ownership & No Duplicates ────────────────────────────────────────────────


def test_rendered_raw_objects_single_ownership() -> None:
    apps = _all_applications()
    raw_leaf_apps = {
        "base": K8S_DIR,
        "monitoring": K8S_DIR / "monitoring",
        "llm": K8S_DIR / "llm",
        "otel": K8S_DIR / "otel",
        "logging": K8S_DIR / "logging",
        "devops": K8S_DIR / "overlays" / "homelab" / "devops",
        "ingress": K8S_DIR / "overlays" / "homelab" / "ingress",
        "gpu-feature-discovery": K8S_DIR / "gpu-feature-discovery",
    }

    seen_objects: dict[tuple[str, str, str, str], str] = {}
    namespaces_declared: list[str] = []

    for app_name, dir_path in raw_leaf_apps.items():
        assert app_name in apps
        proc = subprocess.run(
            ["kubectl", "kustomize", str(dir_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        docs = list(yaml.safe_load_all(proc.stdout))
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
    raw_leaf_apps = [
        K8S_DIR,
        K8S_DIR / "monitoring",
        K8S_DIR / "llm",
        K8S_DIR / "otel",
        K8S_DIR / "logging",
        K8S_DIR / "overlays" / "homelab" / "devops",
        K8S_DIR / "overlays" / "homelab" / "ingress",
        K8S_DIR / "gpu-feature-discovery",
    ]

    for dir_path in raw_leaf_apps:
        proc = subprocess.run(
            ["kubectl", "kustomize", str(dir_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        docs = list(yaml.safe_load_all(proc.stdout))
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
    assert ("Prune=false" in grafana_opts, "Delete=false" in grafana_opts) == (True, True)
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


# ── Perimeters & Network Policies ────────────────────────────────────────────


def test_perimeters_in_applications() -> None:
    apps = _all_applications()
    for name, app in apps.items():
        spec = app["spec"]
        if "source" in spec and "path" in spec["source"]:
            p = REPO_ROOT / spec["source"]["path"]
            kust = p / "kustomization.yaml"
            if kust.exists():
                kust_data = _load_yaml(kust)
                resources = kust_data.get("resources", [])
                assert "networkpolicy.yaml" not in resources or name != "argocd", (
                    "No app may sync k8s/argocd/networkpolicy.yaml"
                )

    otel_kust = _load_yaml(K8S_DIR / "otel" / "kustomization.yaml")
    assert "networkpolicy.yaml" in otel_kust.get("resources", [])


# ── Domain Overlays ──────────────────────────────────────────────────────────


def test_homelab_domain_overlays() -> None:
    for overlay in ("devops", "ingress"):
        overlay_dir = K8S_DIR / "overlays" / "homelab" / overlay
        proc = subprocess.run(
            ["kubectl", "kustomize", str(overlay_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"Overlay {overlay} failed to build: {proc.stderr}"

        docs = [d for d in yaml.safe_load_all(proc.stdout) if d]
        assert len(docs) > 0, f"No documents rendered for overlay {overlay}"
        for doc in docs:
            assert "kind" in doc
            assert "metadata" in doc


# ── Deploy-time homelab values (#1290) ───────────────────────────────────────


def test_the_app_of_apps_keeps_the_hosts_deploy_stack_sets_on_the_homelab_applications() -> None:
    """`cluster` leaves the Kustomize overrides of the homelab Applications to deploy-stack."""
    from devops_cli.k8s.argocd_overrides import HOMELAB_APPLICATIONS

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
        ],
        True,
    )


def test_no_homelab_application_sets_kustomize_overrides_in_git() -> None:
    """Git leaves the field to deploy-stack, so the two never contend for it."""
    from devops_cli.k8s.argocd_overrides import HOMELAB_APPLICATIONS

    apps = _all_applications()
    assert [
        name for name in HOMELAB_APPLICATIONS if "kustomize" in apps[name]["spec"]["source"]
    ] == []


def test_no_application_renders_the_devops_cli_config_map_and_no_commit_holds_it() -> None:
    """The ConfigMap is rendered from the active config at deploy time, never from git."""
    rendered = subprocess.run(
        ["kubectl", "kustomize", str(K8S_DIR / "overlays" / "homelab" / "devops")],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    objects = [(d["kind"], d["metadata"]["name"]) for d in yaml.safe_load_all(rendered) if d]
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "k8s/devops/configmap.yaml"], cwd=REPO_ROOT, check=False
    ).returncode
    tracked = subprocess.run(
        ["git", "ls-files", "k8s/devops/configmap.yaml"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert (("ConfigMap", "devops-cli-config") in objects, ignored, tracked) == (False, 0, "")

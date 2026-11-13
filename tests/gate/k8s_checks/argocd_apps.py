"""What the Argo CD Applications render (#2164)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

from tests.gate.k8s_render import kustomize, kustomized_objects
from tests.support.k8s_tree import TREE
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"


ARGOCD_DIR = K8S_DIR / "argocd"


APPS_DIR = ARGOCD_DIR / "apps"


BOOTSTRAP_DIR = ARGOCD_DIR / "bootstrap"


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


def check_rendered_raw_objects_single_ownership() -> None:
    from devops_cli.k8s.argocd_gate import discover_path_applications

    apps = _all_applications()
    raw_leaf_apps = discover_path_applications(TREE, APPS_DIR)

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


def check_namespace_and_pvc_data_safety() -> None:
    from devops_cli.k8s.argocd_gate import discover_path_applications

    raw_leaf_apps = list(discover_path_applications(TREE, APPS_DIR).values())

    for dir_path in raw_leaf_apps:
        proc = kustomize(dir_path)
        docs = list(yaml.load_all(proc.stdout, Loader=yaml.CSafeLoader))
        for doc in docs:
            if not doc:
                continue
            kind = doc.get("kind", "")
            if kind in ("Namespace", "PersistentVolumeClaim", "Cluster", "Mattermost"):
                annos = doc.get("metadata", {}).get("annotations", {})
                sync_opts = annos.get("argocd.argoproj.io/sync-options", "")
                assert "Prune=false" in sync_opts, (
                    f"{kind}/{doc['metadata']['name']} missing Prune=false"
                )
                assert "Delete=false" in sync_opts, (
                    f"{kind}/{doc['metadata']['name']} missing Delete=false"
                )


def check_exactly_one_application_renders_argocd_default_perimeter() -> None:
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


def check_homelab_domain_overlays() -> None:
    for overlay in ("devops", "ingress"):
        overlay_dir = K8S_DIR / "overlays" / "homelab" / overlay
        proc = kustomize(overlay_dir)
        assert proc.returncode == 0, f"Overlay {overlay} failed to build: {proc.stderr}"

        docs = [d for d in yaml.load_all(proc.stdout, Loader=yaml.CSafeLoader) if d]
        assert len(docs) > 0, f"No documents rendered for overlay {overlay}"
        for doc in docs:
            assert "kind" in doc
            assert "metadata" in doc


def check_no_application_renders_the_devops_cli_config_map_and_no_commit_holds_it() -> None:
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

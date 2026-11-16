"""The Grafana sidecar provisions the shipped dashboards from generated ConfigMaps (#692).

Only the four Kubernetes views reached the sidecar, through hand-copied ConfigMaps that nothing
applied, and devops-cli's own dashboards reached Grafana only through `grafana dashboards sync`.
A `configMapGenerator` now builds the ConfigMaps from the dashboard files, and the root
kustomization that `devops k8s deploy-stack` applies includes it. The product dashboards of
devops-cli have their own generator in `k8s/devops/dashboards/`, which the environment generator
in `k8s/monitoring/dashboards/` lists as a resource (#5292). These tests read the kustomizations
in Python; they never run kustomize or kubectl.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from devops_cli.roadmap.job_result import LINE_PREFIX
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
MONITORING_DIR = K8S_DIR / "monitoring"
DASHBOARDS_DIR = MONITORING_DIR / "dashboards"
DEVOPS_DIR = K8S_DIR / "devops"
PRODUCT_DASHBOARDS_DIR = DEVOPS_DIR / "dashboards"
# kubectl's client-side apply stores the object in an annotation, and annotations are capped.
LAST_APPLIED_ANNOTATION_LIMIT_BYTES = 262_144


def _kustomization(directory: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (directory / "kustomization.yaml").read_text(encoding="utf-8")
    )
    return loaded


def _generator_options(kustomization: dict[str, Any], generator: dict[str, Any]) -> dict[str, Any]:
    """A generator's options: the kustomization's `generatorOptions`, then its own."""
    shared = kustomization.get("generatorOptions", {})
    own = generator.get("options", {})
    return {
        **shared,
        **own,
        "labels": {**shared.get("labels", {}), **own.get("labels", {})},
    }


def _configmap(
    directory: Path, kustomization: dict[str, Any], generator: dict[str, Any]
) -> dict[str, Any]:
    """The ConfigMap one generator of the kustomization in `directory` produces, built as
    kustomize builds it."""
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": generator["name"],
            "namespace": kustomization.get("namespace", generator.get("namespace")),
            "labels": _generator_options(kustomization, generator)["labels"],
        },
        "data": {
            name: (directory / name).read_text(encoding="utf-8") for name in generator["files"]
        },
    }


def _generator_dirs() -> list[Path]:
    """The dashboards kustomization of `k8s/monitoring`, then each kustomization it lists."""
    resources = _kustomization(DASHBOARDS_DIR).get("resources", [])
    return [DASHBOARDS_DIR, *((DASHBOARDS_DIR / resource).resolve() for resource in resources)]


def _generators() -> Iterator[tuple[Path, dict[str, Any], dict[str, Any]]]:
    """Each ConfigMap generator of the dashboards, with its directory and its kustomization."""
    for directory in _generator_dirs():
        kustomization = _kustomization(directory)
        for generator in kustomization["configMapGenerator"]:
            yield directory, kustomization, generator


def _generated_configmaps() -> list[dict[str, Any]]:
    """The ConfigMaps the dashboards generators produce."""
    return [_configmap(*generator) for generator in _generators()]


def test_each_configmap_fits_kubectls_last_applied_annotation() -> None:
    """Verify each ConfigMap, as compact JSON, stays under the 262,144-byte annotation limit.

    `kubectl apply` stores the whole object in its last-applied annotation, and an object past
    the limit fails to apply; the Kubernetes views were split into two ConfigMaps for it.
    """
    sizes = {
        cm["metadata"]["name"]: len(json.dumps(cm, separators=(",", ":")).encode("utf-8"))
        for cm in _generated_configmaps()
    }
    assert [
        name for name, size in sizes.items() if size >= LAST_APPLIED_ANNOTATION_LIMIT_BYTES
    ] == []


def _kustomization_dirs(directory: Path) -> set[Path]:
    """`directory` and each kustomization directory that its resources reach."""
    found = {directory.resolve()}
    for resource in _kustomization(directory).get("resources", []):
        path = (directory / resource).resolve()
        if (path / "kustomization.yaml").is_file():
            found |= _kustomization_dirs(path)
    return found


def test_the_devops_root_leaves_the_product_dashboards_to_monitoring() -> None:
    """Neither `k8s/devops` nor the overlay of Application `devops` reaches
    `k8s/devops/dashboards`. Else Application `devops` takes the ConfigMap that Application
    `monitoring` owns, and the two Applications sync it in turn (#5292)."""
    overlay = K8S_DIR / "overlays" / "homelab" / "devops"

    assert (
        DEVOPS_DIR.resolve() in _kustomization_dirs(overlay),
        PRODUCT_DASHBOARDS_DIR.resolve() in _kustomization_dirs(overlay),
    ) == (True, False)


def test_root_kustomization_leaves_dashboards_to_monitoring_stack() -> None:
    """Verify `k8s/kustomization.yaml` avoids duplicate dashboard ownership with `k8s/monitoring`.

    Argo CD's `monitoring` application owns `dashboards` in namespace `monitoring`. Listing
    dashboards in the root kustomization causes a SharedResourceWarning conflict loop with `base`.
    """
    resources = _kustomization(K8S_DIR)["resources"]

    assert "monitoring/dashboards" not in resources


def _expressions(node: Any) -> list[str]:
    """Every query expression in a dashboard: `expr` for Prometheus and Loki targets."""
    if isinstance(node, dict):
        own = [node["expr"]] if isinstance(node.get("expr"), str) else []
        return own + [expr for value in node.values() for expr in _expressions(value)]
    if isinstance(node, list):
        return [expr for value in node for expr in _expressions(value)]
    return []


def test_each_count_of_the_result_lines_starts_with_the_base_of_the_job_grades() -> None:
    """The panels of the row `Roadmap Job Success` and `devops roadmap eval grades` read the same
    result lines: the streams of the Service and of the Job pods, and both forms of a line. Each
    count of the dashboard starts with the one base of the report (#5556)."""
    from devops_cli.roadmap.job_grade_report import RESULT_LINES

    dashboard = json.loads(
        (PRODUCT_DASHBOARDS_DIR / "roadmap-service-telemetry.json").read_text(encoding="utf-8")
    )
    counts = [
        count
        for expr in _expressions(dashboard)
        if LINE_PREFIX in expr
        for count in expr.split("count_over_time(")[1:]
    ]

    assert len(counts) > 0
    assert [count for count in counts if not count.startswith(f"{RESULT_LINES} | regexp ")] == []

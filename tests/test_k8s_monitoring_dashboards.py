"""The Grafana sidecar provisions the shipped dashboards from generated ConfigMaps (#692).

Only the four Kubernetes views reached the sidecar, through hand-copied ConfigMaps that nothing
applied, and devops-cli's own dashboards reached Grafana only through `grafana dashboards sync`.
A `configMapGenerator` now builds the ConfigMaps from the dashboard files, and the root
kustomization that `devops k8s deploy-stack` applies includes it. These tests read the
kustomizations in Python; they never run kustomize or kubectl.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"
MONITORING_DIR = K8S_DIR / "monitoring"
DASHBOARDS_DIR = MONITORING_DIR / "dashboards"

# Today's ConfigMap names and groupings, so a re-apply updates them in place.
PROVISIONED = {
    "grafana-k8s-global-dashboards": ["k8s-views-global.json", "k8s-views-pods.json"],
    "grafana-k8s-node-dashboards": ["k8s-views-nodes.json", "k8s-views-namespaces.json"],
    "grafana-devops-cli-dashboards": ["devops-cli.json", "ai-spend.json"],
}
# Reachable through `devops grafana dashboards sync` only: llm-stack charts a removed vLLM
# deployment (#693) and otel-collector needs collector self-metrics nothing scrapes (#551).
SYNC_ONLY = {"llm-stack.json", "otel-collector.json"}
SIDECAR_LABELS = {
    "grafana_dashboard": "1",
    "app.kubernetes.io/name": "grafana",
    "app.kubernetes.io/part-of": "devops-cli-stack",
}
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


def _configmap(kustomization: dict[str, Any], generator: dict[str, Any]) -> dict[str, Any]:
    """The ConfigMap one generator produces, built as kustomize builds it."""
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": generator["name"],
            "namespace": kustomization.get("namespace", generator.get("namespace")),
            "labels": _generator_options(kustomization, generator)["labels"],
        },
        "data": {
            name: (DASHBOARDS_DIR / name).read_text(encoding="utf-8") for name in generator["files"]
        },
    }


def _generated_configmaps() -> list[dict[str, Any]]:
    """The ConfigMaps the dashboards generator produces."""
    kustomization = _kustomization(DASHBOARDS_DIR)
    return [
        _configmap(kustomization, generator) for generator in kustomization["configMapGenerator"]
    ]


def _hashed_names() -> list[bool]:
    """Whether kustomize appends a content hash to each generated ConfigMap's name."""
    kustomization = _kustomization(DASHBOARDS_DIR)
    return [
        _generator_options(kustomization, generator).get("disableNameSuffixHash") is not True
        for generator in kustomization["configMapGenerator"]
    ]


def test_the_generator_provisions_six_dashboards_under_todays_configmap_names() -> None:
    """Verify three unhashed ConfigMaps in `monitoring` carry the six files and sidecar labels."""
    configmaps = _generated_configmaps()

    assert (
        {cm["metadata"]["name"]: sorted(cm["data"]) for cm in configmaps},
        [cm["metadata"]["namespace"] for cm in configmaps],
        [cm["metadata"]["labels"] for cm in configmaps],
        _hashed_names(),
    ) == (
        {name: sorted(files) for name, files in PROVISIONED.items()},
        ["monitoring"] * len(PROVISIONED),
        [SIDECAR_LABELS] * len(PROVISIONED),
        [False] * len(PROVISIONED),
    )


def test_every_other_dashboard_is_left_to_sync_by_name() -> None:
    """Verify a dashboard added to the directory cannot be left out of the generator unnoticed."""
    generated = {name for cm in _generated_configmaps() for name in cm["data"]}
    shipped = {path.name for path in DASHBOARDS_DIR.glob("*.json")}

    assert sorted(shipped - generated - SYNC_ONLY) == []


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


def test_the_monitoring_kustomization_takes_its_dashboards_from_the_generator() -> None:
    """Verify `k8s/monitoring` lists the generator and every resource it lists exists."""
    resources = _kustomization(MONITORING_DIR)["resources"]

    assert (
        "dashboards" in resources,
        [resource for resource in resources if not (MONITORING_DIR / resource).exists()],
    ) == (True, [])


def test_deploy_stack_applies_the_dashboards_through_the_root_kustomization() -> None:
    """Verify `k8s/kustomization.yaml` lists `monitoring/dashboards` and every resource exists.

    `devops k8s deploy-stack` runs `kubectl apply -k <k8s_dir>` on the root kustomization, in
    the same run that creates the `monitoring` namespace.
    """
    resources = _kustomization(K8S_DIR)["resources"]

    assert (
        "monitoring/dashboards" in resources,
        [resource for resource in resources if not (K8S_DIR / resource).exists()],
    ) == (True, [])

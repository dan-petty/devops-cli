"""Tests verifying Kubernetes monitoring stack integration and dashboard metric invariants."""

from __future__ import annotations

import re
from typing import Any

import yaml
from kubernetes.utils.quantity import parse_quantity

from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"

# The chart names the Deployment, the Service and the token Secret of its image renderer
# `<release>-image-renderer` (#5185).
GRAFANA_RENDERER = "grafana-image-renderer"


def _k8s_yaml(relative: str) -> Any:
    with open(K8S_DIR / relative, encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.CSafeLoader)


def test_grafana_runs_the_image_renderer_of_its_chart_at_a_release_tag() -> None:
    """With no renderer, the render API of Grafana returned HTTP 500, so no panel image could be
    made (#5185). The renderer of the chart runs its image at a release tag, not `latest`, with
    CPU and memory requests and limits, `GOMEMLIMIT` below the memory limit, and the ingress
    policy of the chart. The values set no renderer URL and no callback URL, so the chart gives
    Grafana the Service DNS name of the renderer and gives the renderer the Grafana Service. The
    token comes from a Secret of the cluster table, not from git."""
    renderer = _k8s_yaml("monitoring/grafana-values.yaml")["imageRenderer"]
    image = renderer["image"]
    resources = renderer["resources"]
    memory_limit = parse_quantity(resources["limits"]["memory"])
    # Go writes the unit of GOMEMLIMIT as MiB or GiB; Kubernetes writes Mi or Gi.
    go_memory_limit = parse_quantity(renderer["env"]["GOMEMLIMIT"].removesuffix("B"))

    assert (
        renderer["enabled"],
        image["repository"],
        re.fullmatch(r"v\d+\.\d+\.\d+", image["tag"]) is not None,
        image["pullPolicy"],
        (sorted(resources["requests"]), sorted(resources["limits"])),
        parse_quantity(resources["requests"]["memory"]) <= memory_limit,
        0 < go_memory_limit < memory_limit,
        renderer.get("networkPolicy", {}).get("limitIngress", True),
        (renderer.get("serverURL", ""), renderer.get("renderingCallbackURL", "")),
        (renderer.get("token", ""), renderer["existingSecret"]),
    ) == (
        True,
        "grafana/grafana-image-renderer",
        True,
        "IfNotPresent",
        (["cpu", "memory"], ["cpu", "memory"]),
        True,
        True,
        True,
        ("", ""),
        ("", GRAFANA_RENDERER),
    )


def _dashboard_configmap_namespaces() -> list[str | None]:
    """The target namespace of every `grafana_dashboard`-labelled ConfigMap kustomizations generate."""
    namespaces: list[str | None] = []
    for path in sorted(K8S_DIR.rglob("kustomization.yaml")):
        kustomization = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        shared_labels = kustomization.get("generatorOptions", {}).get("labels", {})
        for generator in kustomization.get("configMapGenerator", []):
            labels = {**shared_labels, **generator.get("options", {}).get("labels", {})}
            if "grafana_dashboard" in labels:
                namespaces.append(kustomization.get("namespace", generator.get("namespace")))
    return namespaces


def test_loki_pyroscope_and_grafana_turn_off_unused_chart_defaults() -> None:
    """Loki canary, Pyroscope debug logging, and Grafana's cluster-wide sidecar watch stay off (#1133).

    Loki keeps retention enabled with `deletion_mode: disabled` (#550), Pyroscope logs at `info`
    rather than the chart's `debug` default, and Grafana disables its datasource sidecar and scopes
    its dashboard sidecar and RBAC to ConfigMaps in `monitoring`, where every generated dashboard
    ConfigMap lives.
    """
    loki = _k8s_yaml("logging/loki-values.yaml")
    pyroscope = _k8s_yaml("monitoring/pyroscope-values.yaml")
    grafana = _k8s_yaml("monitoring/grafana-values.yaml")
    dashboards_sc = grafana.get("sidecar", {}).get("dashboards", {})
    datasources_sc = grafana.get("sidecar", {}).get("datasources", {})
    dashboard_namespaces = _dashboard_configmap_namespaces()

    assert (
        loki.get("lokiCanary", {}).get("enabled"),
        loki["loki"]["limits_config"]["deletion_mode"],
        loki["loki"]["compactor"]["retention_enabled"],
        pyroscope.get("pyroscope", {}).get("extraArgs", {}).get("log.level"),
        datasources_sc.get("enabled"),
        (dashboards_sc.get("searchNamespace"), dashboards_sc.get("resource")),
        grafana.get("rbac", {}).get("namespaced"),
        (bool(dashboard_namespaces), set(dashboard_namespaces)),
    ) == (
        False,
        "disabled",
        True,
        "info",
        False,
        ("monitoring", "configmap"),
        True,
        (True, {"monitoring"}),
    )

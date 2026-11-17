"""The GPU feature discovery manifests under `k8s/gpu-feature-discovery/` (#5791)."""

from __future__ import annotations

from typing import Any

from tests.support.k8s_tree import manifests, pod_spec


def _object(kind: str, name: str) -> dict[str, Any]:
    (found,) = (
        document
        for _, document in manifests()
        if document["kind"] == kind and document["metadata"]["name"] == name
    )
    return found


def _container() -> dict[str, Any]:
    spec = pod_spec(_object("DaemonSet", "gpu-feature-discovery"))
    assert spec is not None
    containers: list[dict[str, Any]] = spec["containers"]
    (container,) = containers
    return container


def test_the_gpu_feature_discovery_container_sets_a_read_only_root_filesystem() -> None:
    container = _container()
    assert container["securityContext"]["readOnlyRootFilesystem"] is True

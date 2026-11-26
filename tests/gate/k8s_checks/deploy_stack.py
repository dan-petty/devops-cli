"""What deploy-stack and the product base `k8s/devops` apply (#2164)."""

from __future__ import annotations

from typing import Any

import yaml
from docker.auth import resolve_repository_name
from docker.utils import parse_repository_tag

from devops_cli.commands.k8s.stack_lifecycle import PRODUCT_MANIFESTS_BY_STACK
from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


def check_no_product_manifest_that_applies_before_the_charts_holds_a_service_monitor() -> None:
    """deploy-stack applies the product files of `PRODUCT_MANIFESTS_BY_STACK` before the charts,
    and the release that installs the ServiceMonitor CRD is a chart, so on a new cluster a
    ServiceMonitor there is refused (#819, #1367). One belongs in `PRODUCT_POST_HELM_BY_STACK`."""
    monitors = [
        path.as_posix()
        for paths in PRODUCT_MANIFESTS_BY_STACK.values()
        for path in paths
        if any(doc.get("kind") == "ServiceMonitor" for doc in applied_documents(DEVOPS_DIR / path))
    ]

    assert monitors == []


# Docker Hub's Distribution image, as docker-py resolves `registry` and `library/registry`.
DISTRIBUTION_IMAGES = {("docker.io", "registry"), ("docker.io", "library/registry")}


# The namespace of the removed in-cluster registry.
REMOVED_REGISTRY_NAMESPACE = "registry"


def _product_objects() -> list[dict[str, Any]]:
    """Every Kubernetes object that a YAML file of `k8s/devops` declares, and every object that
    its kustomization renders."""
    declared = [
        document
        for path in sorted(DEVOPS_DIR.rglob("*.y*ml"))
        for document in yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    ]
    return [
        document
        for document in [*declared, *applied_documents(DEVOPS_DIR)]
        if isinstance(document, dict) and "kind" in document and "metadata" in document
    ]


def _container_images(node: object) -> list[str]:
    """The image of every container and init container in `node`, at any depth."""
    if isinstance(node, list):
        return [image for item in node for image in _container_images(item)]
    if not isinstance(node, dict):
        return []
    images = [
        container["image"]
        for key in ("containers", "initContainers")
        for container in node.get(key) or []
        if isinstance(container, dict) and isinstance(container.get("image"), str)
    ]
    return images + [image for value in node.values() for image in _container_images(value)]


def _objects_of_the_removed_registry(objects: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(kind, name) of each object in the removed registry's namespace, and of that Namespace."""
    return sorted(
        {
            (obj["kind"], obj["metadata"]["name"])
            for obj in objects
            if obj["metadata"].get("namespace") == REMOVED_REGISTRY_NAMESPACE
            or (
                obj["kind"] == "Namespace" and obj["metadata"]["name"] == REMOVED_REGISTRY_NAMESPACE
            )
        }
    )


def check_no_product_manifest_runs_an_in_cluster_image_registry() -> None:
    """Gitea's container registry is the internal registry (#1081). No object of `k8s/devops`
    runs the Distribution image or sits in namespace `registry` (#1630)."""
    objects = _product_objects()
    distribution = sorted(
        image
        for image in _container_images(objects)
        if resolve_repository_name(parse_repository_tag(image)[0]) in DISTRIBUTION_IMAGES
    )

    assert (distribution, _objects_of_the_removed_registry(objects)) == ([], [])

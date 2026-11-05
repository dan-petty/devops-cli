"""What the manifests of deploy-stack apply, and in which order (#2164)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from docker.auth import resolve_repository_name
from docker.utils import parse_repository_tag
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

runner = CliRunner()


def _dry_run_details(output: str) -> dict[str, Any]:
    """The details of a dry-run result, after its heading."""
    details: dict[str, Any] = json.loads(output[output.index("{") :])["details"]
    return details


def check_llm_stack_applies_the_gateway_policy_before_the_gateway_and_deletes_it() -> None:
    """deploy-stack --stack llm applies llm-gateway-perimeter before the gateway's Deployment,
    and teardown-stack deletes it (#795). Without Argo CD the gateway ran with no policy, so its
    egress was unrestricted. Both apply the gateway kustomization, whose render puts the policy
    first (#1929). Neither dry run makes a request."""
    gateway = Path("k8s", "llm", "gateway")
    deploy = runner.invoke(app, ["deploy-stack", "--stack", "llm", "--dry-run"])
    teardown = runner.invoke(app, ["teardown-stack", "--stack", "llm", "--dry-run"])
    rendered = [
        (doc["kind"], doc["metadata"]["name"])
        for doc in applied_documents(gateway)
        if doc["kind"] in ("NetworkPolicy", "Deployment")
    ]

    assert (
        deploy.exit_code,
        teardown.exit_code,
        str(gateway) in _dry_run_details(deploy.output)["manifests"],
        str(gateway) in _dry_run_details(teardown.output)["manifest_deletes"],
        rendered,
    ) == (
        0,
        0,
        True,
        True,
        [("NetworkPolicy", "llm-gateway-perimeter"), ("Deployment", "llm-gateway")],
    )


def _renders_service_monitor(values: object) -> bool:
    """Whether chart values add a ServiceMonitor object or turn on a chart's own monitor."""
    if isinstance(values, list):
        return any(_renders_service_monitor(item) for item in values)
    if not isinstance(values, dict):
        return False
    own_monitor = values.get("serviceMonitor")
    return (
        values.get("kind") == "ServiceMonitor"
        or (isinstance(own_monitor, dict) and own_monitor.get("enabled") is True)
        or any(_renders_service_monitor(item) for item in values.values())
    )


def check_prometheus_operator_crds_install_before_every_service_monitor() -> None:
    """The CRD release installs first, ahead of every release or manifest with a ServiceMonitor.

    k8s-monitoring 4.x and dcgm-exporter ship no ServiceMonitor CRD, so on a cluster without it
    Helm refused both releases and the infra stack came up without Alloy (#819). Pre-Helm
    `_MANIFESTS_BY_STACK` paths apply before any chart, so no pre-Helm file or kustomization may
    hold a ServiceMonitor and `k8s/llm/gateway/servicemonitor.yaml` lives in `_POST_HELM_BY_STACK`
    (#1367).
    """
    from devops_cli.commands.k8s.stack_lifecycle import (
        _HELM_RELEASES_BY_STACK,
        _HELM_REPOS_BY_STACK,
        _MANIFESTS_BY_STACK,
        _POST_HELM_BY_STACK,
        DEFAULT_K8S_DIR,
    )

    crds = _HELM_RELEASES_BY_STACK["infra"][0]
    monitor_releases = [
        (stack, release["name"])
        for stack, releases in _HELM_RELEASES_BY_STACK.items()
        for release in releases
        if _renders_service_monitor(yaml.safe_load(Path(release["values"]).read_text("utf-8")))
    ]
    pre_helm_monitors = [
        (stack, path.as_posix())
        for stack, paths in _MANIFESTS_BY_STACK.items()
        for path in paths
        if any(doc.get("kind") == "ServiceMonitor" for doc in applied_documents(path))
    ]
    post_helm_monitors = [
        (stack, path.as_posix())
        for stack, paths in _POST_HELM_BY_STACK.items()
        for path in paths
        if (DEFAULT_K8S_DIR / path).is_file()
        and any(
            isinstance(doc, dict) and doc.get("kind") == "ServiceMonitor"
            for doc in yaml.safe_load_all((DEFAULT_K8S_DIR / path).read_text("utf-8"))
        )
    ]

    assert (
        (crds["name"], crds["chart"], crds["namespace"]),
        crds["chart"].split("/")[0] in _HELM_REPOS_BY_STACK["infra"],
        monitor_releases,
        pre_helm_monitors,
        post_helm_monitors,
    ) == (
        ("prometheus-operator-crds", "prometheus-community/prometheus-operator-crds", "monitoring"),
        True,
        [
            ("infra", "argocd"),
            ("infra", "argo-workflows"),
            ("infra", "pyroscope"),
            ("llm", "qdrant"),
        ],
        [],
        [("llm", "llm/gateway/servicemonitor.yaml")],
    )


# Docker Hub's Distribution image, as docker-py resolves `registry` and `library/registry`.
DISTRIBUTION_IMAGES = {("docker.io", "registry"), ("docker.io", "library/registry")}


# The namespace of the removed registry. Argo CD keeps it, with PVC `registry-data`, until a person
# deletes it (k8s/README.md, Internal Image Registry).
REMOVED_REGISTRY_NAMESPACE = "registry"


def _k8s_objects() -> list[dict[str, Any]]:
    """Every Kubernetes object that a YAML file under k8s/ declares."""
    return [
        document
        for path in sorted((REPO_ROOT / "k8s").rglob("*.y*ml"))
        for document in yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
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
        (obj["kind"], obj["metadata"]["name"])
        for obj in objects
        if obj["metadata"].get("namespace") == REMOVED_REGISTRY_NAMESPACE
        or (obj["kind"] == "Namespace" and obj["metadata"]["name"] == REMOVED_REGISTRY_NAMESPACE)
    )


def check_no_manifest_runs_an_in_cluster_image_registry() -> None:
    """Gitea's container registry is the internal registry (#1081). No manifest under k8s/ runs
    the Distribution image or declares an object in namespace `registry`, and the root
    kustomization renders none of them (#1630)."""
    objects = _k8s_objects()
    distribution = sorted(
        image
        for image in _container_images(objects)
        if resolve_repository_name(parse_repository_tag(image)[0]) in DISTRIBUTION_IMAGES
    )

    assert (
        distribution,
        _objects_of_the_removed_registry(objects),
        _objects_of_the_removed_registry(applied_documents(REPO_ROOT / "k8s")),
    ) == ([], [], [])

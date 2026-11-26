"""The cluster and the namespace that the devops-cli pods name in their telemetry (#4512).

The tracer names `k8s.cluster.name` and `k8s.namespace.name` from the environment values
`K8S_CONTEXT` and `POD_NAMESPACE` (`_detect_k8s_context` in src/devops_cli/telemetry/tracer.py).
With no `K8S_CONTEXT`, it uses the setting `k8s.context`, whose default is `minikube`, so each
span and log record of a pod named a cluster that does not exist.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


DEVOPS_CLI_IMAGE = "ghcr.io/dan-petty/devops-cli/"


NAMESPACE_FROM_DOWNWARD_API = {"fieldRef": {"fieldPath": "metadata.namespace"}}


def _containers(document: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """The name and the spec of each container of a rendered object that has a pod template, its
    init containers first."""
    spec = document.get("spec", {})
    match document["kind"]:
        case "Deployment":
            pod = spec["template"]["spec"]
        case "CronJob":
            pod = spec["jobTemplate"]["spec"]["template"]["spec"]
        case "WorkflowTemplate":
            for template in spec.get("templates", []):
                if "container" in template:
                    yield template["name"], template["container"]
            return
        case _:
            return
    for container in [*pod.get("initContainers", []), *pod["containers"]]:
        yield container["name"], container


def _named_namespace(entry: dict[str, Any] | None, namespace: str) -> str | None:
    """The namespace that a `POD_NAMESPACE` entry gives in an object of `namespace`."""
    if entry is None:
        return None
    if entry.get("valueFrom") == NAMESPACE_FROM_DOWNWARD_API:
        return namespace
    value: str | None = entry.get("value")
    return value


def check_each_devops_cli_container_names_the_cluster_and_its_namespace() -> None:
    """Each devops-cli container sets `K8S_CONTEXT` to one cluster name, the same in every
    container, and `POD_NAMESPACE` to the namespace of its object: from the Downward API, or as a
    plain value where the admission policy `roadmap-service-jobs` refuses `valueFrom` (the runner
    and the stage templates)."""
    contexts: set[str | None] = set()
    named: dict[tuple[str, str, str], str | None] = {}
    for document in applied_documents(DEVOPS_DIR):
        namespace = document["metadata"].get("namespace", "")
        for name, container in _containers(document):
            if not str(container.get("image", "")).startswith(DEVOPS_CLI_IMAGE):
                continue
            env = {entry["name"]: entry for entry in container.get("env", [])}
            contexts.add(env.get("K8S_CONTEXT", {}).get("value"))
            named[(document["kind"], document["metadata"]["name"], name)] = _named_namespace(
                env.get("POD_NAMESPACE"), namespace
            )
    (cluster, *others) = contexts
    assert (bool(cluster), others) == (True, [])
    assert named == {
        ("CronJob", "devops-cli", "devops-cli"): "devops",
        ("CronJob", "devops-cli-planner-run", "runner"): "devops",
        ("CronJob", "devops-cli-runner", "prepare"): "devops",
        ("CronJob", "devops-cli-runner", "agent"): "devops",
        ("CronJob", "devops-cli-runner", "publish"): "devops",
        ("CronJob", "repos-drift", "repos-drift"): "devops",
        ("CronJob", "roadmap-stage", "stage"): "devops",
        ("Deployment", "mcp-server", "mcp-server"): "devops",
        ("Deployment", "roadmap-service", "service"): "devops",
        ("WorkflowTemplate", "infra-drift", "drift"): "devops",
        ("WorkflowTemplate", "rag-ingest", "ingest"): "devops",
    }

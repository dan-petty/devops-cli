"""The cluster and the namespace that the devops-cli pods name in their telemetry (#4512).

The tracer names `k8s.cluster.name` and `k8s.namespace.name` from the environment values
`K8S_CONTEXT` and `POD_NAMESPACE` (`_detect_k8s_context` in src/devops_cli/telemetry/tracer.py).
With no `K8S_CONTEXT`, it uses the setting `k8s.context`, whose default is `minikube`, so each
span and log record of a pod named a cluster that does not exist.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import yaml

from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


# The cluster name of the metrics that Alloy sends. The pods give their spans the same name.
MONITORING_VALUES = REPO_ROOT / "k8s" / "monitoring" / "k8s-monitoring-values.yaml"


DEVOPS_CLI_IMAGE = "ghcr.io/dan-petty/devops-cli/"


NAMESPACE_FROM_DOWNWARD_API = {"fieldRef": {"fieldPath": "metadata.namespace"}}


def _containers(document: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """The name and the spec of each container of a rendered object that has a pod template."""
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
    for container in pod["containers"]:
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
    """Each devops-cli container sets `K8S_CONTEXT` to the cluster name of the monitoring stack,
    and `POD_NAMESPACE` to the namespace of its object: from the Downward API, or as a plain value
    where the admission policy `roadmap-service-jobs` refuses `valueFrom` (the runner template)."""
    monitoring = yaml.safe_load(MONITORING_VALUES.read_text(encoding="utf-8"))
    cluster = monitoring["cluster"]["name"]
    named: dict[tuple[str, str, str], tuple[str | None, str | None]] = {}
    for document in applied_documents(DEVOPS_DIR):
        namespace = document["metadata"].get("namespace", "")
        for name, container in _containers(document):
            if not str(container.get("image", "")).startswith(DEVOPS_CLI_IMAGE):
                continue
            env = {entry["name"]: entry for entry in container.get("env", [])}
            context = env.get("K8S_CONTEXT", {}).get("value")
            named[(document["kind"], document["metadata"]["name"], name)] = (
                context,
                _named_namespace(env.get("POD_NAMESPACE"), namespace),
            )
    assert named == {
        ("CronJob", "devops-cli", "devops-cli"): (cluster, "devops"),
        ("CronJob", "devops-cli-runner", "runner"): (cluster, "devops"),
        ("Deployment", "mcp-server", "mcp-server"): (cluster, "devops"),
        ("Deployment", "roadmap-service", "service"): (cluster, "devops"),
        ("WorkflowTemplate", "rag-ingest", "ingest"): (cluster, "devops"),
    }

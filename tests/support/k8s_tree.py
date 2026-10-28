"""Readers of the Kubernetes tree under `k8s/`: the manifests, and the values of each chart that an
Argo CD Application installs. They read files only and render no chart."""

from __future__ import annotations

from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from tests.support.paths import REPO_ROOT

K8S = REPO_ROOT / "k8s"
APPLICATIONS = K8S / "argocd" / "apps"
VALUES_PREFIX = "$values/"

# Where each workload kind keeps its pod spec.
POD_SPEC_PATHS: dict[str, tuple[str, ...]] = {
    "Pod": ("spec",),
    "Deployment": ("spec", "template", "spec"),
    "StatefulSet": ("spec", "template", "spec"),
    "DaemonSet": ("spec", "template", "spec"),
    "ReplicaSet": ("spec", "template", "spec"),
    "Job": ("spec", "template", "spec"),
    "CronJob": ("spec", "jobTemplate", "spec", "template", "spec"),
}


def value_at(values: Any, path: str, default: Any = None) -> Any:
    """The value at a dotted path, or the default when a key on the path is absent."""
    for key in path.split("."):
        if not isinstance(values, dict) or key not in values:
            return default
        values = values[key]
    return values


@cache
def yaml_documents(path: Path) -> tuple[dict[str, Any], ...]:
    """The mappings a YAML file holds, read once."""
    return tuple(
        document
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(document, dict)
    )


def application_sources() -> Iterator[dict[str, Any]]:
    """Each source of each Application, in file order."""
    for application_file in sorted(APPLICATIONS.glob("*.yaml")):
        for application in yaml_documents(application_file):
            if application.get("kind") != "Application":
                continue
            spec = application["spec"]
            yield from (source for source in spec.get("sources") or [spec.get("source")] if source)


def pinned_charts() -> frozenset[tuple[str, str]]:
    """Each chart an Application installs, with the version that the Application pins."""
    return frozenset(
        (source["chart"], str(source["targetRevision"]))
        for source in application_sources()
        if "chart" in source
    )


def chart_values() -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Each chart an Application installs, its values file and the values, in file order."""
    for source in application_sources():
        if "chart" not in source:
            continue
        for value_file in source.get("helm", {}).get("valueFiles", []):
            relative = value_file.removeprefix(VALUES_PREFIX)
            (values,) = yaml_documents(REPO_ROOT / relative)
            yield source["chart"], relative, values


def manifests() -> Iterator[tuple[str, dict[str, Any]]]:
    """Each Kubernetes object a manifest under k8s/ declares, with its file.

    A values file that an Application names is not a manifest, so its mappings are left out.
    """
    values = frozenset(relative for _, relative, _ in chart_values())
    for path in sorted(K8S.rglob("*.y*ml")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in values:
            continue
        for document in yaml_documents(path):
            if "kind" in document:
                yield relative, document


def pod_spec(document: dict[str, Any]) -> dict[str, Any] | None:
    """The pod spec of a workload, or None for another kind."""
    path = POD_SPEC_PATHS.get(str(document.get("kind")))
    spec = document
    for key in path or ():
        spec = spec.get(key) or {}
    return spec if path else None

"""Readers of the Kubernetes tree under `k8s/`: the manifests, and the values of each chart that an
Argo CD Application installs. They read files only and render no chart."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from devops_cli.k8s.environment import EnvironmentTree
from tests.support.paths import REPO_ROOT

K8S = REPO_ROOT / "k8s"
# The environment tree of this repository, as `.devops/project.toml` declares it (#5131).
TREE = EnvironmentTree(K8S, REPO_ROOT)
APPLICATIONS = K8S / "argocd" / "apps"
# A value file `$<ref>/<path>` names a file of the source whose `ref` is `<ref>`. Every ref source
# of this tree names this repository, whatever its ref (#5131).
REF_VALUE_FILE = re.compile(r"^\$(?P<ref>[^/]+)/(?P<path>.+)$")

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


def release_values(release: Mapping[str, Any]) -> list[Path]:
    """The values files of a release of `HELM_RELEASES_BY_STACK`, in their order: the files of the
    environment tree, then the files of the product base `k8s/devops` (#5131)."""
    return [
        *(TREE.path(value) for value in release["values"]),
        *(TREE.path("devops") / value for value in release.get("product_values", [])),
    ]


def deploy_stack_manifests(stacks: Iterable[str] | None = None) -> list[Path]:
    """The manifest paths that deploy-stack applies before the charts, for `stacks` (every stack
    when None), in its order: the files of the product base `k8s/devops`, then the paths of the
    environment tree (#5131)."""
    from devops_cli.commands.k8s.stack_lifecycle import (
        MANIFESTS_BY_STACK,
        PRODUCT_MANIFESTS_BY_STACK,
    )

    product = TREE.path("devops")
    selected = (
        list(stacks)
        if stacks is not None
        else sorted(MANIFESTS_BY_STACK.keys() | PRODUCT_MANIFESTS_BY_STACK.keys())
    )
    return [
        path
        for stack in selected
        for path in (
            *(product / p for p in PRODUCT_MANIFESTS_BY_STACK.get(stack, [])),
            *(TREE.path(p) for p in MANIFESTS_BY_STACK.get(stack, [])),
        )
    ]


def value_file_path(value_file: str) -> str:
    """The path in this repository of a value file of a chart source: `$<ref>/<path>` for any
    ref, else the path as written."""
    match = REF_VALUE_FILE.match(value_file)
    return match["path"] if match else value_file


def _value_files(source: dict[str, Any]) -> list[str]:
    """The values files of a chart source, relative to the repository, in their order."""
    return [
        value_file_path(value_file) for value_file in source.get("helm", {}).get("valueFiles", [])
    ]


def _merged(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """`override` over `base`, as Helm merges two values files: a map by key, and any other value
    in place of the earlier one."""
    merged = dict(base)
    for key, value in override.items():
        earlier = merged.get(key)
        both_maps = isinstance(value, dict) and isinstance(earlier, dict)
        merged[key] = _merged(earlier, value) if both_maps else value
    return merged


def chart_values() -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Each chart an Application installs, its first values file and the values that the chart
    gets: each values file of the source over the one before it (#5292), in file order."""
    for source in application_sources():
        if "chart" not in source or not (files := _value_files(source)):
            continue
        values: dict[str, Any] = {}
        for relative in files:
            (document,) = yaml_documents(REPO_ROOT / relative)
            values = _merged(values, document)
        yield source["chart"], files[0], values


def manifests() -> Iterator[tuple[str, dict[str, Any]]]:
    """Each Kubernetes object a manifest under k8s/ declares, with its file.

    A values file that an Application names is not a manifest, so its mappings are left out.
    """
    values = frozenset(
        relative
        for source in application_sources()
        if "chart" in source
        for relative in _value_files(source)
    )
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

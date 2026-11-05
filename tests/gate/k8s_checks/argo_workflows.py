"""The Argo Workflows kustomization (#2164)."""

from __future__ import annotations

import functools
from collections.abc import Iterator
from typing import Any

import yaml

from tests.gate.k8s_render import kustomize
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"


ARGO_DIR = K8S_DIR / "argo-workflows"


NAMESPACE = "argo-workflows"


@functools.cache
def _load(path: str) -> Any:
    """A YAML document of the repository, by path below the repository root."""
    return yaml.load((REPO_ROOT / path).read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)


def _values() -> Any:
    return _load("k8s/argo-workflows/values.yaml")


def _secret_fields(node: object, path: str = "") -> Iterator[str]:
    """Path of every mapping key that names a Secret, at any depth.

    A Kubernetes field that refers to a Secret has `secret` in its name (`secretKeyRef`,
    `secretRef`, `secretName`, `imagePullSecrets`, `existingSecret`), so the match is not a subset.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            if "secret" in str(key).lower():
                yield here
            yield from _secret_fields(value, here)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _secret_fields(item, f"{path}[{index}]")


def check_the_workflow_directory_and_its_values_reference_no_secret() -> None:
    """No object `kubectl kustomize` renders from the directory, and nothing in the chart's
    values, names a Secret field, so Secret `devops-cli` is never mounted or read here."""
    rendered = [d for d in yaml.safe_load_all(kustomize(ARGO_DIR).stdout) if d]
    assert (
        [path for document in rendered for path in _secret_fields(document)],
        [document["kind"] for document in rendered if document["kind"] == "Secret"],
        list(_secret_fields(_values())),
    ) == ([], [], [])


def check_the_kustomization_renders_the_template_and_the_perimeter_and_nothing_else() -> None:
    rendered = [d for d in yaml.safe_load_all(kustomize(ARGO_DIR).stdout) if d]
    assert sorted(
        (d["kind"], d["metadata"]["namespace"], d["metadata"]["name"]) for d in rendered
    ) == [
        ("NetworkPolicy", NAMESPACE, "argo-workflows-default-perimeter"),
        ("WorkflowTemplate", NAMESPACE, "devops-cli-version"),
    ]

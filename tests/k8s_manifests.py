"""The objects the repository's Kubernetes manifests apply, read the way kubectl reads them.

`kubectl kustomize` renders a kustomization exactly as `kubectl apply -k` applies it: nested
kustomizations, generators and the `namespace` transformer included. A manifest file is what
`kubectl apply -f` applies. Both answer with (namespace, name) for each object of one kind.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

import yaml

# `kubectl kustomize` reads local files only and renders the repository's largest kustomization
# in well under a second; the bound stops a hung binary, not a slow render.
KUSTOMIZE_TIMEOUT_SECONDS = 30


def _named(documents: Iterable[object], kind: str) -> set[tuple[str, str]]:
    """Return (namespace, name) of each document of this kind."""
    return {
        (document["metadata"].get("namespace", ""), document["metadata"]["name"])
        for document in documents
        if isinstance(document, dict) and document.get("kind") == kind
    }


def kustomized_objects(directory: Path, kind: str) -> set[tuple[str, str]]:
    """Return (namespace, name) of every `kind` object `kubectl apply -k <directory>` applies."""
    rendered = subprocess.run(
        ["kubectl", "kustomize", str(directory)],
        check=True,
        capture_output=True,
        text=True,
        timeout=KUSTOMIZE_TIMEOUT_SECONDS,
    )
    return _named(yaml.load_all(rendered.stdout, Loader=yaml.CSafeLoader), kind)


def manifest_objects(path: Path, kind: str) -> set[tuple[str, str]]:
    """Return (namespace, name) of every `kind` object `kubectl apply -f <path>` applies."""
    return _named(yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader), kind)

"""The objects the repository's Kubernetes manifests apply, read the way kubectl reads them.

`kubectl kustomize` renders a kustomization exactly as `kubectl apply -k` applies it: nested
kustomizations, generators and the `namespace` transformer included. A manifest file is what
`kubectl apply -f` applies. Both answer with (namespace, name) for each object of one kind. A
path of deploy-stack's manifest tables is either: it applies a directory with `kubectl apply -k`
and a file with `kubectl apply -f`.

A committed kustomization under the repository's `k8s/` renders the same for the whole run, since
no test writes to the workspace, so each is rendered once per test process, keyed by its resolved
directory, and shared by every test that asks for it. A kustomization a test builds under
`tmp_path` is rendered each time it is asked for.
"""

from __future__ import annotations

import functools
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from tests.support.paths import REPO_ROOT

# `kubectl kustomize` reads local files only and renders the repository's largest kustomization
# in well under a second; the bound stops a hung binary, not a slow render.
KUSTOMIZE_TIMEOUT_SECONDS = 30

COMMITTED_KUSTOMIZATIONS = REPO_ROOT / "k8s"
"""The tree of committed kustomizations, whose renders the run shares."""


def _render(directory: Path) -> subprocess.CompletedProcess[str]:
    """Run `kubectl kustomize <directory>`, keeping its exit code and output for the caller."""
    return subprocess.run(
        ["kubectl", "kustomize", str(directory)],
        check=False,
        capture_output=True,
        text=True,
        timeout=KUSTOMIZE_TIMEOUT_SECONDS,
    )


@functools.cache
def _render_committed(directory: Path) -> subprocess.CompletedProcess[str]:
    """The render of a committed kustomization, made once per test process."""
    return _render(directory)


def kustomize(directory: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """`kubectl kustomize <directory>`; with `check`, a failed render raises `CalledProcessError`."""
    resolved = directory.resolve()
    if resolved.is_relative_to(COMMITTED_KUSTOMIZATIONS):
        rendered = _render_committed(resolved)
    else:
        rendered = _render(directory)
    if check:
        rendered.check_returncode()
    return rendered


def _named(documents: Iterable[object], kind: str) -> set[tuple[str, str]]:
    """Return (namespace, name) of each document of this kind."""
    return {
        (document["metadata"].get("namespace", ""), document["metadata"]["name"])
        for document in documents
        if isinstance(document, dict) and document.get("kind") == kind
    }


def kustomized_objects(directory: Path, kind: str) -> set[tuple[str, str]]:
    """Return (namespace, name) of every `kind` object `kubectl apply -k <directory>` applies."""
    return _named(yaml.load_all(kustomize(directory).stdout, Loader=yaml.CSafeLoader), kind)


def manifest_objects(path: Path, kind: str) -> set[tuple[str, str]]:
    """Return (namespace, name) of every `kind` object `kubectl apply -f <path>` applies."""
    return _named(yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader), kind)


def applied_documents(path: Path) -> list[dict[str, Any]]:
    """Return the objects deploy-stack applies from one path of its manifest tables.

    It renders a directory with `kubectl apply -k` and reads a file with `kubectl apply -f`.
    """
    text = kustomize(path).stdout if path.is_dir() else path.read_text(encoding="utf-8")
    return [doc for doc in yaml.load_all(text, Loader=yaml.CSafeLoader) if isinstance(doc, dict)]


def applied_objects(path: Path, kind: str) -> set[tuple[str, str]]:
    """Return (namespace, name) of every `kind` object deploy-stack applies from one path."""
    return _named(applied_documents(path), kind)

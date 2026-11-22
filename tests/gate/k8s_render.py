"""The objects the repository's Kubernetes manifests apply, read the way kubectl reads them.

`kubectl kustomize` renders a kustomization exactly as `kubectl apply -k` applies it: nested
kustomizations, generators and the `namespace` transformer included. A manifest file is what
`kubectl apply -f` applies. Both answer with (namespace, name) for each object of one kind. A
path of deploy-stack's manifest tables is either: it applies a directory with `kubectl apply -k`
and a file with `kubectl apply -f`.

A committed kustomization under the repository's `k8s/` renders the same for the whole run, so
each is rendered once per process, keyed by its resolved directory, and shared by every check
of the `k8s` row that asks for it. A kustomization a check builds in a temporary directory is
rendered each time it is asked for.

A chart source of an Argo CD Application renders with `helm template`, as `devops k8s image-pins`
renders it (`chart_objects`). Helm fetches the chart from its repository, so this render needs
the network. Each Application is rendered once per process.
"""

from __future__ import annotations

import functools
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.constants import CONST_CANONICAL_OCI_SOURCE
from devops_cli.k8s.app_sources import (
    SourceTrees,
    application_sources,
    normalize_git_url,
    ref_sources,
)
from tests.support.paths import REPO_ROOT

# `kubectl kustomize` reads local files only and renders the repository's largest kustomization
# in well under a second; the bound stops a hung binary, not a slow render.
KUSTOMIZE_TIMEOUT_SECONDS = 30

COMMITTED_KUSTOMIZATIONS = REPO_ROOT / "k8s"
"""The tree of committed kustomizations, whose renders the run shares."""

# `helm template` fetches the index of the chart repository and the chart, which took about 4 s;
# the bound stops a hung fetch, not a slow one.
HELM_TIMEOUT_SECONDS = 60

ARGOCD_APPLICATIONS = REPO_ROOT / "k8s" / "argocd" / "apps"
"""The folder of the Argo CD Applications of the repository."""


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


@functools.cache
def chart_objects(application: Path) -> tuple[dict[str, Any], ...]:
    """The objects that the chart source of the Argo CD Application in the file `application`
    renders, made once per process.

    The command is the one of `devops k8s image-pins`: `helm template` with the release name of the
    Application, its chart, repository and `targetRevision`, its destination namespace and its
    value files, and with no test hook, which Argo CD does not apply. A value file
    `$<ref>/<path>` of a source of this repository reads the checkout, so the render shows what
    Argo CD applies after a merge.
    """
    doc = yaml.safe_load(application.read_text(encoding="utf-8"))
    name = str(doc["metadata"]["name"])
    sources = application_sources(doc)
    refs = ref_sources(sources)
    (chart,) = (source for source in sources if "chart" in source)
    helm = chart.get("helm") or {}
    command = [
        "helm",
        "template",
        str(helm.get("releaseName") or name),
        str(chart["chart"]),
        "--repo",
        str(chart["repoURL"]),
        "--version",
        str(chart["targetRevision"]),
        "--namespace",
        str(doc["spec"]["destination"]["namespace"]),
        "--skip-tests",
    ]
    with tempfile.TemporaryDirectory(prefix="chart-sources-") as workdir:
        trees = SourceTrees(REPO_ROOT, normalize_git_url(CONST_CANONICAL_OCI_SOURCE), Path(workdir))
        for value_file in helm.get("valueFiles") or []:
            command += ["--values", str(trees.value_file(str(value_file), refs))]
        rendered = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=HELM_TIMEOUT_SECONDS
        )
    assert rendered.returncode == 0, (
        f"{application}: {' '.join(command[:4])} exited {rendered.returncode}: "
        f"{rendered.stderr.strip()}"
    )
    documents = yaml.load_all(rendered.stdout, Loader=yaml.CSafeLoader)
    return tuple(document for document in documents if isinstance(document, dict))

"""The render of the chart source of an Argo CD Application, for the checks of the `charts` row.

A chart source of an Argo CD Application renders with `helm template`, as `devops k8s image-pins`
renders it (`chart_objects`). Helm fetches the chart from its repository, so this render needs
the network. Each Application is rendered once per process, and every check of the row that asks
for it reads that one render (#6730).
"""

from __future__ import annotations

import functools
import subprocess
import tempfile
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

# `helm template` fetches the index of the chart repository and the chart, which took about 4 s;
# the bound stops a hung fetch, not a slow one.
HELM_TIMEOUT_SECONDS = 60

ARGOCD_APPLICATIONS = REPO_ROOT / "k8s" / "argocd" / "apps"
"""The folder of the Argo CD Applications of the repository."""


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

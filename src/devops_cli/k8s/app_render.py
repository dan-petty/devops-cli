"""The builds of the path sources of the Argo CD Applications of an environment tree (#6068).

Argo CD builds a path source with Kustomize. `render_path_source` builds one as `devops k8s
image-pins` builds it: a source of the repository that holds the tree reads the checkout, and a
source of another public repository is fetched at its revision (`devops_cli.k8s.app_sources`). A
dry run fetches nothing, so it builds no source of another repository. `path_source_folder` gives
the local path of a source, which `devops k8s deploy-stack` builds itself (#6681).

`write_path_renders` writes the build of each path source to a file of its own in one folder,
`<application>-<index>.yaml`, where the index is the place of the source in the Application. The
folder then holds what Argo CD applies from the path sources, and one kube-linter run reads every
object of it. So a check that reads two objects, such as `non-isolated-pod`, finds the
NetworkPolicy of another Application. A chart source is not built here: kube-linter takes an
exception only from an annotation of the object, and the values of some charts cannot annotate
their objects.
"""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Final

from devops_cli.k8s.app_sources import (
    SourceTrees,
    application_sources,
    normalize_git_url,
    repository_origin,
    source_revision,
)
from devops_cli.k8s.argocd_gate import discover_argocd_applications
from devops_cli.k8s.environment import EnvironmentTree
from devops_cli.k8s.template import build_manifest_path

# The folders under the work folder of `write_path_renders`: the builds, and the fetched sources.
_RENDERS_DIR: Final[str] = "renders"
_SOURCES_DIR: Final[str] = "sources"
# Sources built at the same time: each build waits on kubectl, or on a fetch, for most of its time.
_WORKERS: Final[int] = 8


def path_source_folder(trees: SourceTrees, source: Mapping[str, Any]) -> Path | None:
    """The local path of the path source `source` of an Application, or None in a dry run that
    would fetch its repository."""
    tree = trees.tree(str(source.get("repoURL") or trees.origin), source_revision(source))
    if tree.planned:
        return None
    return (tree.root / str(source["path"])).resolve()


def render_path_source(trees: SourceTrees, source: Mapping[str, Any]) -> str | None:
    """The build of the path source `source` of an Application, or None in a dry run that would
    fetch its repository."""
    folder = path_source_folder(trees, source)
    return None if folder is None else build_manifest_path(folder)


def write_path_renders(
    env: EnvironmentTree, workdir: Path, *, origin_url: str | None = None
) -> Path:
    """Build each path source of each Application of `env` into a file of the folder
    `workdir/renders`, and return that folder.

    A git source of the origin of `env.repo` (or `origin_url`) reads the checkout. A fetched
    repository goes under `workdir/sources`, so the folder of the builds holds only the builds.
    """
    origin = normalize_git_url(origin_url or repository_origin(env.repo))
    trees = SourceTrees(env.repo, origin, workdir / _SOURCES_DIR)
    renders = workdir / _RENDERS_DIR
    renders.mkdir(parents=True)
    sources = [
        (renders / f"{name}-{index}.yaml", source)
        for name, doc in sorted(discover_argocd_applications(env.application_dirs).items())
        for index, source in enumerate(application_sources(doc))
        if "path" in source
    ]

    def write(item: tuple[Path, Mapping[str, Any]]) -> None:
        rendered = render_path_source(trees, item[1])
        if rendered is not None:
            item[0].write_text(rendered, encoding="utf-8")

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        list(pool.map(write, sources))
    return renders


__all__ = ["path_source_folder", "render_path_source", "write_path_renders"]

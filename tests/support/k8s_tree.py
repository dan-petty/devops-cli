"""The Kubernetes tree under `k8s/`: its root, and the paths that deploy-stack applies there. The
`k8s` gate row renders and checks these files and folders; no test asserts a value of them
(#6060)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from devops_cli.k8s.environment import EnvironmentTree
from tests.support.paths import REPO_ROOT

K8S = REPO_ROOT / "k8s"
# The environment tree of this repository, as `.devops/project.toml` declares it (#5131).
TREE = EnvironmentTree(K8S, REPO_ROOT)


def release_values(release: Mapping[str, Any], workdir: Path) -> list[Path]:
    """The values files of a release of `HELM_RELEASES_BY_STACK`, in their order: the `valueFiles`
    of the chart source of its Application in the tree, as deploy-stack reads them (#6680). A
    source of devops-cli is this checkout, whatever its `origin`, and a source of another
    repository is fetched into `workdir`."""
    from devops_cli.config.constants import CONST_CANONICAL_OCI_SOURCE
    from devops_cli.k8s.app_sources import SourceTrees, chart_sources, normalize_git_url

    source = chart_sources(TREE.application_dirs)[str(release["name"])]
    trees = SourceTrees(TREE.repo, normalize_git_url(CONST_CANONICAL_OCI_SOURCE), workdir)
    return [trees.value_file(value_file, source.refs) for value_file in source.value_files]


def deploy_stack_manifests(stacks: Iterable[str] | None = None) -> list[Path]:
    """The paths that deploy-stack applies before the charts, for `stacks` (every stack when
    None): for each stack, the files of the product base `k8s/devops`, the paths of the
    environment tree (#5131), and the folder of each path source of the Applications that
    `APPLICATIONS_BY_STACK` names, which deploy-stack builds (#6681). Each such source of the tree
    is a folder of this checkout."""
    from devops_cli.commands.k8s.stack_lifecycle import (
        APPLICATIONS_BY_STACK,
        MANIFESTS_BY_STACK,
        PRODUCT_MANIFESTS_BY_STACK,
    )
    from devops_cli.k8s.app_sources import application_sources
    from devops_cli.k8s.argocd_gate import discover_argocd_applications

    product = TREE.path("devops")
    applications = discover_argocd_applications(TREE.application_dirs)
    selected = (
        list(stacks)
        if stacks is not None
        else sorted(
            MANIFESTS_BY_STACK.keys()
            | PRODUCT_MANIFESTS_BY_STACK.keys()
            | APPLICATIONS_BY_STACK.keys()
        )
    )
    return [
        path
        for stack in selected
        for path in (
            *(product / p for p in PRODUCT_MANIFESTS_BY_STACK.get(stack, [])),
            *(TREE.path(p) for p in MANIFESTS_BY_STACK.get(stack, [])),
            *(
                TREE.repo / str(source["path"])
                for name in APPLICATIONS_BY_STACK.get(stack, ())
                for source in application_sources(applications[name])
                if "path" in source
            ),
        )
    ]

"""The environment tree of a cluster: the Kubernetes folder of an infra repo (#5131).

The environment tree holds what one cluster runs: its Argo CD Applications, the values of its
charts, its overlays and dashboards. devops-cli ships no environment tree. A command that reads one
takes its root from the option `--k8s-dir`, else from the project profile fact `kubernetes.dir`
(`.devops/project.toml`, or detection) of the repository of the current folder, else from the one
entry of `infra.repos` whose profile gives `kubernetes.dir`. A path in the tree is relative to its
root, and a source path of an Application is relative to the repository that holds the tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import ERRORS
from devops_cli.project.profile import PROJECT_FILE, resolve_profile

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings

_GIT: Final[str] = ".git"
_APPLICATION_DIRS: Final[tuple[Path, ...]] = (Path("argocd/apps"), Path("argocd/bootstrap"))
_ROOT_APPLICATION: Final[Path] = Path("argocd/bootstrap/bootstrap.yaml")
_DASHBOARDS: Final[Path] = Path("monitoring/dashboards")
_GATEWAY_CONFIG: Final[Path] = Path("llm/gateway/config.yaml")
_OLLAMA_PROFILES: Final[Path] = Path("llm/profiles/ollama-profiles.yaml")
_GPU_THRESHOLDS: Final[Path] = Path("llm/profiles/gpu-thresholds.yaml")
_TIER_TEMPLATES: Final[Path] = Path("llm/profiles/tier-templates")
_LLM_SERVICES: Final[Path] = Path("llm/profiles/services.yaml")
_PRODUCT_BASE: Final[Path] = Path("k8s/devops")
OPTION: Final[str] = "--k8s-dir"
PRODUCT_OPTION: Final[str] = "--product-dir"


@dataclass(frozen=True)
class EnvironmentTree:
    """An environment tree: its root folder, and the repository that holds it.

    `repo` is the folder that the source paths of the Applications are relative to: the nearest
    folder at or above `root` with a `.git`, else the parent of `root`, so a copy of the tree
    outside a repository reads as it reads in the repository.
    """

    root: Path
    repo: Path

    def path(self, relative: str | Path) -> Path:
        """`relative`, a path in the tree, under the root."""
        return self.root / relative

    @property
    def application_dirs(self) -> tuple[Path, ...]:
        """The folders of the Argo CD Applications: the leaf Applications, then the root ones."""
        return tuple(self.root / folder for folder in _APPLICATION_DIRS)

    @property
    def root_application(self) -> Path:
        """The file of the root Application, which `devops argo cd apps bootstrap-gitops` applies."""
        return self.root / _ROOT_APPLICATION

    @property
    def dashboards(self) -> Path:
        """The folder of the Grafana dashboard files."""
        return self.root / _DASHBOARDS

    @property
    def gateway_config(self) -> Path:
        """The LiteLLM config of the LLM gateway."""
        return self.root / _GATEWAY_CONFIG

    @property
    def ollama_profiles(self) -> Path:
        """The Ollama tier DaemonSets."""
        return self.root / _OLLAMA_PROFILES

    @property
    def gpu_thresholds(self) -> Path:
        """The GPU architecture thresholds of the Ollama tiers."""
        return self.root / _GPU_THRESHOLDS

    @property
    def tier_templates(self) -> Path:
        """The folder of the Ollama tier templates."""
        return self.root / _TIER_TEMPLATES

    @property
    def llm_services(self) -> Path:
        """The Services of the Ollama tiers."""
        return self.root / _LLM_SERVICES


def tree_at(root: Path) -> EnvironmentTree:
    """The environment tree whose root is `root`, kept as given, so a relative root gives relative
    paths in the output of a command."""
    given = root.expanduser()
    resolved = given.resolve()
    return EnvironmentTree(given, _repository(resolved) or resolved.parent)


def resolve_environment(
    k8s_dir: Path | None = None, *, settings: Settings | None = None, start: Path | None = None
) -> EnvironmentTree:
    """The environment tree that a command reads.

    `k8s_dir` (the option `--k8s-dir`) wins. Else the profile of the repository that holds `start`
    (the current folder), else the one infra repo of `settings.infra.repos` whose checkout has a
    profile with `kubernetes.dir`. The reads are local files only.

    Raises:
        ConfigurationError: no source gives a tree, two infra repos give one, or a project file
            does not fit the profile.
    """
    if k8s_dir is not None:
        return tree_at(k8s_dir)
    current = _repository((start or Path.cwd()).resolve())
    found = _profile_tree(current) if current is not None else None
    if found is not None:
        return found
    if settings is None:
        from devops_cli.config.settings import load_settings

        settings = load_settings()
    trees = [
        tree
        for checkout in _infra_checkouts(settings)
        if (tree := _profile_tree(checkout)) is not None
    ]
    if len(trees) > 1:
        raise ConfigurationError(
            ERRORS.k8s.environment_root_ambiguous.format(
                option=OPTION, roots=", ".join(str(tree.root) for tree in trees)
            ),
            key="infra.repos",
        )
    if not trees:
        raise ConfigurationError(
            ERRORS.k8s.environment_root_not_found.format(option=OPTION, file=PROJECT_FILE),
            key="kubernetes.dir",
        )
    return trees[0]


def resolve_product_root(product_dir: Path | None = None, *, start: Path | None = None) -> Path:
    """The product base `k8s/devops` that devops-cli ships, apart from the environment tree.

    `product_dir` (the option `--product-dir`) wins, else `k8s/devops` of the repository that holds
    `start` (the current folder), else of the current folder.
    """
    if product_dir is not None:
        return product_dir.expanduser().resolve()
    folder = (start or Path.cwd()).resolve()
    return (_repository(folder) or folder) / _PRODUCT_BASE


def _repository(folder: Path) -> Path | None:
    """The nearest folder at or above `folder` that holds `.git`."""
    return next((path for path in (folder, *folder.parents) if (path / _GIT).exists()), None)


def _profile_tree(checkout: Path) -> EnvironmentTree | None:
    """The tree that the profile of the repository at `checkout` names, or None."""
    if not checkout.is_dir():
        return None
    folder = resolve_profile(checkout).profile.kubernetes.dir
    if folder is None:
        return None
    return EnvironmentTree((checkout / folder).resolve(), checkout.resolve())


def _infra_checkouts(settings: Settings) -> list[Path]:
    """The checkout of each infra repo: its `path`, else `<repos.base_dir>/<owner>/<name>`."""
    from devops_cli.github.repo_ref import RepoRef
    from devops_cli.infra.onboard import default_checkout

    return [
        (entry.path or default_checkout(RepoRef(entry.repo), settings)).expanduser().resolve()
        for entry in settings.infra.repos
    ]


__all__ = [
    "OPTION",
    "PRODUCT_OPTION",
    "EnvironmentTree",
    "resolve_environment",
    "resolve_product_root",
    "tree_at",
]

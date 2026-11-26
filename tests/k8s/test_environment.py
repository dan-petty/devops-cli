"""The environment tree that a command reads: `--k8s-dir`, else the profile fact `kubernetes.dir`
of the repository of the current folder, else of the one infra repo that gives it (#5131)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.config.settings import InfraConfig, InfraRepoConfig, ReposConfig, Settings
from devops_cli.exceptions import ConfigurationError
from devops_cli.k8s.environment import (
    EnvironmentTree,
    resolve_environment,
    resolve_product_root,
    tree_at,
)


def _checkout(folder: Path, *, project_file: str | None = None) -> Path:
    """A git checkout, with a `.devops/project.toml` when `project_file` is given."""
    (folder / ".git").mkdir(parents=True)
    if project_file is not None:
        (folder / ".devops").mkdir()
        (folder / ".devops" / "project.toml").write_text(project_file, encoding="utf-8")
    return folder


def _settings(tmp_path: Path, *repos: InfraRepoConfig) -> Settings:
    return Settings(
        repos=ReposConfig(base_dir=tmp_path / "repos"), infra=InfraConfig(repos=list(repos))
    )


def test_the_option_wins_and_its_repository_holds_the_source_paths(tmp_path: Path) -> None:
    """A folder in a checkout reads against that checkout; a copy outside any repository reads
    against its parent, as `k8s/` reads against the root of this repository."""
    repo = _checkout(tmp_path / "infra", project_file='[kubernetes]\ndir = "cluster"\n')
    (repo / "env").mkdir()
    (tmp_path / "copy" / "k8s").mkdir(parents=True)

    assert (
        resolve_environment(repo / "env", start=repo),
        resolve_environment(tmp_path / "copy" / "k8s", start=repo),
    ) == (
        EnvironmentTree(repo / "env", repo),
        EnvironmentTree(tmp_path / "copy" / "k8s", tmp_path / "copy"),
    )


def test_the_profile_of_the_current_repository_gives_the_tree(tmp_path: Path) -> None:
    """A subfolder of the checkout finds the profile of the checkout."""
    repo = _checkout(tmp_path / "repo", project_file='[kubernetes]\ndir = "k8s"\n')
    (repo / "docs").mkdir()

    tree = resolve_environment(start=repo / "docs", settings=_settings(tmp_path))

    assert (tree, tree.gateway_config, tree.application_dirs) == (
        EnvironmentTree(repo / "k8s", repo),
        repo / "k8s" / "llm" / "gateway" / "config.yaml",
        (repo / "k8s" / "argocd" / "apps", repo / "k8s" / "argocd" / "bootstrap"),
    )


def test_the_one_infra_repo_with_a_kubernetes_folder_gives_the_tree(tmp_path: Path) -> None:
    """The current repository has no `kubernetes.dir`. The infra repo at its default checkout
    detects `k8s` from its `ansible.cfg`, and an infra repo with no checkout gives nothing."""
    current = _checkout(tmp_path / "work")
    infra = _checkout(tmp_path / "repos" / "example" / "infra")
    (infra / "ansible.cfg").write_text("[defaults]\n", encoding="utf-8")
    (infra / "k8s").mkdir()
    settings = _settings(
        tmp_path,
        InfraRepoConfig(repo="example/infra"),
        InfraRepoConfig(repo="example/absent"),
    )

    assert resolve_environment(start=current, settings=settings) == EnvironmentTree(
        infra / "k8s", infra
    )


def test_two_infra_repos_with_a_tree_need_the_option(tmp_path: Path) -> None:
    current = _checkout(tmp_path / "work")
    first = _checkout(tmp_path / "one", project_file='[kubernetes]\ndir = "k8s"\n')
    second = _checkout(tmp_path / "two", project_file='[kubernetes]\ndir = "k8s"\n')
    settings = _settings(
        tmp_path,
        InfraRepoConfig(repo="example/one", path=first),
        InfraRepoConfig(repo="example/two", path=second),
    )

    with pytest.raises(ConfigurationError) as caught:
        resolve_environment(start=current, settings=settings)

    assert caught.value.message == (
        f"Two or more infra repos give an environment tree: {first / 'k8s'}, {second / 'k8s'}. "
        "Keep one of them in infra.repos, or, if the command has the option --k8s-dir, give the "
        "one to read with it."
    )


def test_no_source_names_the_option_and_the_project_file(tmp_path: Path) -> None:
    current = _checkout(tmp_path / "work")

    with pytest.raises(ConfigurationError) as caught:
        resolve_environment(start=current, settings=_settings(tmp_path))

    assert caught.value.message == (
        "No environment tree is known. Add to infra.repos the checkout of the infra repo, whose "
        ".devops/project.toml gives kubernetes.dir, or, if the command has the option --k8s-dir, "
        "give the Kubernetes folder of that repo with it."
    )


def test_the_product_base_is_k8s_devops_of_the_current_repository(tmp_path: Path) -> None:
    repo = _checkout(tmp_path / "repo")
    (repo / "src").mkdir()

    assert (
        resolve_product_root(start=repo / "src"),
        resolve_product_root(tmp_path / "base", start=repo),
        tree_at(repo / "k8s").repo,
    ) == (repo / "k8s" / "devops", tmp_path / "base", repo)


def test_the_secret_table_of_a_tree_is_its_own_file_alone(tmp_path: Path) -> None:
    """A `cluster-secrets.toml` in another folder of the repository is not the table of the tree."""
    repo = _checkout(tmp_path / "repo")
    other = repo / "tests" / "fixtures" / "cluster-secrets.toml"
    other.parent.mkdir(parents=True)
    other.write_text("[[secret]]\n", encoding="utf-8")
    nested = repo / "k8s" / "k8s" / "cluster-secrets.toml"
    nested.parent.mkdir(parents=True)
    nested.write_text("[[secret]]\n", encoding="utf-8")
    tree = EnvironmentTree(root=repo / "k8s", repo=repo)

    assert tree.cluster_secrets == repo / "k8s" / "cluster-secrets.toml"


def test_a_required_path_that_the_tree_lacks_is_named_with_the_way_to_give_the_tree(
    tmp_path: Path,
) -> None:
    tree = EnvironmentTree(tmp_path, tmp_path)
    (tmp_path / "llm").mkdir()

    with pytest.raises(ConfigurationError) as caught:
        tree.require(tree.gateway_config)

    assert (tree.require(tmp_path / "llm"), caught.value.message) == (
        tmp_path / "llm",
        f"The environment tree {tmp_path} has no llm/gateway/config.yaml. Add to infra.repos the "
        "checkout of the infra repo that holds it, or, if the command has the option --k8s-dir, "
        "give the Kubernetes folder of that repo with it.",
    )


def test_a_tree_with_an_application_has_applications(tmp_path: Path) -> None:
    tree = EnvironmentTree(tmp_path, tmp_path)
    apps = tmp_path / "argocd" / "apps"
    apps.mkdir(parents=True)
    (apps / "web.yaml").write_text("kind: ConfigMap\n", encoding="utf-8")

    with pytest.raises(ConfigurationError) as caught:
        tree.require_applications()
    (apps / "web.yaml").write_text("kind: Application\nmetadata:\n  name: web\n", "utf-8")
    tree.require_applications()

    assert caught.value.message == (
        f"The environment tree {tmp_path} has no Argo CD Application under argocd/apps, "
        "argocd/bootstrap. Add to infra.repos the checkout of the infra repo that holds them, "
        "or, if the command has the option --k8s-dir, give the Kubernetes folder of that repo "
        "with it."
    )

"""One data directory across git worktrees (#553).

A relative data directory resolved against the current worktree, so each worktree kept its own
reviews, benchmarks and evaluations, and removing it deleted them: the first full sample
validation (#505) was lost that way. Linked worktrees now resolve to the main worktree, and
repositories cloned under the workspace's `repos/` keep sharing the workspace's (#582).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.ai.review.review_environment import _get_reviews_base_dir
from devops_cli.core.repo import main_worktree_root, resolve_data_path


@pytest.fixture
def repo_with_worktree(tmp_path: Path, git: Callable[..., None]) -> tuple[Path, Path]:
    """A repository and a linked worktree of it, outside the repository's own tree."""
    main = tmp_path / "project"
    main.mkdir()
    git(main, "init", "--quiet")
    (main / "README.md").write_text("project\n", encoding="utf-8")
    git(main, "add", ".")
    git(main, "commit", "--quiet", "-m", "first")
    linked = tmp_path / "worktrees" / "feature"
    git(main, "worktree", "add", "--quiet", "-b", "feature", str(linked))
    return main, linked


def test_a_linked_worktree_resolves_to_the_main_worktree(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    """Verify the main worktree is found from the main one, a linked one and a subdirectory."""
    main, linked = repo_with_worktree
    (linked / "src").mkdir()

    roots = (
        main_worktree_root(main),
        main_worktree_root(linked),
        main_worktree_root(linked / "src"),
    )

    assert roots == (main.resolve(),) * 3


def test_nested_linked_worktree_resolves_to_the_main_worktree(
    nested_worktree: tuple[Path, Path],
) -> None:
    """Verify a linked worktree nested inside the main checkout resolves to the main worktree."""
    main, nested = nested_worktree
    (nested / "src").mkdir()

    roots = (
        main_worktree_root(nested),
        main_worktree_root(nested / "src"),
        resolve_data_path(Path(".data/reviews"), nested),
    )
    expected = (
        main.resolve(),
        main.resolve(),
        (main / ".data" / "reviews").resolve(),
    )
    assert roots == expected


def test_a_nested_worktree_with_a_relative_gitdir_resolves_to_the_main_worktree(
    nested_worktree: tuple[Path, Path], git: Callable[..., None]
) -> None:
    """Verify a nested worktree added with `--relative-paths` shares the main worktree."""
    main, _ = nested_worktree
    relative = main / ".claude" / "worktrees" / "relative"
    try:
        git(main, "worktree", "add", "--quiet", "--relative-paths", "-b", "rel", str(relative))
    except subprocess.CalledProcessError:
        pytest.skip("git does not support `worktree add --relative-paths`")

    assert main_worktree_root(relative) == main.resolve()


def test_a_pruned_nested_worktree_shares_the_main_worktree(
    nested_worktree: tuple[Path, Path],
) -> None:
    """Verify a nested worktree whose git directory was pruned still shares the main worktree."""
    main, nested = nested_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "wt")

    assert main_worktree_root(nested) == main.resolve()


def test_a_pruned_worktree_outside_the_checkout_shares_the_main_worktree(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    """Verify a worktree outside the checkout whose git directory was pruned still shares the
    main worktree's data, found through the shared git directory its `.git` file names."""
    main, linked = repo_with_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "feature")

    roots = (main_worktree_root(linked), resolve_data_path(Path(".data"), linked))

    assert roots == (main.resolve(), (main / ".data").resolve())


def test_a_pruned_worktree_of_a_moved_checkout_keeps_its_own_data(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    """Verify a stale worktree whose main checkout is gone resolves to itself rather than to a
    directory that no longer holds the repository."""
    main, linked = repo_with_worktree
    main.rename(tmp_path / "moved")

    assert main_worktree_root(linked) == linked.resolve()


def test_a_clone_under_repos_and_its_worktree_share_the_workspace_data(
    nested_worktree: tuple[Path, Path], tmp_path: Path, git: Callable[..., None]
) -> None:
    """Verify a repository cloned under `repos/`, and a linked worktree of that clone, keep
    resolving to the workspace's data directory rather than to a directory of their own."""
    main, _ = nested_worktree
    clone = main / "repos" / "org" / "clone"
    git(tmp_path, "clone", "--quiet", str(main), str(clone))
    clone_worktree = main / "repos" / "org" / "clone-wt"
    git(clone, "worktree", "add", "--quiet", "-b", "clone-wt", str(clone_worktree))

    roots = (
        main_worktree_root(clone),
        main_worktree_root(clone_worktree),
        resolve_data_path(Path(".data/reviews"), clone_worktree),
    )

    assert roots == (main.resolve(), main.resolve(), (main / ".data" / "reviews").resolve())


def test_relative_data_paths_are_shared_and_absolute_ones_kept(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    """Verify every worktree's relative data path lands in the main worktree's data directory."""
    main, linked = repo_with_worktree

    resolved = (
        resolve_data_path(Path(".data/reviews"), linked),
        resolve_data_path(Path(".data/reviews"), main),
        resolve_data_path(tmp_path / "elsewhere", linked),
    )

    assert resolved == (
        (main / ".data" / "reviews").resolve(),
        (main / ".data" / "reviews").resolve(),
        tmp_path / "elsewhere",
    )


def test_a_git_file_without_a_shared_directory_and_no_git_keep_their_own_root(
    tmp_path: Path,
) -> None:
    """Verify a `.git` file whose git directory has no `commondir` (a submodule's) is not
    followed, and a directory outside git resolves to itself."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    modules = tmp_path / "store" / "modules" / "lib"
    modules.mkdir(parents=True)
    (checkout / ".git").write_text(f"gitdir: {modules}\n", encoding="utf-8")
    plain = tmp_path / "plain"
    plain.mkdir()

    assert (main_worktree_root(checkout), main_worktree_root(plain)) == (
        checkout.resolve(),
        plain.resolve(),
    )


def test_reviews_saved_from_a_worktree_outlive_it(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a review run in a linked worktree saves into the main worktree's data directory."""
    main, linked = repo_with_worktree
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    reviews = _get_reviews_base_dir()

    assert reviews == (main / ".data" / "reviews").resolve()


def test_the_spend_ledger_is_shared_from_any_directory(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the ledger no longer lands under whatever directory the command ran in."""
    from devops_cli.ai.spend.ledger import SpendLedger
    from devops_cli.config.defaults import DEFAULT_AI_SPEND_DB_FILENAME

    main, linked = repo_with_worktree
    (linked / "src").mkdir()
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked / "src")

    ledger = SpendLedger()

    assert ledger.db_path == (main / ".data").resolve() / "ai" / DEFAULT_AI_SPEND_DB_FILENAME


def test_cleanup_data_tier_from_outside_worktree_prunes_main_data(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cleanup_data_tier run in an outside linked worktree prunes the main worktree's .data."""
    import time

    from devops_cli.core.cleanup import cleanup_data_tier

    main, linked = repo_with_worktree
    reviews_dir = main / ".data" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    old_file = reviews_dir / "old_review.json"
    old_file.write_text('{"status": "ok"}', encoding="utf-8")
    ten_days_ago = time.time() - (10 * 86400)
    os.utime(old_file, (ten_days_ago, ten_days_ago))

    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    summary = cleanup_data_tier(repo_root=linked, older_than_seconds=7 * 86400, dry_run=False)

    assert (len(summary.pruned_files), old_file.exists()) == (1, False)


def test_cleanup_data_tier_refuses_non_dedicated_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cleanup_data_tier refuses to prune when data_dir is the repo root or invalid."""
    from devops_cli.core.cleanup import cleanup_data_tier

    repo = tmp_path / "repo"
    repo.mkdir()
    reviews = repo / "reviews"
    reviews.mkdir()
    old_file = reviews / "old.json"
    old_file.write_text("{}", encoding="utf-8")

    # Point data.dir directly to the repository root itself
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", ".")
    summary = cleanup_data_tier(repo_root=repo, older_than_seconds=0, dry_run=False)

    assert (len(summary.pruned_files), len(summary.pruned_dirs), old_file.exists()) == (
        0,
        0,
        True,
    )


def test_hallucination_catalog_and_feedback_dataset_shared_from_outside_worktree(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify hallucination catalog and feedback datasets resolve to the main worktree."""
    from devops_cli.ai.benchmark.suite import _resolve_suite_dataset_path
    from devops_cli.ai.prompt_eval import _resolve_dataset_path
    from devops_cli.ai.review.common_hallucinations import get_common_hallucinations_file_path

    main, linked = repo_with_worktree
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    actual = (
        get_common_hallucinations_file_path(),
        _resolve_suite_dataset_path(None),
        _resolve_dataset_path(None, main_worktree_root(linked)),
    )
    expected = (
        (main / ".data" / "common_hallucinations.json").resolve(),
        (main / ".data" / "feedback_dataset.jsonl").resolve(),
        (main / ".data" / "feedback_dataset.jsonl").resolve(),
    )
    assert actual == expected


def test_relative_devops_cli_data_dir_resolves_to_main_worktree(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a relative DEVOPS_CLI_DATA_DIR anchors under the main worktree."""
    from devops_cli.ai.review.common_hallucinations import get_common_hallucinations_file_path

    main, linked = repo_with_worktree
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "custom_data")
    monkeypatch.chdir(linked)

    assert (
        get_common_hallucinations_file_path()
        == (main / "custom_data" / "common_hallucinations.json").resolve()
    )


def test_model_bundler_and_workspace_discovery_shared_from_outside_worktree(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify model bundles and workspace discovery resolve to the main worktree."""
    import asyncio

    from devops_cli.ai.model_bundler import bundle_ollama_models
    from devops_cli.server.routes.workspace import list_workspaces

    main, linked = repo_with_worktree
    repos_dir = main / "repos" / "owner" / "child_repo"
    repos_dir.mkdir(parents=True, exist_ok=True)
    (repos_dir / ".git").mkdir()

    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    _count, manifest_path = bundle_ollama_models(models=["test-model"])
    res = asyncio.run(list_workspaces())

    assert (
        manifest_path.parent == (main / ".data" / "models").resolve(),
        res.workspace_root == str(main.resolve()),
        len(res.repositories) == 1,
    ) == (True, True, True)


def test_subsystems_shared_from_outside_worktree(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify CI cache, library drift auditor, dashboard reviews, controller, sandbox and quota resolve to main."""
    from devops_cli.ai.controller.manager import _resolve_data_dir
    from devops_cli.ai.library.drift_auditor import LibraryDriftAuditor
    from devops_cli.ai.spend.pricing import PricingRegistry
    from devops_cli.argo.gitops import _get_baseline_cache_file
    from devops_cli.ci.cache import resolve_ci_cache_path
    from devops_cli.github.rate_limiter import resolve_quota_cache_path
    from devops_cli.k8s.port_forward_daemon import get_daemon_manager
    from devops_cli.sandbox.logs import resolve_incident_dir
    from devops_cli.sandbox.registry import get_default_sandbox_registry_path
    from devops_cli.ui.data_providers import _reviews_root

    main, linked = repo_with_worktree
    (main / ".data" / "reviews").mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    auditor = LibraryDriftAuditor()
    pricing = PricingRegistry()
    daemon_mgr = get_daemon_manager()

    actual = (
        resolve_ci_cache_path(),
        auditor.contracts_dir,
        _reviews_root(),
        _resolve_data_dir(),
        get_default_sandbox_registry_path(),
        resolve_incident_dir(),
        resolve_quota_cache_path(),
        pricing.data_dir,
        _get_baseline_cache_file(["k8s/test.yaml"]).parent,
        daemon_mgr.state_file,
    )
    expected = (
        (main / ".data" / "cache" / "ci_cache.json").resolve(),
        (main / ".data" / "libraries").resolve(),
        (main / ".data" / "reviews").resolve(),
        (main / ".data").resolve(),
        (main / ".data" / "sandbox" / "instances.json").resolve(),
        (main / ".data" / "sandbox" / "incidents").resolve(),
        (main / ".data" / "cache" / "gh_quota.json").resolve(),
        (main / ".data").resolve(),
        (main / ".data" / "gitops").resolve(),
        (main / ".data" / "k8s" / "port_forwards.json").resolve(),
    )
    assert actual == expected

"""One data directory across git worktrees (#553).

A relative data directory resolved against the current worktree, so each worktree kept its own
reviews, benchmarks and evaluations, and removing it deleted them: the first full sample
validation (#505) was lost that way. Linked worktrees now resolve to the main worktree, and
repositories cloned under the workspace's `repos/` keep sharing the workspace's (#582).
"""

from __future__ import annotations

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

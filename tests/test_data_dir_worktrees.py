"""One data directory across git worktrees (#553).

A relative data directory resolved against the current worktree, so each worktree kept its own
reviews, benchmarks and evaluations, and removing it deleted them: the first full sample
validation (#505) was lost that way. Linked worktrees now resolve to the main worktree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.ai.review.review_environment import _get_reviews_base_dir
from devops_cli.core.repo import main_worktree_root, resolve_data_path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A repository and a linked worktree of it, outside the repository's own tree."""
    main = tmp_path / "project"
    main.mkdir()
    _git(main, "init", "--quiet")
    (main / "README.md").write_text("project\n", encoding="utf-8")
    _git(main, "add", ".")
    _git(main, "commit", "--quiet", "-m", "first")
    linked = tmp_path / "worktrees" / "feature"
    _git(main, "worktree", "add", "--quiet", "-b", "feature", str(linked))
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

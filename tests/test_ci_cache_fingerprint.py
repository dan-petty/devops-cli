"""Test suite for the content-addressed CI cache fingerprint."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.ci.cache import (
    _worktree_divergent_paths,
    compute_workspace_fingerprint,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a git repository with one committed file."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)
    return tmp_path


def fingerprint(repo: Path) -> str:
    """Compute the workspace fingerprint, failing loudly if it cannot be produced."""
    result = compute_workspace_fingerprint(root=repo)
    assert result is not None
    return result[0]


def git(repo: Path, *args: str) -> None:
    """Run a git command in the repository."""
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


# =============================================================================
# Invariance
# =============================================================================


def test_staging_a_change_does_not_change_the_fingerprint(repo: Path) -> None:
    """`git add` moves content between the worktree and the index without altering it.

    The fingerprint previously hashed the staged and unstaged diffs separately, so staging
    invalidated a verified run even though nothing the checks read had changed.
    """
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    before = fingerprint(repo)
    git(repo, "add", "-A")
    assert fingerprint(repo) == before


def test_committing_does_not_change_the_fingerprint(repo: Path) -> None:
    """This is the defect that made the cache useless in practice.

    Committing is exactly what happens between running `devops ci` and pushing, and the
    fingerprint included HEAD -- so the pre-push hook could never hit the cache and re-ran
    the entire suite on every push.
    """
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    before = fingerprint(repo)
    git(repo, "commit", "-qm", "change")
    assert fingerprint(repo) == before


def test_a_verified_tree_survives_the_whole_commit_and_push_sequence(repo: Path) -> None:
    """The sequence a developer actually performs, end to end."""
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    after_ci = fingerprint(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "change")
    assert fingerprint(repo) == after_ci


def test_an_amended_commit_preserves_the_fingerprint(repo: Path) -> None:
    """Amending rewrites history without changing what the checks read."""
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "change")
    before = fingerprint(repo)
    git(repo, "commit", "-q", "--amend", "-m", "reworded")
    assert fingerprint(repo) == before


# =============================================================================
# Sensitivity
# =============================================================================


def test_editing_a_tracked_file_changes_the_fingerprint(repo: Path) -> None:
    """Invariance is only safe if real changes still invalidate."""
    before = fingerprint(repo)
    (repo / "app.py").write_text("value = 99\n", encoding="utf-8")
    assert fingerprint(repo) != before


def test_an_untracked_file_changes_the_fingerprint(repo: Path) -> None:
    """A new file is code the checks will read."""
    before = fingerprint(repo)
    (repo / "extra.py").write_text("value = 1\n", encoding="utf-8")
    assert fingerprint(repo) != before


def test_deleting_a_file_changes_the_fingerprint(repo: Path) -> None:
    """Removal changes what the checks read just as much as addition."""
    before = fingerprint(repo)
    (repo / "app.py").unlink()
    assert fingerprint(repo) != before


def test_reverting_a_change_restores_the_fingerprint(repo: Path) -> None:
    """Content addressing means the fingerprint follows content, not history.

    Undoing an edit returns the tree to a state that was already verified.
    """
    before = fingerprint(repo)
    (repo / "scratch.py").write_text("value = 1\n", encoding="utf-8")
    assert fingerprint(repo) != before
    (repo / "scratch.py").unlink()
    assert fingerprint(repo) == before


def test_options_are_part_of_the_fingerprint(repo: Path) -> None:
    """A run with different options verified something different."""
    first = compute_workspace_fingerprint(root=repo, options={"fast": True})
    second = compute_workspace_fingerprint(root=repo, options={"fast": False})
    assert first is not None and second is not None
    assert first[0] != second[0]


def test_an_ignored_file_does_not_change_the_fingerprint(repo: Path) -> None:
    """Build output and caches are not inputs to any check.

    Counting them would invalidate a verified tree every time a tool wrote a log.
    """
    (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "ignore logs")
    before = fingerprint(repo)
    (repo / "run.log").write_text("noise\n", encoding="utf-8")
    assert fingerprint(repo) == before


# =============================================================================
# Status Parsing
# =============================================================================


def test_a_worktree_modification_is_detected(repo: Path) -> None:
    """Porcelain reports an unmodified index as a leading space.

    Stripping that space shifts every column by one, so a file modified in the working tree
    reads as one modified in the index -- inverting the distinction entirely.
    """
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    changed, deleted = _worktree_divergent_paths(repo)
    assert ("app.py" in changed, deleted) == (True, [])


def test_an_untracked_file_is_detected(repo: Path) -> None:
    """Untracked files are inputs too."""
    (repo / "new.py").write_text("value = 1\n", encoding="utf-8")
    changed, _ = _worktree_divergent_paths(repo)
    assert "new.py" in changed


def test_a_deleted_file_is_detected(repo: Path) -> None:
    """A removal must drop the path rather than hash a file that is gone."""
    (repo / "app.py").unlink()
    _, deleted = _worktree_divergent_paths(repo)
    assert "app.py" in deleted


def test_a_rename_changes_the_fingerprint(repo: Path) -> None:
    """A rename changes which paths the checks read, even though no content differs.

    `git mv` stages the move, so the index already carries the new path and nothing needs
    re-hashing -- the fingerprint changes because it is computed over paths and contents
    together.
    """
    before = fingerprint(repo)
    git(repo, "mv", "app.py", "renamed.py")
    assert fingerprint(repo) != before


def test_an_unstaged_rename_reports_the_new_path(repo: Path) -> None:
    """Moving a file without staging leaves a deletion and an untracked path."""
    (repo / "renamed.py").write_text(
        (repo / "app.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo / "app.py").unlink()
    changed, deleted = _worktree_divergent_paths(repo)
    assert ("renamed.py" in changed, "app.py" in deleted) == (True, True)


def test_a_clean_repository_reports_nothing_divergent(repo: Path) -> None:
    """A freshly committed tree has no divergence to hash."""
    assert _worktree_divergent_paths(repo) == ([], [])

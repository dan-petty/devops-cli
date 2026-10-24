"""Tests for devops repos worktrees status and prune (#700)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.repos import app
from devops_cli.git.worktree_inventory import (
    count_dirty_paths,
    parse_worktree_porcelain_z,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository with a committed main branch."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def _add_worktree(repo: Path, branch: str, path: Path) -> None:
    """Helper to create a git worktree on a new branch."""
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", branch, str(path)],
        check=True,
        capture_output=True,
    )


def test_worktrees_status_table_and_lock_reason(git_repo: Path, tmp_path: Path) -> None:
    """Criteria 1 & 7: status lists worktrees with ahead, dirty, contained, and lock reason."""
    wt_merged = tmp_path / "wt_merged"
    _add_worktree(git_repo, "branch-merged", wt_merged)

    wt_ahead = tmp_path / "wt_ahead"
    _add_worktree(git_repo, "branch-ahead", wt_ahead)
    (wt_ahead / "new_file.txt").write_text("feature\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(wt_ahead), "add", "new_file.txt"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(wt_ahead), "commit", "-m", "ahead commit"],
        check=True,
        capture_output=True,
    )

    # Lock wt_ahead with owner marker
    subprocess.run(
        ["git", "-C", str(git_repo), "worktree", "lock", "--reason", "agent-42", str(wt_ahead)],
        check=True,
        capture_output=True,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["worktrees", "status", "--repo-dir", str(git_repo)])

    assert (
        result.exit_code,
        "branch-merged" in result.stdout,
        "branch-ahead" in result.stdout,
        "locked=true" in result.stdout,
        "agent-42" in result.stdout,
    ) == (0, True, True, True, True)


def test_worktrees_status_json_schema(git_repo: Path, tmp_path: Path) -> None:
    """Criterion 2: devops repos worktrees status --json emits typed JSON array."""
    wt_one = tmp_path / "wt_one"
    _add_worktree(git_repo, "branch-one", wt_one)

    runner = CliRunner()
    result = runner.invoke(app, ["worktrees", "status", "--repo-dir", str(git_repo), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert len(payload) >= 2

    # Check types on each entry
    for obj in payload:
        assert isinstance(obj["ahead"], int)
        assert isinstance(obj["dirty"], int)
        assert isinstance(obj["contained"], bool)
        assert isinstance(obj["locked"], bool)
        assert isinstance(obj["prunable"], bool)


def test_worktrees_prune_unmerged_refused_without_delete(git_repo: Path, tmp_path: Path) -> None:
    """Criterion 3: prune defaults to preview, unmerged commits are refused and not deleted."""
    wt_unmerged = tmp_path / "wt_unmerged"
    _add_worktree(git_repo, "branch-unmerged", wt_unmerged)
    (wt_unmerged / "data.txt").write_text("unmerged\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(wt_unmerged), "add", "data.txt"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(wt_unmerged), "commit", "-m", "unmerged commit"],
        check=True,
        capture_output=True,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["worktrees", "prune", "--repo-dir", str(git_repo)])

    assert (
        result.exit_code,
        wt_unmerged.exists(),
        "refused" in result.stdout,
    ) == (0, True, True)


def test_worktrees_prune_removes_clean_contained_and_refuses_unmerged(
    git_repo: Path, tmp_path: Path
) -> None:
    """Criterion 4: prune removes clean and contained worktree, refuses unmerged one."""
    # Worktree 1: merged into main (clean and contained)
    wt_clean = tmp_path / "wt_clean"
    _add_worktree(git_repo, "branch-clean", wt_clean)

    # Worktree 2: unmerged commit
    wt_unmerged = tmp_path / "wt_unmerged2"
    _add_worktree(git_repo, "branch-unmerged2", wt_unmerged)
    (wt_unmerged / "feature.txt").write_text("feature\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(wt_unmerged), "add", "feature.txt"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(wt_unmerged), "commit", "-m", "unmerged"], check=True, capture_output=True
    )

    runner = CliRunner()
    result = runner.invoke(app, ["worktrees", "prune", "--repo-dir", str(git_repo)])

    assert (
        result.exit_code,
        wt_clean.exists(),
        wt_unmerged.exists(),
        "removed" in result.stdout,
        "refused" in result.stdout,
    ) == (0, False, True, True, True)


def test_worktrees_prune_force_removes_unmerged(git_repo: Path, tmp_path: Path) -> None:
    """Criterion 5 & 6: prune --force removes entries regardless of state and cleans git metadata."""
    wt_unmerged = tmp_path / "wt_force"
    _add_worktree(git_repo, "branch-force", wt_unmerged)
    (wt_unmerged / "draft.txt").write_text("draft\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(wt_unmerged), "add", "draft.txt"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(wt_unmerged), "commit", "-m", "force candidate"],
        check=True,
        capture_output=True,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["worktrees", "prune", "--force", "--repo-dir", str(git_repo)])

    proc = subprocess.run(
        ["git", "-C", str(git_repo), "worktree", "list"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert (
        result.exit_code,
        wt_unmerged.exists(),
        "branch-force" in proc.stdout,
    ) == (0, False, False)


def test_worktrees_nul_separated_path_with_newline() -> None:
    """Criterion 8: parser handles NUL-separated records and paths containing newline bytes."""
    raw = (
        b"worktree /path/to/my\nworktree\0"
        b"HEAD 1234567890abcdef1234567890abcdef12345678\0"
        b"branch refs/heads/feature-newline\0"
        b"locked owner-agent\0\0"
        b"worktree /second/worktree\0"
        b"HEAD abcdef1234567890abcdef1234567890abcdef12\0"
        b"detached\0"
        b"prunable missing directory\0\0"
    )

    parsed = parse_worktree_porcelain_z(raw)
    assert len(parsed) == 2

    first, second = parsed[0], parsed[1]
    assert (
        str(first.path),
        first.head,
        first.branch,
        first.locked,
        first.lock_reason,
        first.is_main,
    ) == (
        "/path/to/my\nworktree",
        "1234567890abcdef1234567890abcdef12345678",
        "refs/heads/feature-newline",
        True,
        "owner-agent",
        True,
    )

    assert (
        str(second.path),
        second.head,
        second.branch,
        second.detached,
        second.prunable,
        second.prunable_reason,
        second.is_main,
    ) == (
        "/second/worktree",
        "abcdef1234567890abcdef1234567890abcdef12",
        None,
        True,
        True,
        "missing directory",
        False,
    )


def test_count_dirty_paths_handles_modifications_and_renames(git_repo: Path) -> None:
    """Test dirty path count with untracked, modified, and renamed files."""
    assert count_dirty_paths(git_repo) == 0

    (git_repo / "untracked.txt").write_text("new\n", encoding="utf-8")
    (git_repo / "file.txt").write_text("modified\n", encoding="utf-8")

    assert count_dirty_paths(git_repo) == 2

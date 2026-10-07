"""Unit tests for detached git worktree management (#1047)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from devops_cli.git.worktree import (
    add_detached_worktree,
    fetch_pr_head,
    get_user_worktrees_dir,
    remove_worktree,
    review_worktrees_context,
)


def _init_git_repo(repo_dir: Path) -> None:
    """Initialize a git repo with configured user."""
    subprocess.run(["git", "init", "-b", "main", str(repo_dir)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.name", "Test Runner"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.email", "runner@example.com"],
        check=True,
        capture_output=True,
    )


def test_get_user_worktrees_dir(monkeypatch: object, tmp_path: Path) -> None:
    """get_user_worktrees_dir honors environment override and creates directory."""
    import os

    custom_root = tmp_path / "custom_data"
    with patch.dict(os.environ, {"DEVOPS_CLI_USER_DATA_ROOT": str(custom_root)}):
        wt_dir = get_user_worktrees_dir()
        assert (wt_dir.is_dir(), wt_dir) == (True, custom_root / "worktrees")


def test_add_and_remove_detached_worktree(tmp_path: Path) -> None:
    """add_detached_worktree creates detached worktree; remove_worktree cleans it up."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    f = repo / "f.txt"
    f.write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True
    )

    dest = tmp_path / "worktrees" / "wt1"
    added = add_detached_worktree(repo, "main", dest)
    assert (added, dest.is_dir(), (dest / "f.txt").is_file()) == (True, True, True)

    remove_worktree(repo, dest)
    assert dest.exists() is False


def test_fetch_pr_head_mocked(tmp_path: Path) -> None:
    """fetch_pr_head executes fetch refs/pull/N/head and rev-parse."""
    repo = tmp_path / "fake_repo"

    ok_proc = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="abcd1234ef\n", stderr=""
    )
    fail_proc = subprocess.CompletedProcess(args=["git"], returncode=128, stdout="", stderr="fatal")

    with patch("devops_cli.git.worktree.run_subprocess", return_value=ok_proc):
        rev = fetch_pr_head(repo, 42)
        assert rev == "abcd1234ef"

    with patch("devops_cli.git.worktree.run_subprocess", return_value=fail_proc):
        rev = fetch_pr_head(repo, 42)
        assert rev is None


def test_review_worktrees_context_lifecycle(tmp_path: Path) -> None:
    """review_worktrees_context sets up worktrees and removes them on exit."""
    repo = tmp_path / "repo_ctx"
    repo.mkdir()
    _init_git_repo(repo)

    f = repo / "main.py"
    f.write_text("print('main')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "initial"], check=True, capture_output=True
    )

    session_id = "test-session-ctx"
    with review_worktrees_context(
        repo, commit_rev="main", base_rev="main", session_id=session_id
    ) as rw:
        assert (
            rw.commit_worktree is not None,
            rw.base_worktree is not None,
            rw.partial_context,
        ) == (
            True,
            True,
            False,
        )
        assert (rw.commit_worktree.is_dir(), rw.base_worktree.is_dir()) == (True, True)
        wt_commit_path = rw.commit_worktree
        wt_base_path = rw.base_worktree

    assert (wt_commit_path.exists(), wt_base_path.exists()) == (False, False)

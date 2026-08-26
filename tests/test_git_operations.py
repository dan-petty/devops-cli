"""Tests for Git operation helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import git as gitlib
import pytest

from devops_cli.git.operations import (
    _ensure_known_host,
    _normalize_clone_url,
    clone_repo,
    create_branch,
    delete_merged_branches,
    fetch_all,
    iter_workspace_repos,
    list_branches,
    pull_tracking,
)


def test_normalize_clone_url() -> None:
    """Verify clone URL normalization logic."""
    assert _normalize_clone_url("git@github.com:org/repo.git") == "git@github.com:org/repo.git"
    assert (
        _normalize_clone_url("ssh://git@github.com/org/repo.git")
        == "ssh://git@github.com/org/repo.git"
    )
    assert _normalize_clone_url("github.com/org/repo.git") == "https://github.com/org/repo.git"
    assert (
        _normalize_clone_url("http://github.com/org/repo.git") == "https://github.com/org/repo.git"
    )
    assert (
        _normalize_clone_url("https://github.com/org/repo.git") == "https://github.com/org/repo.git"
    )
    assert (
        _normalize_clone_url("https://gitlab.com/org/repo.git") == "https://gitlab.com/org/repo.git"
    )


def test_iter_workspace_repos(tmp_path: Path) -> None:
    """Verify iter_workspace_repos traverses two directory levels and discovers .git repos."""
    # Non-existent root
    assert list(iter_workspace_repos(tmp_path / "nonexistent")) == []

    # Valid root with group and repo directories
    group_a = tmp_path / "group_a"
    group_a.mkdir()
    repo_1 = group_a / "repo_1"
    repo_1.mkdir()
    (repo_1 / ".git").mkdir()

    repo_2 = group_a / "repo_2"
    repo_2.mkdir()  # No .git

    # Plain file in root should be skipped
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")

    discovered = list(iter_workspace_repos(tmp_path))
    assert discovered == [repo_1]


def test_ensure_known_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _ensure_known_host checks and writes host keys."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    # 1. Host already known in known_hosts
    known_hosts = fake_home / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    known_hosts.write_text("github.com ssh-ed25519 AAAAC3\n", encoding="utf-8")

    with patch("devops_cli.git.operations.run_subprocess") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _ensure_known_host("github.com")
        mock_run.assert_called_once()

    # 2. Host missing from known_hosts -> fetch with keyscan
    with patch("devops_cli.git.operations.run_subprocess") as mock_run:
        # First call (ssh-keygen check) fails
        keygen_res = MagicMock(returncode=1)
        # Second call (ssh-keyscan) succeeds
        keyscan_res = MagicMock(
            returncode=0, stdout="github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA"
        )
        mock_run.side_effect = [keygen_res, keyscan_res]
        _ensure_known_host("github.com")

        content = known_hosts.read_text(encoding="utf-8")
        assert "AAAAC3NzaC1lZDI1NTE5AAAA" in content


def test_clone_repo_ensures_github_known_host_for_ssh_urls(tmp_path: Path) -> None:
    with (
        patch("devops_cli.git.operations._ensure_known_host") as mock_known_host,
        patch("devops_cli.git.operations.gitlib.Repo.clone_from") as mock_clone_from,
    ):
        clone_repo("git@github.com:example/repo.git", tmp_path / "repo")

    mock_known_host.assert_called_once_with()
    mock_clone_from.assert_called_once()


def test_fetch_all(tmp_path: Path) -> None:
    """Verify fetch_all calls remote.fetch on all remotes."""
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_repo.remotes = [mock_remote]
        mock_repo_cls.return_value = mock_repo

        fetch_all(tmp_path)
        mock_remote.fetch.assert_called_once_with(prune=True)

        # Exception handling
        mock_remote.fetch.side_effect = gitlib.GitCommandError("fetch", "network error")
        fetch_all(tmp_path)


def test_pull_tracking(tmp_path: Path) -> None:
    """Verify pull_tracking pulls tracking branch when configured."""
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.head.is_detached = False
        mock_tracking = MagicMock(remote_name="origin")
        mock_branch = MagicMock()
        mock_branch.name = "main"
        mock_branch.tracking_branch.return_value = mock_tracking
        mock_repo.active_branch = mock_branch
        mock_remote = MagicMock()
        mock_repo.remotes = {"origin": mock_remote}
        mock_repo_cls.return_value = mock_repo

        pull_tracking(tmp_path)
        mock_remote.pull.assert_called_once_with("main")


def test_create_branch(tmp_path: Path) -> None:
    """Verify create_branch checks input and runs checkout."""
    # Invalid name starting with hyphen
    with pytest.raises(ValueError, match="cannot start with a hyphen"):
        create_branch(tmp_path, "-invalid")

    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_b1 = MagicMock(name="main")
        mock_b1.name = "main"
        mock_repo.branches = [mock_b1]
        mock_repo_cls.return_value = mock_repo

        # Already exists
        with pytest.raises(ValueError, match="already exists"):
            create_branch(tmp_path, "main")

        # Success
        create_branch(tmp_path, "feat/test")
        mock_repo.git.checkout.assert_called_once_with("-b", "--", "feat/test")


def test_list_branches(tmp_path: Path) -> None:
    """Verify list_branches returns local and remote branch listings."""
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "main"
        mock_b1 = MagicMock()
        mock_b1.name = "main"
        mock_b2 = MagicMock()
        mock_b2.name = "feat/xyz"
        mock_repo.branches = [mock_b1, mock_b2]

        mock_remote = MagicMock()
        mock_ref1 = MagicMock()
        mock_ref1.name = "origin/feat/remote"
        mock_ref_head = MagicMock()
        mock_ref_head.name = "origin/HEAD"
        mock_remote.refs = [mock_ref1, mock_ref_head]
        mock_repo.remotes = [mock_remote]
        mock_repo_cls.return_value = mock_repo

        # Local only
        listing_local = list_branches(tmp_path, all_branches=False)
        assert listing_local.current == "main"
        assert listing_local.branches == ["feat/xyz", "main"]

        # All branches
        listing_all = list_branches(tmp_path, all_branches=True)
        assert "origin/feat/remote" in listing_all.branches
        assert "origin/HEAD" not in listing_all.branches


def test_delete_merged_branches(tmp_path: Path) -> None:
    """Verify delete_merged_branches identifies and removes non-protected merged branches."""
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_main = MagicMock()
        mock_main.name = "main"
        mock_feat = MagicMock()
        mock_feat.name = "feat/merged"
        mock_repo.branches = [mock_main, mock_feat]
        mock_repo.git.branch.return_value = "  main\n* feat/merged\n"
        mock_repo_cls.return_value = mock_repo

        # Dry run
        deleted_dry = delete_merged_branches(tmp_path, dry_run=True)
        assert deleted_dry == ["feat/merged"]
        mock_repo.delete_head.assert_not_called()

        # Actual run
        deleted_act = delete_merged_branches(tmp_path, dry_run=False)
        assert deleted_act == ["feat/merged"]
        mock_repo.delete_head.assert_called_once_with(mock_feat, force=False)


def test_is_git_clean_and_get_latest_tag(tmp_path: Path) -> None:
    """Verify is_git_clean and get_latest_git_tag."""
    from devops_cli.git.operations import get_latest_git_tag, is_git_clean

    mock_clean = MagicMock(returncode=0, stdout="")
    with patch("devops_cli.git.operations.run_subprocess", return_value=mock_clean):
        assert is_git_clean(tmp_path) is True

    mock_dirty = MagicMock(returncode=0, stdout=" M file.py\n")
    with patch("devops_cli.git.operations.run_subprocess", return_value=mock_dirty):
        assert is_git_clean(tmp_path) is False

    mock_tag = MagicMock(returncode=0, stdout="v0.2.1\n")
    with patch("devops_cli.git.operations.run_subprocess", return_value=mock_tag):
        assert get_latest_git_tag(tmp_path) == "v0.2.1"

    mock_no_tag = MagicMock(returncode=128, stdout="")
    with patch("devops_cli.git.operations.run_subprocess", return_value=mock_no_tag):
        assert get_latest_git_tag(tmp_path) is None

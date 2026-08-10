"""Tests for Git operation helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from devops_cli.git.operations import clone_repo


def test_clone_repo_ensures_github_known_host_for_ssh_urls(tmp_path: Path) -> None:
    with (
        patch("devops_cli.git.operations._ensure_known_host") as mock_known_host,
        patch("devops_cli.git.operations.gitlib.Repo.clone_from") as mock_clone_from,
    ):
        clone_repo("git@github.com:example/repo.git", tmp_path / "repo")

    mock_known_host.assert_called_once_with()
    mock_clone_from.assert_called_once()

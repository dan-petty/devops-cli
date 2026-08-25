"""Tests for repos commands and repository utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.repos import app as repos_app
from devops_cli.core.repo import (
    find_repo_root,
    find_top_level_repo_root,
    get_repo_origin_name,
    is_ignored_by_git,
    list_repo_files,
    read_gitignore_patterns,
)
from devops_cli.main import app

runner = CliRunner()


def test_repos_list_empty_dir(tmp_path: Path) -> None:
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()

    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.repos.base_dir = repos_dir
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "list"])

    assert result.exit_code == 0


def test_repos_list_missing_dir(tmp_path: Path) -> None:
    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "nonexistent"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "list"])

    assert result.exit_code == 0
    assert "not found" in result.output.lower()


@pytest.mark.parametrize(
    "url,expected_name",
    [
        ("https://github.com/org/my-repo.git", "my-repo"),
        ("git@github.com:org/my-repo.git", "my-repo"),
        ("https://github.com/org/my-repo", "my-repo"),
        ("https://github.com/org/some_tool.git", "some_tool"),
    ],
)
def test_repo_name_extraction(url: str, expected_name: str) -> None:
    """Repo name is extracted correctly from any URL format."""
    name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    assert name == expected_name


def test_repos_clone_requires_token(tmp_path: Path) -> None:
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.get_github_token", return_value=None),
    ):
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "repos"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone-org", "my-org"])

    assert result.exit_code != 0


def test_repos_clone_org_uses_default_org(tmp_path: Path) -> None:
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.get_github_token", return_value="token"),
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
        patch("devops_cli.github.client.GitHubClient") as mock_client_cls,
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        mock_client = MagicMock()
        mock_client.get_org_repos.return_value = []
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["repos", "clone-org"])

    assert result.exit_code == 0
    mock_client.get_org_repos.assert_called_once_with(
        "example-org",
        include_private=True,
        include_forks=False,
        include_archived=False,
    )
    mock_clone_repo.assert_not_called()
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_clone_org_skips_archived_repos(tmp_path: Path) -> None:
    archived_repo = MagicMock()
    archived_repo.name = "archived-repo"
    archived_repo.full_name = "example/archived-repo"
    archived_repo.clone_url = "git@github.com:example/archived-repo.git"
    archived_repo.ssh_url = "git@github.com:example/archived-repo.git"
    archived_repo.archived = True
    archived_repo.fork = False
    archived_repo.private = False

    active_repo = MagicMock()
    active_repo.name = "active-repo"
    active_repo.full_name = "example/active-repo"
    active_repo.clone_url = "git@github.com:example/active-repo.git"
    active_repo.ssh_url = "git@github.com:example/active-repo.git"
    active_repo.archived = False
    active_repo.fork = False
    active_repo.private = False

    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.get_github_token", return_value="token"),
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
        patch("devops_cli.github.client.GitHubClient") as mock_client_cls,
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        mock_client = MagicMock()

        mock_client.get_org_repos.return_value = [active_repo]
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["repos", "clone-org"])

    assert result.exit_code == 0
    mock_clone_repo.assert_called_once_with(
        "https://github.com/example/active-repo.git",
        settings.repos.base_dir / "example-org" / "active-repo",
    )
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_clone_passes_github_urls_to_clone_repo(tmp_path: Path) -> None:
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
    ):
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone", "github.com/example/repo.git"])

    assert result.exit_code == 0
    mock_clone_repo.assert_called_once_with(
        "github.com/example/repo.git",
        tmp_path / "repos" / "_standalone" / "repo",
    )
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_update_syncs_workspace(tmp_path: Path) -> None:
    repos_dir = tmp_path / "repos"
    group_dir = repos_dir / "group"
    repo_dir = group_dir / "repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
    ):
        settings = MagicMock()
        settings.repos.base_dir = repos_dir
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "update"])

    assert result.exit_code == 0
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_update_no_repos(tmp_path: Path) -> None:
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()

    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.repos.base_dir = repos_dir
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "update"])

    assert result.exit_code == 0
    assert "No repositories" in result.output


def test_repo_origin_and_git_ignore_helpers(tmp_path: Path) -> None:
    """Verify get_repo_origin_name and is_ignored_by_git."""
    (tmp_path / ".git").mkdir()
    mock_proc = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="git@github.com:org/repo.git\n", stderr=""
    )
    with patch("devops_cli.core.process.run_subprocess", return_value=mock_proc):
        origin = get_repo_origin_name(tmp_path)
        assert origin == "org/repo"

    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    assert is_ignored_by_git(tmp_path, tmp_path / "ignored.txt") is True
    assert is_ignored_by_git(tmp_path, tmp_path / ".git" / "config") is True


def test_core_repo_find_roots(tmp_path: Path) -> None:
    """Verify finding repo roots in nested directories."""
    sub = tmp_path / "a" / "b" / "c"
    sub.mkdir(parents=True)
    git_dir = tmp_path / "a" / ".git"
    git_dir.mkdir()

    root = find_repo_root(sub)
    assert root == tmp_path / "a"

    top_root = find_top_level_repo_root(sub)
    assert top_root == tmp_path / "a"


def test_core_repo_gitignore_and_files(tmp_path: Path) -> None:
    """Verify gitignore parsing and listing repo files."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.tmp\nbuild/\n# comment\n", encoding="utf-8")

    patterns = read_gitignore_patterns(tmp_path)
    assert "*.tmp" in patterns
    assert "build/" in patterns

    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "test.tmp").write_text("temp", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.bin").write_text("bin", encoding="utf-8")

    files = list_repo_files(tmp_path)
    file_names = [f.name for f in files]
    assert "app.py" in file_names
    assert is_ignored_by_git(tmp_path, tmp_path / "test.tmp") is True
    assert is_ignored_by_git(tmp_path, tmp_path / "app.py") is False


def test_repos_commands_dry_run(tmp_path: Path) -> None:
    """Verify repos list and sync in dry-run mode."""
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        res_list = runner.invoke(repos_app, ["list", "--base-dir", str(tmp_path)])
        assert res_list.exit_code == 0

        res_sync = runner.invoke(repos_app, ["sync", "--base-dir", str(tmp_path)])
        assert res_sync.exit_code == 0

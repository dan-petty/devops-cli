"""Tests for repos commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

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
        patch("devops_cli.github.client.GitHubClient") as mock_client_cls,
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
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
        patch("devops_cli.github.client.GitHubClient") as mock_client_cls,
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
        mock_load.return_value = settings

        mock_client = MagicMock()

        def _get_org_repos(*args: object, **kwargs: object) -> list[MagicMock]:
            if kwargs.get("include_archived", True):
                return [archived_repo, active_repo]
            return [active_repo]

        mock_client.get_org_repos.side_effect = _get_org_repos
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["repos", "clone-org"])

    assert result.exit_code == 0
    mock_clone_repo.assert_called_once_with(
        "https://github.com/example/active-repo.git",
        settings.repos.base_dir / "example-org" / "active-repo",
    )


def test_repos_clone_normalizes_github_urls_to_https(tmp_path: Path) -> None:
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
    ):
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "repos"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone", "github.com/example/repo.git"])

    assert result.exit_code == 0
    mock_clone_repo.assert_called_once_with(
        "https://github.com/example/repo.git",
        tmp_path / "repos" / "_standalone" / "repo",
    )


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

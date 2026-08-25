"""Tests for workspace subcommands and multi-root workspace file generation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.workspace import app as workspace_app
from devops_cli.commands.workspace import sync_from_repos
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_SHORT_TIMEOUT_SECONDS
from devops_cli.main import app

runner = CliRunner()


def test_sync_from_repos_generates_multiroot_workspace(tmp_path: Path) -> None:
    repos_root = tmp_path / "repos"
    alpha = repos_root / "group-a" / "alpha"
    beta = repos_root / "group-b" / "beta"
    (alpha / ".git").mkdir(parents=True)
    (beta / ".git").mkdir(parents=True)

    workspace_file = tmp_path / ".code-workspace"

    sync_from_repos(repos_root, workspace_file)

    data = json.loads(workspace_file.read_text(encoding="utf-8"))
    assert [folder["path"] for folder in data["folders"]] == [
        str(alpha.resolve()),
        str(beta.resolve()),
        ".",
    ]
    assert data["settings"]["editor.formatOnSave"] is True
    assert data["settings"]["files.trimTrailingWhitespace"] is True


def test_workspace_generate_resolves_default_paths_from_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    repos_root = project_root / "repos"
    repo_dir = repos_root / "group" / "repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    settings = MagicMock()
    settings.repos.base_dir = Path("repos")
    settings.workspace.file = Path(".code-workspace")

    with (
        patch("devops_cli.commands.workspace.load_settings", return_value=settings),
        patch("devops_cli.commands.workspace._PROJECT_ROOT", project_root),
    ):
        result = runner.invoke(app, ["workspace", "generate"], catch_exceptions=False)

    assert result.exit_code == 0
    workspace_file = project_root / ".code-workspace"
    assert workspace_file.exists()

    data = json.loads(workspace_file.read_text(encoding="utf-8"))
    assert [folder["path"] for folder in data["folders"]] == [str(repo_dir.resolve()), "."]


def test_workspace_open_resolves_default_workspace_file_from_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    workspace_file = project_root / ".code-workspace"
    workspace_file.write_text('{"folders": [{"path": "."}]}\n', encoding="utf-8")

    settings = MagicMock()
    settings.workspace.file = Path(".code-workspace")

    with (
        patch("devops_cli.commands.workspace.load_settings", return_value=settings),
        patch("devops_cli.commands.workspace._PROJECT_ROOT", project_root),
        patch("devops_cli.commands.workspace.run_subprocess") as mock_run,
    ):
        result = runner.invoke(app, ["workspace", "open"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["code", str(workspace_file)],
        check=True,
        timeout=DEFAULT_SUBPROCESS_SHORT_TIMEOUT_SECONDS,
    )


def test_workspace_add_remove_commands(tmp_path: Path) -> None:
    """Verify workspace add, remove, and generate subcommands."""
    ws_file = tmp_path / "test.code-workspace"
    ws_file.write_text(json.dumps({"folders": [{"path": "."}]}), encoding="utf-8")

    with patch("devops_cli.commands.workspace._PROJECT_ROOT", tmp_path):
        res_add = runner.invoke(workspace_app, ["add", str(tmp_path), "--workspace", str(ws_file)])
        assert res_add.exit_code == 0

        res_remove = runner.invoke(
            workspace_app, ["remove", str(tmp_path), "--workspace", str(ws_file)]
        )
        assert res_remove.exit_code == 0

        res_gen = runner.invoke(workspace_app, ["generate", "--workspace", str(ws_file)])
        assert res_gen.exit_code == 0

"""Unit tests for devcontainer CLI commands and templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from devops_cli.commands.devcontainer import app

if TYPE_CHECKING:
    pass


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestDevcontainerCli:
    """Tests for devcontainer CLI commands."""

    def test_init_creates_devcontainer_and_mcp_files(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """devops devcontainer init must scaffold devcontainer.json, postCreate.sh, and mcp.json."""
        result = runner.invoke(app, ["init", str(tmp_path), "--name", "test-project"])
        assert result.exit_code == 0

        dc_file = tmp_path / ".devcontainer" / "devcontainer.json"
        sh_file = tmp_path / ".devcontainer" / "postCreate.sh"
        mcp_file = tmp_path / ".vscode" / "mcp.json"

        assert dc_file.exists()
        assert sh_file.exists()
        assert mcp_file.exists()

        mcp_data = json.loads(mcp_file.read_text(encoding="utf-8"))
        assert "mcpServers" in mcp_data
        assert "test-project" in mcp_data["mcpServers"]
        assert mcp_data["mcpServers"]["test-project"]["command"] == "uv"

    def test_init_fails_if_devcontainer_json_exists(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """devops devcontainer init must fail if devcontainer.json already exists."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir(parents=True)
        (dc_dir / "devcontainer.json").write_text("{}", encoding="utf-8")

        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_update_modifies_python_image(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer update must update python image version in devcontainer.json."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir(parents=True)
        dc_file = dc_dir / "devcontainer.json"
        dc_file.write_text('{"image": "python:3.12"}', encoding="utf-8")

        result = runner.invoke(app, ["update", str(tmp_path), "--python", "3.14"])
        assert result.exit_code == 0
        assert "Updated image" in result.output

        data = json.loads(dc_file.read_text(encoding="utf-8"))
        assert data["image"] == "mcr.microsoft.com/devcontainers/python:3.14"

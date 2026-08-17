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
        """devops devcontainer init must scaffold devcontainer.json and mcp.json."""
        result = runner.invoke(app, ["init", str(tmp_path), "--name", "test-project"])
        assert result.exit_code == 0

        dc_file = tmp_path / ".devcontainer" / "devcontainer.json"
        mcp_file = tmp_path / ".vscode" / "mcp.json"

        assert dc_file.exists()
        assert mcp_file.exists()

        dc_data = json.loads(dc_file.read_text(encoding="utf-8"))
        assert "customizations" in dc_data
        assert "antigravity" in dc_data["customizations"]
        assert "vscode" in dc_data["customizations"]

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

    def test_post_create_command_executes_successfully(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer post-create must run post-create setup tasks."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        result = runner.invoke(app, ["post-create", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "post-create setup ready" in result.output
        assert (fake_home / ".bash_history").exists()
        assert (fake_home / ".gemini" / "config").exists()
        assert (fake_home / ".zshrc").exists()
        assert "source_zsh" in (fake_home / ".zshrc").read_text(encoding="utf-8")

    def test_post_start_command_executes_successfully(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer post-start must run post-start lifecycle tasks."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "false")
        monkeypatch.setenv("DEVOPS_K8S_AUTO_DEPLOY", "false")

        result = runner.invoke(app, ["post-start", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "post-start lifecycle complete" in result.output
        assert (fake_home / ".kube" / "config").exists()

    def test_post_start_autostarts_minikube_when_stopped(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer post-start must start minikube if stopped and autostart enabled."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "true")
        monkeypatch.setenv("DEVOPS_K8S_AUTO_DEPLOY", "false")

        calls: list[list[str]] = []

        def mock_run_subprocess(cmd: list[str], **kwargs: object) -> object:
            calls.append(cmd)
            import subprocess

            if cmd[:2] == ["minikube", "status"]:
                return subprocess.CompletedProcess(cmd, returncode=1, stdout="Stopped", stderr="")
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr("devops_cli.commands.devcontainer.run_subprocess", mock_run_subprocess)
        monkeypatch.setattr("shutil.which", lambda prog: f"/usr/local/bin/{prog}")

        result = runner.invoke(app, ["post-start", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "Started Minikube cluster (--driver=docker --gpus=all)" in result.output
        assert any(c[:2] == ["minikube", "start"] for c in calls)

    def test_post_start_skips_start_when_minikube_already_running(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer post-start must recognize already running minikube."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "true")
        monkeypatch.setenv("DEVOPS_K8S_AUTO_DEPLOY", "false")

        calls: list[list[str]] = []

        def mock_run_subprocess(cmd: list[str], **kwargs: object) -> object:
            calls.append(cmd)
            import subprocess

            if cmd[:2] == ["minikube", "status"]:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="Running", stderr="")
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr("devops_cli.commands.devcontainer.run_subprocess", mock_run_subprocess)
        monkeypatch.setattr("shutil.which", lambda prog: f"/usr/local/bin/{prog}")

        result = runner.invoke(app, ["post-start", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "Minikube cluster is already running" in result.output
        assert not any(c[:2] == ["minikube", "start"] for c in calls)

    def test_run_lifecycle_command_executes_hooks(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer run-lifecycle --all must run all lifecycle hooks."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "false")
        monkeypatch.setenv("DEVOPS_K8S_AUTO_DEPLOY", "false")

        result = runner.invoke(app, ["run-lifecycle", "--all", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "post-create setup ready" in result.output
        assert "post-start lifecycle complete" in result.output

    def test_run_lifecycle_dry_run_outputs_json(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer run-lifecycle in dry-run mode renders dry-run JSON."""
        monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")

        result = runner.invoke(app, ["run-lifecycle", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        json_text = result.output[result.output.find("{") :]
        data = json.loads(json_text)
        assert data["command"] == "devops devcontainer run-lifecycle"
        assert data["action"] == "run_lifecycle"
        assert data["dry_run"] is True

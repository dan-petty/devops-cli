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

    def test_init_with_published_flag(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer init --published must use the published GHCR image."""
        result = runner.invoke(app, ["init", str(tmp_path), "--name", "pub-proj", "--published"])
        assert result.exit_code == 0

        dc_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert dc_file.exists()
        dc_data = json.loads(dc_file.read_text(encoding="utf-8"))
        assert "ghcr.io/dan-petty/devops-cli/devcontainer" in dc_data["image"]

    def test_init_with_custom_image(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer init --image must use the specified container image."""
        custom_img = "custom.registry.io/org/custom-devcontainer:v1.0"
        result = runner.invoke(app, ["init", str(tmp_path), "--image", custom_img])
        assert result.exit_code == 0

        dc_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert dc_file.exists()
        dc_data = json.loads(dc_file.read_text(encoding="utf-8"))
        assert dc_data["image"] == custom_img

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

    def test_post_start_minikube_falls_back_to_cpu_when_no_gpu(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer post-start must fallback to CPU minikube if no GPU is found."""
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
        monkeypatch.setattr(
            "shutil.which",
            lambda prog: f"/usr/local/bin/{prog}" if prog != "nvidia-smi" else None,
        )

        result = runner.invoke(app, ["post-start", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "Started Minikube cluster (--driver=docker)" in result.output
        assert any(c == ["minikube", "start", "--driver=docker"] for c in calls)

    def test_post_start_warns_when_docker_daemon_down(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer post-start must warn if Docker daemon is not running."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "true")
        monkeypatch.setenv("DEVOPS_K8S_AUTO_DEPLOY", "false")

        def mock_run_subprocess(cmd: list[str], **kwargs: object) -> object:
            import subprocess

            if cmd[:2] == ["docker", "info"]:
                return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="error")
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr("devops_cli.commands.devcontainer.run_subprocess", mock_run_subprocess)
        monkeypatch.setattr("shutil.which", lambda prog: f"/usr/local/bin/{prog}")

        result = runner.invoke(app, ["post-start", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "Docker daemon is not running" in result.output

    def test_post_start_mcp_scaffolding_and_sync(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer post-start must scaffold and sync MCP configuration."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "false")
        monkeypatch.setenv("DEVOPS_K8S_AUTO_DEPLOY", "false")

        # Create pyproject.toml and .agents directory
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
        (tmp_path / ".agents").mkdir()

        result = runner.invoke(app, ["post-start", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".vscode" / "mcp.json").exists()
        assert (fake_home / ".gemini" / "config" / "mcp_config.json").exists()
        assert (tmp_path / ".agents" / "mcp_config.json").exists()

        mcp_data = json.loads(
            (fake_home / ".gemini" / "config" / "mcp_config.json").read_text(encoding="utf-8")
        )
        assert "mcpServers" in mcp_data
        server_key = list(mcp_data["mcpServers"].keys())[0]
        assert mcp_data["mcpServers"][server_key]["cwd"] == str(tmp_path)

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

    def test_post_start_installs_pre_commit_hooks(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops devcontainer post-start must install pre-commit hooks if config and .git exist."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "false")
        monkeypatch.setenv("DEVOPS_K8S_AUTO_DEPLOY", "false")

        # Scaffold .git and .pre-commit-config.yaml
        (tmp_path / ".git").mkdir()
        (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

        calls: list[list[str]] = []

        def mock_run_subprocess(cmd: list[str], **kwargs: object) -> object:
            calls.append(cmd)
            import subprocess

            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr("devops_cli.commands.devcontainer.run_subprocess", mock_run_subprocess)

        result = runner.invoke(app, ["post-start", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "Installed pre-commit Git hooks" in result.output
        assert any(c == ["uv", "run", "pre-commit", "install"] for c in calls)

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

    def test_validate_valid_devcontainer_manifest(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer validate must succeed for valid devcontainer.json."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir(parents=True)
        manifest = {
            "name": "test-repo",
            "image": "python:3.14-trixie",
            "features": {"ghcr.io/devcontainers/features/git:1": {}},
            "mounts": ["source=tmp-vol,target=/tmp,type=volume"],
            "forwardPorts": [8080],
            "customizations": {"vscode": {"extensions": ["ms-python.python"]}},
        }
        (dc_dir / "devcontainer.json").write_text(json.dumps(manifest), encoding="utf-8")

        result = runner.invoke(app, ["validate", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "DevContainer manifest is valid" in result.output
        assert "test-repo" in result.output

    def test_validate_with_comments_jsonc(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer validate must handle JSONC manifests with comments."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir(parents=True)
        jsonc_content = """// Main devcontainer config
{
  /* Project metadata */
  "name": "jsonc-project",
  "image": "python:3.14", // Container base
  "features": {}
}
"""
        (dc_dir / "devcontainer.json").write_text(jsonc_content, encoding="utf-8")

        result = runner.invoke(app, ["validate", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "DevContainer manifest is valid" in result.output
        assert "jsonc-project" in result.output

    def test_validate_missing_manifest_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer validate must fail when devcontainer.json is missing."""
        result = runner.invoke(app, ["validate", "--workspace", str(tmp_path)])
        assert result.exit_code == 1
        assert "manifest not found" in result.output.lower()

    def test_validate_invalid_json_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer validate must fail when manifest has invalid JSON."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir(parents=True)
        (dc_dir / "devcontainer.json").write_text("{ unquoted_key: 123 ", encoding="utf-8")

        result = runner.invoke(app, ["validate", "--workspace", str(tmp_path)])
        assert result.exit_code == 1
        assert "failed to parse devcontainer manifest json" in result.output.lower()

    def test_validate_missing_required_fields_fails(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """devops devcontainer validate must fail when required base image is missing."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir(parents=True)
        (dc_dir / "devcontainer.json").write_text('{"name": "no-image"}', encoding="utf-8")

        result = runner.invoke(app, ["validate", "--workspace", str(tmp_path)])
        assert result.exit_code == 1
        assert "validation failed" in result.output.lower()
        assert "specify a base container" in result.output.lower()

    def test_validate_missing_build_dockerfile_fails(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """devops devcontainer validate must fail if referenced Dockerfile does not exist."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir(parents=True)
        manifest = {
            "name": "build-repo",
            "build": {"dockerfile": "Dockerfile.nonexistent"},
        }
        (dc_dir / "devcontainer.json").write_text(json.dumps(manifest), encoding="utf-8")

        result = runner.invoke(app, ["validate", "--workspace", str(tmp_path)])
        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_validate_dry_run_outputs_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer validate --dry-run outputs structured JSON result."""
        result = runner.invoke(app, ["validate", "--workspace", str(tmp_path), "--dry-run"])
        assert result.exit_code == 0
        json_text = result.output[result.output.find("{") :]
        data = json.loads(json_text)
        assert data["command"] == "devops devcontainer validate"
        assert data["action"] == "validate_devcontainer_manifest"
        assert data["dry_run"] is True

    def test_validate_outside_dockerfile_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer validate must fail if referenced Dockerfile is outside workspace."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir(parents=True)
        manifest = {
            "name": "traversal-repo",
            "build": {"dockerfile": "../../../etc/passwd"},
        }
        (dc_dir / "devcontainer.json").write_text(json.dumps(manifest), encoding="utf-8")

        result = runner.invoke(app, ["validate", "--workspace", str(tmp_path)])
        assert result.exit_code == 1
        assert "outside repository workspace" in result.output

    def test_init_invalid_python_version_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops devcontainer init must reject invalid python version formats."""
        result = runner.invoke(app, ["init", str(tmp_path), "--python", "3.14-malformed;rm -rf /"])
        assert result.exit_code == 1
        assert "Invalid Python version format" in result.output

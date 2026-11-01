"""Tests for dry-run classifications, plans, and preview execution across devcontainer and install-tools commands.

Issue #2256: Devcontainer and install-tools commands list their requests in a dry run and make none.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.devcontainer import (
    bootstrap_k8s_cmd,
    list_devcontainers,
    post_create,
    post_start,
    run_lifecycle,
    unlock_keyring,
)
from devops_cli.commands.devcontainer import (
    init as devcontainer_init,
)
from devops_cli.commands.devcontainer import (
    update as devcontainer_update,
)
from devops_cli.commands.devcontainer import (
    validate as devcontainer_validate,
)
from devops_cli.commands.install_tools import (
    install_all,
)
from devops_cli.commands.install_tools import (
    status as install_tools_status,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

COMMANDS_TO_CLASSIFY = [
    # Request plan (6)
    (bootstrap_k8s_cmd, "request-plan"),
    (post_create, "request-plan"),
    (post_start, "request-plan"),
    (run_lifecycle, "request-plan"),
    (unlock_keyring, "request-plan"),
    (install_all, "request-plan"),
    # Local preview (2)
    (devcontainer_init, "no-external-request"),
    (devcontainer_update, "no-external-request"),
    # Mark only (3)
    (list_devcontainers, "no-external-request"),
    (devcontainer_validate, "no-external-request"),
    (install_tools_status, "no-external-request"),
]

GAP_COMMAND_NAMES = [
    "devcontainer bootstrap-k8s",
    "devcontainer init",
    "devcontainer list",
    "devcontainer post-create",
    "devcontainer post-start",
    "devcontainer run-lifecycle",
    "devcontainer unlock-keyring",
    "devcontainer update",
    "devcontainer validate",
    "install-tools",
    "install-tools status",
]


@pytest.mark.parametrize("callback,expected_class", COMMANDS_TO_CLASSIFY)
def test_dry_run_classifications(callback: Any, expected_class: str) -> None:
    """Verify each command callback has the expected dry-run classification."""
    actual_class = get_dry_run_class(callback)
    assert actual_class == expected_class, (
        f"{callback.__name__} expected {expected_class}, got {actual_class}"
    )


def test_removed_from_gaps() -> None:
    """Verify all 11 commands are removed from dry_run_gaps.json."""
    gap_file = Path("tests/fixtures/dry_run_gaps.json")
    with gap_file.open("r", encoding="utf-8") as f:
        gaps = json.load(f)
    for cmd in GAP_COMMAND_NAMES:
        assert cmd not in gaps, f"Command '{cmd}' should be removed from dry_run_gaps.json"


# =============================================================================
# Request Plan Commands (6)
# =============================================================================


def test_bootstrap_k8s_dry_run_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify devcontainer bootstrap-k8s --dry-run prints planned minikube commands and starts no process."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(
        app, ["devcontainer", "bootstrap-k8s", "--workspace", str(tmp_path), "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "minikube status" in result.output
    assert "minikube start" in result.output
    assert "minikube update-context" in result.output
    fail_subprocess.assert_not_called()


def test_bootstrap_k8s_dry_run_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify devcontainer bootstrap-k8s --dry-run --json outputs structured JSON plan."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(
        app, ["devcontainer", "bootstrap-k8s", "--workspace", str(tmp_path), "--dry-run", "--json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert "requests" in data
    methods = [r["method"] for r in data["requests"]]
    assert "minikube" in methods
    fail_subprocess.assert_not_called()


def test_post_create_dry_run_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify devcontainer post-create --dry-run prints tool install plans without running subprocesses."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(
        app, ["devcontainer", "post-create", "--workspace", str(tmp_path), "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in result.output
    assert "uv tool install pre-commit" in result.output
    assert "curl -fsSL https://claude.ai/install.sh | bash" in result.output
    fail_subprocess.assert_not_called()


def test_post_create_dry_run_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify devcontainer post-create --dry-run --json outputs structured JSON plan."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(
        app, ["devcontainer", "post-create", "--workspace", str(tmp_path), "--dry-run", "--json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert len(data["requests"]) > 0
    fail_subprocess.assert_not_called()


def test_post_start_dry_run_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify devcontainer post-start --dry-run prints git and kubectl config plans."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(
        app, ["devcontainer", "post-start", "--workspace", str(tmp_path), "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "git config --global push.autoSetupRemote true" in result.output
    assert "git config --global init.defaultBranch main" in result.output
    assert "kubectl config get-contexts -o name" in result.output
    assert "kubectl config use-context" in result.output
    fail_subprocess.assert_not_called()


def test_post_start_dry_run_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify devcontainer post-start --dry-run --json outputs structured JSON plan."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(
        app, ["devcontainer", "post-start", "--workspace", str(tmp_path), "--dry-run", "--json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert any("git" in r["argv"] for r in data["requests"] if r.get("argv"))
    assert any("kubectl" in r["argv"] for r in data["requests"] if r.get("argv"))
    fail_subprocess.assert_not_called()


def test_run_lifecycle_dry_run_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify devcontainer run-lifecycle --dry-run prints lifecycle plans."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    # Post-create only
    res_pc = runner.invoke(
        app,
        [
            "devcontainer",
            "run-lifecycle",
            "--workspace",
            str(tmp_path),
            "--post-create",
            "--dry-run",
        ],
    )
    assert res_pc.exit_code == 0, res_pc.output
    assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in res_pc.output
    assert "git config --global push.autoSetupRemote true" not in res_pc.output

    # Post-start only
    res_ps = runner.invoke(
        app,
        [
            "devcontainer",
            "run-lifecycle",
            "--workspace",
            str(tmp_path),
            "--post-start",
            "--dry-run",
        ],
    )
    assert res_ps.exit_code == 0, res_ps.output
    assert "git config --global push.autoSetupRemote true" in res_ps.output
    assert "curl -LsSf https://astral.sh/uv/install.sh | sh" not in res_ps.output

    fail_subprocess.assert_not_called()


def test_unlock_keyring_dry_run_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devcontainer unlock-keyring --dry-run prints planned keyring unlock and gh auth."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(app, ["devcontainer", "unlock-keyring", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "gnome-keyring-daemon --replace --unlock --components=secrets" in result.output
    assert "gh auth token -h" in result.output
    assert "gh auth login -h" in result.output
    fail_subprocess.assert_not_called()


def test_unlock_keyring_dry_run_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devcontainer unlock-keyring --dry-run --json outputs structured JSON plan."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(app, ["devcontainer", "unlock-keyring", "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert any("gnome-keyring-daemon" in r["argv"] for r in data["requests"] if r.get("argv"))
    assert any("gh" in r["argv"] for r in data["requests"] if r.get("argv"))
    fail_subprocess.assert_not_called()


def test_install_tools_dry_run_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify install-tools --dry-run prints tool downloads without performing HTTP requests."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(app, ["install-tools", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "devops install-tools" in result.output
    assert "GET https://" in result.output
    fail_subprocess.assert_not_called()


def test_install_tools_dry_run_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify install-tools --dry-run --json outputs structured JSON plan."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(app, ["install-tools", "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert len(data["requests"]) > 0
    fail_subprocess.assert_not_called()


# =============================================================================
# Local Preview Commands (2)
# =============================================================================


def test_devcontainer_init_dry_run_preview(tmp_path: Path) -> None:
    """Verify devcontainer init --dry-run prints preview and writes no files."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()

    fail_write = MagicMock(side_effect=AssertionError("write_text_file called during dry run"))
    with patch("devops_cli.commands.devcontainer.write_text_file", fail_write):
        res = runner.invoke(app, ["devcontainer", "init", str(repo_dir), "--dry-run"])
        assert res.exit_code == 0, res.output
        assert f"Would create devcontainer configuration in {repo_dir.resolve()}" in res.output
        assert not (repo_dir / ".devcontainer").exists()
        fail_write.assert_not_called()


def test_devcontainer_update_dry_run_preview(tmp_path: Path) -> None:
    """Verify devcontainer update --dry-run prints preview and does not modify devcontainer.json."""
    dc_dir = tmp_path / ".devcontainer"
    dc_dir.mkdir(parents=True)
    dc_file = dc_dir / "devcontainer.json"
    initial_content = json.dumps({"image": "ghcr.io/dan-petty/devops-cli/devcontainer:3.12"})
    dc_file.write_text(initial_content, encoding="utf-8")

    fail_write = MagicMock(side_effect=AssertionError("write_json_file called during dry run"))
    with patch("devops_cli.commands.devcontainer.write_json_file", fail_write):
        res = runner.invoke(
            app, ["devcontainer", "update", str(tmp_path), "--python", "3.14", "--dry-run"]
        )
        assert res.exit_code == 0, res.output
        assert (
            f"Would update image in {dc_file} to mcr.microsoft.com/devcontainers/python:3.14"
            in res.output
        )
        assert dc_file.read_text(encoding="utf-8") == initial_content
        fail_write.assert_not_called()


# =============================================================================
# Mark Only Commands (3)
# =============================================================================


def test_mark_only_commands_under_global_dry_run(tmp_path: Path) -> None:
    """Verify devops --dry-run runs mark-only commands normally without error."""
    # 1. devcontainer list
    res_list = runner.invoke(
        app, ["--dry-run", "devcontainer", "list", "--base-dir", str(tmp_path)]
    )
    assert res_list.exit_code == 0, res_list.output

    # 2. devcontainer validate
    dc_dir = tmp_path / ".devcontainer"
    dc_dir.mkdir(parents=True)
    (dc_dir / "devcontainer.json").write_text(
        json.dumps({"name": "test-repo", "image": "python:3.14"}), encoding="utf-8"
    )
    res_val = runner.invoke(
        app, ["--dry-run", "devcontainer", "validate", "--workspace", str(tmp_path)]
    )
    assert res_val.exit_code == 0, res_val.output
    assert "DevContainer manifest is valid" in res_val.output

    # 3. install-tools status
    res_status = runner.invoke(app, ["--dry-run", "install-tools", "status"])
    assert res_status.exit_code == 0, res_status.output
    assert "DevOps Tool" in res_status.output
    assert "not installed" in res_status.output

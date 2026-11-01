"""Tests for dry-run classifications, plans, and preview execution across config, workspace, openspec, and docs commands.

Issue #2255: Dry-run request classification and preview for config, workspace, openspec, and docs commands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.config import (
    audit_keys_cmd,
    audit_stream,
    auth_headless,
    get_value,
    init,
    output_env_vars,
    set_value,
    show,
    unset_value,
)
from devops_cli.commands.docs import (
    check as docs_check_cmd,
)
from devops_cli.commands.docs import (
    generate as docs_generate_cmd,
)
from devops_cli.commands.docs import (
    sync_readme_cmd,
)
from devops_cli.commands.openspec import (
    archive as openspec_archive_cmd,
)
from devops_cli.commands.openspec import (
    check as openspec_check_cmd,
)
from devops_cli.commands.openspec import (
    regenerate as openspec_regenerate_cmd,
)
from devops_cli.commands.workspace import (
    add as workspace_add_cmd,
)
from devops_cli.commands.workspace import (
    clean_workspace as workspace_clean_cmd,
)
from devops_cli.commands.workspace import (
    generate as workspace_generate_cmd,
)
from devops_cli.commands.workspace import (
    open_workspace as workspace_open_cmd,
)
from devops_cli.commands.workspace import (
    remove as workspace_remove_cmd,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

COMMANDS_TO_CLASSIFY = [
    # Config (init is request-plan; show, get, set, unset, output/env/env-vars, auth-headless, audit-stream, audit-keys)
    (init, "request-plan"),
    (set_value, "no-external-request"),
    (show, "no-external-request"),
    (get_value, "no-external-request"),
    (unset_value, "no-external-request"),
    (output_env_vars, "no-external-request"),
    (auth_headless, "no-external-request"),
    (audit_stream, "no-external-request"),
    (audit_keys_cmd, "no-external-request"),
    # Docs (3)
    (docs_check_cmd, "no-external-request"),
    (docs_generate_cmd, "no-external-request"),
    (sync_readme_cmd, "no-external-request"),
    # OpenSpec (3)
    (openspec_archive_cmd, "no-external-request"),
    (openspec_check_cmd, "no-external-request"),
    (openspec_regenerate_cmd, "no-external-request"),
    # Workspace (5)
    (workspace_add_cmd, "no-external-request"),
    (workspace_clean_cmd, "no-external-request"),
    (workspace_generate_cmd, "no-external-request"),
    (workspace_open_cmd, "no-external-request"),
    (workspace_remove_cmd, "no-external-request"),
]

GAP_COMMAND_NAMES = [
    "config audit-keys",
    "config audit-stream",
    "config auth-headless",
    "config env",
    "config env-vars",
    "config get",
    "config init",
    "config output",
    "config set",
    "config show",
    "config unset",
    "docs check",
    "docs generate",
    "docs sync-readme",
    "openspec archive",
    "openspec check",
    "openspec regenerate",
    "workspace add",
    "workspace clean",
    "workspace generate",
    "workspace open",
    "workspace remove",
]


@pytest.mark.parametrize("callback,expected_class", COMMANDS_TO_CLASSIFY)
def test_dry_run_classifications(callback: Any, expected_class: str) -> None:
    """Verify each command callback has the expected dry-run classification."""
    actual_class = get_dry_run_class(callback)
    assert actual_class == expected_class, (
        f"{callback.__name__} expected {expected_class}, got {actual_class}"
    )


def test_removed_from_gaps() -> None:
    """Verify all 22 commands are removed from dry_run_gaps.json."""
    gap_file = Path("tests/fixtures/dry_run_gaps.json")
    with gap_file.open("r", encoding="utf-8") as f:
        gaps = json.load(f)
    for cmd in GAP_COMMAND_NAMES:
        assert cmd not in gaps, f"Command '{cmd}' should be removed from dry_run_gaps.json"


def test_config_init_dry_run_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify config init --dry-run prints planned gh auth status and invokes no subprocess."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(app, ["config", "init", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "gh auth status" in result.output
    fail_subprocess.assert_not_called()


def test_config_init_dry_run_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify config init --dry-run --json outputs structured JSON plan."""
    fail_subprocess = MagicMock(side_effect=AssertionError("Subprocess called during dry run"))
    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    result = runner.invoke(app, ["config", "init", "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert "requests" in data
    assert len(data["requests"]) == 1
    assert data["requests"][0]["method"] == "gh"
    assert data["requests"][0]["target"] == "auth status"
    assert data["requests"][0]["argv"] == ["gh", "auth", "status"]
    fail_subprocess.assert_not_called()


def test_config_set_dry_run_preview(
    monkeypatch: pytest.MonkeyPatch, keyring_store: Any, isolate_devops_cli_config: Path
) -> None:
    """Verify config set --dry-run prints preview and modifies neither config nor keyring."""
    fail_save = MagicMock(side_effect=AssertionError("save_settings called during dry run"))
    monkeypatch.setattr("devops_cli.commands.config.save_settings", fail_save)

    # Setting a non-secret configuration key
    res = runner.invoke(app, ["config", "set", "github.default_org", "octocat", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "Would set github.default_org = octocat" in res.output
    fail_save.assert_not_called()
    assert keyring_store.writes == {}

    # Setting a secret configuration key
    res = runner.invoke(app, ["config", "set", "ai.api_key", "secret123", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "Would store secret 'ai.api_key' in keyring." in res.output
    fail_save.assert_not_called()
    assert keyring_store.writes == {}


def test_workspace_add_dry_run_preview(tmp_path: Path) -> None:
    """Verify workspace add --dry-run previews addition without mutating the workspace file."""
    repo_dir = tmp_path / "repo1"
    repo_dir.mkdir()
    ws_file = tmp_path / "test.code-workspace"
    ws_file.write_text('{"folders": []}\n', encoding="utf-8")

    with patch("devops_cli.commands.workspace._PROJECT_ROOT", tmp_path):
        res = runner.invoke(
            app, ["workspace", "add", str(repo_dir), "--workspace", str(ws_file), "--dry-run"]
        )
        assert res.exit_code == 0, res.output
        assert f"Would add folder '{repo_dir.resolve()}' to workspace" in res.output
        assert ws_file.read_text(encoding="utf-8") == '{"folders": []}\n'


def test_workspace_remove_dry_run_preview(tmp_path: Path) -> None:
    """Verify workspace remove --dry-run previews removal without mutating the workspace file."""
    repo_dir = tmp_path / "repo1"
    repo_dir.mkdir()
    ws_file = tmp_path / "test.code-workspace"
    content = json.dumps({"folders": [{"path": str(repo_dir.resolve())}]})
    ws_file.write_text(content, encoding="utf-8")

    with patch("devops_cli.commands.workspace._PROJECT_ROOT", tmp_path):
        res = runner.invoke(
            app, ["workspace", "remove", str(repo_dir), "--workspace", str(ws_file), "--dry-run"]
        )
        assert res.exit_code == 0, res.output
        assert f"Would remove folder '{repo_dir.resolve()}' from workspace" in res.output
        assert ws_file.read_text(encoding="utf-8") == content


def test_workspace_generate_dry_run_preview(tmp_path: Path) -> None:
    """Verify workspace generate --dry-run previews generation without creating workspace file."""
    (tmp_path / "repos").mkdir()
    ws_file = tmp_path / "generated.code-workspace"
    with patch("devops_cli.commands.workspace._PROJECT_ROOT", tmp_path):
        res = runner.invoke(
            app, ["workspace", "generate", "--workspace", str(ws_file), "--dry-run"]
        )
        assert res.exit_code == 0, res.output
        assert f"Would generate workspace {ws_file}" in res.output
        assert not ws_file.exists()


def test_global_dry_run_on_mark_only_commands(
    keyring_store: Any, isolate_devops_cli_config: Path
) -> None:
    """Verify devops --dry-run runs mark-only commands normally without error."""
    # Test config show with global dry run
    res = runner.invoke(app, ["--dry-run", "config", "show"])
    assert res.exit_code == 0, res.output

    # Test config env with global dry run
    res = runner.invoke(app, ["--dry-run", "config", "env"])
    assert res.exit_code == 0, res.output

    # Test config get with global dry run
    res = runner.invoke(app, ["--dry-run", "config", "get", "github.default_org"])
    assert res.exit_code == 0, res.output

"""Unit tests for devops config subcommands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.config import app as config_app
from devops_cli.config.settings import SecretStorageError, Settings

runner = CliRunner()


def test_config_show_command(tmp_path: Path) -> None:
    """Verify devops config show displays table with masked secrets."""
    settings = Settings()
    with (
        patch("devops_cli.commands.config.load_settings", return_value=settings),
        patch("devops_cli.commands.config.get_github_token", return_value="ghp_test"),
        patch("devops_cli.commands.config.get_grafana_token", return_value=None),
    ):
        result = runner.invoke(config_app, ["show"])
        assert result.exit_code == 0
        assert "configuration" in result.output.lower()
        assert "set (****)" in result.output


def test_config_get_command() -> None:
    """Verify devops config get for values, secret warnings, and unknown keys."""
    settings = Settings()
    settings.github.default_org = "my-org"

    with patch("devops_cli.commands.config.load_settings", return_value=settings):
        # Regular key
        res_ok = runner.invoke(config_app, ["get", "github.default_org"])
        assert res_ok.exit_code == 0
        assert "my-org" in res_ok.output

        # Secret key blocked
        res_sec = runner.invoke(config_app, ["get", "github.token"])
        assert res_sec.exit_code == 1
        assert "Secret keys cannot be retrieved" in res_sec.output

        # Unknown key
        res_unk = runner.invoke(config_app, ["get", "invalid.key.name"])
        assert res_unk.exit_code == 1
        assert "Unknown config key" in res_unk.output


def test_config_set_command(tmp_path: Path) -> None:
    """Verify devops config set for regular and secret keys and error branches."""
    settings = Settings()

    with (
        patch("devops_cli.commands.config.load_settings", return_value=settings),
        patch("devops_cli.commands.config.save_settings"),
    ):
        # Set regular key
        res_set = runner.invoke(config_app, ["set", "github.default_org", "new-org"])
        assert res_set.exit_code == 0
        assert "github.default_org = new-org" in res_set.output

        # Set secret key
        with patch("devops_cli.commands.config.dotted_set"):
            res_sec = runner.invoke(config_app, ["set", "github.token", "ghp_12345"])
            assert res_sec.exit_code == 0
            assert "stored in keyring" in res_sec.output

        # SecretStorageError
        with patch(
            "devops_cli.commands.config.dotted_set",
            side_effect=SecretStorageError("Keyring locked"),
        ):
            res_err = runner.invoke(config_app, ["set", "github.token", "ghp_12345"])
            assert res_err.exit_code == 1
            assert "Could not store secret" in res_err.output

        # Invalid key error
        res_inv = runner.invoke(config_app, ["set", "nonexistent.field", "val"])
        assert res_inv.exit_code == 1


def test_config_init_wizard_flow(tmp_path: Path) -> None:
    """Verify devops config init interactive setup wizard."""
    settings = Settings()

    # Case 1: with gh CLI available and authenticated
    mock_gh_status = MagicMock(returncode=0)
    mock_gh_token = MagicMock(returncode=0, stdout="ghp_cli_token\n")

    def mock_subprocess_gh(cmd, *args, **kwargs):
        if cmd == ["gh", "auth", "status"]:
            return mock_gh_status
        if cmd == ["gh", "auth", "token"]:
            return mock_gh_token
        return MagicMock(returncode=0)

    with (
        patch("devops_cli.commands.config.load_settings", return_value=settings),
        patch("devops_cli.commands.config.save_settings"),
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.core.process.run_subprocess", side_effect=mock_subprocess_gh),
        patch("typer.confirm", return_value=True),
        patch(
            "typer.prompt",
            side_effect=[
                "test-org",
                str(tmp_path),
                "https://grafana.example.com",
                "g_tok",
                "https://prom.example.com",
                "https://argo.example.com",
                "a_tok",
            ],
        ),
        patch("devops_cli.commands.config.validate_service_url"),
    ):
        result = runner.invoke(config_app, ["init"])
        assert result.exit_code == 0
        assert "setup wizard" in result.output
        assert "Configuration saved!" in result.output


def test_config_output_env_vars() -> None:
    """Verify devops config output / env command with table, export, and JSON formats."""
    settings = Settings()

    with patch("devops_cli.commands.config.load_settings", return_value=settings):
        # Table
        res_table = runner.invoke(config_app, ["output"])
        assert res_table.exit_code == 0
        assert "devops-cli environment variables" in res_table.output

        # Export
        res_export = runner.invoke(config_app, ["output", "--export"])
        assert res_export.exit_code == 0
        assert "export" in res_export.output

        # JSON
        res_json = runner.invoke(config_app, ["output", "--json"])
        assert res_json.exit_code == 0
        assert "DEVOPS_" in res_json.output


def test_config_auth_headless_and_audit_stream(tmp_path: Path) -> None:
    """Verify devops config auth-headless and audit-stream subcommands."""
    # Auth headless valid key
    res_auth = runner.invoke(config_app, ["auth-headless", "github.token", "ghp_mock_token"])
    assert res_auth.exit_code == 0
    assert "Ephemeral secret loaded" in res_auth.output

    # Auth headless invalid key
    res_auth_inv = runner.invoke(config_app, ["auth-headless", "invalid_key", "token"])
    assert res_auth_inv.exit_code == 1

    # Audit stream
    with patch("devops_cli.core.audit.stream_audit_records", return_value=5):
        res_stream = runner.invoke(config_app, ["audit-stream", "https://siem.internal.corp/logs"])
        assert res_stream.exit_code == 0
        assert "Streamed 5 audit record(s)" in res_stream.output


def test_config_extended_commands(tmp_path: Path) -> None:
    """Verify config env alias and gh auth helpers."""
    from devops_cli.commands.config import _gh_auth_status, _gh_auth_token

    settings = Settings()

    # 1. Config env alias
    with patch("devops_cli.commands.config.load_settings", return_value=settings):
        res_env = runner.invoke(config_app, ["env", "--json"])
        assert res_env.exit_code == 0
        assert "DEVOPS_" in res_env.output

    # 2. _gh_auth_status and _gh_auth_token failure
    with patch("devops_cli.core.process.run_subprocess", side_effect=OSError("gh not found")):
        assert _gh_auth_status() is False
        assert _gh_auth_token() is None


def test_config_settings_and_keyring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test dotted_get, dotted_set, settings loading/saving, and token retrieval."""
    from devops_cli.config.settings import (
        Settings,
        dotted_get,
        dotted_set,
        get_active_config_path,
        get_ai_api_key,
        get_argocd_token,
        get_github_token,
        get_grafana_token,
        load_settings,
    )

    s = Settings()
    dotted_set(s, "ai.model", "qwen2.5-coder:14b")
    assert dotted_get(s, "ai.model") == "qwen2.5-coder:14b"
    with pytest.raises(AttributeError):
        dotted_get(s, "non.existent.path")

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("ai:\n  model: qwen2.5-coder:14b\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))
    assert get_active_config_path() == cfg_file.resolve()

    loaded = load_settings()
    assert loaded.ai.model == "qwen2.5-coder:14b"

    # Token getters with ephemeral keyring storage
    monkeypatch.setenv("DEVOPS_CLI_HEADLESS_AUTH", "true")
    dotted_set(s, "ai.api_key", "ai-secret-123")
    dotted_set(s, "argocd.token", "argo-secret-123")
    dotted_set(s, "github.token", "gh-secret-123")
    dotted_set(s, "grafana.token", "grafana-secret-123")

    assert get_ai_api_key(loaded) == "ai-secret-123"
    assert get_argocd_token(loaded) == "argo-secret-123"
    assert get_github_token(loaded) == "gh-secret-123"
    assert get_grafana_token(loaded) == "grafana-secret-123"

    # Dotted set boolean, list, and top-level section guard
    dotted_set(s, "telemetry.enabled", "true")
    assert s.telemetry.enabled is True

    dotted_set(s, "ai.ollama_urls", "http://node1:11434, http://node2:11434")
    assert s.ai.ollama_urls == ["http://node1:11434", "http://node2:11434"]

    with pytest.raises(Exception, match="Cannot set top-level"):
        dotted_set(s, "ai", "invalid")

    # get_llm_client instantiation
    from devops_cli.config.settings import get_llm_client

    client = get_llm_client(task="chat")
    assert client is not None

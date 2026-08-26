"""Tests for devops config subcommands (show, get, set, output, env)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.config import app
from devops_cli.main import app as main_app

runner = CliRunner(env={"COLUMNS": "250"})


def test_config_output_table_view() -> None:
    result = runner.invoke(app, ["output"])
    assert result.exit_code == 0
    assert "DEVOPS_CLI_AI_MODEL" in result.stdout
    assert "DEVOPS_CLI_GITHUB_TOKEN" in result.stdout
    assert "devops-cli environment variables" in result.stdout


def test_config_output_export_view() -> None:
    result = runner.invoke(app, ["output", "--export"])
    assert result.exit_code == 0
    assert "# devops-cli environment variables export" in result.stdout
    assert "export DEVOPS_CLI_" in result.stdout or "# export DEVOPS_CLI_" in result.stdout
    assert '# export DEVOPS_CLI_GITHUB_TOKEN="****"' in result.stdout


def test_config_output_json_view() -> None:
    result = runner.invoke(app, ["output", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    env_vars = [item["env_var"] for item in data]
    assert "DEVOPS_CLI_CONFIG" in env_vars
    assert "DEVOPS_CLI_AI_MODEL" in env_vars
    assert "DEVOPS_CLI_GITHUB_TOKEN" in env_vars

    ai_model_item = next(item for item in data if item["env_var"] == "DEVOPS_CLI_AI_MODEL")
    assert ai_model_item["option_key"] == "ai.model"
    assert ai_model_item["is_secret"] is False

    github_token_item = next(item for item in data if item["env_var"] == "DEVOPS_CLI_GITHUB_TOKEN")
    assert github_token_item["option_key"] == "github.token"
    assert github_token_item["is_secret"] is True


def test_config_env_aliases() -> None:
    res1 = runner.invoke(app, ["env"])
    assert res1.exit_code == 0
    assert "DEVOPS_CLI_AI_MODEL" in res1.stdout

    res2 = runner.invoke(app, ["env-vars"])
    assert res2.exit_code == 0
    assert "DEVOPS_CLI_AI_MODEL" in res2.stdout


def test_config_output_reflects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_MODEL", "gpt-4o")
    result = runner.invoke(app, ["output", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    ai_item = next(item for item in data if item["env_var"] == "DEVOPS_CLI_AI_MODEL")
    assert ai_item["value"] == "gpt-4o"
    assert ai_item["from_env"] is True

    result_table = runner.invoke(app, ["output"])
    assert result_table.exit_code == 0
    assert "gpt-4o" in result_table.stdout
    assert "(via env)" in result_table.stdout


def test_config_show_includes_allow_private_network_and_active_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_cfg = tmp_path / "custom_config.yaml"
    custom_cfg.write_text(
        "ai:\n"
        "  allow_private_network: true\n"
        "  ollama_urls:\n"
        "    - http://node1.example.test:11434\n"
        "    - http://node2.example.test:11435\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(custom_cfg))

    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0
    assert "ai.allow_private_network" in result.stdout
    assert "ai.ollama_urls" in result.stdout
    assert "http://node1.example.test:11434, http://node2.example.test:11435" in result.stdout
    assert "True" in result.stdout
    assert str(custom_cfg) in result.stdout


def test_dotted_set_rejects_top_level_section_overwrite() -> None:
    """dotted_set must raise ValueError when setting a top-level section directly."""
    from devops_cli.config.settings import Settings, dotted_set

    settings = Settings()
    with pytest.raises(ValueError, match="Cannot set top-level section 'github' directly"):
        dotted_set(settings, "github", "invalid_string_overwrite")


def test_config_commands_comprehensive(tmp_path: Path) -> None:
    """Verify config show, get, set, output, env, auth-headless, audit-stream subcommands."""
    cfg_file = tmp_path / "config.yaml"
    with (
        patch("devops_cli.config.settings.CONFIG_PATH", cfg_file),
        patch("devops_cli.commands.config._gh_auth_status", return_value=True),
        patch("devops_cli.commands.config._gh_auth_token", return_value="ghp_test"),
    ):
        res_show = runner.invoke(main_app, ["config", "show"])
        assert res_show.exit_code == 0

        res_get = runner.invoke(main_app, ["config", "get", "ai.provider"])
        assert res_get.exit_code == 0

        res_set = runner.invoke(main_app, ["config", "set", "ai.provider", "openai"])
        assert res_set.exit_code == 0

        res_out = runner.invoke(main_app, ["config", "output"])
        assert res_out.exit_code == 0

        res_env = runner.invoke(main_app, ["config", "env"])
        assert res_env.exit_code == 0

        res_headless = runner.invoke(app, ["auth-headless", "github.token", "ghp_mocktoken"])
        assert res_headless.exit_code == 0

        res_headless_bad = runner.invoke(app, ["auth-headless", "invalid_key", "val"])
        assert res_headless_bad.exit_code == 1

        with patch("devops_cli.core.audit.stream_audit_records", return_value=5):
            res_stream = runner.invoke(app, ["audit-stream", "https://siem.example.com/ingest"])
            assert res_stream.exit_code == 0


def test_ensure_keyring_backend_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _ensure_keyring_backend properly rejects FailKeyring and insecure backends."""
    import keyring
    from keyring.backends.fail import Keyring as FailKeyring

    from devops_cli.config.settings import _ensure_keyring_backend

    # 1. FailKeyring
    monkeypatch.setattr(keyring, "get_keyring", lambda: FailKeyring())
    assert _ensure_keyring_backend() is False

    # 2. None
    monkeypatch.setattr(keyring, "get_keyring", lambda: None)
    assert _ensure_keyring_backend() is False

    # 3. Plaintext backend
    fake_plaintext = type("PlaintextKeyring", (), {"priority": 1})()
    monkeypatch.setattr(keyring, "get_keyring", lambda: fake_plaintext)
    assert _ensure_keyring_backend() is False

    # 4. Zero priority backend
    fake_zero_pri = type("CustomKeyring", (), {"priority": 0})()
    monkeypatch.setattr(keyring, "get_keyring", lambda: fake_zero_pri)
    assert _ensure_keyring_backend() is False

    # 5. Valid encrypted backend
    fake_secure = type("EncryptedKeyring", (), {"priority": 5})()
    monkeypatch.setattr(keyring, "get_keyring", lambda: fake_secure)
    assert _ensure_keyring_backend() is True

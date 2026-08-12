"""Tests for devops config output / env subcommands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from devops_cli.commands.config import app

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
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_cfg = tmp_path / "custom_config.yaml"
    custom_cfg.write_text(
        "ai:\n  allow_private_network: true\n  ollama_urls:\n    - http://hog.lan:11434\n    - http://workhorse.lan:11435\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(custom_cfg))

    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0
    assert "ai.allow_private_network" in result.stdout
    assert "ai.ollama_urls" in result.stdout
    assert "http://hog.lan:11434, http://workhorse.lan:11435" in result.stdout
    assert "True" in result.stdout
    assert str(custom_cfg) in result.stdout


def test_dotted_set_rejects_top_level_section_overwrite() -> None:
    """dotted_set must raise ValueError when setting a top-level section directly."""
    from devops_cli.config.settings import Settings, dotted_set

    settings = Settings()
    with pytest.raises(ValueError, match="Cannot set top-level section 'github' directly"):
        dotted_set(settings, "github", "invalid_string_overwrite")

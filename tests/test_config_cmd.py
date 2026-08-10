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

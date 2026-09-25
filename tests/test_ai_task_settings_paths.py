"""Gateway and per-task AI settings from the CLI and the environment (#456).

Routing a task to the gateway was possible only by editing `config.yaml`:
- `devops ai config --provider gateway` rejected `gateway`;
- `devops config set ai.tasks.chat.model ...` failed, because only two-level keys were handled;
- `DEVOPS_CLI_AI_TASK_CHAT_*` overrides hit the same error and were silently dropped.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.config.settings import (
    dotted_set,
    load_settings,
    reset_settings_cache,
)
from devops_cli.exceptions import ConfigurationError
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"})


@pytest.fixture(autouse=True)
def own_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A config file of this test's own, read fresh from disk."""
    config = tmp_path / "config.yaml"
    config.write_text("ai:\n  provider: ollama\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(config))
    monkeypatch.setattr("devops_cli.config.settings.CONFIG_PATH", config)
    reset_settings_cache()
    yield config
    reset_settings_cache()


def _chat_task() -> tuple[str | None, str | None]:
    reset_settings_cache()
    chat = load_settings().ai.tasks.chat
    return chat.provider, chat.model


def test_ai_config_routes_one_task_to_the_gateway() -> None:
    """Verify `devops ai config --task chat --provider gateway` sets the chat task alone."""
    result = cli.invoke(
        app, ["ai", "config", "--task", "chat", "--provider", "gateway", "--model", "devops-coder"]
    )

    assert result.exit_code == 0, result.output
    assert _chat_task() == ("gateway", "devops-coder")
    assert load_settings().ai.provider == "ollama"


def test_ai_config_accepts_the_gateway_provider() -> None:
    """Verify every provider the client supports is accepted, `gateway` included."""
    result = cli.invoke(app, ["ai", "config", "--provider", "gateway"])

    reset_settings_cache()
    assert (result.exit_code, load_settings().ai.provider) == (0, "gateway")


def test_ai_config_refuses_an_unknown_task() -> None:
    """Verify a mistyped task is an error rather than a silent global change."""
    result = cli.invoke(app, ["ai", "config", "--task", "chatt", "--provider", "gateway"])

    assert (result.exit_code, "Unknown task" in result.output) == (1, True)


def test_config_set_reaches_nested_task_settings() -> None:
    """Verify `devops config set` takes keys of any depth, typed by the field."""
    for key, value in (
        ("ai.tasks.chat.provider", "gateway"),
        ("ai.tasks.chat.model", "devops-coder"),
        ("ai.tasks.chat.context_window", "16384"),
        ("ai.tasks.chat.ollama_urls", "http://a:11434, http://b:11434"),
    ):
        result = cli.invoke(app, ["config", "set", key, value])
        assert result.exit_code == 0, result.output

    reset_settings_cache()
    chat = load_settings().ai.tasks.chat
    assert (chat.provider, chat.model, chat.context_window, chat.ollama_urls) == (
        "gateway",
        "devops-coder",
        16384,
        ["http://a:11434", "http://b:11434"],
    )


def test_an_unknown_nested_key_is_an_error() -> None:
    """Verify a key naming no field raises instead of setting nothing."""
    settings = load_settings()

    with pytest.raises(ConfigurationError, match="Unknown configuration key"):
        dotted_set(settings, "ai.tasks.chat.no_such_field", "x")
    with pytest.raises(ConfigurationError, match="Unknown configuration key"):
        dotted_set(settings, "ai.no_such_section.model", "x")


def test_environment_overrides_set_a_gateway_chat_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify DEVOPS_CLI_AI_TASK_CHAT_* apply instead of being silently dropped."""
    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_CHAT_PROVIDER", "gateway")
    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_CHAT_MODEL", "devops-coder")

    assert _chat_task() == ("gateway", "devops-coder")


def test_an_environment_override_that_cannot_apply_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an invalid override names its variable rather than being ignored."""
    monkeypatch.setenv("DEVOPS_CLI_AI_MAX_RETRIES", "several")
    reset_settings_cache()

    with pytest.raises(ConfigurationError, match="DEVOPS_CLI_AI_MAX_RETRIES"):
        load_settings()

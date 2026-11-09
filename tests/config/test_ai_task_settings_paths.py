"""Gateway and per-task AI settings from the CLI and the environment (#456).

Routing a task to the gateway was possible only by editing `config.yaml`:
- `devops ai config --provider gateway` rejected `gateway`;
- `devops config set ai.tasks.chat.model ...` failed, because only two-level keys were handled;
- `DEVOPS_CLI_AI_TASK_CHAT_*` overrides hit the same error and were silently dropped.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.config.settings import (
    dotted_set,
    load_settings,
    reset_settings_cache,
)
from devops_cli.exceptions import ConfigurationError
from devops_cli.main import app
from tests.support.config_writes import written_keys

cli = CliRunner(env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"})


@pytest.fixture(autouse=True)
def own_config(config: Callable[..., Path]) -> Path:
    """The test's own config file, with the global provider set, read fresh from disk."""
    return config(ai={"provider": "ollama"})


def _chat_task() -> tuple[str | None, str | None]:
    reset_settings_cache()
    chat = load_settings().ai.tasks.chat
    return chat.provider, chat.model


def test_ai_config_routes_one_task_to_the_gateway(own_config: Path, isolate_data_dir: Path) -> None:
    """Verify `devops ai config --task chat --provider gateway` sets the chat task alone, and
    writes only its provider and model into the config file."""
    before = yaml.safe_load(own_config.read_text(encoding="utf-8"))

    result = cli.invoke(
        app, ["ai", "config", "--task", "chat", "--provider", "gateway", "--model", "devops-coder"]
    )

    assert result.exit_code == 0, result.output
    assert _chat_task() == ("gateway", "devops-coder")
    assert load_settings().ai.provider == "ollama"
    before["ai"]["tasks"] = {"chat": {"provider": "gateway", "model": "devops-coder"}}
    assert (
        yaml.safe_load(own_config.read_text(encoding="utf-8")),
        written_keys(isolate_data_dir),
    ) == (before, [["ai.tasks.chat.model", "ai.tasks.chat.provider"]])


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


@pytest.mark.parametrize("task", ["analysis", "stage", "verification"])
def test_a_variable_sets_the_context_window_of_a_task(
    task: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `DEVOPS_CLI_AI_TASK_<TASK>_CONTEXT_WINDOW` sets the window that `for_task` reads,
    where it was dropped without an error (#4225)."""
    monkeypatch.setenv(f"DEVOPS_CLI_AI_TASK_{task.upper()}_CONTEXT_WINDOW", "131072")
    reset_settings_cache()

    assert load_settings().ai.for_task(task).context_window == 131072


@pytest.mark.parametrize("task", ["analysis", "stage", "verification"])
def test_a_variable_sets_the_max_tokens_of_a_task(
    task: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `DEVOPS_CLI_AI_TASK_<TASK>_MAX_TOKENS` sets the reply limit that `for_task` reads
    (#4225)."""
    monkeypatch.setenv(f"DEVOPS_CLI_AI_TASK_{task.upper()}_MAX_TOKENS", "8192")
    reset_settings_cache()

    assert load_settings().ai.for_task(task).max_tokens == 8192


def test_the_stage_window_variable_beats_the_analysis_window_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a baseline run sets the window of the stage task alone: the stage variable wins
    for `stage`, and the analysis task keeps its own window (#4225)."""
    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_ANALYSIS_CONTEXT_WINDOW", "65536")
    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW", "131072")
    reset_settings_cache()

    ai = load_settings().ai
    assert (ai.for_task("stage").context_window, ai.for_task("analysis").context_window) == (
        131072,
        65536,
    )


def test_a_window_variable_that_is_not_a_positive_number_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a bad window names its variable instead of being ignored (#4225)."""
    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW", "wide")
    reset_settings_cache()

    with pytest.raises(ConfigurationError, match="DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW"):
        load_settings()

"""Tests for environment variable overrides in configuration loading."""

from __future__ import annotations

from pathlib import Path

from devops_cli.config import constants, settings


def test_load_settings_applies_env_overrides_for_non_secret_fields(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
ai:
  provider: ollama
  model: gemma4:26b
  ollama_urls:
    - http://localhost:11434
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(constants, "CONST_CONFIG_PATH", config_path)
    monkeypatch.setenv("DEVOPS_CLI_AI_MODEL", "qwen3.6:35b")
    monkeypatch.setenv("DEVOPS_CLI_AI_OLLAMA_URLS", "http://192.168.1.4:11434")

    loaded_settings = settings.load_settings()

    assert loaded_settings.ai.model == "qwen3.6:35b"
    assert loaded_settings.ai.get_ollama_urls == ["http://192.168.1.4:11434"]

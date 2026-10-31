"""Tests verifying service URL settings have suggested values in example config and no code defaults (#1165)."""

from __future__ import annotations

import yaml

from devops_cli.config.settings import Settings
from tests.support.paths import REPO_ROOT

LOCAL_SERVICE_URL_SETTINGS: tuple[str, ...] = (
    "qdrant.url",
    "tempo.url",
    "telemetry.endpoint",
    "pyroscope.url",
    "ai.gateway_url",
    "ai.portkey_url",
    "ai.ollama_urls",
)


def _get_nested(data: dict, dotted_key: str) -> object:
    cur: object = data
    for part in dotted_key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def test_service_url_settings_have_no_code_defaults() -> None:
    """Every service URL setting in Settings defaults to None or empty list, never a hard-coded URL."""
    default_settings = Settings()
    for setting in LOCAL_SERVICE_URL_SETTINGS:
        val = _get_nested(default_settings.model_dump(), setting)
        assert val is None or val == [], f"Setting {setting} has code default: {val!r}"


def test_config_example_yaml_has_suggested_value_for_every_service_url() -> None:
    """config.example.yaml defines a suggested URL for every service URL setting."""
    example_path = REPO_ROOT / "config.example.yaml"
    raw = yaml.safe_load(example_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)

    for setting in LOCAL_SERVICE_URL_SETTINGS:
        val = _get_nested(raw, setting)
        assert val is not None, f"Setting {setting} missing suggested value in config.example.yaml"
        assert val != [], f"Setting {setting} missing suggested value in config.example.yaml"

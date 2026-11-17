"""Tests verifying service URL settings have no code defaults (#1165)."""

from __future__ import annotations

from devops_cli.config.settings import Settings

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

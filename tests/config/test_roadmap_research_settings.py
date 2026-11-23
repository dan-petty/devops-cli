"""Tests for roadmap research settings (#3915)."""

from __future__ import annotations

import pytest

from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_RESEARCH_ANSWER_EXPIRY_DAYS,
    DEFAULT_ROADMAP_RESEARCH_MAX_CALLS_PER_RUN,
)
from devops_cli.config.settings import load_settings, setting_default


def test_roadmap_research_defaults() -> None:
    assert DEFAULT_ROADMAP_RESEARCH_MAX_CALLS_PER_RUN == 20
    assert DEFAULT_ROADMAP_RESEARCH_ANSWER_EXPIRY_DAYS == 30
    assert setting_default("roadmap.research.max_calls_per_run") == 20
    assert setting_default("roadmap.research.answer_expiry_days") == 30

    settings = load_settings()
    assert settings.roadmap.research.max_calls_per_run == 20
    assert settings.roadmap.research.answer_expiry_days == 30


def test_roadmap_research_env_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_RESEARCH_MAX_CALLS_PER_RUN", "42")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_RESEARCH_ANSWER_EXPIRY_DAYS", "15")

    settings = load_settings()
    assert settings.roadmap.research.max_calls_per_run == 42
    assert settings.roadmap.research.answer_expiry_days == 15

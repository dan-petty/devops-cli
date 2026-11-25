"""Tests for roadmap research settings (#3915)."""

from __future__ import annotations

import pytest

from devops_cli.config.settings import load_settings


def test_roadmap_research_env_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_RESEARCH_MAX_CALLS_PER_RUN", "42")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_RESEARCH_ANSWER_EXPIRY_DAYS", "15")

    settings = load_settings()
    assert settings.roadmap.research.max_calls_per_run == 42
    assert settings.roadmap.research.answer_expiry_days == 15

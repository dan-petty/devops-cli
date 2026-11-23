"""Tests for research judge configuration limits (#3909)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.config.defaults import (
    DEFAULT_RESEARCH_JUDGE_DAILY_TOKEN_LIMIT,
    DEFAULT_RESEARCH_JUDGE_RECORD_LIMIT,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_configuration_shows_the_limits(cli: Callable[..., Any]) -> None:
    result = cli("config", "show", "--json")
    assert result.exit_code == 0
    rows = {row["key"]: row["value"] for row in json.loads(result.stdout)}
    assert rows["research.judge.record_limit"] == DEFAULT_RESEARCH_JUDGE_RECORD_LIMIT
    assert rows["research.judge.daily_token_limit"] == DEFAULT_RESEARCH_JUDGE_DAILY_TOKEN_LIMIT

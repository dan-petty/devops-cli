"""Tests for `devops roadmap step fix-conflict` CLI command (#5019)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


def test_fix_conflict_help(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-conflict", "--help")
    assert result.exit_code == 0
    assert "--pull" in result.output
    assert "--confirm" in result.output


def test_fix_conflict_missing_pull(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-conflict", "--repo", "example/project")
    assert result.exit_code == 1
    assert "Pass --pull" in result.output


def test_fix_conflict_invalid_repo(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-conflict", "--repo", "invalid", "--pull", "42")
    assert result.exit_code == 1
    assert "Cannot resolve the repository" in result.output


def test_fix_conflict_dry_run(cli: Cli) -> None:
    result = cli(
        "roadmap", "step", "fix-conflict", "--repo", "example/project", "--pull", "42", "--dry-run"
    )
    assert result.exit_code == 0

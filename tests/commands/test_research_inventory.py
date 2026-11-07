"""Tests for `devops research inventory`."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from devops_cli.research.inventory import read_inventory
from tests.support.paths import FIXTURES

FIXTURE_REPO = FIXTURES / "research" / "repo"


def test_inventory_json_is_the_inventory_of_the_root(cli: Callable[..., Any]) -> None:
    result = cli("research", "inventory", "--root", FIXTURE_REPO, "--json")

    assert result.exit_code == 0
    assert json.loads(result.output) == json.loads(read_inventory(FIXTURE_REPO).model_dump_json())


def test_inventory_table_lists_each_component_and_the_unknown_count(
    cli: Callable[..., Any],
) -> None:
    result = cli("research", "inventory", "--root", FIXTURE_REPO)

    assert result.exit_code == 0
    assert "astral-sh/setup-uv" in result.output
    assert "27 components, 1 with an unknown ecosystem." in result.output


def test_inventory_refuses_an_unknown_format(cli: Callable[..., Any]) -> None:
    result = cli("research", "inventory", "--root", FIXTURE_REPO, "--format", "xml")

    assert result.exit_code == 1

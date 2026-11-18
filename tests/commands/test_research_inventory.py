"""Tests for `devops research inventory`."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.research.mapping import mapped_inventory
from tests.support.paths import FIXTURES

FIXTURE_REPO = FIXTURES / "research" / "repo"
RENDERED_IMAGE_NAME = "quay.io/example-org/only-in-chart"
RENDERED_IMAGE = f"{RENDERED_IMAGE_NAME}:1.2.3"


def test_inventory_json_is_the_inventory_of_the_root(cli: Callable[..., Any]) -> None:
    result = cli("research", "inventory", "--root", FIXTURE_REPO, "--json")

    assert result.exit_code == 0
    assert json.loads(result.output) == json.loads(mapped_inventory(FIXTURE_REPO).model_dump_json())


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


def test_the_render_option_lists_an_image_of_the_rendered_applications(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.commands import research as research_command

    built: list[str] = []

    def renderer_for() -> Callable[[], list[str]]:
        built.append("renderer_for")

        def rendered() -> list[str]:
            return [RENDERED_IMAGE]

        return rendered

    monkeypatch.setattr(research_command, "renderer_for", renderer_for)

    rendered_run = cli("research", "inventory", "--root", FIXTURE_REPO, "--render")

    assert rendered_run.exit_code == 0
    assert RENDERED_IMAGE_NAME in rendered_run.output
    assert built == ["renderer_for"]

    built.clear()
    default_run = cli("research", "inventory", "--root", FIXTURE_REPO)

    assert default_run.exit_code == 0
    assert RENDERED_IMAGE_NAME not in default_run.output
    assert built == []


def test_a_dry_run_with_the_render_option_calls_the_renderer_never(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.commands import research as research_command

    built: list[str] = []

    def renderer_for() -> Callable[[], list[str]]:
        built.append("renderer_for")
        raise AssertionError("a dry run built the renderer")

    monkeypatch.setattr(research_command, "renderer_for", renderer_for)

    result = cli("--dry-run", "research", "inventory", "--root", FIXTURE_REPO, "--render")

    assert result.exit_code == 0
    assert built == []

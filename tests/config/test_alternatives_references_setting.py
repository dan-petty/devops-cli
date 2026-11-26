"""The setting `roadmap.alternatives.references` (#4672): the mode of the reference step of the
alternatives check, `off`, `plan` or `on`, as a row of ADR 0021 has it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import Settings, load_settings


def test_the_references_setting_is_plan_when_it_is_not_set(config: Callable[..., Path]) -> None:
    config()

    assert load_settings().roadmap.alternatives.references == "plan"


@pytest.mark.parametrize("mode", ["off", "plan", "on"])
def test_the_references_setting_holds_each_of_the_three_modes(mode: str) -> None:
    settings = Settings(roadmap={"alternatives": {"references": mode}})

    assert settings.roadmap.alternatives.references == mode


def test_a_references_value_outside_the_three_modes_is_refused() -> None:
    with pytest.raises(ValidationError, match="references"):
        Settings(roadmap={"alternatives": {"references": "shadow"}})


def test_the_references_setting_reads_its_variable(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config()
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_ALTERNATIVES_REFERENCES", "off")

    assert load_settings().roadmap.alternatives.references == "off"


def test_the_step_has_no_mcp_server_until_its_url_is_set(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config()
    unset = load_settings().roadmap.alternatives.references_mcp_url
    monkeypatch.setenv(
        "DEVOPS_CLI_ROADMAP_ALTERNATIVES_REFERENCES_MCP_URL", "https://mcp.example.com/mcp"
    )

    assert (unset, load_settings().roadmap.alternatives.references_mcp_url) == (
        None,
        "https://mcp.example.com/mcp",
    )

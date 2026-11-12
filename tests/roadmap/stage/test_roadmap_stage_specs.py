"""The base specs that the stage job gives the model and checks a plan against (#3013)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from devops_cli.openspec.tool import OpenSpecTool, isolated_openspec
from devops_cli.roadmap.stage.stage_change import StageSpec
from devops_cli.roadmap.stage.stage_specs import read_base_specs, read_spec

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.openspec import OpenSpecFake

SPEC = """# alpha Specification

## Purpose
Keeps the alpha state.
It has two lines.

## Requirements

### Requirement:   First name
The job SHALL do it.

#### Scenario: One
- **WHEN** a
- **THEN** b

### Requirement: Second name
The job SHALL do more.
"""


def test_a_spec_gives_its_purpose_and_the_names_of_its_requirements() -> None:
    spec = read_spec(SPEC)

    assert (spec.purpose, spec.requirements) == (
        "Keeps the alpha state. It has two lines.",
        ("First name", "Second name"),
    )


def test_a_spec_gives_the_statement_of_each_requirement_with_its_name() -> None:
    spec = read_spec(SPEC)

    assert spec.statements == (
        ("First name", "The job SHALL do it."),
        ("Second name", "The job SHALL do more."),
    )
    assert "Scenario" not in spec.statements[0][1]
    assert "WHEN" not in spec.statements[0][1]


def test_a_spec_with_no_purpose_or_requirement_gives_empty_values() -> None:
    spec = read_spec("# beta Specification\n")

    assert (spec.purpose, spec.requirements, spec.statements) == ("", (), ())


LIST = ("list", "--specs", "--json")


def _listing(*ids: str) -> str:
    """What `openspec list --specs --json` prints for the capabilities `ids` (1.14.3)."""
    return json.dumps({"specs": [{"id": cap, "requirementCount": 1} for cap in ids]})


def _write_spec(root: Path, capability: str, text: str = SPEC) -> None:
    path = root / "openspec" / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_base_specs_are_the_capabilities_that_openspec_lists(
    tmp_path: Path, openspec_fake: OpenSpecFake
) -> None:
    source = tmp_path / "source"
    _write_spec(source, "alpha")
    _write_spec(source, "area/cap-one")
    (source / "openspec" / "specs" / "empty").mkdir()
    openspec_fake.script(LIST, 0, _listing("alpha", "area/cap-one"))

    specs = read_base_specs(source, OpenSpecTool(tmp_path / "cfg"))

    assert sorted(specs) == ["alpha", "area/cap-one"]
    assert specs["area/cap-one"].requirements == ("First name", "Second name")
    assert [call.argv for call in openspec_fake.calls] == [LIST]


def test_with_no_openspec_the_job_knows_no_base_spec(tmp_path: Path) -> None:
    _write_spec(tmp_path, "alpha")

    assert read_base_specs(tmp_path, None) == {}


def test_a_checkout_with_no_specs_folder_has_no_base_spec(
    tmp_path: Path, openspec_fake: OpenSpecFake
) -> None:
    assert read_base_specs(tmp_path, OpenSpecTool(tmp_path / "cfg")) == {}
    assert openspec_fake.calls == []


@pytest.mark.live("openspec")
def test_the_real_openspec_lists_a_nested_capability_beside_a_flat_one(tmp_path: Path) -> None:
    (tmp_path / "openspec").mkdir()
    (tmp_path / "openspec" / "config.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
    _write_spec(tmp_path, "alpha")
    _write_spec(tmp_path, "area/cap-one")

    with isolated_openspec() as tool:
        specs = read_base_specs(tmp_path, tool)

    assert sorted(specs) == ["alpha", "area/cap-one"]
    assert specs["area/cap-one"].purpose == "Keeps the alpha state. It has two lines."


@pytest.mark.parametrize("name", ["comment-thread", "roadmap-stage/paths-gate"])
def test_a_delta_names_a_flat_or_a_nested_capability(name: str) -> None:
    assert StageSpec(capability=name).capability == name


@pytest.mark.parametrize(
    "name", ["Comment-thread", "roadmap-stage/", "/paths-gate", "roadmap-stage//paths", "a/../b"]
)
def test_a_delta_refuses_a_capability_that_is_no_name(name: str) -> None:
    with pytest.raises(ValidationError, match="is not a name"):
        StageSpec(capability=name)

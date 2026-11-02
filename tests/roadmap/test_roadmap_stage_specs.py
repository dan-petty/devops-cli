"""The base specs that the stage job gives the model and checks a plan against (#3013)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.roadmap.stage_specs import BaseSpec, read_base_specs, read_spec

if TYPE_CHECKING:
    from pathlib import Path

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
    assert read_spec(SPEC) == BaseSpec(
        purpose="Keeps the alpha state. It has two lines.",
        requirements=("First name", "Second name"),
    )


def test_a_spec_with_no_purpose_or_requirement_gives_empty_values() -> None:
    assert read_spec("# beta Specification\n") == BaseSpec(purpose="", requirements=())


def test_the_base_specs_are_the_folders_under_openspec_specs(tmp_path: Path) -> None:
    (tmp_path / "openspec" / "specs" / "alpha").mkdir(parents=True)
    (tmp_path / "openspec" / "specs" / "alpha" / "spec.md").write_text(SPEC, encoding="utf-8")
    (tmp_path / "openspec" / "specs" / "empty").mkdir()
    (tmp_path / "openspec" / "specs" / "README.md").write_text("x", encoding="utf-8")

    specs = read_base_specs(tmp_path)

    assert specs["alpha"].requirements == ("First name", "Second name")
    assert specs["empty"] == BaseSpec(purpose="", requirements=())
    assert sorted(specs) == ["alpha", "empty"]


def test_a_checkout_with_no_specs_folder_has_no_base_spec(tmp_path: Path) -> None:
    assert read_base_specs(tmp_path) == {}

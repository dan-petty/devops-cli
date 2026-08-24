"""Unit tests for centralized project metadata loader."""

from __future__ import annotations

from pathlib import Path

from devops_cli import (
    ProjectMetadata,
    __version__,
    get_project_description,
    get_project_name,
    get_project_python_version,
    get_version,
    load_project_metadata,
)


def test_load_project_metadata_authoritative() -> None:
    """Project metadata must match pyproject.toml as authoritative source."""
    meta = load_project_metadata()
    assert isinstance(meta, ProjectMetadata)
    assert meta.name == "devops-cli"
    assert meta.version == __version__
    assert meta.python_version == "3.14"
    assert meta.requires_python == ">=3.14"
    assert "DevOps CLI" in meta.description


def test_metadata_helper_functions() -> None:
    """Helper functions must return expected values directly."""
    assert get_version() == __version__
    assert __version__.count(".") == 2
    assert get_project_name() == "devops-cli"
    assert get_project_python_version() == "3.14"
    assert "DevOps CLI" in get_project_description()


def test_load_custom_pyproject(tmp_path: Path) -> None:
    """load_project_metadata must parse custom pyproject.toml paths properly."""
    custom_toml = tmp_path / "pyproject.toml"
    custom_toml.write_text(
        """[project]
name = "custom-tool"
version = "1.2.3"
description = "Custom Tool Description"
requires-python = ">=3.13"
""",
        encoding="utf-8",
    )

    meta = load_project_metadata(custom_toml)
    assert meta.name == "custom-tool"
    assert meta.version == "1.2.3"
    assert meta.description == "Custom Tool Description"
    assert meta.python_version == "3.13"
    assert meta.requires_python == ">=3.13"

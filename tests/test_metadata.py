"""Unit tests for centralized project metadata loader."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest

from devops_cli import (
    ProjectMetadata,
    __version__,
    get_project_description,
    get_project_name,
    get_project_python_version,
    get_version,
    load_project_metadata,
)
from devops_cli.config.metadata import _DEFAULT_METADATA, _parse_python_version


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


def test_parse_python_version() -> None:
    """Verify _parse_python_version handling of various specifiers."""
    assert _parse_python_version(">=3.14.0") == "3.14.0"
    assert _parse_python_version("3.14") == "3.14"
    assert _parse_python_version(">=3.13") == "3.13"
    assert _parse_python_version("") == "3.14"


def test_metadata_fallback_to_dist(tmp_path: Path) -> None:
    """Verify metadata falls back to importlib.metadata when pyproject.toml is invalid."""
    corrupt_toml = tmp_path / "pyproject.toml"
    corrupt_toml.write_text("invalid [ [ [ toml syntax", encoding="utf-8")

    meta = load_project_metadata(corrupt_toml)
    assert meta.name == "devops-cli"
    assert meta.version != ""


def test_metadata_fallback_to_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify metadata falls back to default constant when both toml and dist fail."""
    corrupt_toml = tmp_path / "pyproject.toml"
    corrupt_toml.write_text("invalid [ [ [ toml syntax", encoding="utf-8")

    def mock_metadata(name: str) -> None:
        raise importlib.metadata.PackageNotFoundError("devops-cli")

    monkeypatch.setattr(importlib.metadata, "metadata", mock_metadata)

    meta = load_project_metadata(corrupt_toml)
    assert meta == _DEFAULT_METADATA


def test_metadata_rejects_non_toml_paths(tmp_path: Path) -> None:
    """Verify metadata loader rejects non-.toml files and safely falls back."""
    non_toml_file = tmp_path / "passwd.txt"
    non_toml_file.write_text("root:x:0:0:root:/root:/bin/bash\n", encoding="utf-8")

    meta = load_project_metadata(non_toml_file)
    assert meta.name == "devops-cli"


def test_metadata_rejects_directory_path(tmp_path: Path) -> None:
    """Verify metadata loader rejects directory paths."""
    meta = load_project_metadata(tmp_path)
    assert meta.name == "devops-cli"

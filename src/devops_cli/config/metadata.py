"""Project metadata loader from pyproject.toml and standard packaging sources."""

from __future__ import annotations

import functools
import importlib.metadata
import logging
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectMetadata:
    """Consolidated project metadata sourced from pyproject.toml or package distribution."""

    name: str
    version: str
    description: str
    requires_python: str
    python_version: str


_DEFAULT_METADATA = ProjectMetadata(
    name="devops-cli",
    version="0.1.11",
    description="DevOps CLI for managing repos, SSH keys, Kubernetes, and more",
    requires_python=">=3.14",
    python_version="3.14",
)


def _find_pyproject_path() -> Path | None:
    """Locate pyproject.toml by searching upward from the current module."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        pyproject = parent / "pyproject.toml"
        if pyproject.is_file():
            return pyproject
    return None


def _parse_python_version(requires_python: str) -> str:
    """Extract standard major.minor Python version from requires-python specifier."""
    match = re.search(r"^>=?\s*([\d.]+)", requires_python.strip())
    if match:
        return match.group(1)
    return requires_python.strip() or "3.14"


@functools.lru_cache(maxsize=4)
def load_project_metadata(pyproject_path: Path | None = None) -> ProjectMetadata:
    """Load project metadata with pyproject.toml as authoritative source.

    Falls back to standard importlib.metadata distribution info.
    """
    target_path = pyproject_path or _find_pyproject_path()

    if target_path and target_path.exists():
        try:
            with target_path.open("rb") as f:
                data = tomllib.load(f)
            project = data.get("project", {})
            name = str(project.get("name") or _DEFAULT_METADATA.name)
            version = str(project.get("version") or _DEFAULT_METADATA.version)
            description = str(project.get("description") or _DEFAULT_METADATA.description)
            requires_python = str(
                project.get("requires-python") or _DEFAULT_METADATA.requires_python
            )
            python_version = _parse_python_version(requires_python)

            return ProjectMetadata(
                name=name,
                version=version,
                description=description,
                requires_python=requires_python,
                python_version=python_version,
            )
        except Exception as exc:
            logger.debug("Failed to parse project metadata from %s: %s", target_path, exc)

    # Fallback to standard packaging distribution metadata
    try:
        dist_meta = importlib.metadata.metadata("devops-cli")
        name = dist_meta.get("Name") or _DEFAULT_METADATA.name
        version = importlib.metadata.version("devops-cli")
        description = dist_meta.get("Summary") or _DEFAULT_METADATA.description
        requires_python = dist_meta.get("Requires-Python") or _DEFAULT_METADATA.requires_python
        python_version = _parse_python_version(requires_python)

        return ProjectMetadata(
            name=name,
            version=version,
            description=description,
            requires_python=requires_python,
            python_version=python_version,
        )
    except importlib.metadata.PackageNotFoundError as exc:
        logger.debug("devops-cli distribution metadata not found: %s", exc)

    return _DEFAULT_METADATA


def get_version(pyproject_path: Path | None = None) -> str:
    """Return project version."""
    return load_project_metadata(pyproject_path).version


def get_project_name(pyproject_path: Path | None = None) -> str:
    """Return project package name."""
    return load_project_metadata(pyproject_path).name


def get_project_description(pyproject_path: Path | None = None) -> str:
    """Return project description."""
    return load_project_metadata(pyproject_path).description


def get_project_python_version(pyproject_path: Path | None = None) -> str:
    """Return project Python runtime version."""
    return load_project_metadata(pyproject_path).python_version

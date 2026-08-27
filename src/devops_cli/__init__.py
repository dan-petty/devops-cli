"""DevOps CLI — manage repos, SSH keys, Kubernetes, and more."""

from __future__ import annotations

from typing import Any

__version__ = "0.2.3"


def get_version() -> str:
    """Return the current package version string."""
    return __version__


def load_project_metadata(pyproject_path: Any = None) -> Any:
    """Load project metadata with pyproject.toml as authoritative source."""
    from devops_cli.config.metadata import load_project_metadata as _load

    return _load(pyproject_path)


def get_project_name() -> str:
    """Return project name."""
    from devops_cli.config.metadata import get_project_name as _get

    return _get()


def get_project_description() -> str:
    """Return project description."""
    from devops_cli.config.metadata import get_project_description as _get

    return _get()


def get_project_python_version() -> str:
    """Return project Python version."""
    from devops_cli.config.metadata import get_project_python_version as _get

    return _get()


def __getattr__(name: str) -> Any:
    if name == "ProjectMetadata":
        from devops_cli.config.metadata import ProjectMetadata

        return ProjectMetadata
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ProjectMetadata",
    "__version__",
    "get_project_description",
    "get_project_name",
    "get_project_python_version",
    "get_version",
    "load_project_metadata",
]

"""DevOps CLI — manage repos, SSH keys, Kubernetes, and more."""

from __future__ import annotations

from devops_cli.config.metadata import (
    ProjectMetadata,
    get_project_description,
    get_project_name,
    get_project_python_version,
    get_version,
    load_project_metadata,
)

__version__ = get_version()

__all__ = [
    "ProjectMetadata",
    "__version__",
    "get_project_description",
    "get_project_name",
    "get_project_python_version",
    "get_version",
    "load_project_metadata",
]

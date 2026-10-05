"""DevOps CLI — manage repos, SSH keys, Kubernetes, and more."""

from __future__ import annotations

import os
from typing import Any

_existing_plugins = os.environ.get("PYDANTIC_DISABLE_PLUGINS")
os.environ["PYDANTIC_DISABLE_PLUGINS"] = (
    f"{_existing_plugins},logfire-plugin"
    if _existing_plugins and "logfire-plugin" not in _existing_plugins.split(",")
    else (_existing_plugins or "logfire-plugin")
)

from devops_cli.config.metadata import (  # noqa: E402
    get_project_description,
    get_project_name,
    get_project_python_version,
    get_version,
    load_project_metadata,
)

__version__ = get_version()


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

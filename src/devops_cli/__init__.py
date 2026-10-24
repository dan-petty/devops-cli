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

__version__: str


def __getattr__(name: str) -> Any:
    if name == "__version__":
        from devops_cli.config.metadata import get_version

        return get_version()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

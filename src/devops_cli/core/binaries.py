"""External binary and developer tool pre-flight verification utilities."""

from __future__ import annotations

import shutil
from pathlib import Path

from devops_cli.exceptions.tools import DependencyError


def check_binary(name: str) -> bool:
    """Return True if an external executable is discoverable on PATH."""
    return bool(shutil.which(name))


def require_binary(name: str, *, install_hint: str | None = None) -> Path:
    """Validate that an external binary is available on PATH, returning its resolved Path.

    Args:
        name: Name or path of the binary (e.g. 'kubectl', 'helm', 'docker').
        install_hint: Optional installation instructions or web link.

    Returns:
        The resolved Path to the executable.

    Raises:
        DependencyError: If the binary is not found on PATH.
    """
    found = shutil.which(name)
    if not found:
        raise DependencyError(tool_name=name, install_hint=install_hint)
    return Path(found).resolve()

"""External binary and developer tool pre-flight verification utilities, and the version that a
command on PATH prints (#5107, #4388).

A caller judges a tool by the binary that PATH resolves, never by a pin: an image with an older
binary then fails the check instead of passing it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from devops_cli.core.process import run_subprocess
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


def version_line(output: str) -> str | None:
    """The first non-empty line of `output`, stripped, or None when it holds none."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def path_version(command: str) -> tuple[str, str | None] | None:
    """The path that PATH resolves for `command`, and the version it prints.

    Answers None when PATH resolves no command. The version is None when the run exits nonzero,
    so a caller reports a binary that cannot state its version instead of passing it.

    The run is a local read, so a dry run reads the binary too and prints the same answer.
    """
    path = shutil.which(command)
    if path is None:
        return None
    result = run_subprocess([path, "--version"], local_read=True)
    if result.returncode != 0:
        return (path, None)
    return (path, version_line(result.stdout))

"""Locked tools laid out as `devops install-tools` leaves them, with no download (#1729).

A command links to the file in its tool's version directory under the user data root, which
the test floor puts in the test's temporary directory. `install_managed_tools` with
`only_missing` then finds each such tool at its pin and installs nothing.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.tools_lock import installed_commands, load_tools_lock

_EXECUTABLE = b"#!/bin/sh\necho mytool\n"


def link_at_pin(name: str, target_dir: Path, content: bytes = _EXECUTABLE) -> None:
    """Install the packaged lock's `name` as install-tools leaves it, without downloading it."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for command, installed in installed_commands(name, load_tools_lock().tools()[name]).items():
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(content)
        (target_dir / command).symlink_to(installed)


def link_every_tool_at_pin(target_dir: Path) -> None:
    """Install every tool of the packaged lock at its pin in `target_dir`, without downloading."""
    for name in load_tools_lock().tools():
        link_at_pin(name, target_dir)

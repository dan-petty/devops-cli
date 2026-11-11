"""Locked tools laid out as `devops install-tools` leaves them, with no download (#1729).

A command links to the file in its tool's version directory under the user data root, which
the test floor puts in the test's temporary directory. The installer's `--only-missing` then
finds each such tool at its pin and installs nothing. The helper writes only in the temporary
directory of a pytest run: outside pytest, the user data root is in the real home (#4739).
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.tools_lock import installed_commands, load_tools_lock
from tests.support.home_write_guard import hold_to_the_run

_EXECUTABLE = b"#!/bin/sh\necho mytool\n"


def link_at_pin(name: str, target_dir: Path, content: bytes = _EXECUTABLE) -> None:
    """Install the packaged lock's `name` as install-tools leaves it, without downloading it.
    Each path is held to the run before the first write, so a refused path leaves no file."""
    commands = installed_commands(name, load_tools_lock().tools()[name])
    for path in (target_dir, *commands.values()):
        hold_to_the_run(path)
    target_dir.mkdir(parents=True, exist_ok=True)
    for command, installed in commands.items():
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(content)
        (target_dir / command).symlink_to(installed)

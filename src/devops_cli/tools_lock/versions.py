"""The version that a command on PATH prints (#5107).

`devops install-tools --check` and `devops openspec check` judge a tool by the binary that PATH
resolves, never by the tools lock alone: an image with an older binary then fails the check
instead of passing it.
"""

from __future__ import annotations

import shutil

from devops_cli.core.process import run_subprocess


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

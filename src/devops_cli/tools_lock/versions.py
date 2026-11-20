"""The version line that a command prints (#5107).

`devops openspec check` judges OpenSpec by the binary it runs, never by a lockfile alone: an image
with an older binary then fails the check instead of passing it.
"""

from __future__ import annotations


def version_line(output: str) -> str | None:
    """The first non-empty line of `output`, stripped, or None when it holds none."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None

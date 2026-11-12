"""The PEP 578 audit events that change a file, which the write guards of the floor read (#1921,
#2192, #4739).

The table holds each event of CPython's table of audit events that changes a file, with the
position of the changed path in the event's arguments and of the directory descriptor the path is
relative to, if any: `open` (a copy opens its destination too), `os.rename` (also `os.replace`)
and `os.remove` (also `os.unlink`). The guards hold it in `tests/`, not in `src/`: the
fail-to-pass replay runs this `tests/` on the base's source, which lacks a name added to `src`
with a guard.
"""

from __future__ import annotations

import os
from typing import Any

_FILE_CHANGE_EVENTS: dict[str, tuple[int, int | None]] = {
    "open": (0, None),
    "os.rename": (1, 3),
    "os.remove": (0, 1),
}
_WRITE_FLAGS: int = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def changed_path(event: str, args: tuple[Any, ...]) -> str | None:
    """The path that the audit event `event` changes, or None for an event that changes no file,
    an open that only reads, a path relative to a directory descriptor and a descriptor in place
    of a path."""
    spot = _FILE_CHANGE_EVENTS.get(event)
    if spot is None:
        return None
    path_at, dir_fd_at = spot
    if event == "open" and not args[2] & _WRITE_FLAGS:
        return None
    if dir_fd_at is not None and args[dir_fd_at] not in (None, -1):
        return None
    target = args[path_at]
    return None if isinstance(target, int) else os.fsdecode(target)

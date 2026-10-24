"""The config write guard: a test that writes a devops-cli config file outside its run's temporary
directory fails at that write, naming itself (#1921).

The workspace tripwire compares the project's `config.yaml` when the session ends, so it finds a
write only after the damage, and it cannot name the test that made it. This guard is a PEP 578
audit hook in the test process, where the network block also is. It refuses an open for
writing, a rename onto and a removal of a config file outside the run's temporary directory. A
config file has the name of a project config candidate or of the user-level config, such as
`config.yaml`, or that name and a dot before more text, such as the copy `save_settings` keeps
and its temporary file. The refusal is `pytest.fail`, which no `except Exception` in the code
under test hides. It names the test from `PYTEST_CURRENT_TEST` and shows the stack. The test
also fails at teardown, because a refused write in another thread fails no test by itself.

An audit hook cannot be removed, so the hook stays for the life of the process. Each run's
temporary directory is pushed at `pytest_configure` and popped at `pytest_unconfigure`, so a run
that pytester starts in this process holds its tests to its own directory.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.support.bootstrap import run_temp_root

# The PEP 578 audit events that change a file, from CPython's table of audit events, each with
# the position of the changed path in the event's arguments and of the directory descriptor the
# path is relative to, if any: `open` (a copy opens its destination too), `os.rename` (also
# `os.replace`) and `os.remove` (also `os.unlink`). Only this guard reads them, and it holds them
# itself: the fail-to-pass replay runs this `tests/` on the base's source, which lacks a name added
# to `src` with the guard.
_FILE_CHANGE_EVENTS: dict[str, tuple[int, int | None]] = {
    "open": (0, None),
    "os.rename": (1, 3),
    "os.remove": (0, 1),
}
_WRITE_FLAGS: int = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_RUN_ROOTS: list[str] = []
_REFUSED: list[str] = []
_HOOKS: list[object] = []


def _config_names() -> frozenset[str]:
    """The names of the files devops-cli reads its settings from."""
    from devops_cli.config.constants import CONST_CONFIG_PATH, CONST_PROJECT_CONFIG_CANDIDATES

    return frozenset(
        {CONST_CONFIG_PATH.name, *(Path(c).name for c in CONST_PROJECT_CONFIG_CANDIDATES)}
    )


def _is_config_name(name: str, names: frozenset[str]) -> bool:
    """Report whether `name` is a config file's name, or one of them and a dot before more text."""
    return any(name == config or name.startswith(f"{config}.") for config in names)


def _changed_path(event: str, args: tuple[Any, ...], spot: tuple[int, int | None]) -> str | None:
    """The path an audit event changes, or None for an open that only reads, a path relative to
    a directory descriptor and a descriptor in place of a path."""
    path_at, dir_fd_at = spot
    if event == "open" and not args[2] & _WRITE_FLAGS:
        return None
    if dir_fd_at is not None and args[dir_fd_at] not in (None, -1):
        return None
    target = args[path_at]
    return None if isinstance(target, int) else os.fsdecode(target)


def _outside_the_run(path: str) -> bool:
    """Report whether `path` lies outside the temporary directory of the run in progress."""
    if not _RUN_ROOTS:
        return False
    root = _RUN_ROOTS[-1]
    resolved = os.path.realpath(path)
    return resolved != root and not resolved.startswith(f"{root}{os.sep}")


def _refuse(path: str) -> None:
    """Record the refused write for the test's teardown and fail the test at the write."""
    test = os.environ.get("PYTEST_CURRENT_TEST", "(no test)")
    message = (
        f"config write outside the run's temporary directory: {os.path.realpath(path)} "
        f"(test: {test}). Write config through the `config` fixture or under `tmp_path`."
    )
    _REFUSED.append(message)
    pytest.fail(message)


def _install() -> None:
    """Add the audit hook once per process."""
    if _HOOKS:
        return
    events = _FILE_CHANGE_EVENTS
    names = _config_names()

    def guard(event: str, args: tuple[Any, ...]) -> None:
        spot = events.get(event)
        if spot is None:
            return
        path = _changed_path(event, args, spot)
        if (
            path is not None
            and _is_config_name(os.path.basename(path), names)
            and _outside_the_run(path)
        ):
            _refuse(path)

    _HOOKS.append(guard)
    sys.addaudithook(guard)


def pytest_configure(config: pytest.Config) -> None:
    """Hold config writes to this run's temporary directory."""
    _install()
    _RUN_ROOTS.append(os.path.realpath(run_temp_root(config)))


def pytest_unconfigure(config: pytest.Config) -> None:
    """Give the run that started this one its temporary directory back."""
    if _RUN_ROOTS:
        _RUN_ROOTS.pop()


@pytest.fixture(autouse=True)
def config_writes_stay_in_the_run() -> Iterator[None]:
    """Fail the test at teardown when it made a config write the guard refused, also one in
    another thread or one that the code under test caught."""
    _REFUSED.clear()
    yield
    if _REFUSED:
        refused = "; ".join(_REFUSED)
        _REFUSED.clear()
        pytest.fail(refused, pytrace=False)

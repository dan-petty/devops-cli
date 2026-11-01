"""The spend ledger write guard: a test that writes to a spend ledger outside its run's temporary
directory fails at that write, naming itself (#2192).

The hermetic floor fails any test that opens or writes to the default spend ledger path outside
the run's temporary directory. This guard is a PEP 578 audit hook in the test process. It refuses
an open for writing, a rename onto, a removal of, or a SQLite write connection to a spend ledger
outside the run's temporary directory. The refusal is `pytest.fail`, which no `except Exception`
in the code under test hides. It names the test from `PYTEST_CURRENT_TEST` and shows the stack.
The test also fails at teardown, because a refused write in another thread fails no test by
itself.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from typing import Any

import pytest

from devops_cli.config.defaults import DEFAULT_AI_SPEND_DB_FILENAME
from tests.support.bootstrap import run_temp_root

_FILE_CHANGE_EVENTS: dict[str, tuple[int, int | None]] = {
    "open": (0, None),
    "os.rename": (1, 3),
    "os.remove": (0, 1),
}
_WRITE_FLAGS: int = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_RUN_ROOTS: list[str] = []
_REFUSED: list[str] = []
_HOOKS: list[object] = []


def _is_spend_db_name(name: str) -> bool:
    """Report whether `name` is the spend ledger database file name or an associated SQLite auxiliary file."""
    return (
        name == DEFAULT_AI_SPEND_DB_FILENAME
        or name.startswith(f"{DEFAULT_AI_SPEND_DB_FILENAME}-")
        or name.startswith(f"{DEFAULT_AI_SPEND_DB_FILENAME}.")
    )


def _extract_sqlite_path(db: Any) -> str | None:
    """Extract file path from sqlite3.connect database argument, or None for memory or read-only."""
    if isinstance(db, os.PathLike):
        db = os.fsdecode(db)
    if not isinstance(db, str):
        return None
    if db == ":memory:" or not db:
        return None
    if db.startswith("file:"):
        uri_path = db[5:].split("?", 1)
        if len(uri_path) > 1 and "mode=ro" in uri_path[1]:
            return None
        return uri_path[0]
    return db


def _changed_path(event: str, args: tuple[Any, ...], spot: tuple[int, int | None]) -> str | None:
    """The path an audit event changes, or None for an open that only reads."""
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
        f"spend ledger write outside the run's temporary directory: {os.path.realpath(path)} "
        f"(test: {test}). Write spend records through the `spend_ledger` fixture or under `tmp_path`."
    )
    _REFUSED.append(message)
    pytest.fail(message)


def _install() -> None:
    """Add the audit hook once per process."""
    if _HOOKS:
        return
    events = _FILE_CHANGE_EVENTS

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event == "sqlite3.connect":
            if not args:
                return
            target = _extract_sqlite_path(args[0])
            if (
                target is not None
                and _is_spend_db_name(os.path.basename(target))
                and _outside_the_run(target)
            ):
                _refuse(target)
            return

        spot = events.get(event)
        if spot is None:
            return
        path = _changed_path(event, args, spot)
        if (
            path is not None
            and _is_spend_db_name(os.path.basename(path))
            and _outside_the_run(path)
        ):
            _refuse(path)

    _HOOKS.append(guard)
    sys.addaudithook(guard)


def pytest_configure(config: pytest.Config) -> None:
    """Hold spend ledger writes to this run's temporary directory."""
    _install()
    _RUN_ROOTS.append(os.path.realpath(run_temp_root(config)))


def pytest_unconfigure(config: pytest.Config) -> None:
    """Give the run that started this one its temporary directory back."""
    if _RUN_ROOTS:
        _RUN_ROOTS.pop()


@pytest.fixture(autouse=True)
def spend_writes_stay_in_the_run() -> Iterator[None]:
    """Fail the test at teardown when it made a spend ledger write the guard refused, also one in
    another thread or one that the code under test caught."""
    _REFUSED.clear()
    yield
    if _REFUSED:
        refused = "; ".join(_REFUSED)
        _REFUSED.clear()
        pytest.fail(refused, pytrace=False)

"""The home write guard: a test that writes a file under the real home, outside its run's
temporary directory, fails at that write, naming itself (#4739).

The floor sets HOME to a directory of the run before devops-cli is imported, so a path that
devops-cli resolves lies in the run. A test can still name a path under the real home, the HOME
that `isolate_home` replaced. This guard is a PEP 578 audit hook in the test process, in the form
of the config write guard. While a test of the run runs, in its setup, call and teardown, it
refuses an open for writing, a rename onto and a removal of a file under the real home, outside
the run's temporary directory and outside the two roots that a run writes to itself: the checkout
with its common git directory, which the workspace tripwire checks, and the interpreter, where
Python writes its bytecode cache. A GitHub-hosted runner has its checkout in its home, and uv
installs an interpreter in the home. Outside a test, pytest itself writes its cache and the
bytecode of the test modules into the root directory of the run: the checkout, or for a run that
pytester starts, the HOME that pytester sets, which is the real home of that run. The refusal is
`pytest.fail`, which no `except Exception` in the code under test hides. It names the test from
`PYTEST_CURRENT_TEST` and shows the stack. The test also fails at teardown, because a refused
write in another thread fails no test by itself.

A support helper can also run outside pytest, where no floor isolates HOME: on 2026-11-09 a
helper called from plain Python wrote stubs over 18 real tools. So a helper that writes to a path
that it does not get from its caller, such as a path that devops-cli resolves, calls
`hold_to_the_run` before the write.

An audit hook cannot be removed, so the hook stays for the life of the process. Each run's
temporary directory and real home are pushed at `pytest_configure` and popped at
`pytest_unconfigure`, so a run that pytester starts in this process holds its tests to its own
directory and home.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.support.bootstrap import REAL_HOME, run_temp_root
from tests.support.file_changes import changed_path
from tests.support.host_paths import checkout_roots
from tests.support.paths import REPO_ROOT


@dataclass
class _Run:
    """The resolved temporary directory and real home of a pytest run, and whether a test of the
    run runs."""

    root: str
    home: str
    testing: bool = False


_RUNS: list[_Run] = []
_REFUSED: list[str] = []
_HOOKS: list[object] = []


def _within(path: str, root: str) -> bool:
    """Report whether the resolved `path` is `root` or lies under it."""
    return path == root or path.startswith(f"{root}{os.sep}")


def _kept_roots() -> tuple[str, ...]:
    """The resolved roots that a run writes to itself: the checkout with its common git
    directory, and the interpreter with its bytecode cache."""
    interpreter = (
        sys.prefix,
        sys.base_prefix,
        sys.exec_prefix,
        sys.base_exec_prefix,
        sys.pycache_prefix,
    )
    roots: list[str | Path] = [*checkout_roots(REPO_ROOT), *(root for root in interpreter if root)]
    return tuple(dict.fromkeys(os.path.realpath(root) for root in roots))


def hold_to_the_run(path: Path) -> None:
    """Fail when `path` lies outside the temporary directory of the pytest run in this process,
    and for each path when no pytest run is active in the process. A support helper that writes
    to a path that it does not get from its caller calls this before the write (#4739)."""
    if not _RUNS:
        pytest.fail(
            f"no pytest run is active in this process, so a support helper writes nothing: "
            f"{path}. Call the helper from a test, where the floor isolates HOME and the user "
            "data root."
        )
    root = _RUNS[-1].root
    if not _within(os.path.realpath(path), root):
        pytest.fail(
            f"a support helper write outside the run's temporary directory {root}: {path}. "
            "Give the helper a path under `tmp_path`."
        )


def _refuse(path: str) -> None:
    """Record the refused write for the test's teardown and fail the test at the write."""
    test = os.environ.get("PYTEST_CURRENT_TEST", "(no test)")
    message = (
        f"write under the real home outside the run's temporary directory: "
        f"{os.path.realpath(path)} (test: {test}). Write under `tmp_path` or under HOME, which "
        "the floor puts in the run."
    )
    _REFUSED.append(message)
    pytest.fail(message)


def _install() -> None:
    """Add the audit hook once per process."""
    if _HOOKS:
        return
    kept = _kept_roots()

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if not _RUNS or not _RUNS[-1].testing:
            return
        path = changed_path(event, args)
        if path is None:
            return
        run = _RUNS[-1]
        resolved = os.path.realpath(path)
        if _within(resolved, run.home) and not any(
            _within(resolved, root) for root in (run.root, *kept)
        ):
            _refuse(path)

    _HOOKS.append(guard)
    sys.addaudithook(guard)


def pytest_configure(config: pytest.Config) -> None:
    """Hold writes under the real home to this run's temporary directory."""
    _install()
    real_home: Path = config.stash[REAL_HOME]
    _RUNS.append(
        _Run(root=os.path.realpath(run_temp_root(config)), home=os.path.realpath(real_home))
    )


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol() -> Generator[None, object, object]:
    """Guard the writes of the test while its setup, call and teardown run."""
    run = _RUNS[-1]
    run.testing = True
    try:
        return (yield)
    finally:
        run.testing = False


def pytest_unconfigure(config: pytest.Config) -> None:
    """Give the run that started this one its temporary directory and real home back."""
    if _RUNS:
        _RUNS.pop()


@pytest.fixture(autouse=True)
def home_writes_stay_in_the_run() -> Iterator[None]:
    """Fail the test at teardown when it made a write under the real home that the guard
    refused, also one in another thread or one that the code under test caught."""
    _REFUSED.clear()
    yield
    if _REFUSED:
        refused = "; ".join(_REFUSED)
        _REFUSED.clear()
        pytest.fail(refused, pytrace=False)

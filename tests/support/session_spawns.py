"""The child `devops ci test` starts, doubled at the stdlib edge, and a guard against a test run
starting a real one (#1669).

`devops ci test` starts pytest through `asyncio.create_subprocess_exec`, in a session of its own.
`record_spawns` doubles that function, the stdlib object itself, as `docs/TESTING.md` allows
for a stdlib edge with no seam, and records each argv; the process it returns has pid 0, which
the group stop refuses to signal, so nothing real is ever signalled. `refuse_nested_test_runs`
makes a test that missed the double fail at once, rather than run the suite inside the suite;
the tests that drive `devops ci test` ask for it, and #1666 makes such a refusal suite-wide.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
from collections.abc import Awaitable, Callable, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

import pytest

NESTED_RUN_PROGRAMS: Final[frozenset[str]] = frozenset({"uv", "uvx", "pytest", "py.test"})
"""The programs whose start, from these tests, means a real test suite or uv run."""


class RecordedSpawn:
    """A stand-in for the `asyncio.subprocess.Process` a run starts: it records the argv and
    keywords it was started with and exits with `exit_code` once its output is read."""

    def __init__(
        self,
        argv: list[str],
        kwargs: dict[str, Any],
        exit_code: int,
        on_communicate: Callable[[RecordedSpawn], Awaitable[int | None]] | None,
    ) -> None:
        self.argv = argv
        self.kwargs = kwargs
        self.pid = 0
        self.returncode: int | None = None
        self.killed = False
        self._exit_code = exit_code
        self._on_communicate = on_communicate

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        """Run the test's hook, if any, which may raise, block or name the exit code, then exit."""
        code = await self._on_communicate(self) if self._on_communicate is not None else None
        self.returncode = self._exit_code if code is None else code
        return b"", b""

    async def wait(self) -> int:
        """The exit code, the kill's if the run was stopped first."""
        if self.returncode is None:
            self.returncode = -9
        return self.returncode

    def kill(self) -> None:
        """Record the kill the group stop falls back to for a pid it refuses to signal."""
        self.killed = True


def record_spawns(
    monkeypatch: pytest.MonkeyPatch,
    *,
    exit_code: int = 0,
    on_communicate: Callable[[RecordedSpawn], Awaitable[int | None]] | None = None,
) -> list[RecordedSpawn]:
    """Double `asyncio.create_subprocess_exec`; the list of what was started, in order."""
    spawns: list[RecordedSpawn] = []

    async def create_subprocess_exec(*argv: Any, **kwargs: Any) -> RecordedSpawn:
        spawn = RecordedSpawn([str(arg) for arg in argv], kwargs, exit_code, on_communicate)
        spawns.append(spawn)
        return spawn

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess_exec)
    return spawns


def runs_a_test_suite(argv: Sequence[str]) -> bool:
    """Whether `argv` starts uv or pytest, or runs pytest as a module. pytester's own subprocess,
    `python -mpytest` in one argument, is not counted."""
    words = list(argv)
    if not words:
        return False
    if Path(words[0]).name in NESTED_RUN_PROGRAMS:
        return True
    return ("-m", "pytest") in pairwise(words)


@pytest.fixture
def refuse_nested_test_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse any child that would start uv or a test suite, failing the test that started it."""
    real_init = subprocess.Popen.__init__

    def refusing_init(self: subprocess.Popen[Any], args: Any, *rest: Any, **kwargs: Any) -> None:
        if isinstance(args, (str, bytes)):
            argv = shlex.split(os.fsdecode(args))
        else:
            argv = [os.fsdecode(arg) if isinstance(arg, bytes) else str(arg) for arg in args]
        if runs_a_test_suite(argv):
            raise AssertionError(f"a test started a real test run: {shlex.join(argv[:6])}")
        real_init(self, args, *rest, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", refusing_init)

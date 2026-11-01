"""A hung child that leaves a grandchild behind, for tests that a run stops its whole process
group (#1669).

The child is `sh`, which starts a `sleep` in its own process group, as `uv run` starts pytest,
writes its own pid and the sleep's to a file, and waits. Killing only the `sh` leaves the sleep
running, as killing only `uv` left pytest running; stopping the group ends both. The sleep
outlives every wait that observes it (`tests/support/waits.py`), so a grandchild still running
when the test looks is one the stop missed.

`watching` opens a pidfd on each as soon as their pids are read, so a test reads whether they
exited, zombies counted as exited, and on the way out SIGKILLs through the pidfd whichever is
still running: a pidfd names one process, never another that later reuses its pid. The watch
fails the test when the child leads no session of its own or the grandchild is outside it,
rather than read either as stopped. A test signals the child as soon as it reads the pids, so the
child is ready for the signal before it writes them (#1913). `default_signal_dispositions` gives
a test the signal dispositions these children rely on.
"""

from __future__ import annotations

import contextlib
import os
import select
import signal
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

GRANDCHILD_HOLD_SECONDS: Final[int] = int(10 * THREAD_HANDOFF_BOUND_SECONDS)
"""How long the grandchild sleeps unless its process group is stopped first."""

SUMMARY_LINE: Final[str] = "========== 3 passed in 0.42s =========="
"""The summary line a fake pytest prints before it hangs."""

SECOND_SIGNAL: Final[str] = "second"
"""The record a test writes into the stop-signal log as it sends its second signal."""


def hung_script(
    *, before: str = "", on_interrupt: str = "", after_spawn: str = "", after_start: str = ""
) -> str:
    """A `sh -c` script, its pid file as `$0`: run `before`, start the sleeping grandchild, run
    `after_spawn`, write both pids, run `after_start` and wait. A test acts on the child as soon
    as it reads the pids. Put what that action needs, such as the traps that record a signal, in
    `before` or `after_spawn`, never in `after_start`. `on_interrupt` is run on SIGINT; in it and
    in `after_spawn` and `after_start`, `$c` is the grandchild's pid."""
    trap = f"trap '{on_interrupt}' INT; " if on_interrupt else ""
    return (
        f'{before}{trap}sleep {GRANDCHILD_HOLD_SECONDS} & c=$!; {after_spawn}echo "$$ $c" > "$0"; '
        f'{after_start}while kill -0 "$c" 2>/dev/null; do wait "$c"; done'
    )


def hung_with_grandchild(pid_file: Path, script: str = "") -> list[str]:
    """The argv of a hung child that writes its pids to `pid_file`; `hung_script()` by default."""
    return ["sh", "-c", script or hung_script(), str(pid_file)]


def interrupted_like_pytest(marker: Path) -> str:
    """A script that handles SIGINT as pytest does: its teardown records `marker`, stops the
    grandchild it started and exits 130."""
    return hung_script(on_interrupt=f'echo teardown > "{marker}"; kill "$c"; exit 130')


def records_stop_signals(log: Path) -> str:
    """A script whose child and grandchild ignore SIGINT and SIGTERM, so only SIGKILL stops them;
    the child records each SIGINT it gets as `int` and each SIGTERM as `term` in `log`, from
    before its pids are written. It sets the traps after it starts the grandchild, because a
    grandchild that starts after the child sets a trap does not ignore SIGTERM."""
    return hung_script(
        before='trap "" INT TERM; ',
        after_spawn=f"trap 'echo int >> \"{log}\"' INT; trap 'echo term >> \"{log}\"' TERM; ",
    )


def mark_second_signal(log: Path) -> None:
    """Record, in the log `records_stop_signals` writes, that the test sends its second signal."""
    with log.open("a", encoding="utf-8") as records:
        records.write(f"{SECOND_SIGNAL}\n")


def records_after_second_signal(log: Path) -> list[str]:
    """The records the child wrote after the test marked its second signal."""
    records = log.read_text(encoding="utf-8").split()
    return records[records.index(SECOND_SIGNAL) + 1 :]


def fake_program(path: Path, pid_file: Path, script: str = "") -> Path:
    """Write an executable at `path` that runs a hung script with `pid_file` as its `$0`, as a
    stand-in for `uv` that a test puts first on PATH."""
    body = (script or hung_script()).replace('"$0"', f'"{pid_file}"')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _has_exited(pidfd: int) -> bool:
    """Whether the process behind `pidfd` has exited: a pidfd turns readable when it does."""
    poller = select.poll()
    poller.register(pidfd, select.POLLIN)
    return bool(poller.poll(0))


def _session_of(pid: int) -> int | None:
    """The session id of `pid`, or None once it is gone."""
    try:
        return os.getsid(pid)
    except OSError:
        return None


def _open_pidfd(pid: int) -> int | None:
    """A pidfd on `pid`, or None when no process has that pid any more: it has exited."""
    if pid <= 1:
        raise AssertionError(f"the hung child wrote pid {pid}, which names no child of its own")
    try:
        return os.pidfd_open(pid)
    except ProcessLookupError:
        return None


class HungChildWatch:
    """The hung child and its grandchild, watched through pidfds opened as soon as their pids are
    read. A check that fails fails the test; it never reads as an exit."""

    def __init__(self, pid_file: Path) -> None:
        self.pid_file = pid_file
        self.pids: tuple[int, int] | None = None
        self._pidfds: list[int | None] = []
        self._failure = ""

    def started(self) -> bool:
        """Whether both pids are written. The first time they are, open a pidfd on each, then
        fail the test unless the child leads a session of its own and the grandchild is in it,
        which also tells the grandchild from a later process that took its pid."""
        if self.pids is None:
            try:
                leader, grandchild = (int(pid) for pid in self.pid_file.read_text().split())
            except OSError, ValueError:
                return False
            self.pids = (leader, grandchild)
            self._pidfds = [_open_pidfd(leader), _open_pidfd(grandchild)]
            self._failure = self._identity_failure(leader, grandchild)
        if self._failure:
            raise AssertionError(self._failure)
        return True

    def _identity_failure(self, leader: int, grandchild: int) -> str:
        """Why the watched pids are not the hung child leading its own session and its grandchild
        in it, or "" when they are. A grandchild outside the session may be another process that
        took its pid, so its pidfd is dropped and nothing signals it."""
        session = _session_of(leader)
        if session is not None and session != leader:
            return (
                f"the hung child {leader} leads no session of its own: it is in session {session}"
            )
        expected = leader if session is None else session
        grandchild_session = _session_of(grandchild)
        if grandchild_session is None or grandchild_session == expected:
            return ""
        pidfd = self._pidfds[1]
        if pidfd is not None:
            os.close(pidfd)
        self._pidfds[1] = None
        return (
            f"pid {grandchild} is in session {grandchild_session}, not the hung child's {expected}"
        )

    def grandchild_stopped(self) -> bool:
        """Whether the grandchild has exited."""
        return self.started() and self._exited(1)

    def leader_stopped(self) -> bool:
        """Whether the hung child itself has exited."""
        return self.started() and self._exited(0)

    def stopped(self) -> bool:
        """Whether the child and its grandchild have both exited."""
        return self.started() and self._exited(0) and self._exited(1)

    def _exited(self, which: int) -> bool:
        pidfd = self._pidfds[which]
        return pidfd is None or _has_exited(pidfd)

    def kill_survivors(self) -> None:
        """SIGKILL, through its pidfd, each watched process still running, and close the pidfds."""
        for pidfd in self._pidfds:
            if pidfd is not None and not _has_exited(pidfd):
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            if pidfd is not None:
                os.close(pidfd)
        self._pidfds = [None for _ in self._pidfds]


@contextlib.contextmanager
def watching(pid_file: Path) -> Iterator[HungChildWatch]:
    """Watch the hung child that writes its pids to `pid_file`, killing what is left on exit."""
    watch = HungChildWatch(pid_file)
    try:
        yield watch
    finally:
        with contextlib.suppress(AssertionError):
            watch.started()
        watch.kill_survivors()


@pytest.fixture
def default_signal_dispositions() -> Iterator[None]:
    """SIGINT on Python's KeyboardInterrupt handler and SIGTERM and SIGHUP on their defaults for
    the test's length, whatever the run inherited: `nohup` ignores SIGHUP, and a background job
    of a non-interactive shell ignores SIGINT, which a child's `sh` could then not trap and a run
    would rightly leave alone. Across exec a child gets the defaults; the previous dispositions
    come back after."""
    wanted = {
        signal.SIGINT: signal.default_int_handler,
        signal.SIGTERM: signal.SIG_DFL,
        signal.SIGHUP: signal.SIG_DFL,
    }
    previous = {sig: signal.signal(sig, handler) for sig, handler in wanted.items()}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, signal.SIG_DFL if handler is None else handler)

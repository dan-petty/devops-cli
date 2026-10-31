"""The hung child that records stop signals is ready for a signal as soon as its pids are visible
(#1913)."""

from __future__ import annotations

import os
import select
import signal
import subprocess
from pathlib import Path

import pytest

from tests.support.hung_children import hung_with_grandchild, records_stop_signals, watching
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

pytestmark = pytest.mark.live("sh")

RECORDED_SIGNALS = (signal.SIGINT, signal.SIGTERM)
"""The signals `records_stop_signals` records."""


def _catches(pid: int, wanted: tuple[signal.Signals, ...]) -> bool:
    """Whether process `pid` has a handler for each signal in `wanted`. `/proc/<pid>/status` lists
    the signals a process catches as a mask with one bit for each signal number, from 1."""
    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines()
    mask = int(next(line for line in status if line.startswith("SigCgt:")).split()[1], 16)
    return all(mask >> (sig - 1) & 1 for sig in wanted)


def _pids_the_child_writes_to(pipe: Path) -> str:
    """The pids the child writes into the named pipe `pipe`, or "" when it writes none within the
    bound. The test opens the pipe without a block, so a child that fails for another reason fails
    the test with a message. A blocking open would wait for a writer that never comes. The open
    also lets the child go on."""
    reader = os.open(pipe, os.O_RDONLY | os.O_NONBLOCK)
    try:
        ready, _, _ = select.select([reader], [], [], THREAD_HANDOFF_BOUND_SECONDS)
        return os.read(reader, select.PIPE_BUF).decode() if ready else ""
    finally:
        os.close(reader)


@pytest.mark.usefixtures("default_signal_dispositions")
def test_the_child_that_records_stop_signals_catches_them_before_its_pids_are_visible(
    tmp_path: Path,
) -> None:
    """A test signals the child as soon as it reads the pids. A signal that comes before the child
    records signals is lost. The pid file here is a named pipe, so the child waits at the write of
    its pids until the test reads them. A child that catches SIGINT and SIGTERM before that point
    has them in place whenever a test can first read its pids."""
    published = tmp_path / "published"
    os.mkfifo(published)
    argv = hung_with_grandchild(published, records_stop_signals(tmp_path / "signals"))
    with (
        subprocess.Popen(argv, start_new_session=True) as child,
        watching(tmp_path / "pids") as watch,
    ):
        caught = wait_until(lambda: _catches(child.pid, RECORDED_SIGNALS))
        # The watch reads the pids from its pid file and ends the child and its grandchild.
        watch.pid_file.write_text(_pids_the_child_writes_to(published), encoding="utf-8")
        started = wait_until(watch.started)

    assert (caught, started) == (True, True)

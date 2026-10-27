"""Host-wide slots that limit how many CPU-heavy `devops ci` gates run at once (#2336).

Every worktree of a repository shares one data directory, so the lock files in one directory of it
are the slots of the host. A slot is an `fcntl.flock` lock that `filelock` takes: the operating
system frees it when its holder exits or dies, so a killed agent cannot keep a slot.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from devops_cli.config.constants import CONST_CI_GATE_SLOT_FILENAME
from devops_cli.config.defaults import DEFAULT_CI_GATE_CPUS_PER_SLOT, DEFAULT_CI_GATE_POLL_SECONDS
from devops_cli.core import clock
from devops_cli.lang import MESSAGES


def gate_slot_count(configured: int | None, *, cpus: int | None = None) -> int:
    """The number of gate slots: `ci.gate_slots` when it is set, else one for each
    DEFAULT_CI_GATE_CPUS_PER_SLOT CPUs of the process, and at least one."""
    if configured is not None:
        return configured
    available = cpus if cpus is not None else (os.process_cpu_count() or 1)
    return max(1, available // DEFAULT_CI_GATE_CPUS_PER_SLOT)


def _took(lock: FileLock) -> bool:
    """Whether this process now holds the slot: `filelock` answers a slot that another process
    holds with a `Timeout`, which is the answer and no failure."""
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return False
    return True


def _take_free_slot(locks: list[FileLock]) -> FileLock | None:
    """The first slot that nobody holds, now held by this process, or None when every slot is held."""
    return next((lock for lock in locks if _took(lock)), None)


def _holder_of(lock: FileLock) -> str:
    """Who the holder of a slot says it is, as `<process number> <worktree>`; empty when the
    holder has not written it yet or the file is gone. The text is a hint for the person who
    waits: the lock is the truth."""
    try:
        return Path(lock.lock_file).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _wait_message(locks: list[FileLock]) -> str:
    """The line a gate prints once, when it finds every slot held."""
    holders = []
    for lock in locks:
        pid, _, worktree = _holder_of(lock).partition(" ")
        if pid and worktree:
            holders.append(MESSAGES.ci.gate_slot_holder.format(pid=pid, worktree=worktree))
    return MESSAGES.ci.gate_slot_wait.format(
        slots=len(locks), holders="; ".join(holders) or MESSAGES.ci.gate_slot_holder_unknown
    )


@contextmanager
def gate_slot(
    directory: Path, slots: int, *, holder: str, notify: Callable[[str], None]
) -> Iterator[float]:
    """Hold one of `slots` slots, kept as lock files in `directory`, for the body of the `with`.

    A gate that finds every slot held tells `notify` once who holds them, then tries again every
    DEFAULT_CI_GATE_POLL_SECONDS until a slot is free. It yields the seconds that it waited. The
    slot holds `holder`, as `<process number> <worktree>`, for the gates that wait behind it. The
    slot is free again when the body ends or raises, and also when the process dies.
    """
    directory.mkdir(parents=True, exist_ok=True)
    locks = [
        FileLock(directory / CONST_CI_GATE_SLOT_FILENAME.format(index=index))
        for index in range(slots)
    ]
    started = clock.monotonic()
    taken = _take_free_slot(locks)
    if taken is None:
        notify(_wait_message(locks))
        while (taken := _take_free_slot(locks)) is None:
            clock.sleep(DEFAULT_CI_GATE_POLL_SECONDS)
    try:
        Path(taken.lock_file).write_text(holder, encoding="utf-8")
        yield clock.monotonic() - started
    finally:
        taken.release()

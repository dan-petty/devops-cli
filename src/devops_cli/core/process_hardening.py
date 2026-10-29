"""Keep a process's own environment and memory from a child of the same user (#2667).

The implement job runs the shell of an agent as a child of its own process, with the same user.
That user can read `/proc/<job pid>/environ`, where the GitHub App's private key and the other
secrets of the pod are, and the job's memory through `/proc/<job pid>/mem`. The kernel refuses
both for a process that is not dumpable, unless the reader holds `CAP_SYS_PTRACE`: the same
protection `ssh-agent` and `gpg-agent` use. `prctl(PR_SET_DUMPABLE, 0)` clears the flag. A child
that the process starts later gets the flag set again on its own `exec`, so the process's work is
not changed.

The standard library has no `prctl`, and `python-prctl` is unmaintained, so `ctypes` makes the
call. It is Linux only: the pod of a runner Job is Linux.

**What this does not close.** Every `git` and `gh` child of the job gets the session's token in
its environment while it runs, and a process of the same user can read that through
`/proc/<pid>/environ`. A pod cannot keep the child from it: the token must reach `git` and `gh`
by their environment, a file the same user can read, or a pipe, and a user namespace for the
agent's shell needs `unshare`, which the pod's `RuntimeDefault` seccomp profile refuses. So the
job guarantees an order instead. The agent's shell is the only process of the user that the agent
controls, and the job ends every process it started (`end_leftover_processes`) when a step ends,
before it runs any program with the token. `adopt_orphans` makes the job the parent of a process
that the agent daemonized, so that none escapes the count.
"""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.util
import os
import sys
import time

import psutil

from devops_cli.exceptions import RoadmapImplementError
from devops_cli.lang import MESSAGES

# `PR_SET_DUMPABLE` and `PR_SET_CHILD_SUBREAPER` of <linux/prctl.h>.
_PR_SET_DUMPABLE = 4
_PR_SET_CHILD_SUBREAPER = 36
# How long a process that was sent SIGKILL may take to leave the process table.
_KILL_WAIT_SECONDS = 1.0
DEFAULT_LEFTOVER_TIMEOUT_SECONDS = 5.0


def _prctl(option: int, argument: int) -> int:
    """Call libc's `prctl(option, argument, 0, 0, 0)` and return its result, -1 on an error."""
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    result: int = libc.prctl(option, argument, 0, 0, 0)
    return result


def deny_environment_reads() -> None:
    """Clear the dumpable flag of this process, so a child of the same user cannot read its
    `/proc` environment or memory. Raises `RoadmapImplementError` when the platform is not Linux
    or the kernel refuses."""
    if sys.platform != "linux":
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_hardening_failed.format(reason=sys.platform)
        )
    if _prctl(_PR_SET_DUMPABLE, 0) != 0:
        reason = os.strerror(ctypes.get_errno())
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_hardening_failed.format(reason=reason)
        )


def adopt_orphans() -> None:
    """Make this process the parent of every descendant that loses its own parent, so that a
    daemon the agent's shell started (a double fork, `setsid`) stays in this process's tree and
    `end_leftover_processes` finds it. Raises `RoadmapImplementError` when the platform is not
    Linux or the kernel refuses."""
    if sys.platform != "linux":
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_hardening_failed.format(reason=sys.platform)
        )
    if _prctl(_PR_SET_CHILD_SUBREAPER, 1) != 0:
        reason = f"PR_SET_CHILD_SUBREAPER: {os.strerror(ctypes.get_errno())}"
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_hardening_failed.format(reason=reason)
        )


def end_leftover_processes(timeout: float = DEFAULT_LEFTOVER_TIMEOUT_SECONDS) -> None:
    """Kill every descendant of this process and wait until none is left, for up to `timeout`
    seconds. A killed process can leave children that the kernel hands to this process
    (`adopt_orphans`), so the sweep repeats until the tree is empty. Raises
    `RoadmapImplementError` naming the processes that outlive the timeout."""
    deadline = time.monotonic() + timeout
    while True:
        found = psutil.Process().children(recursive=True)
        if not found:
            return
        for process in found:
            with contextlib.suppress(psutil.NoSuchProcess):
                process.kill()
        _, alive = psutil.wait_procs(found, timeout=_KILL_WAIT_SECONDS)
        if alive and time.monotonic() >= deadline:
            names = ", ".join(_describe(process) for process in alive)
            raise RoadmapImplementError(
                MESSAGES.roadmap.implement_leftover_processes.format(names=names)
            )


def _describe(process: psutil.Process) -> str:
    try:
        return f"{process.name()} ({process.pid})"
    except psutil.Error:
        return str(process.pid)


__all__ = ["adopt_orphans", "deny_environment_reads", "end_leftover_processes"]

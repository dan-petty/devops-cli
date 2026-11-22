"""Keep a process's own environment and memory from a child of the same user (#2667).

A roadmap step runs code of a pull request as a child of its own process, with the same user.
That user can read `/proc/<job pid>/environ`, where the secrets of the container are, and the
job's memory through `/proc/<job pid>/mem`. The kernel refuses both for a process that is not
dumpable, unless the reader holds `CAP_SYS_PTRACE`: the same protection `ssh-agent` and
`gpg-agent` use. `prctl(PR_SET_DUMPABLE, 0)` clears the flag. A child that the process starts
later gets the flag set again on its own `exec`, so the process's work is not changed.

The standard library has no `prctl`, and `python-prctl` is unmaintained, so `ctypes` makes the
call. It is Linux only: the pod of a runner Job is Linux.

The runner Job runs each phase in its own container (#3700, ADR 0030). The agent phase holds the
model key and no GitHub credential, and mounts no state folder of the other phases. `prepare` and
`publish` hold the App key and run no code of the pull request.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys

from devops_cli.exceptions import RoadmapImplementError
from devops_cli.lang import MESSAGES

# `PR_SET_DUMPABLE` of <linux/prctl.h>.
_PR_SET_DUMPABLE = 4


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


__all__ = ["deny_environment_reads"]

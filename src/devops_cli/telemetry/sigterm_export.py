"""One more export of the process's telemetry when the process gets SIGTERM (#5916).

Kubernetes stops the pod of a Job for its deadline, an eviction or a node drain with SIGTERM, and
with SIGKILL when the grace period of the pod ends. The metrics since the last export of the
tracer were lost then. A process with no handler for SIGTERM stops at once and runs no `atexit`
hook. The kernel drops SIGTERM to a process that is PID 1 in its container and has no handler, as
`devops` is in the images, so SIGKILL ended it at the end of the grace period.

`install_sigterm_export` sets a handler at the start of the CLI (`devops_cli.entry`). The handler
exports what the tracer holds (`flush_tracer`), then does what the handler before it did: it calls
a Python handler, ignores the signal when that handler ignored it, and else sets the default
action and sends SIGTERM to the process again. So the process stops as it did with no handler: the
signal ends it, or, as PID 1, it runs on until SIGKILL.

A handler that a block sets later replaces this one while the block runs and gives it back after,
such as `sigterm_raises` of a stage Job, whose kill exports at exit, and the stop of uvicorn in the
Service, which sends SIGTERM again when it ends.

A signal handler runs in the main thread between two bytecodes, and that thread can hold a lock
that the export needs. So the export runs in a thread of its own, and the handler waits for it for
at most `_EXPORT_SECONDS`, well below the grace period of 30 s that a pod has by default.
"""

from __future__ import annotations

import signal
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from types import FrameType

_EXPORT_SECONDS: Final[float] = 5.0
_TRACER_MODULE: Final[str] = "devops_cli.telemetry.tracer"


def _export_buffered_telemetry() -> None:
    """Export what the tracer holds. A process that never loaded the tracer has nothing to send,
    and an import here could wait for the import lock that the main thread holds."""
    tracer = sys.modules.get(_TRACER_MODULE)
    if tracer is not None:
        tracer.flush_tracer(_EXPORT_SECONDS)


@dataclass(frozen=True)
class SigtermExport:
    """The SIGTERM handler that exports first, then does what `previous` did."""

    previous: Callable[[int, FrameType | None], Any] | int | None

    def __call__(self, signum: int, frame: FrameType | None) -> None:
        export = threading.Thread(
            target=_export_buffered_telemetry, name="devops-otel-sigterm", daemon=True
        )
        export.start()
        export.join(_EXPORT_SECONDS)
        if callable(self.previous):
            self.previous(signum, frame)
        elif self.previous != signal.SIG_IGN:
            signal.signal(signum, signal.SIG_DFL)
            signal.raise_signal(signum)


def install_sigterm_export() -> None:
    """Make SIGTERM export the telemetry first, then do what the handler in place did. A second
    call keeps the one handler. Only the main thread can set a handler, so another thread sets
    none."""
    if threading.current_thread() is not threading.main_thread():
        return
    current = signal.getsignal(signal.SIGTERM)
    if isinstance(current, SigtermExport):
        return
    signal.signal(signal.SIGTERM, SigtermExport(current))


def uninstall_sigterm_export() -> None:
    """Set back the handler that `install_sigterm_export` replaced, when its handler is in place."""
    if threading.current_thread() is not threading.main_thread():
        return
    current = signal.getsignal(signal.SIGTERM)
    if isinstance(current, SigtermExport):
        previous = current.previous
        signal.signal(signal.SIGTERM, signal.SIG_DFL if previous is None else previous)


__all__ = ["SigtermExport", "install_sigterm_export", "uninstall_sigterm_export"]

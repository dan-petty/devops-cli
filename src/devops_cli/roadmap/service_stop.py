"""The stop of the Service, as the rounds in flight see it (#4485).

A pod that gets SIGTERM drains. The Service sets the stop, and from then on a round starts no
new row, and the stage and refine rows start no new item. The row in flight ends after its item
in progress, through the stop path of #2753: it writes what it did, counts no failure, and
leaves the items it did not take to the next pod. The stop is process-wide, as SIGTERM is. The
command line never sets it.
"""

from __future__ import annotations

import threading

from devops_cli.exceptions import ServiceStoppingError
from devops_cli.lang import MESSAGES

_stop = threading.Event()


def begin_service_stop() -> None:
    """Tell the rounds in flight that the Service stops."""
    _stop.set()


def service_stopping() -> bool:
    """Whether the Service stops, so no new row or item may start."""
    return _stop.is_set()


def stop_before(work: str) -> ServiceStoppingError:
    """The error that ends a round because the Service stops before `work`, a row or an item,
    starts."""
    return ServiceStoppingError(MESSAGES.serve.stop_before_work.format(work=work))


def raise_if_service_stops(work: str) -> None:
    """Raise `ServiceStoppingError` once the Service stops, so `work` does not start."""
    if _stop.is_set():
        raise stop_before(work)


def reset_service_stop() -> None:
    """Clear the stop (for tests)."""
    _stop.clear()

"""The waiting functions and the monotonic clock reading the libraries take (#1320)."""

from __future__ import annotations

import time


def sleep(seconds: float) -> None:
    # Clock seam is the one allowed real wait in the codebase (#4669).
    time.sleep(seconds)  # noqa: TID251


def monotonic() -> float:
    return time.monotonic()


__all__ = ["monotonic", "sleep"]

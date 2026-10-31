"""The waiting functions and the monotonic clock reading the libraries take (#1320)."""

from __future__ import annotations

import time


def sleep(seconds: float) -> None:
    time.sleep(seconds)


def monotonic() -> float:
    return time.monotonic()


__all__ = ["monotonic", "sleep"]

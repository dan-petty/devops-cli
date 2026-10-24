"""The waiting functions and the monotonic clock reading the libraries take (#1320)."""

from __future__ import annotations

import time

sleep = time.sleep
monotonic = time.monotonic

__all__ = ["monotonic", "sleep"]

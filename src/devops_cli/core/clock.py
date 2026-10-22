"""The waiting functions the libraries take, and the monotonic reading `ratelimit` takes (#1320)."""

from __future__ import annotations

import time

sleep = time.sleep
monotonic = time.monotonic

__all__ = ["monotonic", "sleep"]

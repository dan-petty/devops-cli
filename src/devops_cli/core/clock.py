"""The waiting functions the libraries take, and the monotonic reading `ratelimit` takes (#1320)."""

from __future__ import annotations

import asyncio
import time

sleep = time.sleep
async_sleep = asyncio.sleep
monotonic = time.monotonic

__all__ = ["async_sleep", "monotonic", "sleep"]

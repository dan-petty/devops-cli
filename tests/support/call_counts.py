"""The calls of one function in a block, which `sys.monitoring` (PEP 669) reports, so a test
counts how often the code under test calls the function and replaces no function (#6516)."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import CodeType

# PEP 669 gives six tool ids, 0 to 5.
_MONITORING_TOOL_IDS = range(6)


@contextmanager
def calls_of(function: Callable[..., object]) -> Iterator[list[CodeType]]:
    """The code of `function` once for each call that starts it in the block. A bound method, such
    as a classmethod read from its class, counts the calls of the function that it binds."""
    code: CodeType = getattr(function, "__func__", function).__code__
    monitoring = sys.monitoring
    tool = next(tool for tool in _MONITORING_TOOL_IDS if monitoring.get_tool(tool) is None)
    calls: list[CodeType] = []

    def on_start(started: CodeType, _offset: int) -> None:
        calls.append(started)

    monitoring.use_tool_id(tool, "call-counts")
    monitoring.register_callback(tool, monitoring.events.PY_START, on_start)
    monitoring.set_local_events(tool, code, monitoring.events.PY_START)
    try:
        yield calls
    finally:
        monitoring.set_local_events(tool, code, monitoring.events.NO_EVENTS)
        monitoring.register_callback(tool, monitoring.events.PY_START, None)
        monitoring.free_tool_id(tool)

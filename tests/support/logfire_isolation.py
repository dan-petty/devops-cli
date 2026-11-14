"""Turn the logfire console and the pydantic-ai instrumentation off between tests (#3532).

A test that calls `logfire.configure` with the console on, and `logfire.instrument_pydantic_ai`,
leaves that state for the next test of the same xdist worker. A later test that parses stdout as
JSON then fails on the console spans. The root conftest calls `quiet_logfire` after every test.
"""

from __future__ import annotations

import sys


def quiet_logfire() -> None:
    """Turn the console of logfire off and uninstrument pydantic-ai, when either is loaded.

    The module is read from `sys.modules`: a test that never loads logfire or pydantic-ai has no
    state to reset, and the fixture stays cheap for the thousands of tests that load neither.
    """
    logfire = sys.modules.get("logfire")
    if logfire is not None:
        # An explicit service version keeps configure from running `git rev-parse HEAD` for one.
        logfire.configure(console=False, service_version="test-suite")
    pydantic_ai = sys.modules.get("pydantic_ai")
    agent = getattr(pydantic_ai, "Agent", None)
    if agent is not None:
        agent.instrument_all(False)

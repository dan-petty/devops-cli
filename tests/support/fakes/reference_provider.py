"""A search provider of the reference step, faked at the provider seam (#4672, ADR 0007).

`FakeReferenceProvider` answers a query with the hits that a test gave for it, and records each
query that it received and the thread that sent it. It can fail each search with an error, hold a search open until the test
releases it, and refuse its connection as a provider whose server is down. A test gives it the
name and the search kind of the provider, and builds the hits, so this module imports no name of
the reference step.

The contract suite `tests/roadmap/references/test_reference_provider_contract.py` runs each case
over this fake and over the GitHub code search provider on the in-memory roadmap store.
"""

from __future__ import annotations

import threading
from typing import Any

from devops_cli.exceptions.roadmap import RoadmapMcpUnavailableError
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

# The longest time that a held search stays open: longer than each wait that observes it.
_HOLD_BOUND_SECONDS = 4 * THREAD_HANDOFF_BOUND_SECONDS


class FakeReferenceProvider:
    """One search provider. `queries` holds each query that it received, in order."""

    __test__ = False

    def __init__(self, name: str, kind: Any, *, down: bool = False) -> None:
        self.name = name
        self.kind = kind
        self.queries: list[str] = []
        # The thread that sent each search.
        self.threads: list[threading.Thread] = []
        self.connected = False
        self.closed = False
        self.released = False
        self._down = down
        self._answers: dict[str, list[Any]] = {}
        self._error: Exception | None = None
        self._gate: threading.Event | None = None
        self.holding = threading.Event()

    def answer(self, query: str, *hits: Any) -> None:
        """Answer `query` with `hits`; any other query finds nothing."""
        self._answers[query] = list(hits)

    def fail(self, error: Exception) -> None:
        """Fail each search with `error`."""
        self._error = error

    def hold(self) -> None:
        """Hold each search open until `release`."""
        self._gate = threading.Event()

    def release(self) -> None:
        """End each held search: it then gives its answer."""
        self.released = True
        if self._gate is not None:
            self._gate.set()

    def search(self, query: str) -> list[Any]:
        self.queries.append(query)
        self.threads.append(threading.current_thread())
        if self._gate is not None:
            self.holding.set()
            self._gate.wait(_HOLD_BOUND_SECONDS)
        if self._error is not None:
            raise self._error
        return list(self._answers.get(query, []))

    def connect(self) -> None:
        """Connect, or refuse the connection as a server that is down at the start."""
        if self._down:
            raise RoadmapMcpUnavailableError(
                "https://mcp.example.com", message="Connection refused"
            )
        self.connected = True

    def close(self) -> None:
        self.closed = True

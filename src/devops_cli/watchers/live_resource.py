"""Generic live terminal resource state watcher powered by Rich Live."""

from __future__ import annotations

import time
from collections.abc import Callable

from devops_cli.output import Console, Live, RenderableType
from devops_cli.telemetry import trace_span


class LiveResourceWatcher:
    """Continuous terminal state watcher with auto-refresh and graceful cancellation."""

    def __init__(
        self,
        render_fn: Callable[[], RenderableType],
        *,
        interval_seconds: float = 2.0,
        console: Console | None = None,
        name: str = "resource_watcher",
    ) -> None:
        self.render_fn = render_fn
        self.interval_seconds = max(0.1, interval_seconds)
        self.console = console or Console()
        self.name = name
        self._running = False

    def stop(self) -> None:
        """Signal the live watcher loop to stop."""
        self._running = False

    def watch(self, *, max_iterations: int | None = None) -> None:
        """Run the live watcher loop until stopped or cancelled via keyboard interrupt."""
        with trace_span(
            f"watcher.{self.name}",
            attributes={
                "watcher.name": self.name,
                "watcher.interval_seconds": self.interval_seconds,
            },
        ) as span_h:
            self._running = True
            iterations = 0

            try:
                with Live(
                    self.render_fn(),
                    console=self.console,
                    refresh_per_second=max(1, int(1.0 / self.interval_seconds)),
                    auto_refresh=False,
                ) as live:
                    while self._running:
                        content = self.render_fn()
                        live.update(content, refresh=True)
                        iterations += 1

                        if max_iterations is not None and iterations >= max_iterations:
                            break

                        time.sleep(self.interval_seconds)
            except KeyboardInterrupt:
                self._running = False
                span_h.add_event("watcher_cancelled_by_user", {"iterations": iterations})
            finally:
                self._running = False
                span_h.set_attribute("watcher.total_iterations", iterations)

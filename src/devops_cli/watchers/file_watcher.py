"""Debounced filesystem change watcher for continuous automated review and drift detection."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from devops_cli.telemetry import trace_span

_IGNORED_DIRECTORIES = {
    ".git",
    ".data",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
}


class DebouncedFileWatcher:
    """Monitors directories for modified files and dispatches debounced change callbacks."""

    def __init__(
        self,
        watch_paths: Sequence[Path | str],
        on_change: Callable[[list[Path]], None],
        *,
        debounce_ms: int = 500,
        poll_interval_seconds: float = 0.5,
        name: str = "file_watcher",
    ) -> None:
        self.watch_paths = [Path(p).resolve() for p in watch_paths]
        self.on_change = on_change
        self.debounce_seconds = max(0.05, debounce_ms / 1000.0)
        self.poll_interval_seconds = max(0.1, poll_interval_seconds)
        self.name = name
        self._running = False
        self._last_mtimes: dict[Path, float] = {}

    def _should_ignore(self, path: Path) -> bool:
        """Check whether a path or its ancestors should be ignored."""
        for part in path.parts:
            if part in _IGNORED_DIRECTORIES or part.startswith("."):
                return True
        return False

    def _scan_files(self) -> dict[Path, float]:
        """Scan watched directories and record current file mtimes."""
        mtimes: dict[Path, float] = {}
        for root in self.watch_paths:
            if not root.exists():
                continue
            if root.is_file():
                if not self._should_ignore(root):
                    with os.scandir(root.parent) as it:
                        for entry in it:
                            if entry.name == root.name and entry.is_file():
                                mtimes[root] = entry.stat().st_mtime
                continue

            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not self._should_ignore(Path(d))]
                for fname in filenames:
                    fpath = Path(dirpath) / fname
                    if not self._should_ignore(fpath):
                        try:
                            mtimes[fpath] = fpath.stat().st_mtime
                        except OSError:
                            pass
        return mtimes

    def check_changes(self) -> list[Path]:
        """Check for modified or newly created files since last scan."""
        current_mtimes = self._scan_files()
        changed: list[Path] = []

        for path, mtime in current_mtimes.items():
            prev_mtime = self._last_mtimes.get(path)
            if prev_mtime is None or mtime > prev_mtime:
                changed.append(path)

        self._last_mtimes = current_mtimes
        return changed

    def stop(self) -> None:
        """Signal the file watcher loop to stop."""
        self._running = False

    def watch(self, *, max_iterations: int | None = None) -> None:
        """Run the file change monitoring loop."""
        with trace_span(
            f"watcher.{self.name}",
            attributes={
                "watcher.name": self.name,
                "watcher.debounce_seconds": self.debounce_seconds,
            },
        ) as span_h:
            self._running = True
            # Prime initial mtimes
            self._last_mtimes = self._scan_files()
            iterations = 0

            try:
                while self._running:
                    changed = self.check_changes()
                    if changed:
                        span_h.add_event(
                            "files_changed",
                            {"count": len(changed), "files": [str(p) for p in changed[:5]]},
                        )
                        # Debounce wait
                        time.sleep(self.debounce_seconds)
                        self.on_change(changed)

                    iterations += 1
                    if max_iterations is not None and iterations >= max_iterations:
                        break

                    time.sleep(self.poll_interval_seconds)
            except KeyboardInterrupt:
                self._running = False
            finally:
                self._running = False
                span_h.set_attribute("watcher.total_iterations", iterations)

"""Bounded log buffer for virtualized terminal streaming.

A terminal can display perhaps fifty lines, but a log stream produces hundreds of
thousands. Retaining all of them to show fifty is how a long-running tail turns into an
out-of-memory kill, and re-rendering all of them is how it turns into dropped frames.

This buffer keeps a fixed-size window of the most recent lines and hands out only the
slice actually being displayed, so memory is bounded by the retention limit rather than
by how long the stream has been running.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from devops_cli.config.defaults import (
    DEFAULT_LOG_BUFFER_MAX_LINES,
    DEFAULT_LOG_VIEWPORT_LINES,
)


@dataclass(frozen=True)
class LogLine:
    """One retained log line and its position in the overall stream."""

    sequence: int
    text: str


class VirtualLogBuffer:
    """A thread-safe ring buffer over a log stream.

    Producers append from a worker thread while the UI reads a viewport, so every
    operation is guarded. Sequence numbers count every line ever appended, not just the
    retained ones, so the display can show true stream position after eviction.
    """

    def __init__(
        self,
        max_lines: int = DEFAULT_LOG_BUFFER_MAX_LINES,
        viewport: int = DEFAULT_LOG_VIEWPORT_LINES,
    ) -> None:
        self._max_lines = max(1, max_lines)
        self.viewport = max(1, viewport)
        self._lines: deque[LogLine] = deque(maxlen=self._max_lines)
        self._lock = threading.RLock()
        self._total_appended = 0
        self._offset = 0
        self._following = True

    # -- Producing ------------------------------------------------------------

    def append(self, text: str) -> LogLine:
        """Append one line, evicting the oldest when the retention limit is reached."""
        with self._lock:
            self._total_appended += 1
            line = LogLine(sequence=self._total_appended, text=text)
            self._lines.append(line)
            if self._following:
                self._offset = max(0, len(self._lines) - self.viewport)
            else:
                # Hold the reader's position steady as eviction shifts indices beneath it.
                self._offset = max(0, min(self._offset, len(self._lines) - 1))
            return line

    def extend(self, texts: Iterable[str]) -> int:
        """Append many lines, returning how many were added.

        The whole batch is appended under a single lock acquisition so the UI never reads a
        viewport from the middle of one chunk of stream output.
        """
        appended = 0
        with self._lock:
            for text in texts:
                self.append(text)
                appended += 1
        return appended

    def clear(self) -> None:
        """Discard retained lines and reset the viewport, preserving the stream count."""
        with self._lock:
            self._lines.clear()
            self._offset = 0
            self._following = True

    # -- Consuming ------------------------------------------------------------

    def viewport_lines(self) -> list[LogLine]:
        """Return only the lines currently visible.

        Rendering the whole buffer is what drops frames; the widget only ever needs the
        slice on screen.
        """
        with self._lock:
            return list(self._lines)[self._offset : self._offset + self.viewport]

    def scroll(self, delta: int) -> int:
        """Move the viewport, clamping to the retained range.

        Scrolling away from the end detaches from following, so incoming lines no longer
        yank the reader's position; returning to the end re-attaches.
        """
        with self._lock:
            maximum = max(0, len(self._lines) - self.viewport)
            self._offset = max(0, min(self._offset + delta, maximum))
            self._following = self._offset >= maximum
            return self._offset

    def scroll_to_end(self) -> int:
        """Jump to the newest lines and resume following the stream."""
        with self._lock:
            self._offset = max(0, len(self._lines) - self.viewport)
            self._following = True
            return self._offset

    def resize_viewport(self, viewport: int) -> None:
        """Change how many lines are visible, keeping the view anchored sensibly."""
        with self._lock:
            self.viewport = max(1, viewport)
            if self._following:
                self._offset = max(0, len(self._lines) - self.viewport)
            else:
                self._offset = max(0, min(self._offset, max(0, len(self._lines) - self.viewport)))

    def search(self, needle: str, limit: int | None = None) -> list[LogLine]:
        """Return retained lines containing a case-insensitive substring."""
        if not needle:
            return []
        lowered = needle.lower()
        with self._lock:
            matches = [line for line in self._lines if lowered in line.text.lower()]
        return matches[:limit] if limit is not None else matches

    # -- Introspection --------------------------------------------------------

    @property
    def retained(self) -> int:
        """Number of lines currently held in memory."""
        with self._lock:
            return len(self._lines)

    @property
    def total_appended(self) -> int:
        """Number of lines seen since the buffer was created, including evicted ones."""
        with self._lock:
            return self._total_appended

    @property
    def dropped(self) -> int:
        """Number of lines evicted to stay within the retention limit."""
        with self._lock:
            return max(0, self._total_appended - len(self._lines))

    @property
    def following(self) -> bool:
        """Whether the viewport tracks newly appended lines."""
        with self._lock:
            return self._following

    @property
    def offset(self) -> int:
        """Index of the first visible line within the retained window."""
        with self._lock:
            return self._offset

    def status(self) -> str:
        """Render a one-line summary of stream position for a status bar."""
        with self._lock:
            suffix = " (following)" if self._following else ""
            dropped = f", {self.dropped} dropped" if self.dropped else ""
            return f"{len(self._lines)} retained of {self._total_appended}{dropped}{suffix}"


def tail(lines: Sequence[str], count: int = DEFAULT_LOG_VIEWPORT_LINES) -> list[str]:
    """Return the last `count` lines of a sequence."""
    return list(lines[-count:]) if count > 0 else []


__all__ = [
    "LogLine",
    "VirtualLogBuffer",
    "tail",
]

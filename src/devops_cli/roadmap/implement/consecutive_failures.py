"""Consecutive failures tracking and state persistence (#3069).

The roadmap Service exposes `devops_cli_service_implement_consecutive_failures` with labels
`repo` and `class`. A stop increments the gauge of that class. A stop of another class or a
delivered item resets the earlier gauge to zero. The state is kept in a record file across restarts.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from devops_cli.config.constants import (
    CONST_SERVICE_CONSECUTIVE_FAILURES_FILENAME,
    CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
)
from devops_cli.output.file_writer import write_json_file
from devops_cli.roadmap.failure import FailureClass
from devops_cli.telemetry.metrics import GLOBAL_METRICS

logger = logging.getLogger(__name__)

_DEFAULT_TRACKER: ConsecutiveFailures | None = None


def _parse_entry(item: object) -> tuple[str, str, int] | None:
    if not isinstance(item, (list, tuple)) or len(item) != 3:
        return None
    repo, failure_class, count = item
    if isinstance(repo, str) and isinstance(failure_class, str) and isinstance(count, (int, float)):
        return repo, failure_class, int(count)
    return None


class ConsecutiveFailures:
    """Tracks consecutive failures by class and repository across Service restarts."""

    def __init__(self, record: Path | None = None) -> None:
        self._record = record
        self._lock = threading.Lock()
        self._failures: dict[str, tuple[str, int]] = {}
        if record is not None and record.exists():
            self._load(record)

    def _load(self, record: Path) -> None:
        try:
            entries = json.loads(record.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                return
            for item in entries:
                parsed = _parse_entry(item)
                if parsed is None:
                    continue
                repo, failure_class, count = parsed
                self._failures[repo] = (failure_class, count)
                GLOBAL_METRICS.set_gauge(
                    CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
                    float(count),
                    labels={"repo": repo, "class": failure_class},
                )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to load consecutive failures from %s: %s", record, exc)

    def failed(self, repo: str, failure_class: str) -> int:
        """Record a failure of class `failure_class` for `repo`."""
        # Validates that failure_class belongs to FailureClass taxonomy.
        klass = FailureClass(failure_class)
        with self._lock:
            current = self._failures.get(repo)
            if current is not None and current[0] != klass.value:
                GLOBAL_METRICS.set_gauge(
                    CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
                    0.0,
                    labels={"repo": repo, "class": current[0]},
                )
                count = 1
            elif current is not None:
                count = current[1] + 1
            else:
                count = 1

            self._failures[repo] = (klass.value, count)
            GLOBAL_METRICS.set_gauge(
                CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
                float(count),
                labels={"repo": repo, "class": klass.value},
            )
            self._keep_locked()
            return count

    def delivered(self, repo: str) -> None:
        """Record a delivered item for `repo`, resetting any earlier consecutive failures gauge."""
        with self._lock:
            current = self._failures.pop(repo, None)
            if current is not None:
                GLOBAL_METRICS.set_gauge(
                    CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
                    0.0,
                    labels={"repo": repo, "class": current[0]},
                )
                self._keep_locked()

    def count(self, repo: str, failure_class: str) -> int:
        """Return the current consecutive failures count for `repo` and `failure_class`."""
        with self._lock:
            current = self._failures.get(repo)
            if current is not None and current[0] == failure_class:
                return current[1]
            return 0

    def _keep_locked(self) -> None:
        if self._record is not None:
            try:
                payload = [
                    [repo, failure_class, count]
                    for repo, (failure_class, count) in self._failures.items()
                ]
                write_json_file(self._record, payload, indent=2, atomic=True)
            except OSError as exc:
                logger.error("Failed to write consecutive failures to %s: %s", self._record, exc)


def get_consecutive_failures(record: Path | None = None) -> ConsecutiveFailures:
    """Return the global or configured consecutive failures tracker."""
    global _DEFAULT_TRACKER
    if record is not None:
        return ConsecutiveFailures(record=record)
    if _DEFAULT_TRACKER is None:
        from devops_cli.roadmap.run import service_state_dir

        state_dir = service_state_dir()
        record_path = state_dir / CONST_SERVICE_CONSECUTIVE_FAILURES_FILENAME
        _DEFAULT_TRACKER = ConsecutiveFailures(record=record_path)
    return _DEFAULT_TRACKER


def reset_consecutive_failures() -> None:
    """Reset the singleton instance for testing."""
    global _DEFAULT_TRACKER
    _DEFAULT_TRACKER = None


__all__ = [
    "ConsecutiveFailures",
    "get_consecutive_failures",
    "reset_consecutive_failures",
]

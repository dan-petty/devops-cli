"""Consecutive failures tracking and state persistence across Service restarts (#3069).

The gauge `devops_cli_service_implement_consecutive_failures` holds how many stops in a row
have a given failure class for a repository. A stop increments the gauge, a stop of another class
or a delivered item resets the earlier gauge to 0, and a state record preserves values over restarts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_SERVICE_CONSECUTIVE_FAILURES_FILENAME,
    CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
)
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement.consecutive_failures import (
    ConsecutiveFailures,
    get_consecutive_failures,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS

REPO = "example-org/repo1"


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    GLOBAL_METRICS.reset()


def _gauge(repo: str, failure_class: str) -> float:
    return GLOBAL_METRICS.get_gauge(
        CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
        labels={"repo": repo, "class": failure_class},
    )


def test_a_stop_increments_its_class_gauge(tmp_path: Path) -> None:
    record = tmp_path / CONST_SERVICE_CONSECUTIVE_FAILURES_FILENAME
    tracker = ConsecutiveFailures(record=record)

    tracker.failed(REPO, FailureClass.TEST.value)
    assert _gauge(REPO, FailureClass.TEST.value) == 1.0

    tracker.failed(REPO, FailureClass.TEST.value)
    assert _gauge(REPO, FailureClass.TEST.value) == 2.0


def test_a_restart_keeps_the_gauge_value(tmp_path: Path) -> None:
    record = tmp_path / CONST_SERVICE_CONSECUTIVE_FAILURES_FILENAME
    tracker = ConsecutiveFailures(record=record)
    tracker.failed(REPO, FailureClass.TEST.value)
    tracker.failed(REPO, FailureClass.TEST.value)
    assert _gauge(REPO, FailureClass.TEST.value) == 2.0

    GLOBAL_METRICS.reset()
    assert _gauge(REPO, FailureClass.TEST.value) == 0.0

    reloaded = ConsecutiveFailures(record=record)
    assert _gauge(REPO, FailureClass.TEST.value) == 2.0
    assert reloaded.count(REPO, FailureClass.TEST.value) == 2


def test_a_different_class_resets_the_earlier_gauge(tmp_path: Path) -> None:
    record = tmp_path / CONST_SERVICE_CONSECUTIVE_FAILURES_FILENAME
    tracker = ConsecutiveFailures(record=record)

    tracker.failed(REPO, FailureClass.TEST.value)
    tracker.failed(REPO, FailureClass.TEST.value)
    assert _gauge(REPO, FailureClass.TEST.value) == 2.0

    tracker.failed(REPO, FailureClass.TIMEOUT.value)
    assert _gauge(REPO, FailureClass.TEST.value) == 0.0
    assert _gauge(REPO, FailureClass.TIMEOUT.value) == 1.0


def test_a_delivered_item_resets_the_earlier_gauge(tmp_path: Path) -> None:
    record = tmp_path / CONST_SERVICE_CONSECUTIVE_FAILURES_FILENAME
    tracker = ConsecutiveFailures(record=record)

    tracker.failed(REPO, FailureClass.TEST.value)
    tracker.failed(REPO, FailureClass.TEST.value)
    assert _gauge(REPO, FailureClass.TEST.value) == 2.0

    tracker.delivered(REPO)
    assert _gauge(REPO, FailureClass.TEST.value) == 0.0


def test_invalid_failure_class_is_rejected(tmp_path: Path) -> None:
    tracker = ConsecutiveFailures()
    with pytest.raises(ValueError, match="unknown_class"):
        tracker.failed(REPO, "unknown_class")


def test_count_for_nonexistent_or_mismatched_class() -> None:
    tracker = ConsecutiveFailures()
    assert tracker.count(REPO, FailureClass.TEST.value) == 0
    tracker.failed(REPO, FailureClass.TEST.value)
    assert tracker.count(REPO, FailureClass.TIMEOUT.value) == 0


def test_get_consecutive_failures_with_record_parameter(tmp_path: Path) -> None:
    record = tmp_path / "custom.json"
    tracker = get_consecutive_failures(record=record)
    tracker.failed(REPO, FailureClass.TEST.value)
    assert tracker.count(REPO, FailureClass.TEST.value) == 1
    assert record.exists()


def test_load_with_malformed_entries_or_json(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    record = tmp_path / "corrupt.json"
    # Not a list
    record.write_text('{"not": "a list"}', encoding="utf-8")
    tracker = ConsecutiveFailures(record=record)
    assert tracker.count(REPO, FailureClass.TEST.value) == 0

    # Invalid JSON
    record.write_text("{invalid json", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        tracker = ConsecutiveFailures(record=record)
    assert "Failed to load consecutive failures" in caplog.text

    # List with various invalid elements (not list, wrong len, non-string, non-numeric)
    record.write_text(
        json.dumps(
            [
                "not a list",
                [REPO, "test"],
                [123, "test", 1],
                [REPO, 123, 1],
                [REPO, "test", "not a count"],
                [REPO, FailureClass.TEST.value, 3],
            ]
        ),
        encoding="utf-8",
    )
    tracker = ConsecutiveFailures(record=record)
    assert tracker.count(REPO, FailureClass.TEST.value) == 3


def test_keep_locked_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    record = tmp_path / "record.json"
    tracker = ConsecutiveFailures(record=record)

    def _fake_write(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(
        "devops_cli.roadmap.implement.consecutive_failures.write_json_file", _fake_write
    )
    with caplog.at_level(logging.ERROR):
        tracker.failed(REPO, FailureClass.TEST.value)
    assert "Failed to write consecutive failures" in caplog.text

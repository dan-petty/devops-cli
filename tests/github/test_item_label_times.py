"""Tests of the record that keeps the label times of the open Items across pods (#3634)."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_AT = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.UTC)
"""The time the label events of the tests were read."""


def _times() -> dict[str, datetime.datetime]:
    """The label times of one Item."""
    return {"status/in-progress": _AT, "owner/agent": _AT}


def test_the_record_round_trips_through_its_file(tmp_path: Path) -> None:
    from devops_cli.github.item_label_times import (
        ITEM_LABEL_TIMES_FILE,
        ItemLabelTimesRecord,
        KeptItemLabelTimes,
        item_label_times_path,
        keep_item_label_times,
        read_item_label_times,
    )

    updated_at = datetime.datetime(2026, 11, 2, 8, 30, tzinfo=datetime.UTC)
    record = ItemLabelTimesRecord(
        items={3634: KeptItemLabelTimes(updated_at=updated_at, times=_times())}
    )

    path = item_label_times_path(tmp_path)
    keep_item_label_times(path, record)

    assert read_item_label_times(path) == record
    assert (path.name, path.parent) == (ITEM_LABEL_TIMES_FILE, tmp_path)


def test_a_missing_record_reads_as_an_empty_record(tmp_path: Path) -> None:
    from devops_cli.github.item_label_times import (
        ItemLabelTimesRecord,
        item_label_times_path,
        read_item_label_times,
    )

    record = read_item_label_times(item_label_times_path(tmp_path))

    assert (record.items, record) == ({}, ItemLabelTimesRecord())


def test_a_record_that_cannot_be_written_logs_one_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from devops_cli.github.item_label_times import (
        ItemLabelTimesRecord,
        KeptItemLabelTimes,
        item_label_times_path,
        keep_item_label_times,
    )

    blocker = tmp_path / "state"
    blocker.write_text("not a directory", encoding="utf-8")
    path = item_label_times_path(blocker)
    record = ItemLabelTimesRecord(items={3634: KeptItemLabelTimes(updated_at=None, times=_times())})

    with caplog.at_level(logging.ERROR, logger="devops_cli.github.item_label_times"):
        keep_item_label_times(path, record)

    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert (len(errors), str(path) in errors[0]) == (1, True)

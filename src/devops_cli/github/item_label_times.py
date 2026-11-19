"""The record that keeps the label times of the open Items across the pods of the metrics row (#3634).

`item-label-times.json` sits in the state directory of each repository, beside its
`schedule.json`, and holds the `updated_at` and the label times of each open Item that the row
read. A new pod reads the file, so it sends no label-event request for an Item whose `updated_at`
the file holds. The row reads the label events of at most 20 Items a round, and the file keeps the
entry of each open Item that the cap defers.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field

from devops_cli.output.file_writer import write_json_file

logger = logging.getLogger(__name__)

ITEM_LABEL_TIMES_FILE: Final[str] = "item-label-times.json"
"""The record file of the metrics row, in the state directory of one repository."""


class KeptItemLabelTimes(BaseModel):
    """The `updated_at` and the label times that the record keeps of one open Item."""

    updated_at: datetime.datetime | None = Field(
        default=None,
        description=(
            "The `updated_at` of the Item when the row read its label events. A null value "
            "matches no Item, so the row reads the label events of that Item again."
        ),
    )
    times: dict[str, datetime.datetime] = Field(
        default_factory=dict,
        description="The time each label of the Item was set last, by label name.",
    )


class ItemLabelTimesRecord(BaseModel):
    """The record file of the metrics row: the label times of the open Items of one repository."""

    items: dict[int, KeptItemLabelTimes] = Field(
        default_factory=dict,
        description="The kept label times of each open Item of the repository, by issue number.",
    )


def item_label_times_path(repo_dir: Path) -> Path:
    """The record file of the metrics row in the state directory `repo_dir` of one repository."""
    return Path(repo_dir) / ITEM_LABEL_TIMES_FILE


def read_item_label_times(path: Path) -> ItemLabelTimesRecord:
    """The record that `path` holds, and an empty record when the file is not there. A file that
    cannot be read, or that does not match the record, logs one warning and reads as empty: the
    file is a cache of the row, and the next round writes it again."""
    if not path.exists():
        return ItemLabelTimesRecord()
    try:
        return ItemLabelTimesRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning(
            "The item label times record %s cannot be read (%s); this round reads the label "
            "events of at most 20 Items and writes the file again.",
            path,
            _reason(exc),
        )
        return ItemLabelTimesRecord()


def keep_item_label_times(path: Path, record: ItemLabelTimesRecord) -> None:
    """Write `record` to `path` atomically, so a stopped pod leaves the old file or the new one.
    A write that fails logs one error that names the file and returns: the round keeps its ages,
    and the next round writes the file again."""
    try:
        write_json_file(path, record.model_dump(mode="json"), indent=2, atomic=True)
    except (OSError, ValueError) as exc:
        logger.error(
            "The item label times record %s cannot be written (%s); this round keeps its ages "
            "and the next round writes the file again.",
            path,
            _reason(exc),
        )


def _reason(exc: Exception) -> str:
    """The first line of the message of `exc`, short enough for one log line."""
    lines = str(exc).splitlines() or [type(exc).__name__]
    return lines[0][:200]


__all__ = [
    "ITEM_LABEL_TIMES_FILE",
    "ItemLabelTimesRecord",
    "KeptItemLabelTimes",
    "item_label_times_path",
    "keep_item_label_times",
    "read_item_label_times",
]

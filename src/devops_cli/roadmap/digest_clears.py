"""The record of the digest clears of an item (#3481).

A new runner image may clear a stop of a class whose default action is `retry`
(`stop_clear.py`). Each clear adds an entry to `implement.digest_clears`: the class of the stop,
the digest of the new image and the time. The list stays when a later clear removes
`implement.stopped` and `implement.failure`, so it counts the clears of an item and of a class for
the whole life of the item. `implement.digest_clear_commented_at` holds the time of the last comment
of a clear, which limits the comments to one in a day.

The functions here read one record and make no request. A record that does not parse raises
`pydantic.ValidationError`; the caller decides what to do.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.store import ImplementRecordKey, Item


class DigestClear(BaseModel):
    """One clear by digest: the class of the stop, the digest that cleared it and the time."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    failure_class: FailureClass = Field(alias="class")
    digest: str
    time: datetime


_CLEARS = TypeAdapter(tuple[DigestClear, ...])
_TIME = TypeAdapter(datetime)


def has_digest_clear(item: Item) -> bool:
    """Whether `item` records a digest clear. It reads no entry, so a record that does not parse
    still counts as an attempt."""
    return bool(item.job_record.get(ImplementRecordKey.DIGEST_CLEARS))


def recorded_clears(item: Item) -> tuple[DigestClear, ...]:
    """The digest clears of `item`, oldest first. Raises `pydantic.ValidationError` when the record
    is not a valid list."""
    text = item.job_record.get(ImplementRecordKey.DIGEST_CLEARS)
    return _CLEARS.validate_json(text) if text else ()


def encode_clears(clears: Sequence[DigestClear]) -> str:
    """The text of `clears` for the record."""
    return _CLEARS.dump_json(tuple(clears), by_alias=True).decode()


def last_clear_comment(item: Item) -> datetime | None:
    """The time of the last comment of a digest clear on `item`, or None. Raises
    `pydantic.ValidationError` when the record is not a time."""
    text = item.job_record.get(ImplementRecordKey.DIGEST_CLEAR_COMMENTED_AT)
    return _TIME.validate_python(text) if text else None


__all__ = [
    "DigestClear",
    "encode_clears",
    "has_digest_clear",
    "last_clear_comment",
    "recorded_clears",
]
